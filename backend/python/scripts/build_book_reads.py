"""Build the whole-book reads for books already stored, or check them.

Each book has two rows: book_read, the Web Demo's (0.0.15), and book_game_read, the game's
(0.0.16). Run in the backend container, after migrations 016 and 017 and the 0.0.16 backend:

    python -m scripts.build_book_reads [--book ID ...] [--check]

Without --book it covers every grimoire in id order, hidden books included. Each book gets its
own transaction and advisory lock, and each row its own savepoint, so one failure leaves the
others written, and running it again changes nothing. It prints a line per row with the
seconds that row took. --check writes nothing and reports each row as current, stale or
missing. Exit 0 when all is well, 1 when a row failed, 2 when --check found a stale or missing
row.
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Sequence

from app.database import transaction
from app.services import book_read

# One result per row: (row, result, seconds).
Rows = list[tuple[str, book_read.BookReadResult, float]]


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


def _line(grimoire_id: int, read: str, result: book_read.BookReadResult, seconds: float) -> str:
    built = result.built
    if built is None:
        return f"book {grimoire_id:>4}  {read:<14}  failed: {book_read.one_line(result.error or '', 200)}"
    counts = built.counts
    if read == book_read.WEB:
        detail = f"sections {counts['sections']:>4}" + "".join(
            f"  {relation_type} {count:>5}" for relation_type, count in sorted(counts["relations"].items())
        ) + f"  crystals {counts['shared_crystals']:>4}"
    else:
        detail = f"figures {counts['figures']:>5}  pages {counts['pages']:>5}"
    return (
        f"book {grimoire_id:>4}  {read:<14}  objects {counts['objects']:>5}  {detail}"
        f"  raw {len(built.body):>10,}  gzip {len(built.body_gzip):>8,}"
        f"  {built.version[:12]}  {result.status:<9}  {seconds:.2f} s"
    )


def _one(grimoire_id: int, check: bool) -> Rows:
    """Both rows of one book in one transaction: built under the book's lock, or checked read-only."""
    rows: Rows = []
    try:
        with transaction() as (_, cur):
            if check:
                cur.execute("SET TRANSACTION READ ONLY")
            else:
                book_read.lock(cur, grimoire_id)
            for read in book_read.READS:
                started = time.perf_counter()
                result = (book_read.check if check else book_read.refresh)(cur, grimoire_id, read)
                rows.append((read, result, time.perf_counter() - started))
    except Exception as exc:  # noqa: BLE001 - one book's failure must not stop the others
        # Nothing of this book was committed, whatever its rows said before the failure.
        failed = book_read.BookReadResult("failed", error=book_read.one_line(exc))
        return [(read, failed, 0.0) for read in book_read.READS]
    return rows


def run(requested: Sequence[int] = (), *, check: bool = False, out=None) -> int:
    out = out or sys.stdout
    started = time.perf_counter()
    print("; ".join(f"{read} format {book_read.FORMAT}" for read in book_read.READS), file=out, flush=True)
    book_ids, unknown = _book_ids(requested)
    tally: dict[str, dict[str, int]] = {read: {} for read in book_read.READS}
    gzip_bytes = 0
    for grimoire_id in unknown:
        print(f"book {grimoire_id:>4}  failed: no such book", file=out, flush=True)
        for read in book_read.READS:
            tally[read]["failed"] = tally[read].get("failed", 0) + 1
    for grimoire_id in book_ids:
        for read, result, seconds in _one(grimoire_id, check):
            print(_line(grimoire_id, read, result, seconds), file=out, flush=True)
            tally[read][result.status] = tally[read].get(result.status, 0) + 1
            if result.built is not None:
                gzip_bytes += len(result.built.body_gzip)
    words = ("current", "stale", "missing", "failed") if check else ("written", "unchanged", "failed")
    total = len(book_ids) + len(unknown)
    print(
        f"{total} books: "
        + "; ".join(read + " " + ", ".join(f"{tally[read].get(word, 0)} {word}" for word in words)
                    for read in book_read.READS)
        + f"; {gzip_bytes:,} bytes gzipped in all; {time.perf_counter() - started:.1f} s",
        file=out, flush=True,
    )
    if any(counts.get("failed") for counts in tally.values()):
        return 1
    if check and any(counts.get("stale") or counts.get("missing") for counts in tally.values()):
        return 2
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or check the whole-book reads of stored books.")
    parser.add_argument("--book", type=int, action="append", default=[], metavar="ID",
                        help="only this grimoire_id; repeat for more")
    parser.add_argument("--check", action="store_true", help="write nothing; report current, stale or missing")
    arguments = parser.parse_args(argv)
    return run(arguments.book, check=arguments.check)


if __name__ == "__main__":
    raise SystemExit(main())
