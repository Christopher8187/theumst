"""Check that the embedding provider gives back the books' stored vectors (0.0.19). Runs on any PC.

    python compare_embeddings.py sample.jsonl

`sample.jsonl` is what scripts/dump_vector_sample.py printed on theumst.com: one JSON line per object with
`text` (the pipeline's `name. statement`), `stored_text` (what the upload stored) and `vector` (the stored
vector). The provider is read from the environment: EMBEDDING_API_URL, EMBEDDING_API_KEY and
EMBEDDING_MODEL, as theumst.com reads them. The key is sent and never printed; no file of settings is opened.
Only the standard library is used.

The pipeline's embed node embedded every stored text after an instruction (Kaic3 node/embed/input/
embedding.json, "maths"): sentence-transformers' `encode(texts, prompt=...)` puts the prompt straight
before the text. So the form expected to match is `instruction + text`. If it does not, the other likely
forms are tried, each in one request for all texts: the plain text, the stored text, a space after
"Query:", and the end-of-text token at the end. Scaling does not change a cosine, so normalising needs no
form of its own. For each form it prints every cosine, the lowest and the mean, and which forms pass:
every cosine at least 0.99.

The search route (services/game_search.py) sends `instruction + name. statement` for a query, the expected
form. The last lines show, for 3 objects, that form and the plain text against the object's own stored
vector, so the query side's number is seen beside the document side's.

Exit 0 when the expected form passes, 2 when only another form passes (the route must then change to it),
1 when no form passes or the provider fails.
"""
from __future__ import annotations

import json
import math
import os
import sys
import urllib.error
import urllib.request

INSTRUCTION = "Instruct: Given a mathematical statement, retrieve statements of the same result\nQuery:"
END_OF_TEXT = "<|endoftext|>"
PASS_MARK = 0.99

FORMS = [
    ("instruction + text (the pipeline's form, the route's form)", lambda row: INSTRUCTION + row["text"]),
    ("plain text", lambda row: row["text"]),
    ("instruction + stored_text", lambda row: INSTRUCTION + row["stored_text"]),
    ("plain stored_text", lambda row: row["stored_text"]),
    ("instruction + space + text", lambda row: INSTRUCTION + " " + row["text"]),
    ("instruction + text + end-of-text token", lambda row: INSTRUCTION + row["text"] + END_OF_TEXT),
    ("plain text + end-of-text token", lambda row: row["text"] + END_OF_TEXT),
]


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return float("nan")
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else float("nan")


def embed(texts: list[str], url: str, key: str, model: str) -> tuple[list[list[float]], str]:
    body = json.dumps({"model": model, "input": texts}).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}",
    })
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            answer = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise SystemExit(f"provider refused: HTTP {exc.code}: {detail}") from None
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise SystemExit(f"provider failed: {type(exc).__name__}: {exc}") from None
    data = sorted(answer.get("data") or [], key=lambda item: int(item.get("index", 0)))
    vectors = [[float(value) for value in item["embedding"]] for item in data]
    if len(vectors) != len(texts):
        raise SystemExit(f"provider gave {len(vectors)} vectors for {len(texts)} texts")
    return vectors, str(answer.get("model") or "")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 1
    url, key, model = (os.environ.get(name, "") for name in ("EMBEDDING_API_URL", "EMBEDDING_API_KEY",
                                                              "EMBEDDING_MODEL"))
    if not (url and key and model):
        print("EMBEDDING_API_URL, EMBEDDING_API_KEY and EMBEDDING_MODEL must all be set", file=sys.stderr)
        return 1
    with open(argv[1], encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip().startswith("{")]
    if not rows:
        print("no sample lines in that file", file=sys.stderr)
        return 1
    print(f"{len(rows)} stored vectors of {len(rows[0]['vector'])} numbers; provider model {model!r} at {url}")

    results: dict[str, list[float]] = {}
    for name, form in FORMS:
        vectors, returned = embed([form(row) for row in rows], url, key, model)
        sizes = {len(vector) for vector in vectors}
        scores = [cosine(vector, row["vector"]) for vector, row in zip(vectors, rows)]
        results[name] = scores
        lowest = min(scores)
        mean = sum(scores) / len(scores)
        verdict = "PASS" if all(score >= PASS_MARK for score in scores) else "fail"
        print(f"\n{name}: {verdict}  lowest {lowest:.5f}  mean {mean:.5f}  "
              f"(returned model {returned!r}, sizes {sorted(sizes)})")
        for row, score in zip(rows, scores):
            print(f"  object {row['knowledge_id']:>6}  book {row['grimoire_id']:>3}  cosine {score:.5f}")
        if name == FORMS[0][0] and verdict == "PASS":
            break

    passing = [name for name, scores in results.items() if all(score >= PASS_MARK for score in scores)]
    print("\nforms that pass:", ", ".join(passing) if passing else "none")

    print("\nthe query side, for 3 objects: each form against the object's own stored vector")
    for index, row in enumerate(rows[:3]):
        expected = results[FORMS[0][0]][index]
        plain = results.get(FORMS[1][0])
        if plain is None:
            plain_vector, _ = embed([row["text"]], url, key, model)
            plain_score = cosine(plain_vector[0], row["vector"])
        else:
            plain_score = plain[index]
        print(f"  object {row['knowledge_id']:>6}: route's query form (instruction + name. statement) "
              f"{expected:.5f}; plain name. statement {plain_score:.5f}")

    if FORMS[0][0] in passing:
        return 0
    return 2 if passing else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
