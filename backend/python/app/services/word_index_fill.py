"""Writing the word index of the game's search (0.0.19's fill script; a service since 0.0.20, so that an upload
and a submission fill their own words).

The word index is the Qdrant collection `knowledge-words-bm25` (word_index.py): one point per active knowledge
object, keyed by its knowledge_id, with BM25's sparse vector of its label, name and statement.

- run(): `python -m scripts.fill_word_index [--book ID ...] [--check]` (scripts/fill_word_index.py). Without
  books it covers every active object of every grimoire, hidden books included (the search filters what a reader
  may see at query time). It creates the collection and its payload indexes when they are missing, writes every
  covered object's point (an object already there is overwritten with the same point, so running it twice
  changes nothing), then deletes the points of objects that are no longer active or no longer exist. Objects are
  read in knowledge_id order, BATCH at a time, so memory stays flat however many books there are. --check writes
  nothing: it reports how many covered objects have no point and how many points are stale.
- index_book(): what run() does for one book, without printing, called by an upload once its facts are
  committed: the book's active objects written, the points of objects the upload turned off deleted.
- index_objects(): the points of the given objects only, called by a submission of one object.

Every function reads PostgreSQL and never writes it.
"""
from __future__ import annotations

import logging
import sys
import time
from typing import Any, Sequence

from ..config import get_settings
from ..database import transaction
from . import word_index
from .qdrant import qdrant_service

BATCH = 1000
LANGUAGE_ID = 1

logger = logging.getLogger(__name__)

_ROWS_SQL = """
    SELECT k.knowledge_id, s.grimoire_id, COALESCE(btrim(k.name), '') AS name,
           COALESCE(btrim(lk.label), '') AS label, lk.statement
    FROM knowledge k
    JOIN section s ON s.section_id = k.section_id
    JOIN language_knowledge lk ON lk.knowledge_id = k.knowledge_id AND lk.language_id = %(language)s
    WHERE k.is_active AND k.knowledge_id > %(after)s {books}
    ORDER BY k.knowledge_id
    LIMIT %(limit)s
"""

_ACTIVE_SQL = """
    SELECT k.knowledge_id
    FROM knowledge k
    JOIN section s ON s.section_id = k.section_id
    JOIN language_knowledge lk ON lk.knowledge_id = k.knowledge_id AND lk.language_id = %(language)s
    WHERE k.knowledge_id = ANY(%(ids)s) AND k.is_active {books}
"""

_ROWS_BY_ID_SQL = """
    SELECT k.knowledge_id, s.grimoire_id, COALESCE(btrim(k.name), '') AS name,
           COALESCE(btrim(lk.label), '') AS label, lk.statement
    FROM knowledge k
    JOIN section s ON s.section_id = k.section_id
    JOIN language_knowledge lk ON lk.knowledge_id = k.knowledge_id AND lk.language_id = %(language)s
    WHERE k.is_active AND k.knowledge_id = ANY(%(ids)s)
    ORDER BY k.knowledge_id
"""


def _books_clause(books: Sequence[int]) -> str:
    return "AND s.grimoire_id = ANY(%(books)s)" if books else ""


def _rows(after: int, books: Sequence[int]) -> list[dict[str, Any]]:
    with transaction() as (_, cur):
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute(_ROWS_SQL.format(books=_books_clause(books)),
                    {"language": LANGUAGE_ID, "after": after, "limit": BATCH, "books": list(books)})
        return [dict(row) for row in cur.fetchall()]


def _active(ids: Sequence[int], books: Sequence[int]) -> set[int]:
    with transaction() as (_, cur):
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute(_ACTIVE_SQL.format(books=_books_clause(books)),
                    {"language": LANGUAGE_ID, "ids": list(ids), "books": list(books)})
        return {int(row["knowledge_id"]) for row in cur.fetchall()}


def _stale(books: Sequence[int], *, delete: bool) -> int:
    """Points of the covered books whose objects are no longer active, deleted unless only checking."""
    flt = {"must": [{"key": "grimoire_id", "match": {"any": list(books)}}]} if books else None
    stale_count = 0
    offset = None
    while True:
        points, offset = qdrant_service.scroll_points(collection=word_index.COLLECTION, filter=flt, limit=BATCH,
                                                      offset=offset)
        ids = [int(point["id"]) for point in points]
        if ids:
            stale = sorted(set(ids) - _active(ids, books))
            stale_count += len(stale)
            if stale and delete:
                qdrant_service.delete_ids(collection=word_index.COLLECTION, point_ids=stale)
        if offset is None:
            return stale_count


def _ensure() -> bool:
    """The collection with its payload indexes; True when it was created now."""
    return qdrant_service.ensure_sparse_collection(
        collection=word_index.COLLECTION, sparse_name=word_index.SPARSE_NAME,
        payload_indexes=word_index.PAYLOAD_INDEXES,
    )


def run(books: Sequence[int] = (), *, check: bool = False, out=None) -> int:
    out = out or sys.stdout
    started = time.perf_counter()
    books = sorted(set(books))
    exists = qdrant_service.collection_exists(word_index.COLLECTION)
    if check and not exists:
        print(f"{word_index.COLLECTION}: missing", file=out, flush=True)
        return 2
    if not check:
        created = _ensure()
        print(f"{word_index.COLLECTION}: {'created' if created else 'present'}", file=out, flush=True)
    covered = missing = terms = 0
    seen_books: set[int] = set()
    after = 0
    try:
        while True:
            rows = _rows(after, books)
            if not rows:
                break
            after = int(rows[-1]["knowledge_id"])
            points = [word_index.point(row) for row in rows]
            covered += len(rows)
            seen_books.update(int(row["grimoire_id"]) for row in rows)
            terms += sum(len(word_index.terms(word_index.document_text(row["label"], row["name"], row["statement"])))
                         for row in rows)
            if check:
                ids = [point["id"] for point in points]
                missing += len(set(ids) - {int(found) for found in
                                           qdrant_service.existing_ids(collection=word_index.COLLECTION,
                                                                       point_ids=ids)})
            else:
                qdrant_service.upsert_raw(collection=word_index.COLLECTION, points=points)
            if covered % (BATCH * 10) == 0:
                print(f"  {covered:,} objects", file=out, flush=True)
        stale = _stale(books, delete=not check)
    except Exception as exc:  # noqa: BLE001 - report one line and exit 1; what was written stays valid
        print(f"failed after {covered:,} objects: {type(exc).__name__}: {str(exc)[:300]}", file=out, flush=True)
        return 1
    average = terms / covered if covered else 0.0
    verb = "missing" if check else "written"
    print(
        f"{covered:,} objects in {len(seen_books)} books; {missing if check else covered:,} {verb}; "
        f"{stale:,} stale {'found' if check else 'deleted'}; {average:.1f} terms an object on average "
        f"(AVGDL {word_index.AVGDL}); {time.perf_counter() - started:.1f} s",
        file=out, flush=True,
    )
    if check and (missing or stale):
        return 2
    return 0


def index_book(grimoire_id: int) -> dict[str, Any]:
    """One book's words after its upload: every active object's point written, the points of objects that are
    no longer active (a re-upload turns the old ones off) deleted. {"state": "off"} when Qdrant is off; a
    failure raises, and the caller keeps the upload and reports it."""
    if not get_settings().qdrant_enabled:
        return {"state": "off", "written": 0, "stale_deleted": 0}
    books = [int(grimoire_id)]
    _ensure()
    written = 0
    after = 0
    while True:
        rows = _rows(after, books)
        if not rows:
            break
        after = int(rows[-1]["knowledge_id"])
        qdrant_service.upsert_raw(collection=word_index.COLLECTION, points=[word_index.point(row) for row in rows])
        written += len(rows)
    return {"state": "written", "written": written, "stale_deleted": _stale(books, delete=True)}


def fill_words(grimoire_id: int, knowledge_ids: Sequence[int] | None = None) -> dict[str, Any]:
    """An upload's book (index_book), or a submission's objects (index_objects), once their facts are committed.
    A failure keeps the upload: one warning in the log, {"state": "failed", "error"} in the answer, and
    `python -m scripts.fill_word_index --book ID` writes the words later."""
    try:
        if knowledge_ids is None:
            return index_book(grimoire_id)
        return index_objects(knowledge_ids)
    except Exception as exc:  # noqa: BLE001 - the facts are committed; the words can be written again later
        detail = " ".join(f"{type(exc).__name__}: {exc}".split())[:200]
        logger.warning("word index for book %s failed: %s", grimoire_id, detail)
        return {"state": "failed", "error": detail}


def index_objects(knowledge_ids: Sequence[int]) -> dict[str, Any]:
    """The points of these objects, those still active, written: a submission's own words."""
    if not get_settings().qdrant_enabled:
        return {"state": "off", "written": 0}
    ids = sorted({int(knowledge_id) for knowledge_id in knowledge_ids})
    if not ids:
        return {"state": "written", "written": 0}
    with transaction() as (_, cur):
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute(_ROWS_BY_ID_SQL, {"language": LANGUAGE_ID, "ids": ids})
        rows = [dict(row) for row in cur.fetchall()]
    _ensure()
    if rows:
        qdrant_service.upsert_raw(collection=word_index.COLLECTION, points=[word_index.point(row) for row in rows])
    return {"state": "written", "written": len(rows)}
