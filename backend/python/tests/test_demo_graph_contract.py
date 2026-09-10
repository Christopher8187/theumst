from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.testclient import TestClient

from app.routers import demo


class Request:
    def __init__(self, *, headers: dict[str, str] | None = None):
        self.headers = headers or {}


class Cursor:
    def __init__(self, book_exists: bool = True):
        self.book_exists = book_exists
        self.queries: list[tuple[str, object]] = []

    def execute(self, query: str, parameters=None):
        self.queries.append((query, parameters))

    def fetchone(self):
        return {"exists": 1} if self.book_exists else None


@contextmanager
def transaction_for(cursor: Cursor):
    yield object(), cursor


def graph_result() -> dict:
    return {
        "nodes": [{
            "knowledge_id": 11,
            "label": "Group",
            "type": "definition",
            "graph_role": "backbone",
            "collapsed_ancestor_count": 0,
            "collapsed_descendant_count": 0,
            "stable_knowledge_id": "artin:group",
        }],
        "edges": [],
        "graph_revision": "book_order_v1:r1",
        "focus_knowledge_id": 11,
        "graph_capability": "book_order_projection",
        "projection_metadata": {
            "version": "book_order_v1",
            "relation_type": "book_order_v1",
            "source": "knowledge.source_metadata.order",
            "authored_dependencies": False,
            "leading_non_main_anchor_knowledge_id": None,
        },
        "edges_truncated": False,
    }


def call_graph(monkeypatch, *, headers=None, **overrides):
    cursor = Cursor()
    captured: dict = {}
    monkeypatch.setattr(demo, "_demo_user", lambda request: {"user_id": 5})
    monkeypatch.setattr(demo, "transaction", lambda: transaction_for(cursor))

    def focused(cur, **kwargs):
        captured.update(kwargs)
        return graph_result()

    monkeypatch.setattr(demo, "fetch_focused_graph", focused)
    response = Response()
    result = demo.get_grimoire_graph(
        7,
        Request(headers=headers),
        response,
        focus="11",
        ancestor_depth=overrides.get("ancestor_depth", 2),
        descendant_depth=overrides.get("descendant_depth", 2),
        include=overrides.get("include", "support,assessment"),
        limit=overrides.get("limit", 150),
    )
    return result, response, cursor, captured


def test_frozen_graph_contract_names_bounds_and_book_scope(monkeypatch):
    result, response, cursor, captured = call_graph(monkeypatch)

    assert set(result) >= {"nodes", "edges", "graph_revision", "focus_knowledge_id"}
    assert set(result["nodes"][0]) >= {
        "knowledge_id", "label", "type", "graph_role",
        "collapsed_ancestor_count", "collapsed_descendant_count",
    }
    assert captured == {
        "grimoire_id": 7,
        "focus": "11",
        "ancestor_depth": 2,
        "descendant_depth": 2,
        "include_roles": ("assessment", "support"),
        "limit": 150,
    }
    assert result["graph_capability"] == "book_order_projection"
    assert result["projection_metadata"]["authored_dependencies"] is False
    assert cursor.queries[0][1] == (7,)
    assert "source_metadata->>'demo'" in cursor.queries[0][0]
    assert response.headers["cache-control"] == "private, max-age=300"
    assert response.headers["vary"] == "Authorization, Cookie, Accept-Encoding"
    assert response.headers["etag"].startswith('"')


def test_graph_etag_revalidation_returns_304(monkeypatch):
    _, first_response, _, _ = call_graph(monkeypatch)
    result, _, _, _ = call_graph(
        monkeypatch,
        headers={"if-none-match": first_response.headers["etag"]},
    )

    assert isinstance(result, Response)
    assert result.status_code == 304
    assert result.headers["etag"] == first_response.headers["etag"]
    assert result.body == b""


def test_atlas_view_uses_stored_dependencies_and_keeps_book_visibility(monkeypatch):
    cursor = Cursor()
    monkeypatch.setattr(demo, "_demo_user", lambda request: {"user_id": 5})
    monkeypatch.setattr(demo, "transaction", lambda: transaction_for(cursor))
    called = []
    def authored(cur, **kwargs):
        called.append(kwargs)
        return {**graph_result(), "authored_dependencies": True, "edges": [{
            "source_knowledge_id": 10, "target_knowledge_id": 11, "relation_type": "dependency",
        }]}
    monkeypatch.setattr(demo, "fetch_atlas_graph", authored)
    response = Response()
    result = demo.get_grimoire_graph(7, Request(), response, focus="11", view="atlas")
    assert result["authored_dependencies"] is True
    assert called == [{"grimoire_id": 7, "focus": "11", "limit": 150}]
    assert "source_metadata->>'demo'" in cursor.queries[0][0]
    cursor.book_exists = False
    with pytest.raises(HTTPException) as error:
        demo.get_grimoire_graph(7, Request(), Response(), focus="11", view="atlas")
    assert error.value.status_code == 404
    assert len(called) == 1


@pytest.mark.parametrize(
    "arguments, detail",
    [
        ({"ancestor_depth": 3}, "ancestor_depth"),
        ({"descendant_depth": 3}, "descendant_depth"),
        ({"limit": 151}, "limit"),
        ({"include": "storage"}, "learning role"),
    ],
)
def test_graph_rejects_unbounded_or_technical_queries(monkeypatch, arguments, detail):
    with pytest.raises(HTTPException) as caught:
        call_graph(monkeypatch, **arguments)
    assert caught.value.status_code == 422
    assert detail in str(caught.value.detail)


def test_graph_requires_demo_auth_before_opening_database(monkeypatch):
    opened = False

    def transaction():
        nonlocal opened
        opened = True
        return transaction_for(Cursor())

    monkeypatch.setattr(demo, "_demo_user", lambda request: (_ for _ in ()).throw(HTTPException(403)))
    monkeypatch.setattr(demo, "transaction", transaction)
    with pytest.raises(HTTPException) as caught:
        demo.get_grimoire_graph(
            7, Request(), Response(), focus="11",
            ancestor_depth=2, descendant_depth=2,
            include="support,assessment", limit=150,
        )
    assert caught.value.status_code == 403
    assert opened is False


def test_openapi_preserves_frozen_route_and_limits(monkeypatch):
    application = FastAPI()
    application.include_router(demo.router)
    schema = application.openapi()
    operation = schema["paths"]["/api/demo/grimoires/{grimoire_id}/graph"]["get"]
    parameters = {item["name"]: item for item in operation["parameters"]}
    assert parameters["ancestor_depth"]["schema"]["maximum"] == 2
    assert parameters["descendant_depth"]["schema"]["maximum"] == 2
    assert parameters["limit"]["schema"]["maximum"] == 150
    assert parameters["limit"]["schema"]["default"] == 150


def test_large_graph_response_is_compressed_without_changing_contract(monkeypatch):
    application = FastAPI()
    application.add_middleware(GZipMiddleware, minimum_size=1_000)
    application.include_router(demo.router)
    client = TestClient(application)
    monkeypatch.setattr(demo, "_demo_user", lambda request: {"user_id": 5})
    monkeypatch.setattr(demo, "transaction", lambda: transaction_for(Cursor()))
    monkeypatch.setattr(demo, "fetch_focused_graph", lambda *args, **kwargs: {
        **graph_result(),
        "nodes": [graph_result()["nodes"][0] | {"knowledge_id": item, "label": "Definition " + ("x" * 80)} for item in range(150)],
    })
    response = client.get(
        "/api/demo/grimoires/7/graph?focus=11",
        headers={"Accept-Encoding": "gzip"},
    )
    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert set(response.json()) >= {"nodes", "edges", "graph_revision", "focus_knowledge_id"}

    main_source = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(encoding="utf-8")
    assert "add_middleware(GZipMiddleware, minimum_size=1_000)" in main_source
