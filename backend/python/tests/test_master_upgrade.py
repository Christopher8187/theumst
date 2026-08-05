from contextlib import contextmanager
from types import SimpleNamespace

from app.routers import api_keys


class Cursor:
    def execute(self, sql, params):
        self.sql = sql
        self.params = params
    def fetchone(self):
        return {"api_key_id": 7, "key_type": "master", "upgraded_at": "now"}


@contextmanager
def fake_transaction():
    yield None, Cursor()


def test_admin_can_upgrade_own_key(monkeypatch):
    monkeypatch.setattr(api_keys, "require_user", lambda request: {"user_id": 3, "authority_type": "admin"})
    monkeypatch.setattr(api_keys, "transaction", fake_transaction)
    result = api_keys.upgrade_master_key(7, SimpleNamespace())
    assert result["key"]["key_type"] == "master"
