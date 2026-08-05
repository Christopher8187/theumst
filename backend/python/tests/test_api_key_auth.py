from contextlib import contextmanager
from types import SimpleNamespace

from app import dependencies
from app.security import hash_secret


class Cursor:
    def __init__(self, key, window=None):
        self.key = key
        self.window = window
        self.fetch_count = 0
        self.statements = []

    def execute(self, sql, params):
        self.statements.append((sql, params))

    def fetchone(self):
        self.fetch_count += 1
        return self.key if self.fetch_count == 1 else self.window


def make_transaction(cursor):
    @contextmanager
    def fake():
        yield None, cursor
    return fake


def test_regular_key_uses_rate_window(monkeypatch):
    key = {
        "api_key_id": 5, "user_id": 2, "name": "reader", "key_type": "regular",
        "api_rate_id": 1, "searches_per_hour": 120, "level_name": "standard",
        "username": "reader", "authority_type": "user",
    }
    cursor = Cursor(key, {"window_started_at": "now", "request_count": 4})
    monkeypatch.setattr(dependencies, "transaction", make_transaction(cursor))
    request = SimpleNamespace(headers={"x-api-key": "secret"})
    result = dependencies.authenticate_api_key(request)
    assert result["rate_remaining"] == 116
    assert any("INSERT INTO api_rate_window" in sql for sql, _ in cursor.statements)
    assert cursor.statements[0][1] == (hash_secret("secret"),)


def test_master_key_bypasses_rate_window(monkeypatch):
    key = {
        "api_key_id": 6, "user_id": 3, "name": "master", "key_type": "master",
        "api_rate_id": None, "searches_per_hour": None, "level_name": None,
        "username": "admin", "authority_type": "admin",
    }
    cursor = Cursor(key)
    monkeypatch.setattr(dependencies, "transaction", make_transaction(cursor))
    request = SimpleNamespace(headers={"authorization": "Bearer secret"})
    result = dependencies.authenticate_api_key(request, master_required=True)
    assert result["rate_remaining"] is None
    assert not any("api_rate_window" in sql for sql, _ in cursor.statements)
