"""Opt-in real PostgreSQL checks of the wrong-password limits around a password reset.

Set THEUMST_SIGN_IN_DB_TESTS=1 with LOCAL loopback database settings and a
PostgreSQL account that may create a database. The fixture builds a UUID-named
database from schema.sql and drops it afterwards; the configured database is
untouched. Requests go through /auth/login, /api/game/sign-in and
/auth/reset-password, so the counts, now() and the transactions are
PostgreSQL's own. No email is sent: the reset links are written to the database
as /auth/forgot-password leaves them once emailed.
"""
from __future__ import annotations

import os
from datetime import timedelta
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2.extras import RealDictCursor

from app import database
from app.config import get_settings
from app.main import create_app
from app.security import hash_password, hash_secret, verify_password
from app.services import sign_in_attempts


pytestmark = pytest.mark.skipif(
    os.getenv("THEUMST_SIGN_IN_DB_TESTS") != "1", reason="Explicit isolated PostgreSQL acceptance only"
)

HOME = "81.2.69.142"  # the player's public address
ELSEWHERE = "81.2.69.160"  # someone else's
OLD_PASSWORD = "old-passphrase-123"
NEW_PASSWORD = "new-passphrase-456"
INVALID_LINK = {"detail": "This reset link is invalid or has expired"}


@pytest.fixture(scope="module")
def application():
    from psycopg2 import sql
    settings = get_settings()
    assert settings.server == "LOCAL" and settings.db_host in {"127.0.0.1", "localhost"}
    name = f"theumst_sign_in_test_{uuid4().hex}"
    admin = database.connect()
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))

    def connect():
        return psycopg2.connect(dbname=name, user=settings.db_user, password=settings.db_password,
                                host=settings.db_host, port=settings.db_port, cursor_factory=RealDictCursor)

    patch = pytest.MonkeyPatch()
    patch.setattr(database, "connect", connect)
    try:
        with database.transaction() as (_, cur):
            cur.execute((settings.sql_dir / "schema.sql").read_text(encoding="utf-8"))
        yield create_app(initialize_services=False)
    finally:
        patch.undo()
        with admin.cursor() as cur:
            cur.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


@pytest.fixture(autouse=True)
def no_attempts_yet(application):
    # Every address starts each test with no wrong passwords.
    with database.transaction() as (_, cur):
        cur.execute('TRUNCATE "user", sign_in_attempt CASCADE')


def at(application, address, **options):
    return TestClient(application, client=(address, 50000), **options)


def account():
    username = f"player_{uuid4().hex[:12]}"
    with database.transaction() as (_, cur):
        cur.execute(
            '''INSERT INTO "user" (username, email, password_hash, authority_id, email_verified_at)
               SELECT %s, %s, %s, authority_id, now() FROM authority WHERE name = 'user'
               RETURNING user_id''',
            (username, f"{username}@example.invalid", hash_password(OLD_PASSWORD)),
        )
        return {"user_id": cur.fetchone()["user_id"], "username": username}


def reset_link(user, *, expires_in=timedelta(hours=1), sent=True, used=False):
    token = uuid4().hex + uuid4().hex
    with database.transaction() as (_, cur):
        cur.execute(
            """
            INSERT INTO password_reset_token (user_id, token_hash, expires_at, sent_at, used_at)
            VALUES (%s, %s, now() + %s, CASE WHEN %s THEN now() END, CASE WHEN %s THEN now() END)
            """,
            (user["user_id"], hash_secret(token), expires_in, sent, used),
        )
    return token


def login(client, user, password):
    return client.post("/auth/login", data={"username": user["username"], "password": password},
                       headers={"Accept": "application/json"})


def game_sign_in(client, user, password):
    return client.post("/api/game/sign-in",
                       json={"username": user["username"], "password": password, "computer": "PC"})


def reset(client, token):
    return client.post("/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD})


def attempts(user):
    """The account's recorded attempts, oldest first, as (address, succeeded)."""
    with database.transaction() as (_, cur):
        cur.execute(
            """
            SELECT host(address) AS address, succeeded FROM sign_in_attempt
            WHERE user_id = %s ORDER BY attempted_at, sign_in_attempt_id
            """,
            (user["user_id"],),
        )
        return [(row["address"], row["succeeded"]) for row in cur.fetchall()]


def lock_out(client, user):
    """Ten wrong passwords, at the website and in the game alike, lock the account."""
    for turn in range(sign_in_attempts.MAX_FAILURES_PER_USERNAME):
        response = login(client, user, "forgotten") if turn % 2 else game_sign_in(client, user, "forgotten")
        assert response.status_code == 401, response.text
    assert_waits(client, user, OLD_PASSWORD)


def assert_waits(client, user, password):
    """The website's login and the game's sign-in both refuse even the right password."""
    website = login(client, user, password)
    assert website.status_code == 429, website.text
    assert website.json()["code"] == "too_many_attempts" and website.json()["retry_after"] > 0
    game = game_sign_in(client, user, password)
    assert game.status_code == 429, game.text
    assert game.json()["code"] == "too_many_attempts"


def assert_signs_in(client, user, password):
    website = login(client, user, password)
    assert website.status_code == 200, website.text
    assert website.json() == {"ok": True, "redirect": "/dashboard/profile/"}
    game = game_sign_in(client, user, password)
    assert game.status_code == 200, game.text
    assert game.json()["user_id"] == user["user_id"]


def test_a_reset_lets_a_locked_out_account_sign_in_at_once(application):
    player, home = account(), at(application, HOME)
    lock_out(home, player)

    assert reset(home, reset_link(player)).json() == {"ok": True, "redirect": "/login?reset=success"}
    # The wrong passwords stay; the reset added a right password with no address.
    assert attempts(player) == [(HOME, False)] * 10 + [(None, True)]
    assert_signs_in(home, player, NEW_PASSWORD)


def test_after_a_reset_an_address_past_its_limit_still_waits(application):
    player, home, elsewhere = account(), at(application, HOME), at(application, ELSEWHERE)
    # Someone elsewhere locks the account, then reaches the address's thirty on
    # usernames no account has.
    lock_out(elsewhere, player)
    assert_waits(home, player, OLD_PASSWORD)
    for turn in range(sign_in_attempts.MAX_FAILURES_PER_ADDRESS - sign_in_attempts.MAX_FAILURES_PER_USERNAME):
        assert login(elsewhere, {"username": f"nobody-{turn}"}, "guess").status_code == 401

    assert reset(home, reset_link(player)).status_code == 200
    assert_signs_in(home, player, NEW_PASSWORD)
    # The address that guessed keeps its count: even the new password waits there.
    assert_waits(elsewhere, player, NEW_PASSWORD)


def test_a_reset_link_that_is_unknown_expired_unsent_or_used_clears_nothing(application):
    player, home = account(), at(application, HOME)
    lock_out(home, player)
    recorded = attempts(player)
    for token in (
        "x" * 40,
        reset_link(player, expires_in=timedelta(minutes=-1)),
        reset_link(player, sent=False),
        reset_link(player, used=True),
    ):
        refused = reset(home, token)
        assert refused.status_code == 400 and refused.json() == INVALID_LINK

    assert attempts(player) == recorded
    assert_waits(home, player, OLD_PASSWORD)
    with database.transaction() as (_, cur):
        cur.execute('SELECT password_hash FROM "user" WHERE user_id = %s', (player["user_id"],))
        assert verify_password(OLD_PASSWORD, cur.fetchone()["password_hash"])


def test_a_reset_that_fails_after_clearing_the_count_clears_nothing(application, monkeypatch):
    player, home = account(), at(application, HOME)
    lock_out(home, player)
    token = reset_link(player)
    clear_account = sign_in_attempts.clear_account

    def clear_then_fail(cur, user_id):
        clear_account(cur, user_id)
        raise RuntimeError("the reset fails after clearing the count")

    with monkeypatch.context() as failing:
        failing.setattr(sign_in_attempts, "clear_account", clear_then_fail)
        assert reset(at(application, HOME, raise_server_exceptions=False), token).status_code == 500

    # The clearing shared the reset's transaction and went back with it.
    assert attempts(player) == [(HOME, False)] * 10
    assert_waits(home, player, OLD_PASSWORD)
    # The link was not spent, so it still works.
    assert reset(home, token).status_code == 200
    assert_signs_in(home, player, NEW_PASSWORD)
