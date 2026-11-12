"""The whole-book read (0.0.15): one stored answer per book, read by the Web Demo in one request.

Ingestion builds the answer inside the transaction that changes a book's facts, and
``scripts.build_book_reads`` builds it for books already stored. The answer holds what a
reader needs to draw a whole book: its sections, its active objects in reader order, the
book's authored relations between them and the crystals they share. Statements and
workings stay on the per-object route. The same database state always gives the same
bytes, so the version (a SHA-256 of the answer) changes only when the facts do.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .graph_sidecar import build_contents_tree

FORMAT = 1
LOCK_NAME = "theumst.book_read"
ERROR_LIMIT = 500

logger = logging.getLogger(__name__)


def one_line(error: BaseException | str, limit: int = ERROR_LIMIT) -> str:
    """An error as one line of at most limit characters (PostgreSQL's carry CONTEXT lines)."""
    text = error if isinstance(error, str) else (str(error) or type(error).__name__)
    return " ".join(text.split())[:limit]

_SECTIONS = """
SELECT s.section_id, s.parent_section, s.section_number, ls.section_name,
       CASE WHEN jsonb_typeof(s.source_metadata->'minutes'->'own') = 'number'
            THEN s.source_metadata->'minutes'->'own' END AS minutes_own,
       CASE WHEN jsonb_typeof(s.source_metadata->'minutes'->'whole') = 'number'
            THEN s.source_metadata->'minutes'->'whole' END AS minutes_whole
FROM section s
LEFT JOIN language_section ls ON ls.section_id = s.section_id AND ls.language_id = 1
WHERE s.grimoire_id = %s
ORDER BY s.section_id
"""

# The rows and order of GET /api/demo/grimoires/{id}/knowledge, without the reader's completion.
_OBJECTS = """
SELECT k.knowledge_id AS id, k.section_id, k.type, k.source_key, k.name,
       COALESCE(NULLIF(btrim(k.name), ''), lk.label) AS label,
       CASE WHEN jsonb_typeof(k.source_metadata->'difficulty') = 'number'
            THEN k.source_metadata->'difficulty' END AS difficulty,
       CASE WHEN jsonb_typeof(k.source_metadata->'estimated_minutes') = 'number'
            THEN k.source_metadata->'estimated_minutes' END AS estimated_minutes,
       k.knowledge_crystal_id AS crystal_id, k.is_default_in_crystal AS crystal_default,
       n.graph_role AS role
FROM knowledge k
JOIN section s ON s.section_id = k.section_id
JOIN language_knowledge lk ON lk.knowledge_id = k.knowledge_id AND lk.language_id = 1
LEFT JOIN knowledge_graph_node n ON n.grimoire_id = s.grimoire_id AND n.knowledge_id = k.knowledge_id
WHERE s.grimoire_id = %s AND k.is_active
ORDER BY COALESCE((k.source_metadata->>'demo_order')::int, 2147483647),
         k.source_metadata->'order' NULLS LAST, k.knowledge_id
"""

_RELATIONS = """
SELECT relation_type, source_knowledge_id, target_knowledge_id
FROM knowledge_graph_edge
WHERE grimoire_id = %s
ORDER BY relation_type, source_knowledge_id, target_knowledge_id
"""

_OBJECT_KEYS = (
    "id", "section_id", "type", "name", "label", "source_key", "difficulty",
    "estimated_minutes", "crystal_id", "crystal_default", "role",
)


@dataclass(frozen=True)
class BuiltBookRead:
    """One book's answer as served, with its version and stored gzip."""

    grimoire_id: int
    answer: dict[str, Any]
    body: bytes
    body_gzip: bytes

    @property
    def version(self) -> str:
        return self.answer["version"]

    @property
    def counts(self) -> dict[str, Any]:
        return self.answer["counts"]


@dataclass(frozen=True)
class BookReadResult:
    """What one rebuild did: written, unchanged or failed (with the error)."""

    status: str
    built: BuiltBookRead | None = None
    error: str | None = None

    def receipt(self) -> dict[str, Any]:
        """The upload receipt's book_read field."""
        if self.built is None:
            return {"error": self.error or "unknown error"}
        return {
            "format": FORMAT,
            "version": self.built.version,
            "raw_bytes": len(self.built.body),
            "gzip_bytes": len(self.built.body_gzip),
        }


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False,
    ).encode("utf-8")


def encode(answer: Mapping[str, Any]) -> BuiltBookRead:
    """Version, body and gzip of an answer given without its version."""
    if "version" in answer:
        raise ValueError("encode takes the answer without its version")
    version = hashlib.sha256(_canonical(answer)).hexdigest()
    served = {**answer, "version": version}
    body = _canonical(served)
    return BuiltBookRead(
        grimoire_id=int(answer["grimoire_id"]),
        answer=served,
        body=body,
        body_gzip=gzip.compress(body, compresslevel=9, mtime=0),
    )


def contents_order(rows: Sequence[Mapping[str, Any]]) -> list[tuple[Mapping[str, Any], int]]:
    """Sections in a depth-first walk of build_contents_tree, each with its depth.

    Roots and children come in the tree's order (section_number as text, then id).
    Orphans, whose parent is not in the book, follow at depth 0 in id order, each
    with its own children beneath it. Every section appears exactly once.
    """
    by_id = {int(row["section_id"]): row for row in rows}
    tree = build_contents_tree(rows)
    cycle = set(tree["cycle_section_ids"])
    children: dict[int, list[int]] = defaultdict(list)
    for section_id in sorted(by_id, key=lambda item: (str(by_id[item].get("section_number") or ""), item)):
        parent = by_id[section_id].get("parent_section")
        if parent is None:
            continue
        parent = int(parent)
        if section_id in cycle and parent in cycle:
            continue
        if parent in by_id:
            children[parent].append(section_id)

    ordered: list[tuple[Mapping[str, Any], int]] = []
    seen: set[int] = set()

    def walk(start: int) -> None:
        stack = [(start, 0)]
        while stack:
            section_id, depth = stack.pop()
            if section_id in seen:
                continue
            seen.add(section_id)
            ordered.append((by_id[section_id], depth))
            stack.extend((child, depth + 1) for child in reversed(children.get(section_id, [])))

    for root in tree["sections"]:
        walk(int(root["section_id"]))
    for orphan in tree["orphan_section_ids"]:
        walk(int(orphan))
    for section_id in sorted(set(by_id) - seen):  # unreachable by construction; never drop a section
        walk(section_id)
    return ordered


def build(cur, grimoire_id: int) -> BuiltBookRead:
    """Read one book's facts and build its answer. LookupError when the book does not exist."""
    cur.execute("SELECT grimoire_id, graph_capability FROM grimoire WHERE grimoire_id = %s", (grimoire_id,))
    book = cur.fetchone()
    if not book:
        raise LookupError(f"Book {grimoire_id} does not exist")

    cur.execute(_SECTIONS, (grimoire_id,))
    section_rows = [dict(row) for row in cur.fetchall()]
    sections = [
        {
            "id": int(row["section_id"]),
            "parent_id": int(row["parent_section"]) if row["parent_section"] is not None else None,
            "number": row["section_number"],
            "name": row["section_name"],
            "depth": depth,
            "minutes_own": row["minutes_own"],
            "minutes_whole": row["minutes_whole"],
        }
        for row, depth in contents_order(section_rows)
    ]

    cur.execute(_OBJECTS, (grimoire_id,))
    objects = [{key: row[key] for key in _OBJECT_KEYS} for row in cur.fetchall()]
    object_ids = {row["id"] for row in objects}

    cur.execute(_RELATIONS, (grimoire_id,))
    relations: dict[str, list[list[int]]] = {}
    for row in cur.fetchall():
        source, target = int(row["source_knowledge_id"]), int(row["target_knowledge_id"])
        if source in object_ids and target in object_ids:
            relations.setdefault(str(row["relation_type"]), []).append([source, target])
    for pairs in relations.values():
        pairs.sort()

    members: dict[int, list[int]] = defaultdict(list)
    for row in objects:
        members[int(row["crystal_id"])].append(int(row["id"]))
    crystals = [
        {"id": crystal_id, "members": ids}
        for crystal_id, ids in sorted(members.items())
        if len(ids) >= 2
    ]

    return encode({
        "format": FORMAT,
        "grimoire_id": int(book["grimoire_id"]),
        "graph_capability": book["graph_capability"],
        "counts": {
            "sections": len(sections),
            "objects": len(objects),
            "shared_crystals": len(crystals),
            "relations": {relation_type: len(pairs) for relation_type, pairs in relations.items()},
        },
        "sections": sections,
        "objects": objects,
        "relations": relations,
        "crystals": crystals,
    })


def lock(cur, grimoire_id: int) -> None:
    """Serialize every writer of one book's row until the transaction ends."""
    cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s), %s)", (LOCK_NAME, grimoire_id))


def stored(cur, grimoire_id: int) -> dict[str, Any] | None:
    cur.execute("SELECT format, version FROM book_read WHERE grimoire_id = %s", (grimoire_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def write(cur, built: BuiltBookRead) -> str:
    """Store a built answer. Returns 'unchanged' and writes nothing when the row already has it."""
    current = stored(cur, built.grimoire_id)
    if current and current["format"] == FORMAT and current["version"] == built.version:
        return "unchanged"
    cur.execute(
        """
        INSERT INTO book_read (grimoire_id, format, version, body_gzip, raw_bytes, object_count, built_at)
        VALUES (%s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (grimoire_id) DO UPDATE SET
            format = EXCLUDED.format,
            version = EXCLUDED.version,
            body_gzip = EXCLUDED.body_gzip,
            raw_bytes = EXCLUDED.raw_bytes,
            object_count = EXCLUDED.object_count,
            built_at = EXCLUDED.built_at
        """,
        (
            built.grimoire_id, FORMAT, built.version, built.body_gzip,
            len(built.body), built.counts["objects"],
        ),
    )
    return "written"


def refresh(cur, grimoire_id: int) -> BookReadResult:
    """Rebuild one book's row inside the caller's transaction, which holds lock(cur, grimoire_id).

    The build runs in a savepoint. If it fails, the savepoint is rolled back, the book's
    row is deleted so no stale answer is served, the failure is logged for the operator
    (a single-object submission reports nothing else), and the caller's transaction goes on.
    """
    cur.execute("SAVEPOINT book_read_build")
    try:
        built = build(cur, grimoire_id)
        status = write(cur, built)
    except Exception as exc:  # noqa: BLE001 - any failure leaves the book without a row
        cur.execute("ROLLBACK TO SAVEPOINT book_read_build")
        cur.execute("DELETE FROM book_read WHERE grimoire_id = %s", (grimoire_id,))
        cur.execute("RELEASE SAVEPOINT book_read_build")
        error = one_line(exc)
        logger.warning(
            "Whole-book read of book %s failed and its row was removed; "
            "run scripts.build_book_reads --book %s once the cause is fixed: %s",
            grimoire_id, grimoire_id, error,
        )
        return BookReadResult("failed", error=error)
    cur.execute("RELEASE SAVEPOINT book_read_build")
    return BookReadResult(status, built=built)


def check(cur, grimoire_id: int) -> BookReadResult:
    """Compare a fresh build with the stored row without writing: current, stale or missing."""
    built = build(cur, grimoire_id)
    current = stored(cur, grimoire_id)
    if not current or current["format"] != FORMAT:
        return BookReadResult("missing", built=built)
    return BookReadResult("current" if current["version"] == built.version else "stale", built=built)
