from contextlib import contextmanager
from datetime import date, datetime, timezone
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
    # An ordinary account: the 'user' authority's access points, no Web Demo.
    key = {
        "api_key_id": 5, "user_id": 2, "name": "reader", "key_prefix": "umst_read_abcdef",
        "key_type": "regular", "client": None, "api_rate_id": 1,
        "requests_per_minute": 600, "level_name": "standard",
        "username": "reader", "authority_type": "user", "access_points": ["api-keys", "profile"],
    }
    key.update(overrides)
    return key


def demo_reader_key(**overrides):
    # An account the Web Demo admits, such as one whose access request was approved.
    return regular_key(authority_type="betatester", access_points=["api-keys", "demo", "profile"], **overrides)


def master_key(**overrides):
    key = {
        "api_key_id": 6, "user_id": 3, "name": "master", "key_prefix": "umst_mstr_abcdef",
        "key_type": "master", "client": None, "api_rate_id": None,
        "requests_per_minute": None, "level_name": None,
        "username": "admin", "authority_type": "admin",
        "access_points": ["admin", "api-keys", "books", "demo", "media", "profile"],
    }
    key.update(overrides)
    return key


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
    assert window_params == (5, "book", 1)
    assert "ON CONFLICT (api_key_id, kind)" in window_sql
    assert "interval '1 minute'" in window_sql and "interval '1 hour'" not in window_sql
    usage_sql, usage_params = cursor.sql_containing("INSERT INTO api_usage_daily")[0]
    assert usage_params == (5, "book", 1)
    assert "ON CONFLICT (api_key_id, day, kind)" in usage_sql
    assert "AT TIME ZONE 'UTC'" in usage_sql
    assert cursor.sql_containing("UPDATE api_key SET last_used_at")
    assert result["rate_limit"] == 600
    assert result["rate_remaining"] == 596
    assert result["kind"] == "book"


def test_character_calls_use_a_separate_window_from_book_reads(monkeypatch):
    cursor = Cursor(regular_key(), {"request_count": 1, "retry_after": 60})
    result = authenticate(monkeypatch, cursor, kind="character")
    assert cursor.sql_containing("INSERT INTO api_rate_window")[0][1] == (5, "character", 1)
    assert cursor.sql_containing("INSERT INTO api_usage_daily")[0][1] == (5, "character", 1)
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


def test_a_tier_without_allowance_is_refused_with_retry_after_before_counting(monkeypatch):
    cursor = Cursor(regular_key(requests_per_minute=0))
    with pytest.raises(HTTPException) as refused:
        authenticate(monkeypatch, cursor, kind="book")
    assert refused.value.status_code == 429
    assert refused.value.headers == {"Retry-After": "60"}
    assert not cursor.sql_containing("api_rate_window")
    assert not cursor.sql_containing("api_usage_daily")


def test_a_route_that_refuses_master_keys_does_so_before_counting(monkeypatch):
    cursor = Cursor(master_key())
    with pytest.raises(HTTPException) as refused:
        authenticate(monkeypatch, cursor, kind="character", master_allowed=False)
    assert refused.value.status_code == 403
    assert not cursor.sql_containing("api_usage_daily")
    assert not cursor.sql_containing("last_used_at")


def test_regular_keys_pass_a_route_that_refuses_master_keys(monkeypatch):
    cursor = Cursor(regular_key(), {"request_count": 1, "retry_after": 60})
    result = authenticate(monkeypatch, cursor, kind="character", master_allowed=False)
    assert result["key_type"] == "regular"


def test_master_key_is_unlimited_but_its_usage_is_recorded(monkeypatch):
    cursor = Cursor(master_key())
    result = authenticate(
        monkeypatch, cursor, kind="book", headers={"authorization": "Bearer secret"}, master_required=True,
    )
    assert result["rate_remaining"] is None and result["rate_limit"] is None
    assert not cursor.sql_containing("api_rate_window")
    assert cursor.sql_containing("INSERT INTO api_usage_daily")[0][1] == (6, "book", 1)


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


# --- book reads need the Web Demo's access (0.0.13) ---------------------------

def test_the_key_query_reads_the_accounts_access_points_as_a_session_does(monkeypatch):
    cursor = Cursor(regular_key(), {"request_count": 1, "retry_after": 60})
    authenticate(monkeypatch, cursor, kind="book")
    sql = cursor.statements[0][0]
    # The authority's access points, from the map current_user reads for a session.
    assert "FROM authority_access_map aam" in sql
    assert "JOIN access ac ON ac.access_id = aam.access_id" in sql
    assert "WHERE aam.authority_id = a.authority_id" in sql
    assert ") AS access_points" in sql
    assert "FOR UPDATE OF k" in sql


def test_a_key_whose_account_the_web_demo_does_not_admit_is_refused_before_counting(monkeypatch):
    cursor = Cursor(regular_key())
    with pytest.raises(dependencies.AccessRefused) as refused:
        authenticate(monkeypatch, cursor, kind="book", access_point=dependencies.DEMO_ACCESS_POINT)
    assert refused.value.status_code == 403
    assert refused.value.code == "demo_access_required"
    assert "Web Demo access" in refused.value.detail
    assert not cursor.sql_containing("api_rate_window")
    assert not cursor.sql_containing("api_usage_daily")
    assert not cursor.sql_containing("last_used_at")


def test_a_key_whose_account_the_web_demo_admits_reads_books_and_is_counted(monkeypatch):
    cursor = Cursor(demo_reader_key(), {"request_count": 3, "retry_after": 50})
    result = authenticate(monkeypatch, cursor, kind="book", access_point="demo")
    assert result["rate_remaining"] == 597
    assert cursor.sql_containing("INSERT INTO api_rate_window")[0][1] == (5, "book", 1)
    assert cursor.sql_containing("INSERT INTO api_usage_daily")[0][1] == (5, "book", 1)


@pytest.mark.parametrize("access_points", [[], ["api-keys", "profile"], None])
def test_a_master_key_keeps_its_book_access_whatever_its_account(monkeypatch, access_points):
    cursor = Cursor(master_key(access_points=access_points))
    result = authenticate(monkeypatch, cursor, kind="book", access_point="demo")
    assert result["key_type"] == "master"
    assert cursor.sql_containing("INSERT INTO api_usage_daily")[0][1] == (6, "book", 1)


def test_without_an_access_point_any_account_passes(monkeypatch):
    # The game's calls ask for no access point, so every confirmed account's key works.
    cursor = Cursor(regular_key(access_points=[]), {"request_count": 1, "retry_after": 60})
    result = authenticate(monkeypatch, cursor, kind="character", master_allowed=False)
    assert result["key_type"] == "regular"
    assert cursor.sql_containing("INSERT INTO api_usage_daily")[0][1] == (5, "character", 1)


def test_a_regular_key_on_a_master_route_is_told_it_needs_a_master_key(monkeypatch):
    cursor = Cursor(regular_key())
    with pytest.raises(HTTPException) as refused:
        authenticate(monkeypatch, cursor, kind="book", master_required=True, access_point="demo")
    assert refused.value.status_code == 403
    assert not isinstance(refused.value, dependencies.AccessRefused)


def test_has_api_key_looks_where_the_key_is_read():
    assert dependencies.has_api_key(SimpleNamespace(headers={"x-api-key": "secret"}))
    assert dependencies.has_api_key(SimpleNamespace(headers={"authorization": "Bearer secret"}))
    assert not dependencies.has_api_key(SimpleNamespace(headers={"x-api-key": "  "}))
    assert not dependencies.has_api_key(SimpleNamespace(headers={"authorization": "Basic abc"}))
    assert not dependencies.has_api_key(SimpleNamespace(headers={}))


# --- a request counting as several (0.0.18) -------------------------------------

WINDOW_STARTED = datetime(2026, 11, 16, 12, 0, 0, 123456, tzinfo=timezone.utc)


def test_a_figure_batch_counts_as_many_requests_as_it_asks_for(monkeypatch):
    window = {"request_count": 70, "retry_after": 30, "window_started_at": WINDOW_STARTED, "usage_day": date(2026, 11, 16)}
    cursor = Cursor(demo_reader_key(), window)
    result = authenticate(monkeypatch, cursor, kind="book", access_point="demo", cost=64)
    window_sql, window_params = cursor.sql_containing("INSERT INTO api_rate_window")[0]
    assert window_params == (5, "book", 64)
    # A new window starts at the cost, and a running one adds it.
    assert "THEN EXCLUDED.request_count" in window_sql
    assert "ELSE api_rate_window.request_count + EXCLUDED.request_count END" in window_sql
    usage_sql, usage_params = cursor.sql_containing("INSERT INTO api_usage_daily")[0]
    assert usage_params == (5, "book", 64)
    assert "api_usage_daily.request_count + EXCLUDED.request_count" in usage_sql
    assert result["rate_remaining"] == 530
    assert result["rate_window_started_at"] == WINDOW_STARTED and result["usage_day"] == date(2026, 11, 16)


def test_a_request_counting_past_the_minute_is_refused_and_counts_nothing(monkeypatch):
    # 598 counted before, and 3 more asked: refused, though 2 were left.
    cursor = Cursor(demo_reader_key(), {"request_count": 601, "retry_after": 12})
    with pytest.raises(HTTPException) as refused:
        authenticate(monkeypatch, cursor, kind="book", access_point="demo", cost=3)
    assert refused.value.status_code == 429 and refused.value.headers == {"Retry-After": "12"}
    assert not cursor.sql_containing("api_usage_daily")
    assert not cursor.sql_containing("last_used_at")


@pytest.mark.parametrize("cost", [0, -1])
def test_a_request_counts_at_least_once(monkeypatch, cost):
    cursor = Cursor(regular_key())
    with pytest.raises(ValueError, match="at least once"):
        authenticate(monkeypatch, cursor, kind="book", cost=cost)
    assert cursor.statements == []


def test_what_a_request_did_not_use_goes_back_to_its_window_and_day(monkeypatch):
    cursor = Cursor(None)
    monkeypatch.setattr(dependencies, "transaction", make_transaction(cursor))
    key = demo_reader_key(kind="book", rate_window_started_at=WINDOW_STARTED, usage_day=date(2026, 11, 16))
    dependencies.return_api_requests(key, 17)
    window_sql, window_params = cursor.sql_containing("UPDATE api_rate_window")[0]
    # Only to the window it was counted in: a window that started since keeps its count.
    assert "window_started_at = %s" in window_sql and "GREATEST(0, request_count - %s)" in window_sql
    assert window_params == (17, 5, "book", WINDOW_STARTED)
    usage_sql, usage_params = cursor.sql_containing("UPDATE api_usage_daily")[0]
    assert "day = %s" in usage_sql and usage_params == (17, 5, "book", date(2026, 11, 16))


@pytest.mark.parametrize(("count", "known"), [(0, True), (-3, True), (5, False)])
def test_nothing_goes_back_when_nothing_is_unused_or_no_window_counted_it(monkeypatch, count, known):
    cursor = Cursor(None)
    monkeypatch.setattr(dependencies, "transaction", make_transaction(cursor))
    extra = {"rate_window_started_at": WINDOW_STARTED, "usage_day": date(2026, 11, 16)} if known else {}
    dependencies.return_api_requests(master_key(kind="book", **extra) if not known else regular_key(kind="book", **extra), count)
    assert cursor.statements == []
