"""Fill the word index of the game's search for the books already stored, or check it (0.0.19).

The word index is the Qdrant collection `knowledge-words-bm25` (app/services/word_index.py). The work is in
app/services/word_index_fill.py since 0.0.20, where an upload and a submission also call it for their own objects.
Run in the backend container:

    python -m scripts.fill_word_index [--book ID ...] [--check]

Without --book it covers every active object of every grimoire, hidden books included (the search filters
what a reader may see at query time). It creates the collection and its payload indexes when they are
missing, writes every covered object's point (an object already there is overwritten with the same point,
so running it twice changes nothing), then deletes the points of objects that are no longer active or no
longer exist. It reads PostgreSQL and never writes it.

--check writes nothing: it reports how many covered objects have no point and how many points are stale.
Exit 0 when all is well, 1 when something failed, 2 when --check found a missing or stale point.

Since 0.0.20 an upload writes its own book's words and a submission its object's, so the command is for the
first fill, after restoring Qdrant or PostgreSQL, and for an upload whose answer says its word index failed.
"""
from __future__ import annotations

import argparse
from typing import Sequence

from app.services.word_index_fill import BATCH, LANGUAGE_ID, run  # noqa: F401  (the command's own names)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fill or check the word index of the game's search.")
    parser.add_argument("--book", type=int, action="append", default=[], metavar="ID",
                        help="only this grimoire_id; repeat for more")
    parser.add_argument("--check", action="store_true", help="write nothing; report missing and stale points")
    arguments = parser.parse_args(argv)
    return run(arguments.book, check=arguments.check)


if __name__ == "__main__":
    raise SystemExit(main())
