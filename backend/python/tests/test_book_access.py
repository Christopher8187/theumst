"""Book reads under /api/v1 need the Web Demo's access (0.0.13).

Requests go through the application with a scripted stand-in for PostgreSQL
that answers each query by its text. These establish which routes ask for Web
Demo access, the order of the checks and the answers; test_key_access_postgres.py
checks the same queries against PostgreSQL.
"""
from __future__ import annotations

import asyncio
import inspect
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import dependencies
from app.config import get_settings
from app.main import create_app
from app.routers import public_api
from app.services import storage


IMAGE = "/api/v1/storage/books/5/images/page-0001.png"
READS = {
    ("GET", "/api/v1/knowledge"),
    ("GET", "/api/v1/knowledge/{knowledge_id}"),
    ("GET", "/api/v1/storage/{path:path}"),
}
MASTER_WRITES = {
    ("POST", "/api/v1/books/ingest-archive"),
    ("POST", "/api/v1/knowledge"),
    ("POST", "/api/v1/knowledge/{knowledge_id}/embeddings"),
    ("POST", "/api/v1/storage/folders"),
    ("POST", "/api/v1/storage/text"),
    ("POST", "/api/v1/storage/files"),
}
READ_PATHS = ["/api/v1/knowledge", "/api/v1/knowledge/31", IMAGE]


def key_row(authority="user", access_points=("api-keys", "profile"), key_type="regular"):
    return {
        "api_key_id": 5, "user_id": 2, "name": "Default", "key_prefix": "umst_read_abcdef",
        "key_type": key_type, "client": None, "api_rate_id": None if key_type == "master" else 1,
        "requests_per_minute": None if key_type == "master" else 600,
        "level_name": None if key_type == "master" else "standard",
        "username": "reader", "authority_type": authority, "access_points": list(access_points),
    }


def demo_key_row():
    return key_row("betatester", ("api-keys", "demo", "profile"))


def session_user(access_points):
    return {
        "user_id": 2, "username": "reader", "email": "reader@example.invalid", "alias": None,
        "description": None, "authority_type": "user", "access_points": list(access_points),
    }


class Database:
    """Answers each query by its text, and keeps every statement."""

    def __init__(self, *, key=None, user=None, image=True):
        self.key, self.user, self.image = key, user, image
        self.statements: list[tuple[str, object]] = []

    @contextmanager
    def transaction(self):
        yield None, self

    def execute(self, sql, params=None):
        self.statements.append((" ".join(sql.split()), params))

    def fetchone(self):
        sql = self.statements[-1][0]
        if "FROM api_key k" in sql:
            return dict(self.key) if self.key else None
        if sql.startswith("INSERT INTO api_rate_window"):
            return {"request_count": 1, "retry_after": 60}
        if "FROM web_session s" in sql:
            return dict(self.user) if self.user else None
        if "FROM book_image bi" in sql:
            return {"?column?": 1} if self.image else None
        raise AssertionError(f"unexpected query: {sql}")

    def ran(self, fragment):
        return [params for sql, params in self.statements if fragment in sql]


@pytest.fixture
def books(monkeypatch):
    state = SimpleNamespace(db=Database(), listed=[], fetched=[], read=[])
    monkeypatch.setattr(dependencies, "transaction", lambda: state.db.transaction())
    monkeypatch.setattr(public_api, "transaction", lambda: state.db.transaction())

    def list_knowledge(**options):
        state.listed.append(options)
        return [{"knowledge_id": 31}]

    def get_knowledge(knowledge_id, language_id, *, include_hidden=False):
        state.fetched.append((knowledge_id, include_hidden))
        return {"knowledge_id": knowledge_id}

    def read_bytes(key):
        state.read.append(key)
        return b"\x89PNG page"

    monkeypatch.setattr(public_api, "list_knowledge", list_knowledge)
    monkeypatch.setattr(public_api, "get_knowledge", get_knowledge)
    monkeypatch.setattr(storage, "read_bytes", read_bytes)
    state.client = TestClient(create_app(initialize_services=False))
    state.cookie = {"Cookie": f"{get_settings().cookie_name}=session-token"}
    return state


def assert_demo_access_required(response):
    assert response.status_code == 403, response.text
    body = response.json()
    assert body == {"code": "demo_access_required", "detail": body["detail"]}
    assert "Web Demo access" in body["detail"]
    assert response.headers["cache-control"] == "no-store"


# --- keys ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", READ_PATHS)
def test_a_key_whose_account_the_web_demo_does_not_admit_reads_no_book(books, path):
    books.db.key = key_row()
    assert_demo_access_required(books.client.get(path, headers={"X-API-Key": "umst_read_x"}))
    # Refused before counting and before anything is read.
    assert not books.db.ran("api_rate_window") and not books.db.ran("api_usage_daily")
    assert not books.db.ran("FROM book_image")
    assert books.listed == [] and books.fetched == [] and books.read == []


@pytest.mark.parametrize("path", READ_PATHS)
def test_a_key_whose_account_the_web_demo_admits_reads_books_counted_as_book_reads(books, path):
    books.db.key = demo_key_row()
    response = books.client.get(path, headers={"Authorization": "Bearer umst_read_x"})
    assert response.status_code == 200, response.text
    assert books.db.ran("INSERT INTO api_usage_daily") == [(5, "book")]


def test_reads_through_a_key_keep_their_answers(books):
    books.db.key = demo_key_row()
    headers = {"X-API-Key": "umst_read_x"}
    listed = books.client.get("/api/v1/knowledge?grimoire_id=5", headers=headers).json()
    assert listed["items"] == [{"knowledge_id": 31}] and listed["key_type"] == "regular"
    assert books.listed[0]["include_hidden"] is False and books.listed[0]["grimoire_id"] == 5
    assert books.client.get("/api/v1/knowledge/31", headers=headers).json()["item"] == {"knowledge_id": 31}
    image = books.client.get(IMAGE, headers=headers)
    assert image.content == b"\x89PNG page" and image.headers["content-type"] == "image/png"
    assert image.headers["cache-control"] == "private, no-store"
    assert image.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in image.headers["content-security-policy"]
    assert books.read == ["books/5/images/page-0001.png"]


@pytest.mark.parametrize("path", READ_PATHS)
def test_master_keys_keep_their_book_access(books, path):
    books.db.key = key_row("admin", (), key_type="master")
    response = books.client.get(path, headers={"X-API-Key": "umst_mstr_x"})
    assert response.status_code == 200, response.text
    assert books.db.ran("INSERT INTO api_usage_daily") == [(5, "book")]
    assert not books.db.ran("api_rate_window")
    if books.listed:
        assert books.listed[0]["include_hidden"] is True


def test_a_revoked_or_unknown_key_is_still_401(books):
    books.db.key = None
    response = books.client.get("/api/v1/knowledge", headers={"X-API-Key": "umst_read_x"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or revoked API key"}


# --- book images and the Web Demo's session --------------------------------------------

def test_the_web_demo_loads_book_images_with_its_session_and_no_key(books):
    books.db.user = session_user(["api-keys", "demo", "profile"])
    response = books.client.get(IMAGE, headers=books.cookie)
    assert response.status_code == 200, response.text
    assert response.content == b"\x89PNG page"
    # A session is not a key: nothing is counted.
    assert not books.db.ran("FROM api_key k") and not books.db.ran("api_usage_daily")


def test_a_signed_in_reader_the_web_demo_does_not_admit_gets_no_book_image(books):
    books.db.user = session_user(["api-keys", "profile"])
    assert_demo_access_required(books.client.get(IMAGE, headers=books.cookie))
    assert not books.db.ran("FROM book_image") and books.read == []


def test_a_book_image_without_a_key_or_session_is_401(books):
    response = books.client.get(IMAGE)
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
    assert not books.db.ran("FROM book_image") and books.read == []


def test_a_key_sent_with_a_session_decides_the_image_read(books):
    books.db.key = key_row()
    books.db.user = session_user(["api-keys", "demo", "profile"])
    assert_demo_access_required(books.client.get(IMAGE, headers={**books.cookie, "X-API-Key": "umst_read_x"}))
    assert not books.db.ran("FROM web_session")


def test_an_image_of_a_hidden_book_or_an_unknown_one_is_still_404(books):
    books.db.key = demo_key_row()
    books.db.image = False
    response = books.client.get(IMAGE, headers={"X-API-Key": "umst_read_x"})
    assert response.status_code == 404
    assert books.read == []


# --- every route under /api/v1 ---------------------------------------------------------------

def api_v1_routes():
    application = create_app(initialize_services=False)
    return {
        (method, route.path): route.endpoint
        for route in application.routes
        if getattr(route, "path", "").startswith("/api/v1")
        for method in getattr(route, "methods", ())
    }


def test_every_route_under_api_v1_is_a_gated_read_or_a_master_write():
    # A new /api/v1 route fails here until it is added to one of the two sets.
    assert set(api_v1_routes()) == READS | MASTER_WRITES


def call(endpoint, request):
    """Call an endpoint function directly, as the refusal comes before any argument is used."""
    arguments = {
        name: (request if name == "request" else None)
        for name in inspect.signature(endpoint).parameters
    }
    result = endpoint(**arguments)
    return asyncio.run(result) if inspect.iscoroutine(result) else result


@pytest.mark.parametrize("route", sorted(READS))
def test_each_read_asks_for_web_demo_access(books, route):
    books.db.key = key_row()
    with pytest.raises(dependencies.AccessRefused) as refused:
        call(api_v1_routes()[route], SimpleNamespace(headers={"x-api-key": "umst_read_x"}))
    assert refused.value.code == "demo_access_required"


@pytest.mark.parametrize("route", sorted(MASTER_WRITES))
@pytest.mark.parametrize("key", [key_row(), demo_key_row()], ids=["ordinary", "web-demo"])
def test_each_write_takes_only_master_keys_whatever_the_account(books, route, key):
    books.db.key = key
    with pytest.raises(HTTPException) as refused:
        call(api_v1_routes()[route], SimpleNamespace(headers={"x-api-key": "umst_read_x"}))
    assert refused.value.status_code == 403
    assert refused.value.detail == "A master API key is required"
    assert not books.db.ran("api_usage_daily")
