"""The website's login (/auth/login) under the game sign-in's wrong-password limits.

Scripted cursors establish the order of checks, the SQL each attempt sends and
the answers. They do not establish PostgreSQL's locks or now(); test_game_api.py
covers the same limiter at /api/game/sign-in.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from functools import cache
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from app.routers import auth, game
from app.security import hash_password
from app.services import sign_in_attempts


USER_ID = 7
NOW = datetime(2026, 11, 5, 10, 0, 0, tzinfo=timezone.utc)
PUBLIC_ADDRESS = "81.2.69.142"
TYPED_HASH = "a" * 64  # what PostgreSQL computes for an unknown username
WAIT_DETAIL = "Too many wrong passwords; wait before trying again"


class ScriptedCursor:
    """Answers fetchone/fetchall from one queue, in the order the endpoint asks."""

    def __init__(self, *results):
        self.results = list(results)
        self.executions: list[tuple[str, object]] = []
        self.outcome = "open"

    def execute(self, sql, params=None):
        self.executions.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.results.pop(0)

    def fetchall(self):
        return self.results.pop(0)

    def sql(self, fragment):
        return [(text, params) for text, params in self.executions if fragment in text]

    def index(self, fragment):
        return next(position for position, (text, _) in enumerate(self.executions) if fragment in text)


@cache
def password_hash(password: str) -> str:
    return hash_password(password)


def account_row(password="right-password", *, confirmed=True):
    return {
        "username_hash": "b" * 64, "user_id": USER_ID, "username": "Christopher",
        "password_hash": password_hash(password), "email_verified_at": NOW if confirmed else None,
    }


def no_account():
    return {"username_hash": TYPED_HASH, "user_id": None, "username": None, "password_hash": None, "email_verified_at": None}


def no_failures():
    return {"failures": 0, "wait_seconds": 0}


@pytest.fixture
def site(monkeypatch):
    state = SimpleNamespace(cursors=[], used=[], subscriptions=[])

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

    def fake_subscription(cur, user_id, enabled, source):
        state.subscriptions.append((user_id, enabled, source))

    monkeypatch.setattr(auth, "transaction", fake_transaction)
    monkeypatch.setattr(auth, "set_subscription", fake_subscription)
    application = FastAPI()
    application.include_router(auth.router)
    state.client = TestClient(application)
    state.public_client = TestClient(application, client=(PUBLIC_ADDRESS, 50000))
    return state


def login(client, *, as_json=True, **fields):
    data = {"username": "christopher", "password": "right-password", **fields}
    headers = {"Accept": "application/json"} if as_json else {}
    return client.post("/auth/login", data=data, headers=headers, follow_redirects=False)


def session_cookie(response) -> bool:
    return f"{get_settings().cookie_name}=" in response.headers.get("set-cookie", "")


# --- answers kept from before -----------------------------------------------------

def test_a_right_password_signs_in_and_counts_as_the_accounts_success(site):
    attempt, session = ScriptedCursor(account_row(), no_failures()), ScriptedCursor()
    site.cursors.extend([attempt, session])
    response = login(site.client)
    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True, "redirect": "/dashboard/profile/"}
    assert session_cookie(response)
    assert attempt.sql("INSERT INTO sign_in_attempt")[0][1] == (USER_ID, None, None, True)
    assert attempt.outcome == "committed"
    assert session.sql("INSERT INTO web_session")[0][1][0] == USER_ID
    assert site.subscriptions == []


def test_a_wrong_password_is_still_401_and_now_counts(site):
    attempt = ScriptedCursor(account_row("another-password"), no_failures())
    site.cursors.append(attempt)
    response = login(site.client)
    assert response.status_code == 401
    assert response.json() == {"ok": False, "detail": "Incorrect username or password"}
    assert "retry-after" not in response.headers and not session_cookie(response)
    assert attempt.sql("INSERT INTO sign_in_attempt")[0][1] == (USER_ID, None, None, False)
    assert attempt.sql("DELETE FROM sign_in_attempt WHERE attempted_at < now() - %s")
    # Committed before the answer, so the failure counts toward the limit.
    assert attempt.outcome == "committed"
    assert site.used == [attempt]


def test_a_wrong_password_form_post_still_goes_back_to_login(site):
    site.cursors.append(ScriptedCursor(account_row("another-password"), no_failures()))
    response = login(site.client, as_json=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=bad-login"


def test_a_right_password_with_an_unconfirmed_email_is_still_403_and_counts_as_a_success(site):
    attempt, subscription = ScriptedCursor(account_row(confirmed=False), no_failures()), ScriptedCursor()
    site.cursors.extend([attempt, subscription])
    response = login(site.client, news_opt_in="on")
    assert response.status_code == 403
    assert response.json()["code"] == "email_unverified"
    assert not session_cookie(response)
    assert attempt.sql("INSERT INTO sign_in_attempt")[0][1] == (USER_ID, None, None, True)
    # The opt-in still waits for the confirmation, as before.
    assert site.subscriptions == [(USER_ID, True, "login")]
    assert site.used == [attempt, subscription]


def test_the_username_is_trimmed_as_before_and_looked_up_as_the_game_does(site):
    attempt = ScriptedCursor(account_row("another-password"), no_failures())
    site.cursors.append(attempt)
    login(site.client, username="  Christopher \t")
    find_sql, find_params = attempt.executions[0]
    assert find_params == {"username": "Christopher"}
    assert "lower(u.username) = lower(btrim(%(username)s))" in find_sql
    assert "encode(sha256(convert_to(lower(btrim(%(username)s)), 'UTF8')), 'hex')" in find_sql


# --- the game's limits ------------------------------------------------------------

def test_an_unknown_username_spends_a_password_check_and_answers_like_a_wrong_password(site, monkeypatch):
    checked_hashes = []
    real_verify = sign_in_attempts.verify_password

    def recording_verify(password, hashed):
        checked_hashes.append(hashed)
        return real_verify(password, hashed)

    monkeypatch.setattr(sign_in_attempts, "verify_password", recording_verify)
    attempt = ScriptedCursor(no_account(), no_failures())
    site.cursors.append(attempt)
    response = login(site.client, username="nobody")
    assert checked_hashes == [sign_in_attempts.decoy_hash()]
    assert response.status_code == 401
    assert response.json() == {"ok": False, "detail": "Incorrect username or password"}
    _, lock_params = attempt.sql("pg_advisory_xact_lock(hashtext('theumst.sign-in.username')")[0]
    assert lock_params == (TYPED_HASH,)
    assert attempt.sql("INSERT INTO sign_in_attempt")[0][1] == (None, TYPED_HASH, None, False)


def test_too_many_wrong_passwords_for_an_account_is_429_with_retry_after(site, monkeypatch):
    def no_check(password, hashed):
        raise AssertionError("a refused attempt must not check the password")

    monkeypatch.setattr(sign_in_attempts, "verify_password", no_check)
    attempt = ScriptedCursor(account_row(), {"failures": 10, "wait_seconds": 312})
    site.cursors.append(attempt)
    response = login(site.client, news_opt_in="on")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "312"
    assert response.json() == {"ok": False, "detail": WAIT_DETAIL, "code": "too_many_attempts", "retry_after": 312}
    # Refused before the password is checked; the refusal itself is not an attempt.
    assert not attempt.sql("INSERT INTO sign_in_attempt")
    assert not session_cookie(response) and site.subscriptions == []
    assert site.used == [attempt]


def test_too_many_wrong_passwords_from_one_public_address_is_429(site):
    attempt = ScriptedCursor(account_row(), no_failures(), {"failures": 30, "wait_seconds": 45})
    site.cursors.append(attempt)
    response = login(site.public_client)
    assert response.status_code == 429
    assert response.json()["retry_after"] == 45 and response.headers["retry-after"] == "45"
    account_lock = attempt.index("hashtext('theumst.sign-in.account')")
    address_lock = attempt.index("hashtext('theumst.sign-in.address')")
    assert account_lock < address_lock < attempt.index("FROM sign_in_attempt WHERE")
    assert attempt.executions[address_lock][1] == (PUBLIC_ADDRESS,)


def test_a_refused_form_post_goes_back_to_login_with_the_wait(site):
    site.cursors.append(ScriptedCursor(account_row(), {"failures": 12, "wait_seconds": 312}))
    response = login(site.client, as_json=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=too-many-attempts&retry_after=312"
    # On a redirect, Retry-After would ask the browser to wait before following it.
    assert "retry-after" not in response.headers


def test_the_login_sends_exactly_the_checks_the_games_sign_in_sends(site, monkeypatch):
    website = ScriptedCursor(account_row("another-password"), no_failures(), no_failures())
    site.cursors.append(website)
    assert login(site.public_client).status_code == 401

    in_game = ScriptedCursor(account_row("another-password"), no_failures(), no_failures())

    @contextmanager
    def game_transaction():
        yield None, in_game

    monkeypatch.setattr(game, "transaction", game_transaction)
    application = FastAPI()
    application.include_router(game.router)
    game.install_error_handlers(application)
    response = TestClient(application, client=(PUBLIC_ADDRESS, 50000)).post(
        "/api/game/sign-in", json={"username": "christopher", "password": "right-password", "computer": "PC"},
    )
    assert response.status_code == 401
    # The same lookup, locks, counts and record, in the same order with the same values.
    assert website.executions == in_game.executions
    assert [text.split()[0] for text, _ in website.executions] == [
        "SELECT", "SELECT", "SELECT", "SELECT", "SELECT", "DELETE", "INSERT",
    ]
