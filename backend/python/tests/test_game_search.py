"""The game's search (0.0.19): services/game_search.py and routers/game_search.py, with no database.

PostgreSQL is a fake cursor answering each of the module's queries from a small in-memory library of four
books, one of them hidden; Qdrant and the embedding provider are fakes that record what they were asked.
These tests check the module's own logic: the query text, the visibility filter inside every query, the
merge by rank, the crystal hiding, the latcher's labels and names, the refusals and that nothing is written.
They do not establish the behaviour of a live PostgreSQL, Qdrant or OpenRouter.
"""
from __future__ import annotations

import json
import math
from contextlib import contextmanager
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.dependencies import AccessRefused
from app.routers import game, game_search as search_router
from app.services import game_search, word_index

STORE = "knowledge-qwen3-embedding-4b"
VISIBLE_BOOKS = {7: "Algebra", 12: "Topology", 18: "Analysis"}
HIDDEN_BOOK = 30


def obj(knowledge_id, book, crystal, name, statement, *, label="", type_="theorem", active=True, source_key=None):
    return {
        "knowledge_id": knowledge_id, "grimoire_id": book, "crystal_id": crystal, "name": name, "label": label,
        "statement": statement, "type": type_, "active": active,
        "source_key": source_key or f"scope-test:{knowledge_id}",
    }


OBJECTS = {row["knowledge_id"]: row for row in [
    obj(1, 7, 100, "Compact image", "The continuous image of a compact space is compact.", label="Theorem 2.1"),
    obj(2, 12, 100, "Image of a compact set", "A continuous map sends compact sets to compact sets.",
        label="Proposition 4.3"),
    obj(3, 18, 100, "Compactness is preserved", "Continuous images of compact spaces are compact.",
        label="Lemma 2.1"),
    obj(4, 7, 200, "Heine-Borel theorem", "A subset of R^n is compact iff it is closed and bounded.",
        label="Theorem 3.4"),
    obj(5, HIDDEN_BOOK, 200, "Heine-Borel", "Closed bounded subsets of Euclidean space are compact.",
        label="Theorem 1.1"),
    obj(6, 12, 300, "Extreme value theorem", "A continuous real function on a compact space attains a maximum.",
        label="Theorem 5.2"),
    obj(7, 18, 300, "Old extreme value", "Retired statement.", label="Theorem 9.9", active=False),
    obj(8, 18, 400, "Lemma on maxima", "A maximum exists.", label="Lemma 2.1", type_="lemma"),
    obj(9, 7, 500, "Permutation of a set", "A bijective map of a set to itself.", label="",
        type_="definition"),
]}
# Crystal 100 has nine members in visible books in all, so a search shows two of them (floor(log3 9) = 2).
EXTRA_MEMBERS = {100: 6}
STATEMENT_POINTS = {kid: f"00000000-0000-0000-0000-{kid:012d}" for kid in OBJECTS if kid != 9}


def visible(row):
    return row["active"] and row["grimoire_id"] in VISIBLE_BOOKS


class FakeCursor:
    def __init__(self, log):
        self.log = log
        self.rows = []

    def execute(self, sql, values=None):
        self.log.append(sql)
        text = " ".join(sql.split())
        if text.startswith("SET TRANSACTION READ ONLY"):
            self.rows = []
        elif "FROM grimoire WHERE grimoire_id = ANY" in text:
            self.rows = [{"grimoire_id": book} for book in values[0] if book in VISIBLE_BOOKS]
        elif "IS DISTINCT FROM 'true'" in text:
            self.rows = [{"grimoire_id": HIDDEN_BOOK}]
        elif "FROM grimoire WHERE source_metadata->>'demo' = 'true'" in text:
            self.rows = [{"grimoire_id": book} for book in sorted(VISIBLE_BOOKS)]
        elif "FROM embedding_model em WHERE" in text:
            self.rows = [{"embedding_model_id": 1, "model_name": "Qwen/Qwen3-Embedding-4B", "vector_size": 4,
                          "distance_metric": "cosine", "qdrant_collection": STORE}]
        elif "count(*)::int AS size" in text:
            sizes = {}
            for row in OBJECTS.values():
                if visible(row) and row["crystal_id"] in values[0]:
                    sizes[row["crystal_id"]] = sizes.get(row["crystal_id"], 0) + 1
            self.rows = [{"crystal_id": crystal, "size": size + EXTRA_MEMBERS.get(crystal, 0)}
                         for crystal, size in sizes.items()]
        elif "WHERE k.source_key = %s" in text:
            self.rows = [{"knowledge_id": row["knowledge_id"]} for row in OBJECTS.values()
                         if row["source_key"] == values[0] and visible(row)][:1]
        elif "FROM semantic_projection sp" in text:
            point = STATEMENT_POINTS.get(values[0])
            self.rows = [{"embedding_id": point, "qdrant_collection": STORE, "vector_size": 4}] if point else []
        elif "rtrim(regexp_replace(lower(lk.label)" in text:
            _, book, keys = values
            self.rows = [{"knowledge_id": row["knowledge_id"], "label_key": game_search.label_key(row["label"])}
                         for row in OBJECTS.values()
                         if row["grimoire_id"] == book and visible(row)
                         and game_search.label_key(row["label"]) in keys]
        elif "SELECT k.knowledge_id, COALESCE(k.source_key" in text:
            books = values.get("books")
            self.rows = [
                {key: row[key] for key in ("knowledge_id", "source_key", "type", "crystal_id", "name", "label",
                                           "statement", "grimoire_id")}
                | {"book_title": VISIBLE_BOOKS[row["grimoire_id"]]}
                for kid, row in OBJECTS.items()
                if kid in values["ids"] and visible(row) and (books is None or row["grimoire_id"] in books)
            ]
        else:
            raise AssertionError(f"unexpected SQL: {text}")

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


class FakeQdrant:
    """Answers from scripted rankings and applies the request's filter to them, as Qdrant would."""

    def __init__(self):
        self.dense = []        # [(knowledge_id, cosine)]
        self.words = []        # [(knowledge_id, bm25)]
        self.word_store = True
        self.queries = []
        self.scrolls = []
        self.fail_dense = False

    @staticmethod
    def _passes(knowledge_id, flt):
        row = OBJECTS[knowledge_id]
        for condition in (flt or {}).get("must", []):
            match = condition["match"]
            value = row["grimoire_id"] if condition["key"] == "grimoire_id" else (
                knowledge_id if condition["key"] == "knowledge_id" else None)
            if condition["key"] == "name_key":
                value = word_index.name_key(row["name"])
            if value is None:
                continue
            if "any" in match and value not in match["any"]:
                return False
            if "value" in match and value != match["value"]:
                return False
        for condition in (flt or {}).get("must_not", []):
            match = condition["match"]
            value = row["grimoire_id"] if condition["key"] == "grimoire_id" else knowledge_id
            if ("any" in match and value in match["any"]) or ("value" in match and value == match["value"]):
                return False
        return True

    def query_raw(self, *, collection, body):
        self.queries.append((collection, body))
        if collection == word_index.COLLECTION:
            ranked = self.words
        else:
            if self.fail_dense:
                raise HTTPException(502, "Qdrant down")
            ranked = self.dense
        points = [{"id": kid, "score": score, "payload": {"knowledge_id": kid}}
                  for kid, score in ranked if self._passes(kid, body.get("filter"))]
        return points[: body["limit"]]

    def collection_exists(self, collection):
        return self.word_store

    def scroll_points(self, *, collection, filter=None, limit=1024, offset=None, with_payload=False):
        self.scrolls.append((collection, filter))
        points = [{"id": kid, "payload": {"knowledge_id": kid, "name_key": word_index.name_key(row["name"])}}
                  for kid, row in sorted(OBJECTS.items()) if self._passes(kid, filter)]
        return points[:limit], None


@pytest.fixture
def library(monkeypatch):
    state = SimpleNamespace(sql=[], qdrant=FakeQdrant(), posts=[], vectors=None,
                            settings=SimpleNamespace(embedding_api_url=None, embedding_api_key=None,
                                                     embedding_model=None))

    @contextmanager
    def fake_transaction():
        yield None, FakeCursor(state.sql)

    def fake_post(url, *, headers, json, timeout):
        state.posts.append({"url": url, "headers": headers, "json": json})
        vectors = state.vectors or [[0.5, 0.5, 0.5, 0.5]] * len(json["input"])
        return httpx.Response(200, json={"data": [{"index": i, "embedding": v} for i, v in enumerate(vectors)]},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(game_search, "transaction", fake_transaction)
    monkeypatch.setattr(game_search, "qdrant_service", state.qdrant)
    monkeypatch.setattr(game_search, "get_settings", lambda: state.settings)
    monkeypatch.setattr(game_search, "_post", fake_post)
    return state


def embedding_on(state):
    state.settings = SimpleNamespace(embedding_api_url="https://openrouter.ai/api/v1/embeddings",
                                     embedding_api_key="test-key", embedding_model="qwen/qwen3-embedding-4b")


def assert_read_only(state):
    for sql in state.sql:
        text = " ".join(sql.split()).upper()
        assert text.startswith(("SELECT", "SET TRANSACTION READ ONLY")), text
        if " KNOWLEDGE K" in text:
            assert "SOURCE_METADATA->>'DEMO' = 'TRUE'" in text, text


# --- pure parts ----------------------------------------------------------------------------------------

@pytest.mark.parametrize(("members", "shown"), [
    (1, 1), (2, 1), (3, 1), (8, 1), (9, 2), (26, 2), (27, 3), (80, 3), (81, 4), (243, 5),
])
def test_crystal_hiding_shows_max_one_or_floor_log3(members, shown):
    assert game_search.shown_members(members) == shown
    assert shown == max(1, math.floor(math.log(members, 3) + 1e-9))


def test_query_text_is_the_pipelines_stored_text():
    assert game_search.query_text("Compact image.", "The continuous image\n\n of a compact space.") == (
        "Compact image. The continuous image of a compact space.")
    assert game_search.query_text("", "Only a statement") == "Only a statement"


def test_same_model_matches_openrouters_name_to_the_books_model():
    assert game_search._same_model("qwen/qwen3-embedding-4b", "Qwen/Qwen3-Embedding-4B")
    assert not game_search._same_model("qwen/qwen3-embedding-0.6b", "Qwen/Qwen3-Embedding-4B")
    assert not game_search._same_model(None, "Qwen/Qwen3-Embedding-4B")


def test_fuse_merges_by_reciprocal_rank_and_breaks_ties_by_id():
    fused = game_search.fuse([("meaning", [(5, 0.9), (2, 0.8)]), ("words", [(2, 11.0), (5, 3.0), (9, 1.0)])])
    assert [entry["knowledge_id"] for entry in fused] == [2, 5, 9]
    assert fused[0]["found_by"] == ["meaning", "words"]
    assert fused[0]["scores"]["fused"] == pytest.approx(1 / 62 + 1 / 61, abs=1e-6)
    assert fused[2]["scores"] == {"meaning": None, "words": 1.0, "fused": pytest.approx(1 / 63, abs=1e-6)}


def test_fuse_puts_named_rankings_first():
    fused = game_search.fuse([("words", [(1, 9.0), (2, 8.0)]), ("label", [(3, 1.0)])], first=("label",))
    assert [entry["knowledge_id"] for entry in fused] == [3, 1, 2]


def test_text_pieces_cover_the_whole_text_in_at_most_eight_pieces():
    text = " ".join(f"Sentence number {i} says something about compact sets." for i in range(200))
    pieces = game_search.text_pieces(text)
    assert 1 < len(pieces) <= game_search.LATCHER_PIECES
    assert " ".join(pieces) == text


def test_label_mentions_keep_the_labels_prefix():
    mentions = game_search.label_mentions("By Lemma 2.1 and theorem 3.4(b), and Exercise 10.4.")
    assert mentions == {"lemma2.1": "Lemma 2.1", "theorem3.4(b)": "theorem 3.4(b)", "exercise10.4": "Exercise 10.4"}
    assert game_search.label_key("Exercise 3.3 <part 1>") == "exercise3.3"


# --- embedding -----------------------------------------------------------------------------------------

def test_embedding_sends_the_pipelines_instruction_and_checks_the_books_size(library):
    embedding_on(library)
    model = {"model_name": "Qwen/Qwen3-Embedding-4B", "vector_size": 4}
    meaning = game_search.embed(["Compact image. The image is compact."], model)
    assert meaning.state == "used" and meaning.vectors == [[0.5, 0.5, 0.5, 0.5]]
    sent = library.posts[0]
    assert sent["json"] == {"model": "qwen/qwen3-embedding-4b", "input": [
        "Instruct: Given a mathematical statement, retrieve statements of the same result\nQuery:"
        "Compact image. The image is compact."]}
    assert sent["headers"]["Authorization"] == "Bearer test-key"
    library.vectors = [[1.0, 0.0]]
    assert game_search.embed(["x"], model).state == "failed"


def test_embedding_is_off_without_settings_or_for_another_model(library):
    model = {"model_name": "Qwen/Qwen3-Embedding-4B", "vector_size": 4}
    assert (game_search.embed(["x"], model).state, game_search.embed(["x"], model).reason) == ("off", "not_configured")
    library.settings = SimpleNamespace(embedding_api_url="https://e.test", embedding_api_key=None,
                                       embedding_model="qwen/qwen3-embedding-0.6b")
    assert game_search.embed(["x"], model).reason == "other_model"
    assert game_search.embed(["x"], None).reason == "no_vectors"
    assert library.posts == []


def test_a_failing_provider_is_reported_without_its_answer(library, monkeypatch):
    embedding_on(library)

    def broken(url, **_):
        return httpx.Response(500, text="echo: the reader's secret note", request=httpx.Request("POST", url))

    monkeypatch.setattr(game_search, "_post", broken)
    meaning = game_search.embed(["the reader's secret note"], {"model_name": "Qwen/Qwen3-Embedding-4B",
                                                               "vector_size": 4})
    assert (meaning.state, meaning.reason) == ("failed", "provider_failed")


# --- 1. search -----------------------------------------------------------------------------------------

def test_search_by_words_alone_says_so_and_filters_hidden_books_inside_the_query(library):
    library.qdrant.words = [(5, 20.0), (4, 15.0), (7, 9.0), (6, 3.0)]
    answer = game_search.search_objects(name="Heine-Borel", statement="closed and bounded is compact",
                                        keywords=["compact"], count=10)
    assert answer["rankings"] == {"meaning": "off", "words": "used"}
    assert "search by words only" in answer["notice"]
    assert [hit["knowledge_id"] for hit in answer["results"]] == [4, 6]  # 5 hidden book, 7 inactive
    collection, body = library.qdrant.queries[0]
    assert collection == word_index.COLLECTION and body["using"] == "words"
    assert body["filter"] == {"must_not": [{"key": "grimoire_id", "match": {"any": [HIDDEN_BOOK]}}]}
    assert set(body["query"]) == {"indices", "values"} and body["query"]["values"][0] == 1.0
    assert library.posts == []
    assert_read_only(library)


def test_search_merges_meaning_and_words_and_hides_a_crystals_extra_members(library):
    embedding_on(library)
    library.qdrant.dense = [(1, 0.95), (2, 0.93), (3, 0.91), (6, 0.80)]
    library.qdrant.words = [(3, 12.0), (1, 10.0), (4, 2.0)]
    answer = game_search.search_objects(name="Compact image", statement="The continuous image of a compact space "
                                        "is compact.", keywords=[], count=10)
    assert answer["rankings"] == {"meaning": "used", "words": "used"} and answer["notice"] is None
    ids = [hit["knowledge_id"] for hit in answer["results"]]
    # Crystal 100 has 9 visible members (3 here and 6 more), so 2 of them show: the two best, 1 and 3.
    # 4 is third by words (1/63), 6 fourth by meaning (1/64).
    assert ids == [1, 3, 4, 6]
    first = answer["results"][0]
    assert first == {
        "knowledge_id": 1, "source_key": "scope-test:1", "grimoire_id": 7, "book_title": "Algebra",
        "label": "Theorem 2.1", "name": "Compact image",
        "statement": "The continuous image of a compact space is compact.", "type": "theorem",
        "crystal_id": 100, "crystal_size": 9, "crystal_shown": 2, "found_by": ["meaning", "words"], "rank": 1,
        "scores": {"meaning": 0.95, "words": 10.0, "fused": pytest.approx(1 / 61 + 1 / 62, abs=1e-6)},
    }
    dense = next(body for collection, body in library.qdrant.queries if collection == STORE)
    must = dense["filter"]["must"]
    assert {"key": "projection_type", "match": {"value": "statement"}} in must
    assert {"key": "direction", "match": {"value": "self"}} in must
    assert dense["filter"]["must_not"] == [{"key": "grimoire_id", "match": {"any": [HIDDEN_BOOK]}}]
    assert_read_only(library)


def test_search_uses_the_books_store_not_the_configured_default(library):
    embedding_on(library)
    library.qdrant.dense = [(4, 0.9)]
    game_search.search_objects(name="", statement="compact", keywords=[], count=3)
    assert {collection for collection, _ in library.qdrant.queries} == {STORE, word_index.COLLECTION}


def test_search_limited_to_books_and_counts(library):
    library.qdrant.words = [(1, 9.0), (2, 8.0), (4, 7.0), (6, 6.0), (9, 5.0)]
    answer = game_search.search_objects(name="", statement="compact", keywords=[], count=2, books=[7, HIDDEN_BOOK])
    assert [hit["knowledge_id"] for hit in answer["results"]] == [1, 4]
    assert library.qdrant.queries[0][1]["filter"] == {"must": [{"key": "grimoire_id", "match": {"any": [7]}}]}
    only_hidden = game_search.search_objects(name="", statement="compact", keywords=[], count=2,
                                             books=[HIDDEN_BOOK])
    assert only_hidden["results"] == [] and only_hidden["count"] == 0


def test_search_with_neither_ranking_is_unavailable(library):
    library.qdrant.word_store = False
    with pytest.raises(game_search.SearchUnavailable, match="word index"):
        game_search.search_objects(name="", statement="compact", keywords=[], count=3)


def test_a_failing_vector_store_leaves_search_by_words(library):
    embedding_on(library)
    library.qdrant.fail_dense = True
    library.qdrant.words = [(4, 3.0)]
    answer = game_search.search_objects(name="", statement="compact", keywords=[], count=3)
    assert answer["rankings"] == {"meaning": "failed", "words": "used"}
    assert "did not answer" in answer["notice"]
    assert [hit["knowledge_id"] for hit in answer["results"]] == [4]


# --- 2. neighbours -------------------------------------------------------------------------------------

def test_neighbours_query_by_the_stored_point_across_visible_books(library):
    library.qdrant.dense = [(1, 1.0), (2, 0.97), (5, 0.96), (3, 0.95), (6, 0.5)]
    answer = game_search.neighbours(knowledge_id=1, count=3)
    assert answer["object"]["knowledge_id"] == 1 and answer["object"]["crystal_size"] == 9
    assert "rank" not in answer["object"]
    assert [hit["knowledge_id"] for hit in answer["results"]] == [2, 3, 6]
    assert [hit["rank"] for hit in answer["results"]] == [1, 2, 3]
    collection, body = library.qdrant.queries[0]
    assert collection == STORE and body["query"] == STATEMENT_POINTS[1]
    assert {"key": "knowledge_id", "match": {"value": 1}} in body["filter"]["must_not"]
    assert library.posts == []
    assert_read_only(library)


def test_neighbours_by_source_key_and_refusals(library):
    library.qdrant.dense = [(4, 0.9)]
    assert game_search.neighbours(source_key="scope-test:6", count=2)["object"]["knowledge_id"] == 6
    with pytest.raises(game_search.ObjectNotFound):
        game_search.neighbours(knowledge_id=5, count=2)  # hidden book
    with pytest.raises(game_search.ObjectNotFound):
        game_search.neighbours(source_key="scope-test:7", count=2)  # inactive
    with pytest.raises(game_search.NoVector):
        game_search.neighbours(knowledge_id=9, count=2)


# --- 3. the latcher's candidates -----------------------------------------------------------------------

def test_latcher_finds_labels_in_its_book_names_anywhere_then_search(library):
    library.qdrant.words = [(6, 4.0), (2, 3.0)]
    text = ("By Lemma 2.1 the function is bounded. The Heine-Borel theorem gives compactness, "
            "and Theorem 9.9 is not in this book.")
    answer = game_search.latcher_candidates(text=text, grimoire_id=18, count=10)
    results = {hit["knowledge_id"]: hit for hit in answer["results"]}
    # Lemma 2.1 of book 18 is objects 3 and 8; "Theorem 2.1" of book 7 is not taken for it.
    assert results[3]["found_by"][0] == "label" and results[3]["mentions"] == ["Lemma 2.1"]
    assert results[8]["mentions"] == ["Lemma 2.1"]
    assert 1 not in results
    # "Heine-Borel theorem" is object 4's whole name; object 5 has that name too, in a hidden book.
    assert results[4]["found_by"] == ["name"] and results[4]["mentions"] == ["heine borel theorem"]
    assert 5 not in results and 7 not in results
    order = [hit["knowledge_id"] for hit in answer["results"]]
    assert order.index(6) > max(order.index(3), order.index(4), order.index(8))
    assert results[6]["mentions"] == []
    assert answer["rankings"]["words"] == "used"
    name_filter = library.qdrant.scrolls[0][1]
    assert {"key": "grimoire_id", "match": {"any": [HIDDEN_BOOK]}} in name_filter["must_not"]
    assert_read_only(library)


def test_latcher_finds_a_name_at_the_end_of_a_long_note(library):
    text = " ".join(f"filler{i}" for i in range(600)) + " so the Extreme value theorem applies."
    answer = game_search.latcher_candidates(text=text, grimoire_id=None, count=5)
    assert answer["results"][0]["knowledge_id"] == 6
    assert answer["results"][0]["mentions"] == ["extreme value theorem"]
    assert len(library.qdrant.scrolls) > 1


def test_latcher_answers_from_labels_alone_when_no_ranking_runs(library):
    library.qdrant.word_store = False
    answer = game_search.latcher_candidates(text="Lemma 2.1 gives it.", grimoire_id=18, count=5)
    # Book 18 labels both 3 and 8 "Lemma 2.1" (crystals 100 and 400); "Theorem 2.1" of book 7 is not taken.
    assert [hit["knowledge_id"] for hit in answer["results"]] == [3, 8]
    assert answer["rankings"] == {"meaning": "off", "words": "off"}


def test_latcher_embeds_each_piece_once_in_one_call(library):
    embedding_on(library)
    text = " ".join(f"Sentence {i} is about compact spaces and continuous maps." for i in range(100))
    game_search.latcher_candidates(text=text, grimoire_id=None, count=5)
    assert len(library.posts) == 1
    assert 1 < len(library.posts[0]["json"]["input"]) <= game_search.LATCHER_PIECES


# --- 4. which crystal ----------------------------------------------------------------------------------

def test_which_crystal_groups_hits_and_shows_log3_members(library):
    embedding_on(library)
    library.qdrant.dense = [(2, 0.96), (1, 0.95), (6, 0.7), (3, 0.69), (4, 0.4)]
    library.qdrant.words = [(1, 8.0), (4, 2.0)]
    answer = game_search.which_crystals(name="", statement="Continuous images of compact sets are compact.",
                                        keywords=[], count=2)
    # Crystal 200's object 4 is found by both rankings (1/65 + 1/62), ahead of crystal 300's 6 (1/63).
    assert [crystal["crystal_id"] for crystal in answer["crystals"]] == [100, 200]
    first = answer["crystals"][0]
    assert first["crystal_size"] == 9 and first["rank"] == 1 and first["found_by"] == ["meaning", "words"]
    assert first["scores"]["meaning"] == 0.96 and first["scores"]["words"] == 8.0
    assert [member["knowledge_id"] for member in first["members"]] == [1, 2]
    assert all(member["crystal_shown"] == 2 for member in first["members"])
    assert_read_only(library)


# --- the routes ----------------------------------------------------------------------------------------

@pytest.fixture
def api(monkeypatch, library):
    state = SimpleNamespace(calls=[], access_points=["demo"], refusal=None, library=library)

    def fake_authenticate(request, *, kind, master_required=False, master_allowed=True, access_point=None, cost=1):
        state.calls.append({"kind": kind, "master_allowed": master_allowed, "access_point": access_point})
        if state.refusal is not None:
            raise state.refusal
        if access_point is not None and access_point not in state.access_points:
            raise AccessRefused(access_point)
        return {"api_key_id": 41, "key_type": "regular"}

    monkeypatch.setattr(search_router, "authenticate_api_key", fake_authenticate)
    application = FastAPI()
    application.include_router(search_router.router)
    game.install_error_handlers(application)
    state.client = TestClient(application)
    return state


def test_routes_count_once_as_search_with_demo_access_and_no_master_key(api):
    api.library.qdrant.words = [(4, 3.0)]
    response = api.client.post("/api/game/search/objects", json={"statement": "compact"},
                               headers={"X-API-Key": "k"})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert api.calls == [{"kind": "search", "master_allowed": False, "access_point": "demo"}]
    assert response.json()["results"][0]["knowledge_id"] == 4


def test_routes_refuse_without_demo_access_before_reading(api):
    api.access_points = []
    response = api.client.post("/api/game/search/crystals", json={"statement": "compact"})
    assert response.status_code == 403
    assert response.json()["code"] == "demo_access_required"
    assert api.library.sql == [] and api.library.qdrant.queries == []


def test_routes_map_key_refusals_to_the_games_codes(api):
    api.refusal = HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": "9"})
    response = api.client.get("/api/game/search/neighbours", params={"knowledge_id": 1})
    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited" and response.json()["retry_after"] == 9
    api.refusal = HTTPException(status_code=403, detail="Master keys are not accepted here")
    assert api.client.get("/api/game/search/neighbours", params={"knowledge_id": 1}).json()["code"] == \
        "master_key_not_allowed"
    api.refusal = HTTPException(status_code=401, detail="Invalid or revoked API key")
    assert api.client.get("/api/game/search/neighbours", params={"knowledge_id": 1}).json()["code"] == "invalid_key"


@pytest.mark.parametrize(("path", "body"), [
    ("/api/game/search/objects", {"statement": ""}),
    ("/api/game/search/objects", {"statement": "x", "count": 51}),
    ("/api/game/search/objects", {"statement": "x", "keywords": ["k"] * 21}),
    ("/api/game/search/objects", {"statement": "x", "books": []}),
    ("/api/game/search/objects", {"statement": "x" * 4001}),
    ("/api/game/search/latcher-candidates", {"text": "x" * 20001}),
    ("/api/game/search/latcher-candidates", {"text": "   "}),
    ("/api/game/search/crystals", {"statement": "x", "count": 21}),
])
def test_routes_validate_their_bodies_in_the_games_shape(api, path, body):
    response = api.client.post(path, json=body)
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "invalid_request"
    assert api.library.qdrant.queries == []


def test_neighbours_route_needs_exactly_one_of_id_and_source_key(api):
    assert api.client.get("/api/game/search/neighbours").status_code == 422
    both = api.client.get("/api/game/search/neighbours", params={"knowledge_id": 1, "source_key": "a"})
    assert both.status_code == 422 and both.json()["errors"][0]["field"] == "knowledge_id"


def test_neighbours_route_answers_404_409_and_200(api):
    api.library.qdrant.dense = [(2, 0.9)]
    assert api.client.get("/api/game/search/neighbours", params={"knowledge_id": 5}).json()["code"] == "not_found"
    assert api.client.get("/api/game/search/neighbours", params={"knowledge_id": 9}).json()["code"] == "no_vector"
    ok = api.client.get("/api/game/search/neighbours", params={"source_key": "scope-test:1", "count": 1})
    assert ok.status_code == 200 and ok.json()["results"][0]["knowledge_id"] == 2


def test_search_route_answers_503_when_no_ranking_can_run(api):
    api.library.qdrant.word_store = False
    response = api.client.post("/api/game/search/objects", json={"statement": "compact"})
    assert response.status_code == 503
    assert response.json()["code"] == "search_unavailable"


def test_latcher_route_stores_nothing_and_echoes_no_text_on_failure(api, monkeypatch):
    secret = "My private attempt: by Lemma 2.1 the sequence converges."
    api.library.qdrant.words = [(3, 2.0)]
    response = api.client.post("/api/game/search/latcher-candidates", json={"text": secret, "grimoire_id": 18})
    assert response.status_code == 200
    assert_read_only(api.library)
    api.library.qdrant.word_store = False
    api.library.settings = SimpleNamespace(embedding_api_url=None, embedding_api_key=None, embedding_model=None)
    refused = api.client.post("/api/game/search/latcher-candidates", json={"text": "No labels here at all."})
    assert refused.status_code == 503 and "No labels" not in refused.text
    assert json.dumps(refused.json()).count("private") == 0


def test_openapi_lists_the_four_routes():
    application = FastAPI()
    application.include_router(search_router.router)
    paths = application.openapi()["paths"]
    assert set(paths) == {
        "/api/game/search/objects", "/api/game/search/neighbours",
        "/api/game/search/latcher-candidates", "/api/game/search/crystals",
    }
