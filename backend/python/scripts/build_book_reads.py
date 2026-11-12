"""Build the whole-book read (0.0.15) for books already stored, or check it.

Run in the backend container, after migration 016 and the 0.0.15 backend:

    python -m scripts.build_book_reads [--book ID ...] [--check]

Without --book it covers every grimoire in id order, hidden books included. Each book
gets its own transaction and advisory lock, so one failure leaves the others written,
and running it again changes nothing. --check writes nothing and reports each book as
current, stale or missing. Exit 0 when all is well, 1 when a book failed, 2 when
--check found a stale or missing book.
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Sequence

from app.database import transaction
from app.services import book_read


def _book_ids(requested: Sequence[int]) -> tuple[list[int], list[int]]:
    """The books to cover in id order, and requested ids no grimoire has."""
    with transaction() as (_, cur):
        cur.execute("SET TRANSACTION READ ONLY")
        if requested:
            cur.execute(
                "SELECT grimoire_id FROM grimoire WHERE grimoire_id = ANY(%s) ORDER BY grimoire_id",
                (sorted(set(requested)),),
            )
        else:
            cur.execute("SELECT grimoire_id FROM grimoire ORDER BY grimoire_id")
        found = [int(row["grimoire_id"]) for row in cur.fetchall()]
    return found, sorted(set(requested) - set(found))


def _line(grimoire_id: int, result: book_read.BookReadResult, seconds: float) -> str:
    built = result.built
    if built is None:
        return f"book {grimoire_id:>4}  failed: {book_read.one_line(result.error or '', 200)}"
    counts = built.counts
    relations = "".join(
        f"  {relation_type} {count:>5}" for relation_type, count in sorted(counts["relations"].items())
    )
    return (
        f"book {grimoire_id:>4}  objects {counts['objects']:>5}  sections {counts['sections']:>4}{relations}"
        f"  crystals {counts['shared_crystals']:>4}  raw {len(built.body):>10,}  gzip {len(built.body_gzip):>8,}"
        f"  {built.version[:12]}  {result.status:<9}  {seconds:.2f} s"
    )


def _one(grimoire_id: int, check: bool) -> book_read.BookReadResult:
    try:
        with transaction() as (_, cur):
            if check:
                cur.execute("SET TRANSACTION READ ONLY")
                return book_read.check(cur, grimoire_id)
            book_read.lock(cur, grimoire_id)
            return book_read.refresh(cur, grimoire_id)
    except Exception as exc:  # noqa: BLE001 - one book's failure must not stop the others
        return book_read.BookReadResult("failed", error=book_read.one_line(exc))


def run(requested: Sequence[int] = (), *, check: bool = False, out=None) -> int:
    out = out or sys.stdout
    started = time.perf_counter()
    print(f"book_read format {book_read.FORMAT}", file=out, flush=True)
    book_ids, unknown = _book_ids(requested)
    tally: dict[str, int] = {}
    gzip_bytes = 0
    for grimoire_id in unknown:
        print(f"book {grimoire_id:>4}  failed: no such book", file=out, flush=True)
        tally["failed"] = tally.get("failed", 0) + 1
    for grimoire_id in book_ids:
        book_started = time.perf_counter()
        result = _one(grimoire_id, check)
        print(_line(grimoire_id, result, time.perf_counter() - book_started), file=out, flush=True)
        tally[result.status] = tally.get(result.status, 0) + 1
        if result.built is not None:
            gzip_bytes += len(result.built.body_gzip)
    words = ("current", "stale", "missing", "failed") if check else ("written", "unchanged", "failed")
    total = len(book_ids) + len(unknown)
    print(
        f"{total} books: " + ", ".join(f"{tally.get(word, 0)} {word}" for word in words)
        + f"; {gzip_bytes:,} bytes gzipped in all; {time.perf_counter() - started:.1f} s",
        file=out, flush=True,
    )
    if tally.get("failed"):
        return 1
    if check and (tally.get("stale") or tally.get("missing")):
        return 2
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or check the whole-book read of stored books.")
    parser.add_argument("--book", type=int, action="append", default=[], metavar="ID",
                        help="only this grimoire_id; repeat for more")
    parser.add_argument("--check", action="store_true", help="write nothing; report current, stale or missing")
    arguments = parser.parse_args(argv)
    return run(arguments.book, check=arguments.check)


if __name__ == "__main__":
    raise SystemExit(main())
