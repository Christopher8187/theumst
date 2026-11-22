"""Fill the word index of the game's search for the books already stored, or check it (0.0.19).

The word index is the Qdrant collection `knowledge-words-bm25` (app/services/word_index.py): one point per
active knowledge object, keyed by its knowledge_id, with BM25's sparse vector of its label, name and
statement. Run in the backend container, after the 0.0.19 backend:

    python -m scripts.fill_word_index [--book ID ...] [--check]

Without --book it covers every active object of every grimoire, hidden books included (the search filters
what a reader may see at query time). It creates the collection and its payload indexes when they are
missing, writes every covered object's point (an object already there is overwritten with the same point,
so running it twice changes nothing), then deletes the points of objects that are no longer active or no
longer exist. Objects are read in knowledge_id order, BATCH at a time, so memory stays flat however many
books there are. It reads PostgreSQL and never writes it.

--check writes nothing: it reports how many covered objects have no point and how many points are stale.
Exit 0 when all is well, 1 when something failed, 2 when --check found a missing or stale point.

Run it once after the release that adds the search, and again for a book after that book is uploaded
(`--book ID`), until an upload fills its own words.
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Any, Sequence

from app.database import transaction
from app.services import word_index
from app.services.qdrant import qdrant_service

BATCH = 1000
LANGUAGE_ID = 1

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


def run(books: Sequence[int] = (), *, check: bool = False, out=None) -> int:
    out = out or sys.stdout
    started = time.perf_counter()
    books = sorted(set(books))
    exists = qdrant_service.collection_exists(word_index.COLLECTION)
    if check and not exists:
        print(f"{word_index.COLLECTION}: missing", file=out, flush=True)
        return 2
    if not check:
        created = qdrant_service.ensure_sparse_collection(
            collection=word_index.COLLECTION, sparse_name=word_index.SPARSE_NAME,
            payload_indexes=word_index.PAYLOAD_INDEXES,
        )
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fill or check the word index of the game's search.")
    parser.add_argument("--book", type=int, action="append", default=[], metavar="ID",
                        help="only this grimoire_id; repeat for more")
    parser.add_argument("--check", action="store_true", help="write nothing; report missing and stale points")
    arguments = parser.parse_args(argv)
    return run(arguments.book, check=arguments.check)


if __name__ == "__main__":
    raise SystemExit(main())
