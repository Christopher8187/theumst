from contextlib import contextmanager
from dataclasses import replace

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
