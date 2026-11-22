"""The word index of the game's search (0.0.19): its terms and BM25 vectors, the Qdrant calls that keep it,
and scripts/fill_word_index.py, with no database and no Qdrant."""
from __future__ import annotations

import io
import json
from contextlib import contextmanager
from types import SimpleNamespace

import httpx
import pytest

from app.services import word_index
from app.services.qdrant import QdrantService
from scripts import fill_word_index


# --- terms and vectors ---------------------------------------------------------------------------------

def test_terms_fold_case_accents_plurals_and_drop_common_and_latex_words():
    assert word_index.terms("The Groups of Möbius $\\mathbb{Q}$ and properties, x") == [
        "group", "mobius", "property"]
    assert word_index.terms("classes boxes series") == ["class", "box", "series"]


def test_term_index_is_a_stable_32_bit_hash():
    assert word_index.term_index("compact") == word_index.term_index("compact")
    assert 0 <= word_index.term_index("compact") < 2 ** 32
    assert word_index.term_index("compact") != word_index.term_index("compacts")


def test_document_vector_is_bm25s_term_frequency_part():
    vector = word_index.document_vector("Theorem 2.1", "Compact image", "compact compact space")
    found = word_index.terms("Theorem 2.1 Compact image compact compact space")
    assert len(found) == 6  # theorem, compact, image, compact, compact, space: "2" and "1" are too short
    length = len(found)
    norm = word_index.K1 * (1 - word_index.B + word_index.B * length / word_index.AVGDL)
    weights = dict(zip(vector["indices"], vector["values"]))
    assert weights[word_index.term_index("compact")] == pytest.approx(3 * 2.2 / (3 + norm), abs=1e-6)
    assert weights[word_index.term_index("space")] == pytest.approx(1 * 2.2 / (1 + norm), abs=1e-6)
    assert vector["indices"] == sorted(vector["indices"])


def test_query_vector_is_one_for_each_distinct_term():
    vector = word_index.query_vector(["compact compact", "Compact sets"])
    assert len(vector["indices"]) == 2 and vector["values"] == [1.0, 1.0]
    assert word_index.query_vector(["the a $x$"]) == {"indices": [], "values": []}


def test_point_keeps_ids_and_the_name_key_and_no_other_text():
    point = word_index.point({"knowledge_id": 846, "grimoire_id": 7, "label": "Exercise 3.3 <part 1>",
                              "name": "A cyclic basis in dimension two", "statement": "Let T be secret."})
    assert point["id"] == 846
    assert point["payload"] == {"knowledge_id": 846, "grimoire_id": 7, "name_key": "a cyclic basis in dimension two"}
    assert set(point["vector"]) == {"words"}
    assert "secret" not in json.dumps(point)


def test_name_ngrams_keep_order_skip_short_single_words_and_stop_at_the_limit():
    grams = word_index.name_ngrams("By the Heine-Borel theorem, a set is compact.", longest=3)
    assert "heine borel theorem" in grams and "compact" in grams
    assert "set" not in grams and "by" not in grams
    assert len(word_index.name_ngrams("word " * 50, limit=10)) <= 10


# --- the Qdrant calls ----------------------------------------------------------------------------------

def _service(handler):
    settings = SimpleNamespace(qdrant_api_key=None, qdrant_url="http://qdrant.test", qdrant_enabled=True)
    return QdrantService(settings=settings, client=httpx.Client(base_url=settings.qdrant_url,
                                                                transport=httpx.MockTransport(handler)))


def test_sparse_collection_is_created_with_idf_on_disk_and_its_indexes():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, json.loads(request.content) if request.content else None))
        if request.method == "GET":
            return httpx.Response(404, json={"status": {"error": "Not found"}})
        return httpx.Response(200, json={"result": True})

    created = _service(handler).ensure_sparse_collection(
        collection="knowledge-words-bm25", sparse_name="words", payload_indexes=word_index.PAYLOAD_INDEXES)
    assert created is True
    assert seen[1] == ("PUT", "/collections/knowledge-words-bm25",
                       {"sparse_vectors": {"words": {"modifier": "idf", "index": {"on_disk": True}}}})
    assert [body["field_name"] for _, _, body in seen[2:]] == ["knowledge_id", "grimoire_id", "name_key"]


def test_sparse_collection_present_keeps_data_and_adds_missing_indexes():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json={"result": {
                "config": {"params": {"sparse_vectors": {"words": {"modifier": "idf"}}}},
                "payload_schema": {"knowledge_id": {}, "grimoire_id": {}},
            }})
        return httpx.Response(200, json={"result": True})

    assert _service(handler).ensure_sparse_collection(
        collection="knowledge-words-bm25", sparse_name="words", payload_indexes=word_index.PAYLOAD_INDEXES) is False
    assert seen == [("GET", "/collections/knowledge-words-bm25"),
                    ("PUT", "/collections/knowledge-words-bm25/index")]


def test_query_raw_never_asks_for_vectors_and_is_bounded():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"result": {"points": [{"id": 4, "score": 2.5, "payload": {"knowledge_id": 4}}]}})

    service = _service(handler)
    points = service.query_raw(collection="knowledge-words-bm25", body={
        "query": {"indices": [1], "values": [1.0]}, "using": "words", "limit": 5})
    assert points == [{"id": 4, "score": 2.5, "payload": {"knowledge_id": 4}}]
    assert seen[0]["with_vector"] is False and seen[0]["using"] == "words"
    with pytest.raises(ValueError):
        service.query_raw(collection="c", body={"query": [0.0], "limit": 0})


def test_integer_ids_are_deleted_and_looked_up_as_integers():
    seen = []

    def handler(request):
        seen.append((request.url.path, json.loads(request.content)))
        if request.url.path.endswith("/points"):
            return httpx.Response(200, json={"result": [{"id": 2}]})
        return httpx.Response(200, json={"result": {}})

    service = _service(handler)
    service.delete_ids(collection="w", point_ids=[1, 2])
    assert service.existing_ids(collection="w", point_ids=[1, 2]) == {2}
    assert seen[0] == ("/collections/w/points/delete", {"points": [1, 2]})
    assert seen[1][1]["ids"] == [1, 2]


# --- the fill script -----------------------------------------------------------------------------------

class Library:
    def __init__(self):
        self.objects = {
            kid: {"knowledge_id": kid, "grimoire_id": 7 if kid < 2500 else 12, "name": f"Object {kid}",
                  "label": f"Theorem {kid}", "statement": f"Statement about compact sets {kid}", "active": True}
            for kid in range(1, 3001)
        }
        self.sql = []

    @contextmanager
    def transaction(self):
        yield None, self

    def execute(self, sql, values=None):
        self.sql.append(sql)
        self.values = values
        self.text = " ".join(sql.split())

    def fetchall(self):
        values = self.values
        books = set(values.get("books") or []) if "ANY(%(books)s)" in self.text else None
        rows = [row for row in self.objects.values() if row["active"]
                and (books is None or row["grimoire_id"] in books)]
        if "k.knowledge_id > %(after)s" in self.text:
            rows = sorted((row for row in rows if row["knowledge_id"] > values["after"]),
                          key=lambda row: row["knowledge_id"])[: values["limit"]]
            return [{key: row[key] for key in ("knowledge_id", "grimoire_id", "name", "label", "statement")}
                    for row in rows]
        if "k.knowledge_id = ANY(%(ids)s)" in self.text:
            return [{"knowledge_id": row["knowledge_id"]} for row in rows if row["knowledge_id"] in values["ids"]]
        return []


class Store:
    def __init__(self):
        self.exists = False
        self.points = {}
        self.writes = 0

    def collection_exists(self, collection):
        return self.exists

    def ensure_sparse_collection(self, *, collection, sparse_name, payload_indexes):
        created = not self.exists
        self.exists = True
        return created

    def upsert_raw(self, *, collection, points, chunk_size=512):
        self.writes += 1
        for point in points:
            self.points[point["id"]] = point

    def existing_ids(self, *, collection, point_ids):
        return {kid for kid in point_ids if kid in self.points}

    def scroll_points(self, *, collection, filter=None, limit=1024, offset=None, with_payload=False):
        books = set(filter["must"][0]["match"]["any"]) if filter else None
        ids = sorted(kid for kid, point in self.points.items()
                     if books is None or point["payload"]["grimoire_id"] in books)
        start = offset or 0
        page = ids[start:start + limit]
        following = start + limit if start + limit < len(ids) else None
        return [{"id": kid, "payload": {}} for kid in page], following

    def delete_ids(self, *, collection, point_ids):
        for kid in point_ids:
            self.points.pop(kid, None)


@pytest.fixture
def fill(monkeypatch):
    library, store = Library(), Store()
    monkeypatch.setattr(fill_word_index, "transaction", library.transaction)
    monkeypatch.setattr(fill_word_index, "qdrant_service", store)
    return SimpleNamespace(library=library, store=store)


def test_fill_writes_every_active_object_and_running_twice_changes_nothing(fill):
    out = io.StringIO()
    assert fill_word_index.run(out=out) == 0
    assert len(fill.store.points) == 3000
    first = dict(fill.store.points)
    assert "created" in out.getvalue() and "3,000 objects in 2 books" in out.getvalue()
    assert fill_word_index.run(out=io.StringIO()) == 0
    assert fill.store.points == first
    assert fill_word_index.run(check=True, out=io.StringIO()) == 0
    for sql in fill.library.sql:
        assert " ".join(sql.split()).upper().startswith(("SELECT", "SET TRANSACTION READ ONLY"))


def test_fill_deletes_points_of_objects_no_longer_active_and_check_reports_them(fill):
    fill_word_index.run(out=io.StringIO())
    fill.library.objects[10]["active"] = False
    del fill.library.objects[2999]
    check = io.StringIO()
    assert fill_word_index.run(check=True, out=check) == 2
    assert "2 stale found" in check.getvalue()
    assert 10 in fill.store.points
    out = io.StringIO()
    assert fill_word_index.run(out=out) == 0
    assert "2 stale deleted" in out.getvalue()
    assert 10 not in fill.store.points and 2999 not in fill.store.points
    assert fill_word_index.run(check=True, out=io.StringIO()) == 0


def test_fill_one_book_touches_only_that_books_points(fill):
    fill_word_index.run(books=[12], out=io.StringIO())
    assert {point["payload"]["grimoire_id"] for point in fill.store.points.values()} == {12}
    assert len(fill.store.points) == 501
    check = io.StringIO()
    assert fill_word_index.run(check=True, out=check) == 2
    assert "2,499 missing" in check.getvalue()


def test_check_without_the_collection_says_so(fill):
    out = io.StringIO()
    assert fill_word_index.run(check=True, out=out) == 2
    assert "missing" in out.getvalue()
