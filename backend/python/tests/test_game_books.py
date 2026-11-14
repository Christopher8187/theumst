"""The game's book and notes routes (0.0.16) against an in-memory stand-in for PostgreSQL.

The stand-in answers each query by its text, so these establish the order of the checks,
the refusals and their shapes, the headers, and which rows each call reads or changes.
test_book_read_postgres.py checks the same routes against PostgreSQL: the answer against the
Web Demo's per-object route, counting, and notes shared with the Web Demo.
"""
from __future__ import annotations

import gzip
import json
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
    state = SimpleNamespace(store=store, calls=[], key=reader_key(), refusal=None)

    def fake_authenticate(request, *, kind, master_required=False, master_allowed=True, access_point=None):
        # The order of authenticate_api_key's own checks: the key, a master key, the access point, the minute.
        state.calls.append({"kind": kind, "master_allowed": master_allowed, "access_point": access_point})
        if state.refusal is not None:
            raise state.refusal
        if access_point is not None and access_point not in state.key["access_points"]:
            raise AccessRefused(access_point)
        return dict(state.key)

    monkeypatch.setattr(game, "transaction", store.transaction)
    monkeypatch.setattr(game, "authenticate_api_key", fake_authenticate)
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


def test_every_book_and_notes_call_counts_as_a_book_read_with_web_demo_access(api):
    row = api.store.note(USER_ID, 18, 1801)
    api.client.get("/api/game/grimoires/18/book", headers=KEY)
    api.client.get("/api/game/grimoires/18/notes", headers=KEY)
    api.client.post("/api/game/grimoires/18/notes", headers=KEY, json={"note_type": "scribble"})
    api.client.put(f"/api/game/grimoires/18/notes/{row['demo_note_id']}", headers=KEY,
                   json={"tag": "", "content": "x", "if_updated_at": stamp(row)})
    api.client.request("DELETE", f"/api/game/grimoires/18/notes/{row['demo_note_id']}", headers=KEY,
                       json={"if_updated_at": stamp(api.store.notes[row["demo_note_id"]])})
    assert api.calls == [{"kind": "book", "master_allowed": False, "access_point": "demo"}] * 5


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
        "/api/game/grimoires/{grimoire_id}/notes": {"GET", "POST"},
        "/api/game/grimoires/{grimoire_id}/notes/{note_id}": {"PUT", "DELETE"},
    }
