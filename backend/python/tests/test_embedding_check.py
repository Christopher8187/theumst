"""The embedding check's two scripts (0.0.19), with no database, Qdrant or provider."""
from __future__ import annotations

import io
import json
from contextlib import contextmanager

import pytest

from app.services import game_search
from scripts import compare_embeddings, dump_vector_sample


def test_dump_prints_the_pipelines_text_the_stored_text_and_the_vector_read_only(monkeypatch):
    executed = []

    class Cursor:
        def execute(self, sql, values=None):
            executed.append(sql)

        def fetchall(self):
            return [{"knowledge_id": 5329, "grimoire_id": 5, "embedding_id": "p-1", "name": "A basis.",
                     "statement": "Let  V\n be a plane.", "embedding_text": "A basis. Let  V\n be a plane"}]

    @contextmanager
    def fake_transaction():
        yield None, Cursor()

    asked = []

    def fake_request(method, path, json=None):
        asked.append((method, path, json))
        return {"result": [{"id": "p-1", "vector": [0.6, 0.8]}]}

    monkeypatch.setattr(dump_vector_sample, "transaction", fake_transaction)
    monkeypatch.setattr(dump_vector_sample.qdrant_service, "_request", fake_request)
    out = io.StringIO()
    assert dump_vector_sample.run(20, "knowledge-qwen3-embedding-4b", out=out) == 0
    line = json.loads(out.getvalue())
    assert line == {"knowledge_id": 5329, "grimoire_id": 5, "embedding_id": "p-1", "text": "A basis. Let V be a plane.",
                    "stored_text": "A basis. Let  V\n be a plane", "vector": [0.6, 0.8]}
    assert executed[0] == "SET TRANSACTION READ ONLY"
    assert all(" ".join(sql.split()).upper().startswith(("SET TRANSACTION READ ONLY", "WITH")) for sql in executed)
    assert asked == [("POST", "/collections/knowledge-qwen3-embedding-4b/points",
                      {"ids": ["p-1"], "with_payload": False, "with_vector": True})]
    assert dump_vector_sample.query_text("A basis.", "x  y") == game_search.query_text("A basis.", "x  y")


def _sample(tmp_path):
    rows = [{"knowledge_id": kid, "grimoire_id": kid, "text": f"Name {kid}. Statement {kid}",
             "stored_text": f"Name {kid}. Statement {kid}", "vector": [1.0, float(kid), 0.0]} for kid in (1, 2, 3, 4)]
    path = tmp_path / "sample.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path, {row["text"]: row["vector"] for row in rows}


def test_compare_passes_on_the_instruction_form_and_never_prints_the_key(tmp_path, monkeypatch, capsys):
    path, stored = _sample(tmp_path)
    monkeypatch.setenv("EMBEDDING_API_URL", "https://embed.test")
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-secret-value")
    monkeypatch.setenv("EMBEDDING_MODEL", "qwen/qwen3-embedding-4b")
    sent = []

    def fake_embed(texts, url, key, model):
        sent.append(texts)
        vectors = []
        for text in texts:
            if text.startswith(compare_embeddings.INSTRUCTION):
                vectors.append([2 * value for value in stored[text[len(compare_embeddings.INSTRUCTION):]]])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors, "Qwen/Qwen3-Embedding-4B"

    monkeypatch.setattr(compare_embeddings, "embed", fake_embed)
    assert compare_embeddings.main(["compare_embeddings.py", str(path)]) == 0
    printed = capsys.readouterr().out
    assert "sk-secret-value" not in printed
    assert "instruction + text (the pipeline's form, the route's form): PASS  lowest 1.00000" in printed
    assert "route's query form (instruction + name. statement) 1.00000; plain name. statement 0.00000" in printed
    assert len(sent) == 1 + 3  # the expected form for all, then the plain text for the 3 query-side lines


def test_compare_tries_other_forms_and_says_which_passes(tmp_path, monkeypatch, capsys):
    path, stored = _sample(tmp_path)
    for name, value in (("EMBEDDING_API_URL", "https://embed.test"), ("EMBEDDING_API_KEY", "k"),
                        ("EMBEDDING_MODEL", "m")):
        monkeypatch.setenv(name, value)

    def plain_only(texts, url, key, model):
        return [stored.get(text, [0.0, 0.0, 1.0]) for text in texts], "m"

    monkeypatch.setattr(compare_embeddings, "embed", plain_only)
    assert compare_embeddings.main(["compare_embeddings.py", str(path)]) == 2
    printed = capsys.readouterr().out
    assert "forms that pass: plain text, plain stored_text" in printed


def test_compare_needs_all_three_settings(tmp_path, monkeypatch):
    path, _ = _sample(tmp_path)
    for name in ("EMBEDDING_API_URL", "EMBEDDING_API_KEY", "EMBEDDING_MODEL"):
        monkeypatch.delenv(name, raising=False)
    assert compare_embeddings.main(["compare_embeddings.py", str(path)]) == 1
    assert compare_embeddings.cosine([1.0, 0.0], [2.0, 0.0]) == pytest.approx(1.0)
