"""The master-key check of 0.0.17, POST /api/game/master-key, with a stand-in for PostgreSQL.

A debug export of the game unlocks its debug powers only once theumst.com says the key typed
into it is a master key. These establish the answers and their shapes, that the check reads
one row and writes nothing, that it never logs or returns the key, and its limits.
test_key_access_postgres.py checks the same route against PostgreSQL's own keys.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import game
from app.security import hash_secret
from app.services import sign_in_attempts


MASTER = "umst_master_test-master-key-0123456789"
REGULAR = "umst_read_test-regular-key-0123456789"
UNKNOWN = "umst_read_test-unknown-key-0123456789"
INSTALL = {"X-Install-Id": "k7m2qx"}
PATH = "/api/game/master-key"


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Cursor:
    def __init__(self, state):
        self.state = state
        self.result = None

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        self.state.statements.append((text, params))
        assert text.startswith("SELECT k.key_type FROM api_key k"), text
        self.result = self.state.keys.get(params[0])

    def fetchone(self):
        return self.result


@pytest.fixture
def api(monkeypatch):
    state = SimpleNamespace(statements=[], clock=Clock(), address="203.0.113.5")
    # Only active keys of confirmed accounts are found; the query's own WHERE decides that.
    state.keys = {hash_secret(MASTER): {"key_type": "master"}, hash_secret(REGULAR): {"key_type": "regular"}}

    @contextmanager
    def transaction():
        yield None, Cursor(state)

    def no_key_check(*args, **kwargs):
        raise AssertionError("the master-key check counts nothing against the key")

    monkeypatch.setattr(game, "transaction", transaction)
    monkeypatch.setattr(game, "authenticate_api_key", no_key_check)
    monkeypatch.setattr(game, "master_checks", game.MasterChecks(clock=state.clock))
    monkeypatch.setattr(sign_in_attempts, "public_address", lambda request: state.address)
    application = FastAPI()
    application.include_router(game.router)
    game.install_error_handlers(application)
    state.client = TestClient(application)

    def check(key=None, **headers):
        sent = {**INSTALL, **headers}
        if key is not None:
            sent["X-API-Key"] = key
        return state.client.post(PATH, headers=sent)

    state.check = check
    return state


def assert_refused(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["code"] == code and isinstance(body["detail"], str) and body["detail"]
    assert response.headers["cache-control"] == "no-store"
    return body


def test_a_master_key_is_confirmed_and_nothing_else_is_said(api):
    response = api.check(MASTER)
    assert response.status_code == 200
    assert response.json() == {"master": True}
    assert response.headers["cache-control"] == "no-store"
    # One read of the key's hash, nothing written, the key itself never sent to the database.
    assert len(api.statements) == 1
    sql, params = api.statements[0]
    assert params == (hash_secret(MASTER),)
    assert "k.revoked_at IS NULL" in sql and "u.email_verified_at IS NOT NULL" in sql
    assert not any(word in sql for word in ("INSERT", "UPDATE", "DELETE", "FOR UPDATE"))


def test_the_key_may_come_as_a_bearer_token(api):
    response = api.client.post(PATH, headers={**INSTALL, "Authorization": f"Bearer {MASTER}"})
    assert response.status_code == 200 and response.json() == {"master": True}


def test_a_regular_key_is_403_not_master_key(api):
    body = assert_refused(api.check(REGULAR), 403, "not_master_key")
    assert set(body) == {"code", "detail"}


def test_an_unknown_revoked_or_unconfirmed_key_is_401(api):
    body = assert_refused(api.check(UNKNOWN), 401, "invalid_key")
    assert set(body) == {"code", "detail"}


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "   "}, {"Authorization": "Basic abc"},
                                     {"Authorization": "Bearer "}])
def test_no_key_is_401_before_the_database_and_is_not_counted(api, headers):
    for _ in range(game.MASTER_CHECKS_PER_ADDRESS + 1):
        assert_refused(api.client.post(PATH, headers={**INSTALL, **headers}), 401, "invalid_key")
    assert api.statements == []
    assert api.check(MASTER).status_code == 200


def test_a_malformed_install_id_is_422_before_the_key(api):
    assert_refused(api.client.post(PATH, headers={"X-Install-Id": "not valid!", "X-API-Key": MASTER}),
                   422, "invalid_request")
    assert api.statements == []


def test_the_key_is_never_logged_or_returned(api, caplog):
    caplog.set_level(logging.DEBUG)
    answers = [api.check(MASTER), api.check(REGULAR), api.check(UNKNOWN)]
    api.address = "198.51.100.9"
    for _ in range(game.MASTER_CHECKS_PER_ADDRESS + 1):
        answers.append(api.check(MASTER))
    assert answers[-1].status_code == 429
    for key in (MASTER, REGULAR, UNKNOWN):
        assert key not in caplog.text
        assert all(key not in answer.text and key not in str(answer.headers) for answer in answers)


def test_one_address_has_ten_checks_in_ten_minutes(api):
    for _ in range(game.MASTER_CHECKS_PER_ADDRESS):
        assert api.check(REGULAR).status_code == 403
    api.clock.now += 120
    response = api.check(MASTER)
    body = assert_refused(response, 429, "rate_limited")
    assert response.headers["retry-after"] == str(game.MASTER_CHECK_SECONDS - 120)
    assert body["retry_after"] == game.MASTER_CHECK_SECONDS - 120
    assert len(api.statements) == game.MASTER_CHECKS_PER_ADDRESS  # a refused check reads nothing
    # Another address is not held back, and this one may check again once the window has passed.
    api.address = "203.0.113.6"
    assert api.check(MASTER).status_code == 200
    api.address = "203.0.113.5"
    api.clock.now += game.MASTER_CHECK_SECONDS - 120
    assert api.check(MASTER).status_code == 200


def test_refused_checks_do_not_extend_the_wait(api):
    for _ in range(game.MASTER_CHECKS_PER_ADDRESS):
        api.check(REGULAR)
    for _ in range(20):
        api.clock.now += 10
        assert api.check(MASTER).status_code == 429
    api.clock.now = 1000.0 + game.MASTER_CHECK_SECONDS
    assert api.check(MASTER).status_code == 200


def test_everyone_together_has_sixty_checks_in_ten_minutes(api):
    for n in range(game.MASTER_CHECKS_IN_ALL):
        api.address = f"203.0.113.{n + 10}" if n % 2 else None  # some through private proxies
        assert api.check(REGULAR).status_code == 403
    api.address = "198.51.100.1"
    assert_refused(api.check(MASTER), 429, "rate_limited")
    api.address = None
    assert_refused(api.check(MASTER), 429, "rate_limited")
    api.clock.now += game.MASTER_CHECK_SECONDS
    assert api.check(MASTER).status_code == 200


def test_the_limiter_forgets_addresses_once_their_window_passes():
    clock = Clock()
    checks = game.MasterChecks(clock=clock)
    for n in range(30):
        assert checks.take(f"203.0.113.{n}") == 0
    clock.now += game.MASTER_CHECK_SECONDS
    assert checks.take("198.51.100.1") == 0
    assert set(checks._by_address) == {"198.51.100.1"}
    assert len(checks._all) == 1


def test_only_post_is_registered():
    from app.main import create_app

    application = create_app(initialize_services=False)
    methods = set()
    for route in application.routes:
        if getattr(route, "path", "") == PATH:
            methods |= route.methods
    assert methods == {"POST"}
