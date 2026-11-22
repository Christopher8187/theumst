"""Print 20 stored statement vectors with the text they were made from, for the embedding check (0.0.19).

Read only. Run in the backend container on theumst.com, as a module once released, or before that fed to the
running container's Python on its standard input (it needs nothing newer than 0.0.18's app.database and
app.services.qdrant):

    python -m scripts.dump_vector_sample [--count 20] [--collection knowledge-qwen3-embedding-4b] > sample.jsonl
    python - --count 20 < dump_vector_sample.py > sample.jsonl

It picks `--count` objects, one from each of that many books (the books in id order, inside a book an object
chosen by a hash of its id, so a rerun picks the same ones), each with an indexed statement vector in the
collection and a statement without an image reference, of at most 1,500 characters. For each it prints one
JSON line:

    {"knowledge_id", "grimoire_id", "embedding_id", "text", "stored_text", "vector"}

`text` is the text as the pipeline's embed node built it, `name. statement` with spaces collapsed
(Kaic3 utils/statements.embedding_text); `stored_text` is semantic_projection.embedding_text as the upload
stored it; `vector` is the stored vector from Qdrant. The pipeline embedded each text after the instruction
in services/game_search.QUERY_INSTRUCTION; scripts/compare_embeddings.py tries that form and others.

The transaction is read only, Qdrant is only read (points by id), nothing is written anywhere, and nothing
from the environment or the settings is printed.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence
from urllib.parse import quote

from app.database import transaction
from app.services.qdrant import qdrant_service


def query_text(name: str | None, statement: str | None) -> str:
    """Kaic3 utils/statements.embedding_text, as services/game_search.query_text (copied so 0.0.18 runs it)."""
    name = " ".join(str(name or "").split()).rstrip(".")
    statement = " ".join(str(statement or "").split())
    return f"{name}. {statement}" if name else statement

_SAMPLE_SQL = """
    WITH candidates AS (
        SELECT DISTINCT ON (s.grimoire_id)
               k.knowledge_id, s.grimoire_id, e.embedding_id::text AS embedding_id,
               COALESCE(btrim(k.name), '') AS name, lk.statement, sp.embedding_text
        FROM semantic_projection sp
        JOIN embedding e ON e.semantic_projection_id = sp.semantic_projection_id AND e.status = 'indexed'
        JOIN embedding_model em ON em.embedding_model_id = e.embedding_model_id
        JOIN knowledge k ON k.knowledge_id = sp.knowledge_id AND k.is_active
        JOIN section s ON s.section_id = k.section_id
        JOIN language_knowledge lk ON lk.knowledge_id = k.knowledge_id AND lk.language_id = sp.language_id
        WHERE em.qdrant_collection = %s AND sp.is_active AND sp.language_id = 1
          AND sp.projection_type = 'statement' AND sp.direction = 'self'
          AND strpos(lk.statement, 'image uid=') = 0 AND length(lk.statement) <= 1500
        ORDER BY s.grimoire_id, md5(k.knowledge_id::text)
    )
    SELECT * FROM candidates ORDER BY grimoire_id LIMIT %s
"""


def run(count: int, collection: str, out=None) -> int:
    out = out or sys.stdout
    with transaction() as (_, cur):
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute(_SAMPLE_SQL, (collection, count))
        rows = [dict(row) for row in cur.fetchall()]
    if not rows:
        print("no indexed statement found in that collection", file=sys.stderr)
        return 1
    found = qdrant_service._request(
        "POST",
        f"/collections/{quote(collection, safe='')}/points",
        json={"ids": [row["embedding_id"] for row in rows], "with_payload": False, "with_vector": True},
    ).get("result", [])
    vectors = {str(point.get("id")): point.get("vector") for point in found}
    missing = 0
    for row in rows:
        vector = vectors.get(row["embedding_id"])
        if isinstance(vector, dict):  # a named vector: take the only one
            vector = next(iter(vector.values()), None)
        if not vector:
            missing += 1
            continue
        print(json.dumps({
            "knowledge_id": row["knowledge_id"],
            "grimoire_id": row["grimoire_id"],
            "embedding_id": row["embedding_id"],
            "text": query_text(row["name"], row["statement"]),
            "stored_text": row["embedding_text"],
            "vector": vector,
        }, ensure_ascii=False), file=out, flush=True)
    print(f"{len(rows) - missing} vectors printed from {len(rows)} books; {missing} without a point",
          file=sys.stderr)
    return 1 if missing else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print stored statement vectors with their texts (read only).")
    parser.add_argument("--count", type=int, default=20, help="how many objects, one a book (default 20)")
    parser.add_argument("--collection", default="knowledge-qwen3-embedding-4b",
                        help="the Qdrant store of the books' vectors")
    arguments = parser.parse_args(argv)
    if not 1 <= arguments.count <= 200:
        parser.error("--count is 1 to 200")
    return run(arguments.count, arguments.collection)


if __name__ == "__main__":
    raise SystemExit(main())
