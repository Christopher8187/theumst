from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from app.routers import demo
from app.services.qdrant import QdrantService


SOURCE_POINT = "00000000-0000-0000-0000-000000000001"
POINT_TWO = "00000000-0000-0000-0000-000000000002"
POINT_THREE = "00000000-0000-0000-0000-000000000003"
POINT_FOUR = "00000000-0000-0000-0000-000000000004"


class ScriptedCursor:
    def __init__(self, *, one=None, all_rows=None):
        self.one = list(one or [])
        self.all_rows = list(all_rows or [])
        self.executions = []

    def execute(self, statement, values=None):
        self.executions.append((statement, values))

    def fetchone(self):
        return self.one.pop(0)

    def fetchall(self):
        return self.all_rows.pop(0)


def scripted_transactions(monkeypatch, *cursors):
    pending = list(cursors)

    @contextmanager
    def fake_transaction():
        yield None, pending.pop(0)

    monkeypatch.setattr(demo, "transaction", fake_transaction)
    return pending


def source_embedding(**overrides):
    row = {
        "embedding_id": SOURCE_POINT,
        "embedding_model_id": 7,
        "knowledge_id": 100,
        "language_id": 1,
        "projection_type": "statement",
        "direction": "self",
        "provider": "local",
        "model_name": "Qwen3-Embedding-0.6B",
        "model_revision": "archive-v1",
        "vector_size": 1024,
        "distance_metric": "cosine",
        "qdrant_collection": "book-vectors",
    }
    row.update(overrides)
    return row


def candidate(point_id, knowledge_id, **overrides):
    row = source_embedding(
        embedding_id=point_id,
        knowledge_id=knowledge_id,
        grimoire_id=12,
        book_title="Artin Algebra",
        label=f"Knowledge {knowledge_id}",
        statement=f"Statement {knowledge_id}",
    )
    row.update(overrides)
    return row


def configure_similarity(monkeypatch):
    monkeypatch.setattr(
        demo,
        "get_settings",
        lambda: SimpleNamespace(
            demo_similarity_projections=("statement:self", "combined:self"),
            qdrant_collection="book-vectors",
        ),
    )
    monkeypatch.setattr(demo, "_demo_user", lambda request: {"user_id": 44})


def test_similar_uses_stored_point_identity_book_scope_and_stable_dedup(monkeypatch):
    configure_similarity(monkeypatch)
    source_cursor = ScriptedCursor(
        one=[{"knowledge_id": 100, "grimoire_id": 12}],
        all_rows=[[source_embedding()]],
    )
    candidate_cursor = ScriptedCursor(
        all_rows=[[
            candidate(POINT_FOUR, 2),
            candidate(POINT_THREE, 1),
            candidate(POINT_TWO, 2),
        ]],
    )
    scripted_transactions(monkeypatch, source_cursor, candidate_cursor)
    seen = {}

    def query_by_point(**kwargs):
        seen.update(kwargs)
        return [
            {"id": SOURCE_POINT, "score": 1.0, "payload": {"knowledge_id": 100}},
            {"id": POINT_FOUR, "score": 0.8, "payload": {"knowledge_id": 9999}},
            {"id": POINT_TWO, "score": 0.8, "payload": {"knowledge_id": 9999}},
            {"id": POINT_THREE, "score": 0.8, "payload": {"knowledge_id": 9999}},
            {"id": "not-a-uuid", "score": 1.0, "payload": {"knowledge_id": 1}},
            {"id": POINT_THREE, "score": float("nan"), "payload": {}},
        ]

    monkeypatch.setattr(demo.qdrant_service, "query_by_point", query_by_point)
    monkeypatch.setattr(
        demo.qdrant_service,
        "embed_query",
        lambda *args, **kwargs: pytest.fail("similar must not call an embedding provider"),
    )

    response = demo.find_similar_knowledge(100, object(), k=2, scope="book")

    assert [row["knowledge_id"] for row in response["results"]] == [1, 2]
    assert response["results"][0]["similarity_score"] == 0.8
    assert set(response["results"][0]) == {
        "knowledge_id", "grimoire_id", "book_title", "label", "statement", "similarity_score",
    }
    assert seen == {
        "collection": "book-vectors",
        "point_id": SOURCE_POINT,
        "limit": 9,
        "filters": {
            "grimoire_id": 12,
            "language_id": 1,
            "projection_type": "statement",
            "direction": "self",
            "is_active": True,
        },
    }
    assert response["vector_projection"] == {
        "field": "semantic_projection.embedding_text",
        "source_embedding_id": SOURCE_POINT,
        "projection_type": "statement",
        "direction": "self",
        "embedding_model_id": 7,
        "provider": "local",
        "model_name": "Qwen3-Embedding-0.6B",
        "model_revision": "archive-v1",
        "vector_dimension": 1024,
        "distance_metric": "cosine",
        "qdrant_collection": "book-vectors",
    }
    hydration_sql, hydration_values = candidate_cursor.executions[0]
    assert "e.embedding_model_id = %s" in hydration_sql
    assert "target_section.grimoire_id = %s" in hydration_sql
    assert "em.vector_size = %s" in hydration_sql
    assert hydration_values[1:] == (
        7, 12, 1, "statement", "self", 1024, "book-vectors",
    )


def test_similar_openapi_contract_has_default_and_maximum_k():
    app = FastAPI()
    app.include_router(demo.router)
    operation = app.openapi()["paths"]["/api/demo/knowledge/{knowledge_id}/similar"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}

    assert parameters["k"]["schema"]["default"] == 10
    assert parameters["k"]["schema"]["minimum"] == 1
    assert parameters["k"]["schema"]["maximum"] == 25
    assert parameters["scope"]["schema"]["const"] == "book"
    assert parameters["scope"]["schema"]["default"] == "book"


def test_similar_rejects_unauthorized_requests_before_database_or_vector_access(monkeypatch):
    def reject(_request):
        raise HTTPException(status_code=403, detail="Access to demo is not permitted")

    monkeypatch.setattr(demo, "_demo_user", reject)
    monkeypatch.setattr(
        demo,
        "transaction",
        lambda: pytest.fail("unauthorized request reached the database"),
    )
    monkeypatch.setattr(
        demo.qdrant_service,
        "query_by_point",
        lambda **kwargs: pytest.fail("unauthorized request reached Qdrant"),
    )

    with pytest.raises(HTTPException) as exc:
        demo.find_similar_knowledge(100, object(), k=10, scope="book")
    assert exc.value.status_code == 403


@pytest.mark.parametrize("k", [0, 26, True])
def test_similar_enforces_frozen_k_bounds_even_when_called_directly(monkeypatch, k):
    monkeypatch.setattr(demo, "_demo_user", lambda request: {"user_id": 44})
    monkeypatch.setattr(
        demo,
        "transaction",
        lambda: pytest.fail("invalid k reached the database"),
    )
    with pytest.raises(HTTPException) as exc:
        demo.find_similar_knowledge(100, object(), k=k, scope="book")
    assert exc.value.status_code == 422


def test_similar_rejects_non_book_scope(monkeypatch):
    monkeypatch.setattr(demo, "_demo_user", lambda request: {"user_id": 44})
    with pytest.raises(HTTPException) as exc:
        demo.find_similar_knowledge(100, object(), k=10, scope="tenant")
    assert exc.value.status_code == 422


def test_similar_excludes_incompatible_model_and_dimension_rows(monkeypatch):
    configure_similarity(monkeypatch)
    source_cursor = ScriptedCursor(
        one=[{"knowledge_id": 100, "grimoire_id": 12}],
        all_rows=[[source_embedding()]],
    )
    candidate_cursor = ScriptedCursor(
        all_rows=[[
            candidate(POINT_TWO, 2, vector_size=768),
            candidate(POINT_THREE, 3, embedding_model_id=8),
            candidate(POINT_FOUR, 4),
        ]],
    )
    scripted_transactions(monkeypatch, source_cursor, candidate_cursor)
    monkeypatch.setattr(
        demo.qdrant_service,
        "query_by_point",
        lambda **kwargs: [
            {"id": POINT_TWO, "score": 0.99},
            {"id": POINT_THREE, "score": 0.98},
            {"id": POINT_FOUR, "score": 0.97},
        ],
    )

    response = demo.find_similar_knowledge(100, object(), k=10, scope="book")

    assert [row["knowledge_id"] for row in response["results"]] == [4]


def test_similar_reports_incompatible_source_projection_without_qdrant(monkeypatch):
    configure_similarity(monkeypatch)
    source_cursor = ScriptedCursor(
        one=[{"knowledge_id": 100, "grimoire_id": 12}],
        all_rows=[[
            source_embedding(distance_metric="dot"),
            source_embedding(projection_type="working"),
        ]],
    )
    scripted_transactions(monkeypatch, source_cursor)
    monkeypatch.setattr(
        demo.qdrant_service,
        "query_by_point",
        lambda **kwargs: pytest.fail("incompatible source reached Qdrant"),
    )

    with pytest.raises(HTTPException) as exc:
        demo.find_similar_knowledge(100, object(), k=10, scope="book")
    assert exc.value.status_code == 409
    assert exc.value.detail == "Similar suggestions are unavailable for this item."


def test_similar_translates_vector_service_errors_for_learners(monkeypatch):
    configure_similarity(monkeypatch)
    source_cursor = ScriptedCursor(
        one=[{"knowledge_id": 100, "grimoire_id": 12}],
        all_rows=[[source_embedding()]],
    )
    scripted_transactions(monkeypatch, source_cursor)

    def unavailable(**kwargs):
        raise HTTPException(status_code=502, detail="Internal vector service detail")

    monkeypatch.setattr(demo.qdrant_service, "query_by_point", unavailable)

    with pytest.raises(HTTPException) as exc:
        demo.find_similar_knowledge(100, object(), k=10, scope="book")
    assert exc.value.status_code == 503
    assert exc.value.detail == "Similar suggestions are temporarily unavailable."


def test_crystallize_reads_membership_and_checks_visibility(monkeypatch):
    monkeypatch.setattr(demo, "_demo_user", lambda request: {"user_id": 44})
    members = [{"knowledge_id": 101, "is_default_in_crystal": True}]
    cursor = ScriptedCursor(one=[{"knowledge_crystal_id": 7}], all_rows=[members])
    scripted_transactions(monkeypatch, cursor)
    assert demo.crystallize(100, object())["results"] == members
    assert cursor.executions[1][1] == (7,)
    assert all("source_metadata->>'demo'" in sql for sql, _ in cursor.executions)


def test_crystallize_requires_demo_access_before_reading(monkeypatch):
    def denied(request):
        raise HTTPException(403, "denied")
    monkeypatch.setattr(demo, "_demo_user", denied)
    monkeypatch.setattr(demo, "transaction", lambda: pytest.fail("unauthorized database access"))
    with pytest.raises(HTTPException) as exc:
        demo.crystallize(100, object())
    assert exc.value.status_code == 403


def test_qdrant_point_query_uses_indexed_identity_and_never_sends_a_vector():
    seen = []

    def handler(request: httpx.Request):
        seen.append(request)
        return httpx.Response(200, json={
            "result": {
                "points": [{"id": POINT_TWO, "score": 0.75, "payload": {"knowledge_id": 2}}]
            }
        })

    settings = SimpleNamespace(
        qdrant_api_key=None,
        qdrant_url="http://qdrant.test",
        qdrant_enabled=True,
    )
    client = httpx.Client(base_url=settings.qdrant_url, transport=httpx.MockTransport(handler))
    service = QdrantService(settings=settings, client=client)

    result = service.query_by_point(
        collection="book vectors/1",
        point_id=SOURCE_POINT,
        limit=10,
        filters={"grimoire_id": 12, "projection_type": "statement"},
    )

    request = seen[0]
    body = __import__("json").loads(request.content)
    assert b"book%20vectors%2F1" in request.url.raw_path
    assert body["query"] == SOURCE_POINT
    assert "vector" not in body
    assert body["with_vector"] is False
    assert body["filter"] == {"must": [
        {"key": "grimoire_id", "match": {"value": 12}},
        {"key": "projection_type", "match": {"value": "statement"}},
    ]}
    assert result == [{"id": POINT_TWO, "score": 0.75, "payload": {"knowledge_id": 2}}]


@pytest.mark.parametrize("limit", [0, 257])
def test_qdrant_point_query_is_bounded(limit):
    settings = SimpleNamespace(
        qdrant_api_key=None,
        qdrant_url="http://qdrant.test",
        qdrant_enabled=True,
    )
    service = QdrantService(
        settings=settings,
        client=httpx.Client(base_url=settings.qdrant_url, transport=httpx.MockTransport(lambda request: None)),
    )
    with pytest.raises(ValueError, match="between 1 and 256"):
        service.query_by_point(collection="book-vectors", point_id=SOURCE_POINT, limit=limit)
