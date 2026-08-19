from dataclasses import replace

from app.config import get_settings
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
