from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

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

    def sql_containing(self, fragment):
        return [(sql, params) for sql, params in self.statements if fragment in sql]


def make_transaction(cursor):
    @contextmanager
    def fake():
        yield None, cursor
    return fake


def regular_key(**overrides):
    key = {
        "api_key_id": 5, "user_id": 2, "name": "reader", "key_prefix": "umst_read_abcdef",
        "key_type": "regular", "client": None, "api_rate_id": 1,
        "requests_per_minute": 600, "level_name": "standard",
        "username": "reader", "authority_type": "user",
    }
    key.update(overrides)
    return key


def master_key():
    return {
        "api_key_id": 6, "user_id": 3, "name": "master", "key_prefix": "umst_mstr_abcdef",
        "key_type": "master", "client": None, "api_rate_id": None,
        "requests_per_minute": None, "level_name": None,
        "username": "admin", "authority_type": "admin",
    }


def authenticate(monkeypatch, cursor, *, kind, headers=None, **options):
    monkeypatch.setattr(dependencies, "transaction", make_transaction(cursor))
    request = SimpleNamespace(headers={"x-api-key": "secret"} if headers is None else headers)
    return dependencies.authenticate_api_key(request, kind=kind, **options)


def test_regular_book_read_counts_in_its_own_minute_window_and_daily_usage(monkeypatch):
    cursor = Cursor(regular_key(), {"request_count": 4, "retry_after": 37})
    result = authenticate(monkeypatch, cursor, kind="book")
    assert cursor.statements[0][1] == (hash_secret("secret"),)
    assert "r.requests_per_minute" in cursor.statements[0][0]
    window_sql, window_params = cursor.sql_containing("INSERT INTO api_rate_window")[0]
    assert window_params == (5, "book")
    assert "ON CONFLICT (api_key_id, kind)" in window_sql
    assert "interval '1 minute'" in window_sql and "interval '1 hour'" not in window_sql
    usage_sql, usage_params = cursor.sql_containing("INSERT INTO api_usage_daily")[0]
    assert usage_params == (5, "book")
    assert "ON CONFLICT (api_key_id, day, kind)" in usage_sql
    assert "AT TIME ZONE 'UTC'" in usage_sql
    assert cursor.sql_containing("UPDATE api_key SET last_used_at")
    assert result["rate_limit"] == 600
    assert result["rate_remaining"] == 596
    assert result["kind"] == "book"


def test_character_calls_use_a_separate_window_from_book_reads(monkeypatch):
    cursor = Cursor(regular_key(), {"request_count": 1, "retry_after": 60})
    result = authenticate(monkeypatch, cursor, kind="character")
    assert cursor.sql_containing("INSERT INTO api_rate_window")[0][1] == (5, "character")
    assert cursor.sql_containing("INSERT INTO api_usage_daily")[0][1] == (5, "character")
    assert result["rate_remaining"] == 599


def test_exceeding_the_minute_answers_429_with_retry_after_seconds_and_counts_nothing(monkeypatch):
    cursor = Cursor(regular_key(requests_per_minute=600), {"request_count": 601, "retry_after": 23})
    with pytest.raises(HTTPException) as refused:
        authenticate(monkeypatch, cursor, kind="book")
    assert refused.value.status_code == 429
    assert refused.value.headers == {"Retry-After": "23"}
    assert "600 book requests per minute" in refused.value.detail
    # The refusal is raised inside the transaction, which rolls the window back;
    # usage and last-used are never written for it.
    assert not cursor.sql_containing("api_usage_daily")
    assert not cursor.sql_containing("last_used_at")


def test_the_last_request_of_the_minute_is_accepted(monkeypatch):
    cursor = Cursor(regular_key(requests_per_minute=600), {"request_count": 600, "retry_after": 1})
    result = authenticate(monkeypatch, cursor, kind="character")
    assert result["rate_remaining"] == 0


def test_a_tier_without_allowance_is_refused_before_counting(monkeypatch):
    cursor = Cursor(regular_key(requests_per_minute=0))
    with pytest.raises(HTTPException) as refused:
        authenticate(monkeypatch, cursor, kind="book")
    assert refused.value.status_code == 429
    assert not cursor.sql_containing("api_rate_window")


def test_master_key_is_unlimited_but_its_usage_is_recorded(monkeypatch):
    cursor = Cursor(master_key())
    result = authenticate(
        monkeypatch, cursor, kind="book", headers={"authorization": "Bearer secret"}, master_required=True,
    )
    assert result["rate_remaining"] is None and result["rate_limit"] is None
    assert not cursor.sql_containing("api_rate_window")
    assert cursor.sql_containing("INSERT INTO api_usage_daily")[0][1] == (6, "book")


def test_regular_key_cannot_use_a_master_route_and_is_not_counted(monkeypatch):
    cursor = Cursor(regular_key())
    with pytest.raises(HTTPException) as refused:
        authenticate(monkeypatch, cursor, kind="book", master_required=True)
    assert refused.value.status_code == 403
    assert not cursor.sql_containing("api_rate_window")
    assert not cursor.sql_containing("api_usage_daily")


def test_unknown_or_revoked_key_is_401(monkeypatch):
    cursor = Cursor(None)
    with pytest.raises(HTTPException) as refused:
        authenticate(monkeypatch, cursor, kind="character")
    assert refused.value.status_code == 401
    assert "k.revoked_at IS NULL" in cursor.statements[0][0]
    assert "u.email_verified_at IS NOT NULL" in cursor.statements[0][0]


def test_missing_key_is_401_without_touching_the_database(monkeypatch):
    cursor = Cursor(regular_key())
    with pytest.raises(HTTPException) as refused:
        authenticate(monkeypatch, cursor, kind="book", headers={})
    assert refused.value.status_code == 401
    assert cursor.statements == []


def test_an_unknown_kind_is_a_programming_error(monkeypatch):
    cursor = Cursor(regular_key())
    with pytest.raises(ValueError, match="Unknown API request kind"):
        authenticate(monkeypatch, cursor, kind="search")
    assert cursor.statements == []
