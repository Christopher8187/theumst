"""The Default key, made when an account without one opens its signed-in API
Keys page, and the revocation of the game's keys. Scripted cursors; no PostgreSQL."""
from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.routers import api_keys, auth
from app.schemas import EmailVerificationRequest
from app.security import hash_secret
from app.services import api_keys as key_service


class ScriptedCursor:
    def __init__(self, *results):
        self.results = list(results)
        self.executions: list[tuple[str, object]] = []

    def execute(self, sql, params=None):
        self.executions.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.results.pop(0)

    def fetchall(self):
        return self.results.pop(0)

    def sql(self, fragment):
        return [(text, params) for text, params in self.executions if fragment in text]


def transaction_for(cursor):
    @contextmanager
    def fake():
        yield None, cursor
    return fake


STANDARD = {"api_rate_id": 1, "requests_per_minute": 600, "level_name": "standard"}


def test_an_account_without_a_default_key_gets_one_at_the_standard_tier():
    cursor = ScriptedCursor({"user_id": 7}, None, STANDARD, {"api_key_id": 30})
    made = key_service.ensure_default_key(cursor, 7)
    assert made["name"] == "Default" and made["api_key_id"] == 30
    assert made["tier"] == "standard" and made["requests_per_minute"] == 600
    assert made["client"] is None and made["key_type"] == "regular"
    assert made["key"].startswith("umst_read_") and made["key_prefix"] == made["key"][:16]
    lock_sql, lock_params = cursor.executions[0]
    assert lock_sql == 'SELECT user_id FROM "user" WHERE user_id = %s FOR UPDATE' and lock_params == (7,)
    look_sql, look_params = cursor.executions[1]
    # Revoked keys count: the query does not filter on revoked_at.
    assert "revoked_at" not in look_sql and "client IS NULL" in look_sql
    assert look_params == (7, "Default")
    _, insert_params = cursor.sql("INSERT INTO api_key")[0]
    assert insert_params == (7, 1, "Default", made["key_prefix"], hash_secret(made["key"]), None)


def test_an_account_that_had_a_default_key_gets_no_other():
    cursor = ScriptedCursor({"user_id": 7}, {"present": 1})
    assert key_service.ensure_default_key(cursor, 7) is None
    assert not cursor.sql("INSERT")


def test_a_missing_account_gets_nothing():
    cursor = ScriptedCursor(None)
    assert key_service.ensure_default_key(cursor, 7) is None
    assert len(cursor.executions) == 1


def test_no_key_is_made_without_the_standard_tier():
    cursor = ScriptedCursor(None)
    with pytest.raises(key_service.StandardTierMissing):
        key_service.create_regular_key(cursor, 7, "Default")
    assert not cursor.sql("INSERT")


def test_a_game_key_records_its_client():
    cursor = ScriptedCursor(STANDARD, {"api_key_id": 31})
    made = key_service.create_regular_key(cursor, 7, "UMST · PC", client="umst")
    assert made["client"] == "umst"
    assert cursor.sql("INSERT INTO api_key")[0][1][-1] == "umst"


@pytest.fixture
def keys_client(monkeypatch):
    state = SimpleNamespace(cursors=[])

    @contextmanager
    def fake_transaction():
        yield None, state.cursors.pop(0)

    monkeypatch.setattr(api_keys, "transaction", fake_transaction)
    monkeypatch.setattr(api_keys, "require_user", lambda request: {"user_id": 7, "authority_type": "user"})
    application = FastAPI()
    application.include_router(api_keys.router)
    state.client = TestClient(application)
    return state


def test_the_api_keys_page_gets_the_default_key_text_once(keys_client):
    keys_client.cursors.append(ScriptedCursor({"user_id": 7}, None, STANDARD, {"api_key_id": 30}))
    response = keys_client.client.post("/api/api-keys/default")
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["created"] is True and body["key"]["name"] == "Default" and body["key"]["key"].startswith("umst_read_")

    keys_client.cursors.append(ScriptedCursor({"user_id": 7}, {"present": 1}))
    again = keys_client.client.post("/api/api-keys/default")
    assert again.status_code == 200 and again.json() == {"created": False}


def test_the_default_key_endpoint_requires_a_session(monkeypatch):
    def refuse(request):
        raise HTTPException(status_code=401, detail="Authentication required")

    monkeypatch.setattr(api_keys, "require_user", refuse)
    application = FastAPI()
    application.include_router(api_keys.router)
    assert TestClient(application).post("/api/api-keys/default").status_code == 401


def test_the_key_list_shows_the_per_minute_allowance_and_the_client(keys_client):
    cursor = ScriptedCursor([{
        "api_key_id": 30, "name": "Default", "key_prefix": "umst_read_abcdef", "key_type": "regular",
        "client": None, "created_at": None, "last_used_at": None, "revoked_at": None, "upgraded_at": None,
        "requests_per_minute": 600, "level_name": "standard",
    }])
    keys_client.cursors.append(cursor)
    body = keys_client.client.get("/api/api-keys").json()
    assert body["keys"][0]["requests_per_minute"] == 600
    assert "r.requests_per_minute" in cursor.executions[0][0] and "k.client" in cursor.executions[0][0]
    assert "searches_per_hour" not in cursor.executions[0][0]


def test_a_dashboard_key_is_made_at_the_standard_tier_without_a_client(keys_client):
    cursor = ScriptedCursor(STANDARD, {"api_key_id": 32})
    keys_client.cursors.append(cursor)
    response = keys_client.client.post("/api/api-keys", json={"name": " Reader "})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Reader" and body["key_type"] == "regular" and body["api_key_id"] == 32
    assert cursor.sql("INSERT INTO api_key")[0][1][-1] is None


def test_revoking_a_key_frees_the_characters_it_had_open(keys_client):
    cursor = ScriptedCursor({"api_key_id": 41})
    keys_client.cursors.append(cursor)
    assert keys_client.client.delete("/api/api-keys/41").json() == {"ok": True}
    _, release_params = cursor.sql('UPDATE "character" SET lease_api_key_id = NULL')[0]
    assert release_params == (41,)


def test_revoking_another_accounts_key_frees_nothing(keys_client):
    cursor = ScriptedCursor(None)
    keys_client.cursors.append(cursor)
    assert keys_client.client.delete("/api/api-keys/41").status_code == 404
    assert not cursor.sql('UPDATE "character"')


def test_confirming_an_email_makes_no_key(monkeypatch):
    # The link works without a session; a key in its answer would reach a mail
    # scanner or anyone the email was forwarded to.
    cursor = ScriptedCursor({"email_verification_token_id": 3, "user_id": 7})
    monkeypatch.setattr(auth, "transaction", transaction_for(cursor))
    body = auth.confirm_email_verification(EmailVerificationRequest(token="t" * 40))
    assert body == {"ok": True, "redirect": "/login?verified=success"}
    assert cursor.sql("SET email_verified_at = now()")
    assert not cursor.sql("api_key") and not cursor.sql("api_rate")


def test_a_used_or_expired_link_makes_no_key(monkeypatch):
    cursor = ScriptedCursor(None)
    monkeypatch.setattr(auth, "transaction", transaction_for(cursor))
    with pytest.raises(HTTPException) as refused:
        auth.confirm_email_verification(EmailVerificationRequest(token="t" * 40))
    assert refused.value.status_code == 400
    assert not cursor.sql("api_key")


def test_revoking_every_game_key_frees_their_characters():
    cursor = ScriptedCursor([{"api_key_id": 41}, {"api_key_id": 43}])
    assert key_service.revoke_game_keys(cursor, 7) == [41, 43]
    revoke_sql, revoke_params = cursor.executions[0]
    assert revoke_sql.startswith("UPDATE api_key SET revoked_at = now()")
    assert "client = %s AND revoked_at IS NULL" in revoke_sql and "name" not in revoke_sql
    assert revoke_params == (7, "umst")
    release_sql, release_params = cursor.executions[1]
    assert 'UPDATE "character" SET lease_api_key_id = NULL' in release_sql
    assert "lease_api_key_id = ANY(%s)" in release_sql and release_params == ([41, 43],)


def test_revoking_one_computers_game_key_names_it():
    cursor = ScriptedCursor([])
    assert key_service.revoke_game_keys(cursor, 7, name="UMST · PC") == []
    assert cursor.executions[0][1] == (7, "umst", "UMST · PC")
    assert len(cursor.executions) == 1  # nothing revoked, nothing to free
