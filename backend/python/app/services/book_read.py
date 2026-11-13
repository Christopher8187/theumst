"""The whole-book read: one stored answer per book, read in one request.

Two rows are kept per book. ``book_read`` (0.0.15) is the Web Demo's: a book's sections,
its active objects in reader order, the book's authored relations between them and the
crystals they share; statements and workings stay on the per-object route.
``book_game_read`` (0.0.16) is UMST's: the same answer with each object's statement,
working, working summary, figures and page scans added, so the game downloads a book
once per version and never fetches per object.

Ingestion builds both inside the transaction that changes a book's facts, and builds the
game's again once the book's images are active (``book_ingestion._finalize_images``).
``scripts.build_book_reads`` builds them for books already stored. The same database
state always gives the same bytes, so a version (a SHA-256 of the answer) changes only
when the facts do.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import quote

from .graph_sidecar import build_contents_tree

FORMAT = 1
LOCK_NAME = "theumst.book_read"
ERROR_LIMIT = 500
# The two stored rows: the Web Demo's (0.0.15) and the game's (0.0.16). Both are in FORMAT.
WEB = "book_read"
GAME = "book_game_read"
READS = (WEB, GAME)
_NAMES = {WEB: "Whole-book read", GAME: "Game whole-book read"}
CACHE_SECONDS = 14 * 24 * 3600  # two weeks; clients revalidate with the ETag on every open

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

# The game's answer adds what GET /api/demo/grimoires/{id}/knowledge/{kid} gives one object at a
# time, read here with one query each for the whole book.
_BOOK_OBJECTS = """
SELECT k.knowledge_id FROM knowledge k JOIN section s ON s.section_id = k.section_id
WHERE s.grimoire_id = %s AND k.is_active
"""

_TEXTS = """
SELECT k.knowledge_id AS id, lk.statement, lk.working, lk.working_summary
FROM knowledge k
JOIN section s ON s.section_id = k.section_id
JOIN language_knowledge lk ON lk.knowledge_id = k.knowledge_id AND lk.language_id = 1
WHERE s.grimoire_id = %s AND k.is_active
"""

# demo._object_images(cur, id, "figure") for every object: active figures, the link an upload
# before migration 012 kept in book_image.knowledge_id included, in book_image_id order.
_FIGURES = f"""
SELECT link.knowledge_id, bi.source_image_id, bi.semantic_context_name, bi.storage_key, bi.url,
       bi.metadata, bi.updated_at
FROM (
    SELECT b.book_image_id, b.knowledge_id FROM book_image b
    WHERE b.knowledge_id IN ({_BOOK_OBJECTS})
    UNION
    SELECT l.book_image_id, l.knowledge_id FROM book_image_knowledge l
    WHERE l.link_type = 'figure' AND l.knowledge_id IN ({_BOOK_OBJECTS})
) link
JOIN book_image bi ON bi.book_image_id = link.book_image_id
WHERE bi.is_active
ORDER BY link.knowledge_id, bi.book_image_id
"""

# demo._object_images(cur, id, "page") for every object: the scans of the pages it appeared on,
# by page number, then book_image_id.
_PAGES = f"""
SELECT l.knowledge_id, bi.source_image_id, bi.storage_key, bi.url, bi.metadata, bi.updated_at
FROM book_image_knowledge l
JOIN book_image bi ON bi.book_image_id = l.book_image_id
WHERE l.link_type = 'page' AND bi.is_active AND l.knowledge_id IN ({_BOOK_OBJECTS})
ORDER BY l.knowledge_id,
         CASE WHEN jsonb_typeof(bi.metadata->'page') = 'number' THEN (bi.metadata->>'page')::numeric END
             NULLS LAST,
         bi.book_image_id
"""


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
    """Read one book's facts and build the Web Demo's answer. LookupError when the book does not exist."""
    return encode(_answer(cur, grimoire_id))


def _answer(cur, grimoire_id: int) -> dict[str, Any]:
    """The Web Demo's answer without its version. LookupError when the book does not exist."""
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

    return {
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
    }


def _iso(value: datetime | None) -> str | None:
    """UTC to the second, as /api/game writes times."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _number(value: Any) -> int | float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    return row["metadata"] if isinstance(row.get("metadata"), dict) else {}


def _image(row: Mapping[str, Any]) -> dict[str, Any]:
    """An image's url, page and time. The url is the governed storage route, as the knowledge
    route writes it (demo._governed_image_rows); page is metadata.page when a number."""
    storage_key = row.get("storage_key")
    return {
        "url": f"/api/v1/storage/{quote(str(storage_key), safe='/')}" if storage_key else row.get("url"),
        "page": _number(_metadata(row).get("page")),
        "updated_at": _iso(row["updated_at"]),
    }


def build_game(cur, grimoire_id: int) -> BuiltBookRead:
    """The game's answer: the Web Demo's with each object's texts, figures and page scans.

    Each object gains statement, working ("" when none), working_summary, figures
    [{image, url, caption, page, updated_at}] and pages, the ids of its page scans in page
    order. The top-level pages table describes every scan an object names once:
    {image: {url, page, printed_page, updated_at}}. counts gains figures (links in all) and
    pages (scans in all). An image's updated_at changes on every upload, so a new upload
    always gives a new version, which is how the game learns an image's bytes changed.
    """
    answer = _answer(cur, grimoire_id)

    cur.execute(_TEXTS, (grimoire_id,))
    texts = {int(row["id"]): row for row in cur.fetchall()}

    cur.execute(_FIGURES, (grimoire_id, grimoire_id))
    figures: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in cur.fetchall():
        image = _image(row)
        figures[int(row["knowledge_id"])].append({
            "image": str(row["source_image_id"]),
            "url": image["url"],
            "caption": row["semantic_context_name"],
            "page": image["page"],
            "updated_at": image["updated_at"],
        })

    cur.execute(_PAGES, (grimoire_id,))
    pages: dict[int, list[str]] = defaultdict(list)
    table: dict[str, dict[str, Any]] = {}
    for row in cur.fetchall():
        printed = _metadata(row).get("printed_page")
        source_image_id = str(row["source_image_id"])
        pages[int(row["knowledge_id"])].append(source_image_id)
        table[source_image_id] = {
            **_image(row),
            "printed_page": printed if isinstance(printed, str) or _number(printed) is not None else None,
        }

    for item in answer["objects"]:
        text = texts[int(item["id"])]
        item["statement"] = text["statement"]
        item["working"] = text["working"] or ""
        item["working_summary"] = text["working_summary"]
        item["figures"] = figures.get(int(item["id"]), [])
        item["pages"] = pages.get(int(item["id"]), [])
    answer["pages"] = table
    answer["counts"]["figures"] = sum(len(item["figures"]) for item in answer["objects"])
    answer["counts"]["pages"] = len(table)
    return encode(answer)


def lock(cur, grimoire_id: int) -> None:
    """Serialize every writer of one book's rows until the transaction ends."""
    cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s), %s)", (LOCK_NAME, grimoire_id))


def _table(read: str) -> str:
    if read not in READS:
        raise ValueError(f"Unknown whole-book read: {read}")
    return read


def _build(cur, grimoire_id: int, read: str) -> BuiltBookRead:
    # Looked up when called, so a test can replace either builder.
    return build(cur, grimoire_id) if read == WEB else build_game(cur, grimoire_id)


def stored(cur, grimoire_id: int, read: str = WEB) -> dict[str, Any] | None:
    cur.execute(f"SELECT format, version FROM {_table(read)} WHERE grimoire_id = %s", (grimoire_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def write(cur, built: BuiltBookRead, read: str = WEB) -> str:
    """Store a built answer. Returns 'unchanged' and writes nothing when the row already has it."""
    current = stored(cur, built.grimoire_id, read)
    if current and current["format"] == FORMAT and current["version"] == built.version:
        return "unchanged"
    cur.execute(
        f"""
        INSERT INTO {_table(read)} (grimoire_id, format, version, body_gzip, raw_bytes, object_count, built_at)
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


def refresh(cur, grimoire_id: int, read: str = WEB) -> BookReadResult:
    """Rebuild one of a book's rows inside the caller's transaction, which holds lock(cur, grimoire_id).

    The build runs in a savepoint. If it fails, the savepoint is rolled back, that row alone
    is deleted so no stale answer is served, the failure is logged for the operator (a
    single-object submission reports nothing else), and the caller's transaction goes on.
    """
    table = _table(read)
    cur.execute(f"SAVEPOINT {table}_build")
    try:
        built = _build(cur, grimoire_id, read)
        status = write(cur, built, read)
    except Exception as exc:  # noqa: BLE001 - any failure leaves the book without this row
        cur.execute(f"ROLLBACK TO SAVEPOINT {table}_build")
        cur.execute(f"DELETE FROM {table} WHERE grimoire_id = %s", (grimoire_id,))
        cur.execute(f"RELEASE SAVEPOINT {table}_build")
        error = one_line(exc)
        logger.warning(
            "%s of book %s failed and its row was removed; "
            "run scripts.build_book_reads --book %s once the cause is fixed: %s",
            _NAMES[read], grimoire_id, grimoire_id, error,
        )
        return BookReadResult("failed", error=error)
    cur.execute(f"RELEASE SAVEPOINT {table}_build")
    return BookReadResult(status, built=built)


def refresh_all(cur, grimoire_id: int) -> dict[str, BookReadResult]:
    """Rebuild both of a book's rows, each in its own savepoint, under the caller's lock."""
    return {read: refresh(cur, grimoire_id, read) for read in READS}


def check(cur, grimoire_id: int, read: str = WEB) -> BookReadResult:
    """Compare a fresh build with the stored row without writing: current, stale or missing.

    The build runs in a savepoint, so a failure is reported as failed and the caller's
    transaction can go on to the book's other row.
    """
    table = _table(read)
    cur.execute(f"SAVEPOINT {table}_check")
    try:
        built = _build(cur, grimoire_id, read)
        current = stored(cur, grimoire_id, read)
    except Exception as exc:  # noqa: BLE001 - reported on the book's line
        cur.execute(f"ROLLBACK TO SAVEPOINT {table}_check")
        cur.execute(f"RELEASE SAVEPOINT {table}_check")
        return BookReadResult("failed", error=one_line(exc))
    cur.execute(f"RELEASE SAVEPOINT {table}_check")
    if not current or current["format"] != FORMAT:
        return BookReadResult("missing", built=built)
    return BookReadResult("current" if current["version"] == built.version else "stale", built=built)


# --- serving ---------------------------------------------------------------------------------

def cache_headers(version: str, vary: str) -> dict[str, str]:
    """A 200 or 304's headers: the version as a strong ETag, two weeks private, and Vary."""
    return {
        "ETag": f'"{version}"',
        "Cache-Control": f"private, max-age={CACHE_SECONDS}",
        "Vary": vary,
    }


def etag_matches(header: str | None, etag: str) -> bool:
    """If-None-Match: a list of tags, weak or strong, or *; any one that matches will do."""
    for entry in (header or "").split(","):
        tag = entry.strip()
        if tag.startswith("W/"):
            tag = tag[2:].strip()
        if tag == "*" or tag == etag:
            return True
    return False


def accepts_gzip(header: str | None) -> bool:
    """Accept-Encoding allows gzip when it lists gzip, or failing that *, with q above 0."""
    named: bool | None = None
    wildcard: bool | None = None
    for entry in (header or "").split(","):
        coding, *parameters = (part.strip() for part in entry.split(";"))
        coding = coding.lower()
        quality = 1.0
        for parameter in parameters:
            name, _, value = parameter.partition("=")
            if name.strip().lower() == "q":
                try:
                    quality = float(value.strip())
                except ValueError:
                    quality = 0.0
        allowed = quality > 0
        if coding in {"gzip", "x-gzip"}:
            named = allowed or bool(named)
        elif coding == "*":
            wildcard = allowed or bool(wildcard)
    return named if named is not None else bool(wildcard)


def served(version: str, body_gzip: bytes, accept_encoding: str | None, vary: str) -> tuple[bytes, dict[str, str]]:
    """A 200's body and headers: the stored gzip as it is to a client that accepts gzip, else the JSON."""
    headers = cache_headers(version, vary)
    if accepts_gzip(accept_encoding):
        # GZipMiddleware passes a response that already names its Content-Encoding through untouched.
        headers["Content-Encoding"] = "gzip"
        return body_gzip, headers
    return gzip.decompress(body_gzip), headers
