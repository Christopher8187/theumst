from contextlib import contextmanager
from dataclasses import replace

import pytest
from fastapi import HTTPException

from app.config import get_settings
from app.routers import auth
from app.schemas import ResetPasswordRequest
from app.services.email import build_email_verification_message, build_password_reset_message


def test_reset_email_contains_one_use_link_without_leaking_credentials():
    settings = replace(
        get_settings(),
        smtp_host="smtp.example.test",
        smtp_password="not-an-email-body-secret",
        smtp_from_email="accounts@theumst.com",
        smtp_from_name="theumst",
        password_reset_ttl_minutes=60,
    )
    link = "https://theumst.com/reset-password?token=one-use-token"
    message = build_password_reset_message("person@example.com", link, settings=settings)
    assert message["To"] == "person@example.com"
    assert message["From"] == "theumst <accounts@theumst.com>"
    assert link in message.get_body(preferencelist=("plain",)).get_content()
    assert "60 minutes" in message.get_body(preferencelist=("plain",)).get_content()
    assert "not-an-email-body-secret" not in message.as_string()


def test_new_password_requires_at_least_eight_characters():
    payload = ResetPasswordRequest(token="x" * 32, new_password="long-enough")
    assert payload.new_password == "long-enough"


def test_email_verification_message_contains_one_use_link():
    settings = replace(
        get_settings(),
        smtp_host="smtp.example.test",
        smtp_from_email="accounts@theumst.com",
        smtp_from_name="theumst",
        email_verification_ttl_hours=24,
    )
    link = "https://theumst.com/verify-email?token=one-use-token"
    message = build_email_verification_message("person@example.com", link, settings=settings)
    plain = message.get_body(preferencelist=("plain",)).get_content()
    assert message["To"] == "person@example.com"
    assert link in plain
    assert "24 hours" in plain
    assert "only be used once" in plain


class ResetCursor:
    def __init__(self, *results):
        self.results = list(results)
        self.executions = []

    def execute(self, sql, params=None):
        self.executions.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.results.pop(0)

    def fetchall(self):
        return self.results.pop(0)


def test_a_password_reset_revokes_the_games_keys_and_frees_their_characters(monkeypatch):
    cursor = ResetCursor({"password_reset_token_id": 2, "user_id": 7}, [{"api_key_id": 41}])
    committed = []

    @contextmanager
    def one_transaction():
        yield None, cursor
        committed.append(cursor)

    monkeypatch.setattr(auth, "transaction", one_transaction)
    result = auth.reset_password(ResetPasswordRequest(token="x" * 32, new_password="long-enough"))
    assert result == {"ok": True, "redirect": "/login?reset=success"}
    statements = [sql for sql, _ in cursor.executions]
    sessions = next(i for i, sql in enumerate(statements) if sql.startswith("UPDATE web_session"))
    keys = next(i for i, sql in enumerate(statements) if sql.startswith("UPDATE api_key SET revoked_at = now()"))
    leases = next(i for i, sql in enumerate(statements) if sql.startswith('UPDATE "character" SET lease_api_key_id = NULL'))
    assert sessions < keys < leases
    assert cursor.executions[keys][1] == (7, "umst")
    assert cursor.executions[leases][1] == ([41],)
    # The same transaction as the new password.
    assert committed == [cursor]


def one_transaction_for(monkeypatch, cursor):
    """Run the reset on `cursor` and note whether its transaction commits."""
    outcomes = []

    @contextmanager
    def one_transaction():
        try:
            yield None, cursor
        except Exception:
            outcomes.append("rolled back")
            raise
        outcomes.append("committed")

    monkeypatch.setattr(auth, "transaction", one_transaction)
    return outcomes


def test_a_password_reset_clears_the_accounts_wrong_password_count_in_its_own_transaction(monkeypatch):
    cursor = ResetCursor({"password_reset_token_id": 2, "user_id": 7}, [])
    outcomes = one_transaction_for(monkeypatch, cursor)
    auth.reset_password(ResetPasswordRequest(token="x" * 32, new_password="long-enough"))
    statements = [sql for sql, _ in cursor.executions]
    password = next(i for i, sql in enumerate(statements) if sql.startswith('UPDATE "user" SET password_hash'))
    cleared = [i for i, sql in enumerate(statements) if "sign_in_attempt" in sql]
    assert len(cleared) == 1 and password < cleared[0]
    # A right password for the account, with no address: the account's count
    # starts again. No wrong password is removed or changed, so each address
    # keeps its count.
    assert cursor.executions[cleared[0]] == (
        "INSERT INTO sign_in_attempt (user_id, username_hash, address, succeeded) VALUES (%s, NULL, NULL, true)",
        (7,),
    )
    assert outcomes == ["committed"]


def test_a_reset_link_that_is_unknown_used_unsent_or_expired_changes_nothing(monkeypatch):
    cursor = ResetCursor(None)
    outcomes = one_transaction_for(monkeypatch, cursor)
    with pytest.raises(HTTPException) as refused:
        auth.reset_password(ResetPasswordRequest(token="x" * 32, new_password="long-enough"))
    assert refused.value.status_code == 400
    # Only the lookup ran: no new password, and the count of wrong passwords stays.
    [(lookup, _)] = cursor.executions
    assert lookup.startswith("SELECT password_reset_token_id, user_id FROM password_reset_token")
    for condition in ("used_at IS NULL", "sent_at IS NOT NULL", "expires_at > now()"):
        assert condition in lookup
    assert outcomes == ["rolled back"]
