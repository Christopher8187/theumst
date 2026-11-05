"""The game's /api/game endpoints against scripted cursors.

These establish request handling, the order of checks, the SQL each endpoint
sends and the JSON it answers. They do not establish PostgreSQL behaviour
(locks, constraints, now()); see test_game_accounts_schema.py and the release
checks in docs/game-accounts.md.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import psycopg2
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.routers import game
from app.security import hash_password
from app.services import sign_in_attempts


KEY_ID = 41
OTHER_KEY_ID = 99
USER_ID = 7
NOW = datetime(2026, 11, 5, 10, 0, 0, tzinfo=timezone.utc)
PUBLIC_ADDRESS = "81.2.69.142"


class ScriptedCursor:
    """Answers fetchone/fetchall from one queue, in the order the endpoint asks."""

    def __init__(self, *results, fail_on=None):
        self.results = list(results)
        self.executions: list[tuple[str, object]] = []
        self.fail_on = fail_on
        self.outcome = "open"

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        self.executions.append((text, params))
        if self.fail_on and self.fail_on[0] in text:
            raise self.fail_on[1]

    def fetchone(self):
        return self.results.pop(0)

    def fetchall(self):
        return self.results.pop(0)

    def sql(self, fragment):
        return [(text, params) for text, params in self.executions if fragment in text]

    def writes(self):
        return [text for text, _ in self.executions if text.startswith(("UPDATE", "INSERT", "DELETE"))]


def game_key(**overrides):
    key = {
        "api_key_id": KEY_ID, "user_id": USER_ID, "username": "Christopher",
        "name": "UMST · DESKTOP-1", "key_prefix": "umst_read_AbCdEf", "key_type": "regular",
        "client": "umst", "level_name": "standard", "requests_per_minute": 600,
        "rate_limit": 600, "rate_remaining": 599, "authority_type": "user",
    }
    key.update(overrides)
    return key


def character_row(**overrides):
    row = {
        "character_id": 12, "name": "Aria", "sex": "female",
        "summary": {"rank": {"key": "rank.novice", "args": []}, "day": 3},
        "created_at": NOW - timedelta(days=2), "last_played_at": NOW - timedelta(hours=1),
        "lease_api_key_id": None, "lease_live": False, "lease_seconds_left": 0,
        "character_data_id": 77, "revision": 5,
    }
    row.update(overrides)
    return row


def with_save(row):
    return {**row, "data": {"level": 4, "inventory": ["wand"]}, "save_version": 3, "updated_at": NOW - timedelta(hours=1)}


@pytest.fixture
def api(monkeypatch):
    state = SimpleNamespace(cursors=[], used=[], kinds=[], key=game_key(), verified=[])

    @contextmanager
    def fake_transaction():
        cursor = state.cursors.pop(0)
        state.used.append(cursor)
        try:
            yield None, cursor
        except Exception:
            cursor.outcome = "rolled back"
            raise
        cursor.outcome = "committed"

    def fake_authenticate(request, *, kind, master_required=False):
        state.kinds.append(kind)
        if isinstance(state.key, Exception):
            raise state.key
        return dict(state.key)

    monkeypatch.setattr(game, "transaction", fake_transaction)
    monkeypatch.setattr(game, "authenticate_api_key", fake_authenticate)
    application = FastAPI()
    application.include_router(game.router)
    game.install_error_handlers(application)

    class Body(BaseModel):
        name: str

    @application.post("/elsewhere")
    def elsewhere(body: Body):
        return {"ok": True}

    state.client = TestClient(application)
    state.public_client = TestClient(application, client=(PUBLIC_ADDRESS, 50000))
    return state


def assert_game_error(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["code"] == code
    assert isinstance(body["detail"], str) and body["detail"]
    assert response.headers["cache-control"] == "no-store"
    return body


# --- sign-in ------------------------------------------------------------------

def account_row(password="right-password", *, confirmed=True):
    return {
        "user_id": USER_ID, "username": "Christopher", "password_hash": hash_password(password),
        "email_verified_at": NOW if confirmed else None,
    }


def no_failures():
    return {"failures": 0, "wait_seconds": 0}


def standard_rate():
    return {"api_rate_id": 1, "requests_per_minute": 600, "level_name": "standard"}


def sign_in(client, **overrides):
    body = {"username": "christopher", "password": "right-password", "computer": "DESKTOP-1"}
    body.update(overrides)
    return client.post("/api/game/sign-in", json=body)


def test_sign_in_makes_a_standard_game_key_named_for_the_computer(api):
    cursor = ScriptedCursor(no_failures(), account_row(), standard_rate(), {"api_key_id": 41})
    api.cursors.append(cursor)
    response = sign_in(api.client, computer="  DESKTOP-1 ")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["user_id"] == USER_ID and body["username"] == "Christopher"
    key = body["key"]
    assert key["name"] == "UMST · DESKTOP-1"
    assert key["client"] == "umst" and key["key_type"] == "regular"
    assert key["tier"] == "standard" and key["requests_per_minute"] == 600
    assert key["key"].startswith("umst_read_") and key["key_prefix"] == key["key"][:16]
    _, insert_params = cursor.sql("INSERT INTO api_key")[0]
    assert insert_params[0] == USER_ID and insert_params[2] == "UMST · DESKTOP-1"
    assert insert_params[-1] == "umst"
    assert key["key"] not in str(insert_params)  # only the hash and prefix are stored
    assert cursor.sql("INSERT INTO sign_in_attempt")[0][1][2] is True
    assert cursor.sql('lower(username) = lower(%s)')[0][1] == ("christopher",)
    assert cursor.outcome == "committed"
    assert api.kinds == []  # signing in uses the password, not a key


def test_wrong_password_is_401_and_the_failed_attempt_is_kept(api):
    cursor = ScriptedCursor(no_failures(), account_row("another-password"))
    api.cursors.append(cursor)
    body = assert_game_error(sign_in(api.client), 401, "wrong_credentials")
    assert "password" in body["detail"].lower()
    attempt = cursor.sql("INSERT INTO sign_in_attempt")[0][1]
    assert attempt == (sign_in_attempts.username_hash("christopher"), None, False)
    assert cursor.sql("DELETE FROM sign_in_attempt WHERE attempted_at < now() - %s")
    assert not cursor.sql("INSERT INTO api_key")
    # Committed before the refusal, so the failure counts toward the limit.
    assert cursor.outcome == "committed"


def test_unknown_username_spends_a_password_check_and_answers_like_a_wrong_password(api, monkeypatch):
    checked = []
    real_verify = game.verify_password

    def recording_verify(password, hashed):
        checked.append(hashed)
        return real_verify(password, hashed)

    monkeypatch.setattr(game, "verify_password", recording_verify)
    cursor = ScriptedCursor(no_failures(), None)
    api.cursors.append(cursor)
    assert_game_error(sign_in(api.client, username="nobody"), 401, "wrong_credentials")
    assert checked == [game._decoy_hash()]
    assert cursor.sql("INSERT INTO sign_in_attempt")[0][1][2] is False


def test_unconfirmed_email_is_403_email_unverified_and_makes_no_key(api):
    cursor = ScriptedCursor(no_failures(), account_row(confirmed=False))
    api.cursors.append(cursor)
    assert_game_error(sign_in(api.client), 403, "email_unverified")
    assert not cursor.sql("INSERT INTO api_key")
    assert cursor.sql("INSERT INTO sign_in_attempt")[0][1][2] is True


def test_too_many_wrong_passwords_for_a_username_is_429_with_retry_after(api):
    cursor = ScriptedCursor({"failures": 10, "wait_seconds": 312})
    api.cursors.append(cursor)
    response = sign_in(api.client)
    body = assert_game_error(response, 429, "too_many_attempts")
    assert body["retry_after"] == 312
    assert response.headers["retry-after"] == "312"
    # Refused before the password is looked at; the refusal itself is not an attempt.
    assert not cursor.sql('FROM "user"')
    assert not cursor.sql("INSERT INTO sign_in_attempt")


def test_too_many_wrong_passwords_from_one_public_address_is_429(api):
    cursor = ScriptedCursor(no_failures(), {"failures": 30, "wait_seconds": 45})
    api.cursors.append(cursor)
    response = sign_in(api.public_client)
    assert assert_game_error(response, 429, "too_many_attempts")["retry_after"] == 45
    assert cursor.sql("WHERE address = %(address)s")[0][1]["address"] == PUBLIC_ADDRESS


def test_a_public_address_is_recorded_with_the_attempt(api):
    cursor = ScriptedCursor(no_failures(), no_failures(), account_row("another-password"))
    api.cursors.append(cursor)
    assert_game_error(sign_in(api.public_client), 401, "wrong_credentials")
    assert cursor.sql("INSERT INTO sign_in_attempt")[0][1][1] == PUBLIC_ADDRESS


@pytest.mark.parametrize(
    ("computer", "expected"),
    [("DESKTOP-1", "DESKTOP-1"), ("  Living   room\tPC ", "Living room PC"), ("PC\x07\x00-2", "PC-2"), ("x" * 150, "x" * 100)],
)
def test_the_computer_name_is_cleaned_and_shortened(computer, expected):
    assert game._computer(computer) == expected


def test_lone_surrogates_are_refused_before_hashing_or_storing(api):
    # Pydantic refuses them in string fields; a save's own values reach _json_text.
    response = api.client.post(
        "/api/game/sign-in",
        content=b'{"username": "chris\\ud800", "password": "right-password", "computer": "PC"}',
        headers={"Content-Type": "application/json"},
    )
    assert_game_error(response, 422, "invalid_request")
    named = api.client.post(
        "/api/game/characters",
        content=b'{"name": "Ar\\udc00ia", "sex": "female", "save": {}, "save_version": 1}',
        headers={"Content-Type": "application/json"},
    )
    assert_game_error(named, 422, "invalid_request")
    saved = api.client.post(
        "/api/game/characters",
        content=b'{"name": "Aria", "sex": "female", "save": {"note": "\\ud800"}, "save_version": 1}',
        headers={"Content-Type": "application/json"},
    )
    assert_game_error(saved, 422, "invalid_request")
    assert api.used == []


def test_a_blank_computer_name_is_refused(api):
    assert_game_error(sign_in(api.client, computer="   "), 422, "invalid_request")
    assert api.used == []


def test_a_malformed_sign_in_gets_the_game_error_shape(api):
    response = api.client.post("/api/game/sign-in", json={"username": "christopher", "computer": "PC"})
    body = assert_game_error(response, 422, "invalid_request")
    assert {"field": "password", "message": "Field required"} in body["errors"]


def test_validation_elsewhere_keeps_fastapis_shape(api):
    response = api.client.post("/elsewhere", json={})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert "code" not in response.json()


# --- the throttle service -------------------------------------------------------

def test_username_hash_ignores_case_and_surrounding_space_and_hides_the_name():
    assert sign_in_attempts.username_hash("  Christopher ") == sign_in_attempts.username_hash("christopher")
    assert "christopher" not in sign_in_attempts.username_hash("Christopher")
    assert len(sign_in_attempts.username_hash("x")) == 64


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        (PUBLIC_ADDRESS, PUBLIC_ADDRESS),
        ("2a00:1450:4009:81f::200e", "2a00:1450:4009:81f::200e"),
        ("172.18.0.5", None),   # the internal proxy when forwarded headers are not trusted
        ("127.0.0.1", None),
        ("192.168.1.20", None),
        ("testclient", None),
    ],
)
def test_only_public_addresses_are_throttled_as_addresses(host, expected):
    request = SimpleNamespace(client=SimpleNamespace(host=host))
    assert sign_in_attempts.public_address(request) == expected
    assert sign_in_attempts.public_address(SimpleNamespace(client=None)) is None


def test_retry_after_is_zero_below_both_limits():
    cursor = ScriptedCursor({"failures": 9, "wait_seconds": 100}, {"failures": 29, "wait_seconds": 100})
    assert sign_in_attempts.retry_after(cursor, "a" * 64, PUBLIC_ADDRESS) == 0
    username_sql, username_params = cursor.executions[0]
    assert "NOT succeeded" in username_sql and "AND succeeded" in username_sql
    assert username_params == {"subject": "a" * 64, "window": timedelta(minutes=15)}


def test_retry_after_waits_for_the_longer_of_the_two_limits():
    cursor = ScriptedCursor({"failures": 10, "wait_seconds": 30}, {"failures": 31, "wait_seconds": 200})
    assert sign_in_attempts.retry_after(cursor, "a" * 64, PUBLIC_ADDRESS) == 200


def test_retry_after_skips_the_address_when_there_is_none():
    cursor = ScriptedCursor({"failures": 0, "wait_seconds": 0})
    assert sign_in_attempts.retry_after(cursor, "a" * 64, None) == 0
    assert len(cursor.executions) == 1


def test_limits_are_ten_per_username_and_thirty_per_address_in_fifteen_minutes():
    assert sign_in_attempts.MAX_FAILURES_PER_USERNAME == 10
    assert sign_in_attempts.MAX_FAILURES_PER_ADDRESS == 30
    assert sign_in_attempts.WINDOW == timedelta(minutes=15)
    assert sign_in_attempts.KEEP == timedelta(days=1)


# --- key calls ------------------------------------------------------------------

def test_me_returns_the_account_and_key_and_counts_as_a_character_call(api):
    response = api.client.get("/api/game/me", headers={"X-API-Key": "umst_read_x"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "user_id": USER_ID, "username": "Christopher",
        "key": {
            "api_key_id": KEY_ID, "name": "UMST · DESKTOP-1", "key_prefix": "umst_read_AbCdEf",
            "key_type": "regular", "client": "umst", "tier": "standard", "requests_per_minute": 600,
        },
    }
    assert api.kinds == ["character"]


def test_me_with_a_master_key_has_no_tier(api):
    api.key = game_key(key_type="master", client=None, level_name=None, requests_per_minute=None)
    key = api.client.get("/api/game/me").json()["key"]
    assert key["tier"] is None and key["requests_per_minute"] is None


def test_an_invalid_key_is_401_invalid_key(api):
    api.key = HTTPException(status_code=401, detail="Invalid or revoked API key")
    assert_game_error(api.client.get("/api/game/characters"), 401, "invalid_key")


def test_a_key_over_its_minute_is_429_rate_limited_with_retry_after(api):
    api.key = HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": "17"})
    response = api.client.get("/api/game/characters")
    assert assert_game_error(response, 429, "rate_limited")["retry_after"] == 17
    assert response.headers["retry-after"] == "17"


def test_sign_out_revokes_only_a_game_key_and_frees_what_it_had_open(api):
    cursor = ScriptedCursor([{"character_id": 12}], {"api_key_id": KEY_ID})
    api.cursors.append(cursor)
    response = api.client.post("/api/game/sign-out")
    assert response.json() == {"revoked": True, "released_characters": 1}
    _, release_params = cursor.sql('UPDATE "character" SET lease_api_key_id = NULL')[0]
    assert release_params == (KEY_ID,)
    revoke_sql, revoke_params = cursor.sql("UPDATE api_key SET revoked_at = now()")[0]
    assert "client = %s" in revoke_sql and revoke_params == (KEY_ID, "umst")


def test_sign_out_with_another_kind_of_key_keeps_it(api):
    api.key = game_key(client=None, name="Default")
    api.cursors.append(ScriptedCursor([], None))
    assert api.client.post("/api/game/sign-out").json() == {"revoked": False, "released_characters": 0}


# --- the character list -----------------------------------------------------------

def test_the_list_shows_who_has_each_character_open_without_any_save(api):
    rows = [
        character_row(),
        character_row(character_id=13, name="Bram", sex="male", summary={},
                      lease_api_key_id=OTHER_KEY_ID, lease_live=True, lease_seconds_left=87, last_played_at=None),
        character_row(character_id=14, name="Cass", lease_api_key_id=KEY_ID, lease_live=True, lease_seconds_left=100),
        character_row(character_id=15, name="Dov", lease_api_key_id=OTHER_KEY_ID, lease_live=False),
    ]
    cursor = ScriptedCursor(rows)
    api.cursors.append(cursor)
    response = api.client.get("/api/game/characters")
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 6
    first, second, third, fourth = body["characters"]
    assert first == {
        "character_id": 12, "name": "Aria", "sex": "female",
        "summary": {"rank": {"key": "rank.novice", "args": []}, "day": 3},
        "created_at": "2026-11-03T10:00:00Z", "last_played_at": "2026-11-05T09:00:00Z",
        "open_elsewhere": False, "open_elsewhere_seconds_left": None,
    }
    assert second["open_elsewhere"] is True and second["open_elsewhere_seconds_left"] == 87
    assert second["last_played_at"] is None and second["summary"] == {}
    assert third["open_elsewhere"] is False   # this computer's own lease
    assert fourth["open_elsewhere"] is False  # another computer's lapsed lease
    list_sql, list_params = cursor.executions[0]
    assert list_params == (USER_ID,)
    assert "ORDER BY c.created_at, c.character_id" in list_sql
    assert "d.data" not in list_sql and "character_data" not in list_sql
    assert api.kinds == ["character"]


# --- making a character -------------------------------------------------------------

def new_character(**overrides):
    body = {
        "name": "  Aria  ", "sex": "female", "save": {"level": 1, "name": "Aria"}, "save_version": 3,
        "summary": {"rank": {"key": "rank.novice", "args": []}, "day": 1},
    }
    body.update(overrides)
    return body


def made_row():
    return {
        "character_id": 12, "name": "Aria", "sex": "female",
        "summary": {"rank": {"key": "rank.novice", "args": []}, "day": 1},
        "created_at": NOW, "last_played_at": None,
        "lease_api_key_id": None, "lease_live": False, "lease_seconds_left": 0,
    }


def test_making_a_character_stores_its_save_and_summary(api):
    cursor = ScriptedCursor({"characters": 5}, {"character_data_id": 77, "revision": 1}, made_row())
    api.cursors.append(cursor)
    response = api.client.post("/api/game/characters", json=new_character())
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["revision"] == 1
    assert body["character"]["name"] == "Aria" and body["character"]["last_played_at"] is None
    assert body["character"]["created_at"] == "2026-11-05T10:00:00Z"
    lock_sql, lock_params = cursor.executions[0]
    assert 'FROM "user" WHERE user_id = %s FOR UPDATE' in lock_sql and lock_params == (USER_ID,)
    data_sql, data_params = cursor.sql("INSERT INTO character_data")[0]
    assert "%s::jsonb" in data_sql
    assert data_params == ('{"level": 1, "name": "Aria"}', 3)
    _, character_params = cursor.sql('INSERT INTO "character"')[0]
    assert character_params == (
        USER_ID, 77, "Aria", "female", '{"rank": {"key": "rank.novice", "args": []}, "day": 1}',
    )
    assert cursor.outcome == "committed"


def test_a_character_without_a_summary_gets_an_empty_one(api):
    cursor = ScriptedCursor({"characters": 0}, {"character_data_id": 77, "revision": 1}, made_row())
    api.cursors.append(cursor)
    body = new_character()
    del body["summary"]
    assert api.client.post("/api/game/characters", json=body).status_code == 201
    assert cursor.sql('INSERT INTO "character"')[0][1][-1] == "{}"


def test_a_seventh_character_is_409_full(api):
    cursor = ScriptedCursor({"characters": 6})
    api.cursors.append(cursor)
    body = assert_game_error(api.client.post("/api/game/characters", json=new_character()), 409, "full")
    assert body["limit"] == 6
    assert not cursor.writes()
    assert cursor.outcome == "rolled back"


@pytest.mark.parametrize("name", ["", "   ", "x" * 51, "Ar\x00ia", "Ar\x1bia"])
def test_names_have_1_to_50_characters_and_no_control_characters(api, name):
    assert_game_error(api.client.post("/api/game/characters", json=new_character(name=name)), 422, "invalid_name")
    assert api.used == []


def test_a_fifty_character_name_is_accepted():
    assert game._valid_name("é" * 50) == "é" * 50
    assert game._valid_name("  Aria   of  Vell ") == "Aria of Vell"


def test_a_save_over_64_kib_is_413_before_the_database(api):
    response = api.client.post("/api/game/characters", json=new_character(save={"blob": "x" * 65536}))
    body = assert_game_error(response, 413, "save_too_large")
    assert body["limit_bytes"] == 65536
    assert api.used == []


def test_a_summary_over_2_kib_is_413(api):
    response = api.client.post("/api/game/characters", json=new_character(summary={"text": "x" * 2048}))
    assert assert_game_error(response, 413, "summary_too_large")["limit_bytes"] == 2048


def test_a_save_just_within_64_kib_is_sent_on(api):
    # {"blob": "..."} adds 12 bytes around the string.
    api.cursors.append(ScriptedCursor({"characters": 0}, {"character_data_id": 77, "revision": 1}, made_row()))
    response = api.client.post("/api/game/characters", json=new_character(save={"blob": "x" * (65536 - 12)}))
    assert response.status_code == 201


@pytest.mark.parametrize(
    "overrides",
    [{"save": [1, 2]}, {"save": "text"}, {"sex": "other"}, {"save_version": -1}, {"summary": [1]}],
)
def test_malformed_characters_are_422_invalid_request(api, overrides):
    assert_game_error(api.client.post("/api/game/characters", json=new_character(**overrides)), 422, "invalid_request")
    assert api.used == []


def test_a_save_with_nan_is_refused_as_invalid_json(api):
    response = api.client.post(
        "/api/game/characters",
        content=b'{"name": "Aria", "sex": "female", "save": {"hp": NaN}, "save_version": 1}',
        headers={"Content-Type": "application/json"},
    )
    assert_game_error(response, 422, "invalid_request")
    assert api.used == []


class SaveCheckViolation(psycopg2.Error):
    # Class attributes stand in for the server's error fields.
    pgcode = "23514"
    diag = SimpleNamespace(constraint_name="character_data_data_check")


def test_the_databases_size_check_is_answered_as_413(api):
    failure = SaveCheckViolation("new row violates check constraint")
    api.cursors.append(ScriptedCursor({"characters": 0}, fail_on=("INSERT INTO character_data", failure)))
    response = api.client.post("/api/game/characters", json=new_character())
    assert assert_game_error(response, 413, "save_too_large")["limit_bytes"] == 65536


@pytest.mark.parametrize(
    ("constraint", "status", "code"),
    [
        ("character_data_data_check", 413, "save_too_large"),
        ("character_summary_check", 413, "summary_too_large"),
        ("character_name_check", 422, "invalid_name"),
    ],
)
def test_stored_errors_map_check_constraints(constraint, status, code):
    error = game._stored_error(SimpleNamespace(pgcode="23514", diag=SimpleNamespace(constraint_name=constraint)))
    assert (error.status_code, error.code) == (status, code)
    assert game._stored_error(SimpleNamespace(pgcode="23514", diag=SimpleNamespace(constraint_name="other"))) is None
    assert game._stored_error(SimpleNamespace(pgcode="22P05", diag=None)).code == "invalid_request"
    assert game._stored_error(SimpleNamespace(pgcode="40001", diag=None)) is None


# --- opening, heartbeats and closing ---------------------------------------------------

def lease_row():
    return {"lease_expires_at": NOW + timedelta(seconds=120)}


def test_opening_takes_the_lease_and_returns_the_save_and_revision(api):
    cursor = ScriptedCursor(with_save(character_row()), lease_row())
    api.cursors.append(cursor)
    response = api.client.post("/api/game/characters/12/open")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["save"] == {"level": 4, "inventory": ["wand"]}
    assert body["save_version"] == 3 and body["revision"] == 5
    assert body["lease_seconds"] == 120 and body["lease_expires_at"] == "2026-11-05T10:02:00Z"
    assert body["updated_at"] == "2026-11-05T09:00:00Z"
    assert body["character"]["character_id"] == 12 and body["character"]["open_elsewhere"] is False
    select_sql, select_params = cursor.executions[0]
    assert "FOR UPDATE" in select_sql and "d.data" in select_sql
    assert select_params == (12, USER_ID)
    _, lease_params = cursor.sql('UPDATE "character" SET lease_api_key_id = %s')[0]
    assert lease_params == (KEY_ID, timedelta(seconds=120), 12)
    assert cursor.outcome == "committed"


def test_another_computers_live_lease_is_409_open_elsewhere_with_seconds_left(api):
    cursor = ScriptedCursor(with_save(character_row(lease_api_key_id=OTHER_KEY_ID, lease_live=True, lease_seconds_left=87)))
    api.cursors.append(cursor)
    body = assert_game_error(api.client.post("/api/game/characters/12/open"), 409, "open_elsewhere")
    assert body["seconds_left"] == 87
    assert not cursor.writes()


def test_the_same_key_may_reopen_its_own_lease(api):
    api.cursors.append(ScriptedCursor(with_save(character_row(lease_api_key_id=KEY_ID, lease_live=True, lease_seconds_left=60)), lease_row()))
    assert api.client.post("/api/game/characters/12/open").status_code == 200


def test_a_lapsed_lease_of_another_computer_can_be_taken(api):
    api.cursors.append(ScriptedCursor(with_save(character_row(lease_api_key_id=OTHER_KEY_ID, lease_live=False)), lease_row()))
    assert api.client.post("/api/game/characters/12/open").status_code == 200


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/api/game/characters/12/open", None),
        ("POST", "/api/game/characters/12/heartbeat", None),
        ("POST", "/api/game/characters/12/close", None),
        ("PUT", "/api/game/characters/12/data", {"save": {}, "save_version": 1, "revision": 1}),
        ("DELETE", "/api/game/characters/12", {"name": "Aria"}),
    ],
)
def test_another_accounts_or_a_missing_character_is_404(api, method, path, body):
    cursor = ScriptedCursor(None)
    api.cursors.append(cursor)
    assert_game_error(api.client.request(method, path, json=body), 404, "not_found")
    assert cursor.executions[0][1] == (12, USER_ID)


def test_a_heartbeat_renews_this_keys_lease(api):
    cursor = ScriptedCursor(character_row(lease_api_key_id=KEY_ID, lease_live=True, lease_seconds_left=20), lease_row())
    api.cursors.append(cursor)
    response = api.client.post("/api/game/characters/12/heartbeat")
    assert response.json() == {"lease_seconds": 120, "lease_expires_at": "2026-11-05T10:02:00Z"}
    assert "d.data" not in cursor.executions[0][0]


def test_a_heartbeat_after_a_lapse_nobody_used_still_renews(api):
    api.cursors.append(ScriptedCursor(character_row(lease_api_key_id=KEY_ID, lease_live=False), lease_row()))
    assert api.client.post("/api/game/characters/12/heartbeat").status_code == 200


def test_a_heartbeat_without_the_lease_is_409(api):
    api.cursors.append(ScriptedCursor(character_row()))
    assert_game_error(api.client.post("/api/game/characters/12/heartbeat"), 409, "not_open")
    api.cursors.append(ScriptedCursor(character_row(lease_api_key_id=OTHER_KEY_ID, lease_live=True, lease_seconds_left=5)))
    assert assert_game_error(api.client.post("/api/game/characters/12/heartbeat"), 409, "open_elsewhere")["seconds_left"] == 5


def test_closing_releases_only_this_keys_lease(api):
    mine = ScriptedCursor(character_row(lease_api_key_id=KEY_ID, lease_live=True, lease_seconds_left=50))
    api.cursors.append(mine)
    assert api.client.post("/api/game/characters/12/close").json() == {"released": True}
    assert mine.sql("SET lease_api_key_id = NULL, lease_expires_at = NULL")[0][1] == (12,)
    theirs = ScriptedCursor(character_row(lease_api_key_id=OTHER_KEY_ID, lease_live=True, lease_seconds_left=50))
    api.cursors.append(theirs)
    assert api.client.post("/api/game/characters/12/close").json() == {"released": False}
    assert not theirs.writes()


# --- saving ------------------------------------------------------------------------

def save_body(**overrides):
    body = {"save": {"level": 5}, "save_version": 3, "revision": 5, "summary": {"day": 4}}
    body.update(overrides)
    return body


def test_a_save_raises_the_revision_sets_last_played_and_renews_the_lease(api):
    cursor = ScriptedCursor(
        character_row(lease_api_key_id=KEY_ID, lease_live=True, lease_seconds_left=40),
        {"revision": 6, "updated_at": NOW},
        {"last_played_at": NOW, "lease_expires_at": NOW + timedelta(seconds=120)},
    )
    api.cursors.append(cursor)
    response = api.client.put("/api/game/characters/12/data", json=save_body())
    assert response.status_code == 200, response.text
    assert response.json() == {
        "revision": 6, "updated_at": "2026-11-05T10:00:00Z", "last_played_at": "2026-11-05T10:00:00Z",
        "lease_seconds": 120, "lease_expires_at": "2026-11-05T10:02:00Z",
    }
    data_sql, data_params = cursor.sql("UPDATE character_data")[0]
    assert "revision = revision + 1" in data_sql and "updated_at = now()" in data_sql
    assert data_params == ('{"level": 5}', 3, 77)
    played_sql, played_params = cursor.sql('UPDATE "character" SET last_played_at = now()')[0]
    assert "COALESCE(%s::jsonb, summary)" in played_sql
    assert played_params == (timedelta(seconds=120), '{"day": 4}', 12)
    assert cursor.outcome == "committed"


def test_a_save_without_a_summary_keeps_the_stored_one(api):
    cursor = ScriptedCursor(
        character_row(lease_api_key_id=KEY_ID, lease_live=True, lease_seconds_left=40),
        {"revision": 6, "updated_at": NOW},
        {"last_played_at": NOW, "lease_expires_at": NOW},
    )
    api.cursors.append(cursor)
    body = save_body()
    del body["summary"]
    assert api.client.put("/api/game/characters/12/data", json=body).status_code == 200
    assert cursor.sql('UPDATE "character" SET last_played_at')[0][1][1] is None


def test_a_save_from_an_older_revision_is_409_stale_with_the_current_one(api):
    cursor = ScriptedCursor(character_row(lease_api_key_id=KEY_ID, lease_live=True, lease_seconds_left=40, revision=6))
    api.cursors.append(cursor)
    body = assert_game_error(api.client.put("/api/game/characters/12/data", json=save_body(revision=5)), 409, "stale")
    assert body["revision"] == 6
    assert not cursor.writes()


def test_a_save_needs_the_lease(api):
    api.cursors.append(ScriptedCursor(character_row()))
    assert_game_error(api.client.put("/api/game/characters/12/data", json=save_body()), 409, "not_open")
    api.cursors.append(ScriptedCursor(character_row(lease_api_key_id=OTHER_KEY_ID, lease_live=True, lease_seconds_left=9)))
    assert_game_error(api.client.put("/api/game/characters/12/data", json=save_body()), 409, "open_elsewhere")


def test_a_save_with_this_keys_lapsed_lease_is_kept(api):
    api.cursors.append(ScriptedCursor(
        character_row(lease_api_key_id=KEY_ID, lease_live=False),
        {"revision": 6, "updated_at": NOW},
        {"last_played_at": NOW, "lease_expires_at": NOW},
    ))
    assert api.client.put("/api/game/characters/12/data", json=save_body()).status_code == 200


def test_an_oversized_save_is_413_before_the_lease_is_checked(api):
    response = api.client.put("/api/game/characters/12/data", json=save_body(save={"blob": "x" * 70000}))
    assert_game_error(response, 413, "save_too_large")
    assert api.used == []


@pytest.mark.parametrize("overrides", [{"revision": 0}, {"save_version": "three"}, {"save": None}])
def test_malformed_saves_are_422(api, overrides):
    assert_game_error(api.client.put("/api/game/characters/12/data", json=save_body(**overrides)), 422, "invalid_request")


# --- deleting ----------------------------------------------------------------------

def test_deleting_needs_the_name_typed_exactly(api):
    cursor = ScriptedCursor(character_row())
    api.cursors.append(cursor)
    response = api.client.request("DELETE", "/api/game/characters/12", json={"name": "aria"})
    assert_game_error(response, 409, "name_mismatch")
    assert not cursor.writes()


def test_deleting_is_refused_while_another_computer_has_it_open(api):
    cursor = ScriptedCursor(character_row(lease_api_key_id=OTHER_KEY_ID, lease_live=True, lease_seconds_left=30))
    api.cursors.append(cursor)
    response = api.client.request("DELETE", "/api/game/characters/12", json={"name": "Aria"})
    assert assert_game_error(response, 409, "open_elsewhere")["seconds_left"] == 30
    assert not cursor.writes()


def test_deleting_removes_the_character_and_its_save(api):
    cursor = ScriptedCursor(character_row(lease_api_key_id=KEY_ID, lease_live=True, lease_seconds_left=30))
    api.cursors.append(cursor)
    response = api.client.request("DELETE", "/api/game/characters/12", json={"name": "  Aria "})
    assert response.json() == {"deleted": True, "character_id": 12}
    assert cursor.sql('DELETE FROM "character" WHERE character_id = %s')[0][1] == (12,)
    assert cursor.sql("DELETE FROM character_data WHERE character_data_id = %s")[0][1] == (77,)
    assert cursor.outcome == "committed"


def test_deleting_without_a_name_is_422(api):
    assert_game_error(api.client.request("DELETE", "/api/game/characters/12"), 422, "invalid_request")


def test_every_key_route_counts_as_a_character_call(api):
    api.cursors.extend([
        ScriptedCursor([]),
        ScriptedCursor(character_row()),
    ])
    api.client.get("/api/game/characters")
    api.client.post("/api/game/characters/12/close")
    api.client.get("/api/game/me")
    assert api.kinds == ["character", "character", "character"]
