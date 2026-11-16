"""The game's book, figures (0.0.18) and notes routes (0.0.16) against an in-memory stand-in for PostgreSQL.

The stand-in answers each query by its text, so these establish the order of the checks,
the refusals and their shapes, the headers, and which rows each call reads or changes.
test_book_read_postgres.py checks the same routes against PostgreSQL: the answer against the
Web Demo's per-object route, counting, and notes shared with the Web Demo.
"""
from __future__ import annotations

import base64
import gzip
import json
import random
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.dependencies import AccessRefused
from app.routers import game
from app.services import book_read


USER_ID = 7
OTHER_USER_ID = 8
KEY = {"X-API-Key": "umst_read_test-key", "X-Install-Id": "k7m2qx"}
TWO_WEEKS = "private, max-age=1209600"
CLOCK = datetime(2026, 11, 13, 19, 45, 0, 1, tzinfo=timezone.utc)


def built_book(grimoire_id=18, objects=60):
    """A game answer over GZipMiddleware's 1,000-byte minimum, so a second gzip layer would show."""
    return book_read.encode({
        "format": 1, "grimoire_id": grimoire_id, "graph_capability": "semantic_relations",
        "counts": {"sections": 0, "objects": objects, "shared_crystals": 0, "relations": {}, "figures": 0, "pages": 0},
        "sections": [], "relations": {}, "crystals": [], "pages": {},
        "objects": [{"id": n, "statement": f"Statement {n} " + "x" * 40, "figures": [], "pages": []}
                    for n in range(objects)],
    })


class Store:
    """What the routes read and write: books, their active objects, game answers and notes."""

    def __init__(self):
        self.books = {
            18: {"visible": True, "title": "Topological Spaces, Part IB lecture notes (Randal-Williams, 2026)",
                 "author": None, "row": built_book(18)},
            8: {"visible": True, "title": "Elementary Differential Equations (Boyce, DiPrima and Meade, 2017)",
                "author": "W. E. Boyce", "row": None},
            40: {"visible": False, "title": "Hidden (Somebody, 2020)", "author": None, "row": built_book(40)},
        }
        self.objects = {1801: 18, 1802: 18, 802: 8}  # active objects and their books
        # Book images by storage key: the book whose active object links it as a figure (None for a
        # page scan), whether it is active, and its time, with "home" the book it is stored under when
        # that is another; the stored bytes are in `stored`.
        self.images = {
            "books/18/images/a.png": {"book": 18, "active": True, "updated_at": CLOCK},
            "books/18/images/b c.png": {"book": 18, "active": True, "updated_at": CLOCK + timedelta(seconds=1)},
            "books/18/images/c.svg": {"book": 18, "active": True, "updated_at": CLOCK + timedelta(seconds=2)},
            "books/18/images/old.png": {"book": 18, "active": False, "updated_at": CLOCK},
            "books/18/images/page-3.jpg": {"book": None, "active": True, "updated_at": CLOCK},
            "books/18/images/lost.png": {"book": 18, "active": True, "updated_at": CLOCK},
            "books/8/images/boyce.png": {"book": 8, "active": True, "updated_at": CLOCK},
            "books/40/images/kept.png": {"book": 18, "active": True, "updated_at": CLOCK, "home": 40},
        }
        self.stored = {key: f"<{key}>".encode() for key in self.images if not key.endswith("lost.png")}
        self.stored["books/18/images/c.svg"] = b"<svg xmlns='http://www.w3.org/2000/svg'/>"
        self.reads: list[str] = []
        self.notes: dict[int, dict] = {}
        self.next_id = 1
        self.clock = CLOCK
        self.deleted_after_check = False
        self.statements: list[tuple[str, object]] = []

    def tick(self):
        self.clock += timedelta(microseconds=1500)
        return self.clock

    def note(self, user_id, grimoire_id, knowledge_id=None, *, tag="", content="text"):
        when = self.tick()
        row = {"demo_note_id": self.next_id, "user_id": user_id, "grimoire_id": grimoire_id,
               "knowledge_id": knowledge_id, "note_type": "attached" if knowledge_id else "scribble",
               "tag": tag, "content": content, "created_at": when, "updated_at": when}
        self.notes[self.next_id] = row
        self.next_id += 1
        return row

    @contextmanager
    def transaction(self):
        yield None, Cursor(self)


def public(row):
    return {key: value for key, value in row.items() if key != "user_id"}


class Cursor:
    def __init__(self, store):
        self.store = store
        self.result = None

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        store = self.store
        store.statements.append((text, params))
        if "FROM grimoire g JOIN language_grimoire lg" in text:
            self.result = [
                {"grimoire_id": grimoire_id, "title": book["title"], "author": book["author"],
                 "version": book["row"].version if book["row"] else None,
                 "object_count": book["row"].counts["objects"] if book["row"] else None,
                 "bytes": len(book["row"].body_gzip) if book["row"] else None}
                for grimoire_id, book in sorted(store.books.items()) if book["visible"]
            ]
        elif "LEFT JOIN book_game_read r USING (grimoire_id)" in text:
            book = store.books.get(params[0])
            self.result = None if book is None else {
                "visible": book["visible"], "format": book.get("format", 1) if book["row"] else None,
                "version": book["row"].version if book["row"] else None,
            }
        elif text.startswith("SELECT version, body_gzip FROM book_game_read"):
            row = store.books[params[0]]["row"]
            self.result = None if store.deleted_after_check or row is None else {
                "version": row.version, "body_gzip": memoryview(row.body_gzip)}
        elif "GROUP BY bi.storage_key" in text:
            # book_read.figure_keys: the asked keys that are active figures of the book's active objects
            # stored under a book the Web Demo shows, as /api/v1/storage requires
            grimoire_id, again, keys = params
            assert grimoire_id == again and "link_type = 'figure'" in text and "bi.is_active" in text
            assert "JOIN grimoire g ON g.grimoire_id = bi.grimoire_id" in text and "g.source_metadata->>'demo' = 'true'" in text
            self.result = [
                {"storage_key": key, "updated_at": image["updated_at"]}
                for key, image in store.images.items()
                if key in keys and image["active"] and image["book"] == grimoire_id
                and store.books[image.get("home", image["book"])]["visible"]
            ]
        elif text.startswith("SELECT 1 FROM grimoire WHERE grimoire_id = %s"):
            book = store.books.get(params[0])
            self.result = {"?column?": 1} if book and book["visible"] else None
        elif text.startswith("SELECT 1 FROM knowledge k"):
            self.result = {"?column?": 1} if store.objects.get(params[0]) == params[1] else None
        elif "FROM demo_note WHERE user_id = %s AND grimoire_id = %s ORDER BY" in text:
            user_id, grimoire_id = params
            rows = [row for row in store.notes.values() if row["user_id"] == user_id and row["grimoire_id"] == grimoire_id]
            self.result = sorted(rows, key=lambda row: (row["updated_at"], row["demo_note_id"]), reverse=True)
        elif text.startswith("INSERT INTO demo_note"):
            user_id, grimoire_id, knowledge_id, note_type, tag, content = params
            row = store.note(user_id, grimoire_id, knowledge_id, tag=tag, content=content)
            assert row["note_type"] == note_type
            self.result = dict(row)
        elif "FROM demo_note WHERE demo_note_id = %s AND user_id = %s AND grimoire_id = %s FOR UPDATE" in text:
            note_id, user_id, grimoire_id = params
            row = store.notes.get(note_id)
            ok = row and row["user_id"] == user_id and row["grimoire_id"] == grimoire_id
            self.result = dict(row) if ok else None
        elif text.startswith("UPDATE demo_note SET tag = %s, content = %s WHERE demo_note_id = %s AND user_id = %s"):
            tag, content, note_id, user_id = params
            row = store.notes[note_id]
            assert row["user_id"] == user_id
            row.update(tag=tag, content=content, updated_at=store.tick())
            self.result = dict(row)
        elif text.startswith("DELETE FROM demo_note WHERE demo_note_id = %s AND user_id = %s"):
            note_id, user_id = params
            assert store.notes[note_id]["user_id"] == user_id
            del store.notes[note_id]
        else:
            raise AssertionError(f"unexpected query: {text}")

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result


def reader_key(**overrides):
    key = {"api_key_id": 41, "user_id": USER_ID, "username": "reader", "key_type": "regular",
           "access_points": ["api-keys", "demo", "profile"], "requests_per_minute": 600}
    key.update(overrides)
    return key


@pytest.fixture
def api(monkeypatch):
    store = Store()
    state = SimpleNamespace(store=store, calls=[], costs=[], returned=[], left=None, key=reader_key(), refusal=None)

    def fake_authenticate(request, *, kind, master_required=False, master_allowed=True, access_point=None, cost=1):
        # The order of authenticate_api_key's own checks: the key, a master key, the access point, the minute.
        state.calls.append({"kind": kind, "master_allowed": master_allowed, "access_point": access_point})
        state.costs.append(cost)
        if state.refusal is not None:
            raise state.refusal
        if access_point is not None and access_point not in state.key["access_points"]:
            raise AccessRefused(access_point)
        if state.left is not None:
            # The minute's window: refused, and nothing counted, when the request would pass it.
            if cost > state.left:
                raise HTTPException(status_code=429, detail="Rate limit exceeded: 600 book requests per minute",
                                    headers={"Retry-After": "17"})
            state.left -= cost
        return dict(state.key)

    def fake_return(key, count):
        state.returned.append(count)
        if state.left is not None:
            state.left += count

    def fake_read_optional(key):
        store.reads.append(key)
        return store.stored.get(key)

    monkeypatch.setattr(game, "transaction", store.transaction)
    monkeypatch.setattr(game, "authenticate_api_key", fake_authenticate)
    monkeypatch.setattr(game, "return_api_requests", fake_return)
    monkeypatch.setattr(game.storage, "read_optional", fake_read_optional)
    application = FastAPI()
    application.include_router(game.router)
    game.install_error_handlers(application)
    state.client = TestClient(application)
    return state


def assert_refused(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["code"] == code and isinstance(body["detail"], str) and body["detail"]
    assert response.headers["cache-control"] == "no-store"
    assert "etag" not in response.headers
    return body


def writes(store):
    return [sql for sql, _ in store.statements if sql.startswith(("INSERT", "UPDATE", "DELETE"))]


# --- the list ----------------------------------------------------------------------------------

def test_the_list_gives_each_shown_book_and_whether_the_account_may_read(api):
    response = api.client.get("/api/game/grimoires", headers=KEY)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    row = api.store.books[18]["row"]
    assert response.json() == {
        "may_read": True,
        "grimoires": [
            {"grimoire_id": 8, "title": api.store.books[8]["title"], "author": "W. E. Boyce",
             "version": None, "objects": None, "bytes": None, "may_read": True},
            {"grimoire_id": 18, "title": api.store.books[18]["title"], "author": "Randal-Williams",
             "version": row.version, "objects": 60, "bytes": len(row.body_gzip), "may_read": True},
        ],
    }
    # It needs no Web Demo access, and counts as a book read.
    assert api.calls == [{"kind": "book", "master_allowed": False, "access_point": None}]


def test_an_account_without_web_demo_access_learns_it_may_not_read(api):
    api.key = reader_key(access_points=["api-keys", "profile"])
    body = api.client.get("/api/game/grimoires", headers=KEY).json()
    assert body["may_read"] is False
    assert [row["may_read"] for row in body["grimoires"]] == [False, False]


@pytest.mark.parametrize(("stored", "title", "author"), [
    ("Randal-Williams", "Anything", "Randal-Williams"),
    ("  Boyce  ", "Anything (Other, 2020)", "Boyce"),
    ("", "Topological Spaces (Randal-Williams, 2026)", "Randal-Williams"),
    (None, "Topological Spaces (Randal-Williams, 2026)", "Randal-Williams"),
    (42, "Groups (Artin)", "Artin"),
    (None, "Analysis (Tao, Vol. 1, 2016)", "Tao, Vol. 1"),
    (None, "Notes (ignored) and more", None),
    (None, "Plain title", None),
    (None, None, None),
    (None, "Empty (, 2020)", None),
])
def test_the_author_is_stored_or_read_from_the_titles_credit(stored, title, author):
    assert game._author(stored, title) == author


# --- the book ----------------------------------------------------------------------------------

KEY_REFUSALS = [
    (HTTPException(401, "Invalid or revoked API key"), 401, "invalid_key"),
    (HTTPException(401, "API key required"), 401, "invalid_key"),
    (HTTPException(403, "Master keys are not accepted here"), 403, "master_key_not_allowed"),
    (AccessRefused("demo"), 403, "demo_access_required"),
    (HTTPException(429, "Rate limit exceeded: 600 book requests per minute", headers={"Retry-After": "17"}),
     429, "rate_limited"),
]


@pytest.mark.parametrize(("refusal", "status", "code", "path"), [
    (*refusal, path)
    for path in ("/api/game/grimoires", "/api/game/grimoires/18/book", "/api/game/grimoires/18/notes")
    for refusal in KEY_REFUSALS
    # The list asks for no access point, so it is never refused for one.
    if not (path == "/api/game/grimoires" and refusal[2] == "demo_access_required")
])
def test_the_keys_refusals(api, refusal, status, code, path):
    api.refusal = refusal
    body = assert_refused(api.client.get(path, headers=KEY), status, code)
    if code == "rate_limited":
        assert body["retry_after"] == 17
    assert api.store.statements == []


def test_a_book_and_its_notes_need_web_demo_access(api):
    api.key = reader_key(access_points=["api-keys", "profile"])
    for method, path, body in [
        ("GET", "/api/game/grimoires/18/book", None),
        ("GET", "/api/game/grimoires/18/notes", None),
        ("POST", "/api/game/grimoires/18/notes", {"note_type": "scribble", "content": "x"}),
        ("PUT", "/api/game/grimoires/18/notes/1", {"tag": "", "content": "x", "if_updated_at": CLOCK.isoformat()}),
        ("DELETE", "/api/game/grimoires/18/notes/1", {"if_updated_at": CLOCK.isoformat()}),
    ]:
        response = api.client.request(method, path, json=body, headers=KEY)
        refused = assert_refused(response, 403, "demo_access_required")
        assert refused["detail"] == "Reading books needs Web Demo access; request it from the dashboard"
    assert api.store.statements == []
    assert {call["access_point"] for call in api.calls} == {"demo"}
    assert {call["kind"] for call in api.calls} == {"book"}
    assert {call["master_allowed"] for call in api.calls} == {False}


@pytest.mark.parametrize("path", [
    "/api/game/grimoires/eighteen/book", "/api/game/grimoires/18.5/notes",
])
def test_an_id_that_is_not_an_integer_is_422_before_the_key(api, path):
    assert_refused(api.client.get(path, headers=KEY), 422, "invalid_request")
    assert api.calls == []


@pytest.mark.parametrize("path", ["/api/game/grimoires", "/api/game/grimoires/18/book", "/api/game/grimoires/18/notes"])
def test_a_malformed_install_id_is_422_before_the_key(api, path):
    assert_refused(api.client.get(path, headers={**KEY, "X-Install-Id": "not valid"}), 422, "invalid_request")
    assert api.calls == []


@pytest.mark.parametrize("grimoire_id", [40, 404])
def test_a_hidden_or_unknown_book_is_404_book_not_found(api, grimoire_id):
    assert_refused(api.client.get(f"/api/game/grimoires/{grimoire_id}/book", headers=KEY), 404, "book_not_found")


def test_a_book_without_its_game_answer_is_409(api):
    assert_refused(api.client.get("/api/game/grimoires/8/book", headers=KEY), 409, "book_read_not_computed")
    api.store.books[18]["format"] = 2
    assert_refused(api.client.get("/api/game/grimoires/18/book", headers=KEY), 409, "book_read_not_computed")


def test_a_row_removed_between_the_two_reads_is_409(api):
    api.store.deleted_after_check = True
    assert_refused(api.client.get("/api/game/grimoires/18/book", headers=KEY), 409, "book_read_not_computed")


def assert_book_headers(response, version):
    assert response.headers["etag"] == f'"{version}"'
    assert response.headers["cache-control"] == TWO_WEEKS  # the router's no-store never reaches it
    vary = [token.strip() for token in response.headers["vary"].split(",")]
    assert set(vary) == {"X-API-Key", "Authorization", "Accept-Encoding"}


def test_the_book_comes_as_the_stored_gzip_in_one_layer(api):
    row = api.store.books[18]["row"]
    with api.client.stream("GET", "/api/game/grimoires/18/book",
                           headers={**KEY, "Accept-Encoding": "gzip"}) as response:
        raw = b"".join(response.iter_raw())
    assert response.status_code == 200
    assert raw == row.body_gzip
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["content-type"] == "application/json"
    assert_book_headers(response, row.version)
    assert json.loads(gzip.decompress(raw)) == row.answer
    assert writes(api.store) == []


def test_a_client_refusing_gzip_gets_the_json(api):
    row = api.store.books[18]["row"]
    response = api.client.get("/api/game/grimoires/18/book", headers={**KEY, "Accept-Encoding": "identity"})
    assert response.status_code == 200 and response.content == row.body
    assert "content-encoding" not in response.headers
    assert_book_headers(response, row.version)


def with_the_applications_gzip():
    """The routes behind the application's own gzip middleware, as create_app installs it."""
    from app.compression import GZipMiddleware

    application = FastAPI()
    application.add_middleware(GZipMiddleware, minimum_size=1_000)
    application.include_router(game.router)
    game.install_error_handlers(application)

    @application.get("/large")
    def large():
        return {"text": "x" * 5_000}

    return TestClient(application)


def raw_get(client, path, accept):
    with client.stream("GET", path, headers={**KEY, "Accept-Encoding": accept}) as response:
        return response, b"".join(response.iter_raw())


@pytest.mark.parametrize("accept", ["gzip;q=0", "gzip; q=0.0, identity", "identity", "br", "x-gzip;q=0, *;q=0"])
def test_a_client_refusing_gzip_gets_the_json_from_the_application_uncompressed(api, accept):
    # Before 0.0.17 Starlette's middleware gzipped this JSON again for "gzip;q=0" (0.0.16's Known).
    client, row = with_the_applications_gzip(), api.store.books[18]["row"]
    response, raw = raw_get(client, "/api/game/grimoires/18/book", accept)
    assert response.status_code == 200 and raw == row.body
    assert "content-encoding" not in response.headers
    response, raw = raw_get(client, "/large", accept)
    assert raw == b'{"text":"' + b"x" * 5_000 + b'"}' and "content-encoding" not in response.headers


@pytest.mark.parametrize("accept", ["gzip", "gzip, deflate, br", "br;q=1, gzip;q=0.5", "*"])
def test_a_client_accepting_gzip_gets_one_layer_from_the_application(api, accept):
    client, row = with_the_applications_gzip(), api.store.books[18]["row"]
    response, raw = raw_get(client, "/api/game/grimoires/18/book", accept)
    assert raw == row.body_gzip and response.headers["content-encoding"] == "gzip"
    response, raw = raw_get(client, "/large", accept)
    assert response.headers["content-encoding"] == "gzip"
    assert json.loads(gzip.decompress(raw)) == {"text": "x" * 5_000}


def test_the_application_uses_the_gzip_middleware_that_reads_accept_encoding_as_the_book_routes_do():
    from app.compression import GZipMiddleware
    from app.main import create_app

    application = create_app(initialize_services=False)
    gzips = [entry for entry in application.user_middleware if "GZip" in entry.cls.__name__]
    assert [entry.cls for entry in gzips] == [GZipMiddleware]


@pytest.mark.parametrize("value", ['"{v}"', 'W/"{v}"', '"other", "{v}"', "*"])
def test_the_kept_version_answers_304_without_reading_the_body(api, value):
    row = api.store.books[18]["row"]
    response = api.client.get("/api/game/grimoires/18/book",
                              headers={**KEY, "If-None-Match": value.format(v=row.version)})
    assert response.status_code == 304 and response.content == b""
    assert_book_headers(response, row.version)
    assert not [sql for sql, _ in api.store.statements if "body_gzip" in sql]


@pytest.mark.parametrize("value", ['"other"', "{v}", '"{v}x"'])
def test_another_version_gets_the_whole_book(api, value):
    row = api.store.books[18]["row"]
    response = api.client.get("/api/game/grimoires/18/book",
                              headers={**KEY, "If-None-Match": value.format(v=row.version)})
    assert response.status_code == 200 and response.json() == row.answer


# --- notes -------------------------------------------------------------------------------------

def note_json(row):
    return {
        **public(row),
        "created_at": row["created_at"].strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "updated_at": row["updated_at"].strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }


def test_the_list_holds_only_this_accounts_notes_in_this_book_newest_first(api):
    store = api.store
    first = store.note(USER_ID, 18, 1801, tag="a")
    scribble = store.note(USER_ID, 18, None, content="loose")
    store.note(OTHER_USER_ID, 18, 1801, content="someone else's")
    store.note(USER_ID, 8, 802, content="another book")
    response = api.client.get("/api/game/grimoires/18/notes", headers=KEY)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store" and "etag" not in response.headers
    assert response.json() == {"notes": [note_json(scribble), note_json(first)]}
    assert response.json()["notes"][1]["updated_at"] == "2026-11-13T19:45:00.001501Z"  # microseconds
    assert set(response.json()["notes"][0]) == {
        "demo_note_id", "grimoire_id", "knowledge_id", "note_type", "tag", "content", "created_at", "updated_at",
    }


@pytest.mark.parametrize("grimoire_id", [40, 404])
def test_notes_of_a_hidden_or_unknown_book_are_404(api, grimoire_id):
    assert_refused(api.client.get(f"/api/game/grimoires/{grimoire_id}/notes", headers=KEY), 404, "book_not_found")
    response = api.client.post(f"/api/game/grimoires/{grimoire_id}/notes", headers=KEY,
                               json={"note_type": "scribble", "content": "x"})
    assert_refused(response, 404, "book_not_found")
    assert writes(api.store) == []


def test_a_note_is_made_on_an_object_of_this_book_with_its_tag_stripped(api):
    response = api.client.post("/api/game/grimoires/18/notes", headers=KEY, json={
        "knowledge_id": 1801, "note_type": "attached", "tag": "  open sets  ", "content": "Let $U$ be open.\nThen",
    })
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    note = response.json()["note"]
    stored = api.store.notes[note["demo_note_id"]]
    assert stored["user_id"] == USER_ID and stored["grimoire_id"] == 18
    assert note == note_json(stored)
    assert note["tag"] == "open sets" and note["content"] == "Let $U$ be open.\nThen"
    scribble = api.client.post("/api/game/grimoires/18/notes", headers=KEY, json={"note_type": "scribble"})
    assert scribble.status_code == 201
    assert scribble.json()["note"]["knowledge_id"] is None and scribble.json()["note"]["content"] == ""


@pytest.mark.parametrize("knowledge_id", [802, 999])
def test_an_object_of_another_book_or_none_is_404_object_not_found(api, knowledge_id):
    response = api.client.post("/api/game/grimoires/18/notes", headers=KEY,
                               json={"knowledge_id": knowledge_id, "note_type": "attached", "content": "x"})
    assert_refused(response, 404, "object_not_found")
    assert writes(api.store) == []


@pytest.mark.parametrize("body", [
    {"note_type": "attached", "content": "x"},                       # attached needs an object
    {"knowledge_id": 1801, "note_type": "scribble", "content": "x"},  # a scribble has none
    {"knowledge_id": 1801, "note_type": "margin", "content": "x"},
    {"knowledge_id": 0, "note_type": "attached", "content": "x"},
    {"knowledge_id": 1801, "note_type": "attached", "tag": "t" * 121},
    {"knowledge_id": 1801, "note_type": "attached", "content": "c" * 50_001},
    {"knowledge_id": 1801, "note_type": "attached", "content": "nul \u0000 inside"},
    {"knowledge_id": 1801, "note_type": "attached", "tag": "nul \u0000"},
    {"content": "x"},
])
def test_a_note_is_checked_as_the_web_demo_checks_it(api, body):
    assert_refused(api.client.post("/api/game/grimoires/18/notes", headers=KEY, json=body), 422, "invalid_request")
    assert writes(api.store) == [] and api.calls == []


def test_the_web_demos_limits_are_reached_not_passed(api):
    response = api.client.post("/api/game/grimoires/18/notes", headers=KEY, json={
        "knowledge_id": 1801, "note_type": "attached", "tag": "t" * 120, "content": "c" * 50_000,
    })
    assert response.status_code == 201


def test_a_lone_surrogate_is_refused_before_the_database(api):
    raw = b'{"note_type": "scribble", "content": "\\ud800"}'
    response = api.client.post("/api/game/grimoires/18/notes", content=raw,
                               headers={**KEY, "Content-Type": "application/json"})
    assert_refused(response, 422, "invalid_request")
    assert writes(api.store) == []


def stamp(row):
    return row["updated_at"].strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def test_an_update_changes_only_tag_and_content(api):
    row = api.store.note(USER_ID, 18, 1801, tag="old", content="old text")
    before = dict(row)
    response = api.client.put(f"/api/game/grimoires/18/notes/{row['demo_note_id']}", headers=KEY,
                              json={"tag": " new ", "content": "new text", "if_updated_at": stamp(row)})
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    note = response.json()["note"]
    assert (note["tag"], note["content"]) == ("new", "new text")
    assert {key: note[key] for key in ("grimoire_id", "knowledge_id", "note_type", "created_at")} == {
        "grimoire_id": 18, "knowledge_id": 1801, "note_type": "attached", "created_at": note_json(before)["created_at"]}
    assert note["updated_at"] != note_json(before)["updated_at"]


def test_the_edit_token_may_be_written_with_any_utc_offset(api):
    row = api.store.note(USER_ID, 18, 1801)
    later = row["updated_at"].astimezone(timezone(timedelta(hours=8))).isoformat()
    response = api.client.put(f"/api/game/grimoires/18/notes/{row['demo_note_id']}", headers=KEY,
                              json={"tag": "", "content": "c", "if_updated_at": later})
    assert response.status_code == 200


def test_an_update_from_an_older_read_is_409_with_the_current_note(api):
    row = api.store.note(USER_ID, 18, 1801, content="edited on the website")
    stale = (row["updated_at"] - timedelta(microseconds=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    response = api.client.put(f"/api/game/grimoires/18/notes/{row['demo_note_id']}", headers=KEY,
                              json={"tag": "", "content": "from the game", "if_updated_at": stale})
    body = assert_refused(response, 409, "note_changed")
    assert body["note"] == note_json(row)
    assert api.store.notes[row["demo_note_id"]]["content"] == "edited on the website"
    assert writes(api.store) == []


@pytest.mark.parametrize("owner, grimoire_id", [(OTHER_USER_ID, 18), (USER_ID, 8)])
def test_another_accounts_note_or_one_in_another_book_is_404_note_not_found(api, owner, grimoire_id):
    row = api.store.note(owner, grimoire_id, None)
    path = f"/api/game/grimoires/18/notes/{row['demo_note_id']}"
    assert_refused(api.client.put(path, headers=KEY, json={"tag": "", "content": "mine now",
                                                           "if_updated_at": stamp(row)}), 404, "note_not_found")
    assert_refused(api.client.request("DELETE", path, headers=KEY, json={"if_updated_at": stamp(row)}),
                   404, "note_not_found")
    assert api.store.notes[row["demo_note_id"]]["content"] == "text"
    assert writes(api.store) == []
    assert_refused(api.client.put("/api/game/grimoires/18/notes/999", headers=KEY,
                                  json={"tag": "", "content": "x", "if_updated_at": stamp(row)}),
                   404, "note_not_found")


@pytest.mark.parametrize("body", [
    {"content": "x", "if_updated_at": "2026-11-13T19:45:00.000001Z"},          # no tag
    {"tag": "", "if_updated_at": "2026-11-13T19:45:00.000001Z"},               # no content
    {"tag": "", "content": "x"},                                                # no edit token
    {"tag": "", "content": "x", "if_updated_at": "2026-11-13T19:45:00.000001"},  # no time zone
    {"tag": "", "content": "x", "if_updated_at": "yesterday"},
    {"tag": "t" * 121, "content": "x", "if_updated_at": "2026-11-13T19:45:00.000001Z"},
    {"tag": "", "content": "c" * 50_001, "if_updated_at": "2026-11-13T19:45:00.000001Z"},
])
def test_a_malformed_update_is_422(api, body):
    row = api.store.note(USER_ID, 18, 1801)
    response = api.client.put(f"/api/game/grimoires/18/notes/{row['demo_note_id']}", headers=KEY, json=body)
    assert_refused(response, 422, "invalid_request")
    assert api.calls == []


def test_a_delete_removes_the_note_once_its_token_matches(api):
    row = api.store.note(USER_ID, 18, 1801)
    path = f"/api/game/grimoires/18/notes/{row['demo_note_id']}"
    stale = (row["updated_at"] + timedelta(microseconds=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    body = assert_refused(api.client.request("DELETE", path, headers=KEY, json={"if_updated_at": stale}),
                          409, "note_changed")
    assert body["note"]["demo_note_id"] == row["demo_note_id"] and row["demo_note_id"] in api.store.notes
    response = api.client.request("DELETE", path, headers=KEY, json={"if_updated_at": stamp(row)})
    assert response.status_code == 200
    assert response.json() == {"deleted": True, "demo_note_id": row["demo_note_id"]}
    assert row["demo_note_id"] not in api.store.notes
    assert_refused(api.client.request("DELETE", path, headers=KEY, json={"if_updated_at": stamp(row)}),
                   404, "note_not_found")
    assert_refused(api.client.request("DELETE", path, headers=KEY), 422, "invalid_request")


# --- figures (0.0.18) --------------------------------------------------------------------------

STORAGE = "/api/v1/storage/"
FIGURE_A = STORAGE + "books/18/images/a.png"
FIGURE_B = STORAGE + "books/18/images/b%20c.png"  # as quote() writes the key "b c.png"
FIGURE_C = STORAGE + "books/18/images/c.svg"


def figures_of(api, urls, grimoire_id=18):
    return api.client.post(f"/api/game/grimoires/{grimoire_id}/figures", headers=KEY, json={"urls": urls})


def test_the_books_figures_come_in_one_answer_in_the_order_asked(api):
    response = figures_of(api, [FIGURE_C, FIGURE_A, FIGURE_B])
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"] == "application/json"
    body = response.json()
    assert body["missing"] == [] and body["later"] == []
    assert [figure["url"] for figure in body["figures"]] == [FIGURE_C, FIGURE_A, FIGURE_B]
    stored = api.store.stored
    for figure, key in zip(body["figures"], ["books/18/images/c.svg", "books/18/images/a.png", "books/18/images/b c.png"]):
        assert base64.b64decode(figure["data"]) == stored[key]
        assert figure["bytes"] == len(stored[key])
        assert figure["updated_at"] == book_read._iso(api.store.images[key]["updated_at"])
    assert [figure["content_type"] for figure in body["figures"]] == ["image/svg+xml", "image/png", "image/png"]
    # A book read with Web Demo access counted once for each url, one query for the keys, and nothing written.
    assert api.calls == [{"kind": "book", "master_allowed": False, "access_point": "demo"}]
    assert api.costs == [3] and api.returned == [0]
    assert sorted(api.store.reads) == ["books/18/images/a.png", "books/18/images/b c.png", "books/18/images/c.svg"]
    assert writes(api.store) == []


def test_a_url_asked_twice_comes_once(api):
    body = figures_of(api, [FIGURE_A, FIGURE_A, FIGURE_B, FIGURE_A]).json()
    assert [figure["url"] for figure in body["figures"]] == [FIGURE_A, FIGURE_B]
    assert api.store.reads.count("books/18/images/a.png") == 1
    assert api.costs == [2]


def test_two_urls_naming_one_figure_are_read_once_and_each_answered(api):
    again = FIGURE_A + "?again"
    encoded = STORAGE + "books/18/images/%61.png"  # the same key, percent-encoded
    body = figures_of(api, [FIGURE_A, FIGURE_B, again, encoded]).json()
    assert [figure["url"] for figure in body["figures"]] == [FIGURE_A, FIGURE_B, again, encoded]
    same = [figure for figure in body["figures"] if figure["url"] != FIGURE_B]
    assert {figure["data"] for figure in same} == {base64.b64encode(api.store.stored["books/18/images/a.png"]).decode()}
    assert sorted(api.store.reads) == ["books/18/images/a.png", "books/18/images/b c.png"]
    # Each url still counts, as it would fetched alone.
    assert api.costs == [4]


@pytest.mark.parametrize("url", [
    STORAGE + "books/8/images/boyce.png",       # another book's figure
    STORAGE + "books/18/images/old.png",        # an inactive figure
    STORAGE + "books/18/images/page-3.jpg",     # a page scan, not a figure
    STORAGE + "books/18/images/none.png",       # no such image
    STORAGE + "books/18/images/lost.png",       # a figure whose bytes storage does not hold
    STORAGE + "books/40/images/kept.png",       # linked to this book, stored under a hidden one
    STORAGE + "books/18/../8/images/boyce.png",  # a path out of the key
    "https://example.com/figure.png",           # not a storage url
    "/api/v1/knowledge/1801",
])
def test_a_url_that_is_no_figure_of_this_book_is_missing_and_the_rest_come(api, url):
    body = figures_of(api, [FIGURE_A, url, FIGURE_B]).json()
    assert [figure["url"] for figure in body["figures"]] == [FIGURE_A, FIGURE_B]
    assert body["missing"] == [url] and body["later"] == []
    # Only a figure of the book is ever read from storage.
    assert set(api.store.reads) <= {"books/18/images/a.png", "books/18/images/b c.png", "books/18/images/lost.png"}


def test_a_batch_of_missing_figures_answers_200_with_all_of_them_missing(api):
    urls = [STORAGE + "books/18/images/none.png", STORAGE + "books/8/images/boyce.png"]
    body = figures_of(api, urls).json()
    assert body == {"figures": [], "missing": urls, "later": []}
    assert api.store.reads == []


@pytest.mark.parametrize("body", [
    {"urls": []},
    {"urls": [FIGURE_A] * 65},
    {"urls": [""]},
    {"urls": ["/" + "x" * 1024]},
    {"urls": "books/18/images/a.png"},
    {"urls": [7]},
    {},
    None,
])
def test_an_empty_or_malformed_batch_is_422_before_the_key(api, body):
    response = api.client.post("/api/game/grimoires/18/figures", headers=KEY, json=body)
    assert_refused(response, 422, "invalid_request")
    assert api.calls == [] and api.store.statements == [] and api.store.reads == []


def test_sixty_four_urls_are_the_most_one_batch_asks(api):
    body = figures_of(api, [STORAGE + f"books/18/images/{n}.png" for n in range(64)]).json()
    assert len(body["missing"]) == 64


@pytest.mark.parametrize(("refusal", "status", "code"), KEY_REFUSALS)
def test_the_figures_keys_refusals(api, refusal, status, code):
    api.refusal = refusal
    body = assert_refused(figures_of(api, [FIGURE_A]), status, code)
    if code == "rate_limited":
        assert body["retry_after"] == 17
    assert api.store.statements == [] and api.store.reads == []


def test_figures_need_web_demo_access(api):
    api.key = reader_key(access_points=["api-keys", "profile"])
    refused = assert_refused(figures_of(api, [FIGURE_A]), 403, "demo_access_required")
    assert refused["detail"] == "Reading books needs Web Demo access; request it from the dashboard"
    assert api.store.statements == [] and api.store.reads == []


@pytest.mark.parametrize("grimoire_id", [40, 404])
def test_figures_of_a_hidden_or_unknown_book_are_404_book_not_found(api, grimoire_id):
    assert_refused(figures_of(api, [FIGURE_A], grimoire_id), 404, "book_not_found")
    assert api.store.reads == []


def test_an_answer_holds_its_bound_and_names_the_rest_later(api, monkeypatch):
    for n in range(20):
        key = f"books/18/images/f{n:02}.png"
        api.store.images[key] = {"book": 18, "active": True, "updated_at": CLOCK}
        api.store.stored[key] = bytes([n]) * 100
    urls = [STORAGE + f"books/18/images/f{n:02}.png" for n in range(20)]
    monkeypatch.setattr(game, "FIGURE_BATCH_BYTES", 350)
    api.left = 600
    body = figures_of(api, urls).json()
    assert [figure["url"] for figure in body["figures"]] == urls[:3]
    assert body["later"] == urls[3:] and body["missing"] == []
    assert sum(figure["bytes"] for figure in body["figures"]) <= 350
    # Storage is read at most FIGURE_READERS figures past what the answer holds.
    assert len(api.store.reads) <= 3 + 1 + game.FIGURE_READERS
    # All 20 were counted; those named later that were never read are given back, and each one read counts.
    assert api.costs == [20] and api.returned == [20 - len(set(api.store.reads))]
    assert api.left == 600 - len(set(api.store.reads))
    # Asking again for what came later gets the next ones, until none is left.
    got = [figure["url"] for figure in body["figures"]]
    left = body["later"]
    requests = 1
    while left:
        answer = figures_of(api, left).json()
        assert answer["figures"] and answer["missing"] == []
        got += [figure["url"] for figure in answer["figures"]]
        left = answer["later"]
        requests += 1
    assert got == urls and requests == 7


def test_a_figure_larger_than_the_bound_comes_alone(api, monkeypatch):
    api.store.stored["books/18/images/a.png"] = b"x" * 1000
    monkeypatch.setattr(game, "FIGURE_BATCH_BYTES", 100)
    body = figures_of(api, [FIGURE_A, FIGURE_B]).json()
    assert [figure["url"] for figure in body["figures"]] == [FIGURE_A] and body["later"] == [FIGURE_B]
    body = figures_of(api, [FIGURE_B, FIGURE_A]).json()
    assert [figure["url"] for figure in body["figures"]] == [FIGURE_B] and body["later"] == [FIGURE_A]


def test_missing_figures_take_no_room_in_the_bound(api, monkeypatch):
    monkeypatch.setattr(game, "FIGURE_BATCH_BYTES", len(api.store.stored["books/18/images/a.png"]))
    lost = STORAGE + "books/18/images/lost.png"
    body = figures_of(api, [lost, FIGURE_A, FIGURE_B]).json()
    assert [figure["url"] for figure in body["figures"]] == [FIGURE_A]
    assert body["missing"] == [lost] and body["later"] == [FIGURE_B]


def test_a_storage_failure_other_than_absence_is_not_answered_as_missing(api, monkeypatch):
    def broken(key):
        raise RuntimeError("storage is down")

    monkeypatch.setattr(game.storage, "read_optional", broken)
    with pytest.raises(RuntimeError):
        figures_of(api, [FIGURE_A])


def test_a_key_with_fewer_requests_left_than_urls_asked_gets_429_and_nothing_is_read(api):
    api.left = 2
    body = assert_refused(figures_of(api, [FIGURE_A, FIGURE_B, FIGURE_C]), 429, "rate_limited")
    assert body["retry_after"] == 17
    assert api.store.statements == [] and api.store.reads == [] and api.left == 2
    # Asked twice, a url counts once.
    assert figures_of(api, [FIGURE_A, FIGURE_B, FIGURE_A]).status_code == 200 and api.left == 0


def test_each_url_asked_counts_as_its_single_fetch_would_so_boyce_fits_one_minute(api):
    figures_of(api, [FIGURE_A, STORAGE + "books/18/images/none.png", "https://example.com/figure.png"])
    # A url that is no figure of the book counts too: /api/v1/storage counts its 404.
    assert api.costs == [3] and api.returned == [0]
    # Boyce's 267 figures, five batches, within the standard tier's 600 a minute.
    assert 267 <= reader_key()["requests_per_minute"]


def large_figures(api, count, size):
    """count figures of size random bytes, which compress no further, as a PNG's or JPEG's do not."""
    urls = []
    for n in range(count):
        key = f"books/18/images/large{n:02}.png"
        api.store.images[key] = {"book": 18, "active": True, "updated_at": CLOCK}
        api.store.stored[key] = random.Random(n).randbytes(size)
        urls.append(STORAGE + key)
    return urls


def raw_figures(client, urls, accept):
    with client.stream("POST", "/api/game/grimoires/18/figures", json={"urls": urls},
                       headers={**KEY, "Accept-Encoding": accept}) as response:
        return response, b"".join(response.iter_raw())


@pytest.mark.parametrize("accept", ["gzip", "gzip, deflate, br", "br;q=1, gzip;q=0.5", "*"])
def test_a_full_batch_is_gzipped_by_the_route_and_the_middleware_sends_it_as_it_is(api, monkeypatch, accept):
    # Before, Starlette's middleware gzipped a full answer of 5.6 MB at level 9 on the event loop (about 140 ms).
    from starlette.middleware.gzip import GZipResponder

    urls = large_figures(api, 15, 300_000)
    packed, squeezed = [], []
    route_gzip, middleware_gzip = game._gzip_answer, GZipResponder.apply_compression
    monkeypatch.setattr(game, "_gzip_answer", lambda content: packed.append(len(content)) or route_gzip(content))
    monkeypatch.setattr(GZipResponder, "apply_compression",
                        lambda self, body, *, more_body: squeezed.append(len(body)) or middleware_gzip(
                            self, body, more_body=more_body))
    response, raw = raw_figures(with_the_applications_gzip(), urls, accept)
    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip" and response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "no-store" and response.headers["vary"] == "Accept-Encoding"
    body = json.loads(gzip.decompress(raw))  # one layer, the route's
    assert [figure["url"] for figure in body["figures"]] == urls[:13] and body["later"] == urls[13:]
    assert len(packed) == 1 and squeezed == []
    # Huffman coding alone takes back base64's overhead.
    assert len(raw) < 0.78 * packed[0]


@pytest.mark.parametrize("accept", ["gzip;q=0", "identity", "br", "x-gzip;q=0, *;q=0"])
def test_a_client_refusing_gzip_gets_the_figures_json_uncompressed(api, monkeypatch, accept):
    urls = large_figures(api, 2, 3_000)
    monkeypatch.setattr(game, "_gzip_answer", lambda content: pytest.fail("compressed for a client refusing gzip"))
    response, raw = raw_figures(with_the_applications_gzip(), urls, accept)
    assert response.status_code == 200 and "content-encoding" not in response.headers
    assert [figure["url"] for figure in json.loads(raw)["figures"]] == urls


def test_every_book_and_notes_call_counts_as_a_book_read_with_web_demo_access(api):
    row = api.store.note(USER_ID, 18, 1801)
    api.client.get("/api/game/grimoires/18/book", headers=KEY)
    api.client.get("/api/game/grimoires/18/notes", headers=KEY)
    api.client.post("/api/game/grimoires/18/notes", headers=KEY, json={"note_type": "scribble"})
    api.client.put(f"/api/game/grimoires/18/notes/{row['demo_note_id']}", headers=KEY,
                   json={"tag": "", "content": "x", "if_updated_at": stamp(row)})
    api.client.request("DELETE", f"/api/game/grimoires/18/notes/{row['demo_note_id']}", headers=KEY,
                       json={"if_updated_at": stamp(api.store.notes[row["demo_note_id"]])})
    api.client.post("/api/game/grimoires/18/figures", headers=KEY, json={"urls": [FIGURE_A, FIGURE_B]})
    assert api.calls == [{"kind": "book", "master_allowed": False, "access_point": "demo"}] * 6
    assert api.costs == [1, 1, 1, 1, 1, 2]


def test_the_routes_are_registered_with_their_methods():
    from app.main import create_app

    application = create_app(initialize_services=False)
    routes = {}
    for route in application.routes:
        path = getattr(route, "path", "")
        if path.startswith("/api/game/grimoires"):
            routes.setdefault(path, set()).update(route.methods)
    assert routes == {
        "/api/game/grimoires": {"GET"},
        "/api/game/grimoires/{grimoire_id}/book": {"GET"},
        "/api/game/grimoires/{grimoire_id}/figures": {"POST"},
        "/api/game/grimoires/{grimoire_id}/notes": {"GET", "POST"},
        "/api/game/grimoires/{grimoire_id}/notes/{note_id}": {"PUT", "DELETE"},
    }
