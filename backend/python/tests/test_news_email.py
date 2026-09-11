from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import MediaPostPayload
from app.services.email import build_email_change_message, email_content
from app.services.news import ensure_news_delivery_configured, resend_key, send_resend, verify_webhook


def test_four_templates_are_escaped_accessible_and_use_runtime_expiry():
    settings = replace(get_settings(), password_reset_ttl_minutes=17, email_verification_ttl_hours=9,
                       smtp_host="mail.invalid", smtp_from_email="accounts@example.invalid")
    for kind in ("reset", "verify", "change", "news"):
        result = email_content(kind, "https://example.invalid/action?a=1&b=2", settings=settings,
                               title="<script>alert(1)</script>", introduction="A <b>quiet</b> page & tea.",
                               unsubscribe_url="https://example.invalid/stop")
        assert '<script>' not in result["html"]
        assert '<b>quiet</b>' not in result["html"]
        assert "role=\"presentation\"" in result["html"]
        assert "logo-email.png" in result["html"]
        assert "https://example.invalid/action?a=1&b=2" in result["text"]
        assert "a=1&amp;b=2" in result["html"]
        if kind == "reset":
            assert "17 minutes" in result["text"]
        if kind in {"verify", "change"}:
            assert "9 hours" in result["text"]
        assert ("Unsubscribe" in result["text"]) == (kind == "news")
    message = build_email_change_message("fixture@example.invalid", "https://example.invalid/confirm", settings=settings)
    assert message["Date"] and message["Message-ID"]
    assert "new" in message["Subject"]
    assert "create this account" not in message.get_body(preferencelist=("plain",)).get_content()


@pytest.mark.parametrize("url", ["javascript:alert(1)", "//bad.example", "/relative"])
def test_email_rejects_non_absolute_web_actions(url):
    with pytest.raises(ValueError):
        email_content("reset", url)


def test_announcement_is_explicit_and_cannot_announce_draft_or_empty_copy():
    assert MediaPostPayload(title="Quiet news", body="A full story").announce is False
    for payload in ({"status": "draft", "email_introduction": "Hello"},
                    {"status": "published", "email_introduction": "   "}):
        with pytest.raises(ValidationError):
            MediaPostPayload(title="Quiet news", body="A full story", announce=True, **payload)


def test_svix_official_vector_and_tampering_replay_rejection():
    body = b'{"event_type":"ping","data":{"success":true}}'
    headers = {"svix-id": "msg_loFOjxBNrRLzqYUf", "svix-timestamp": "1731705121",
               "svix-signature": "v1,rAvfW3dJ/X/qxhsaXPOyyCGmRKsaKWcsNccKXlIktD0="}
    secret = "whsec_plJ3nmyCDGBKInavdOK15jsl"
    assert verify_webhook(body, headers, secret, now=1731705121) == headers["svix-id"]
    for changed_body, changed_headers, now in (
        (body + b" ", headers, 1731705121), (body, {}, 1731705121),
        (body, headers, 1731705522), (body, headers, 1731704000),
    ):
        with pytest.raises(ValueError):
            verify_webhook(changed_body, changed_headers, secret, now=now)


def test_resend_uses_saved_payload_and_exact_idempotency_key(monkeypatch):
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, json={"id": "provider-fixture"}, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", post)
    settings = SimpleNamespace(resend_api_key="fixture-only", smtp_host="other.invalid", smtp_password="", smtp_from_email="a@example.invalid")
    payload = {"subject": "A quiet page", "to": ["fixture@example.invalid"]}
    assert send_resend(payload, "delivery-fixture", settings=settings) == "provider-fixture"
    send_resend(payload, "delivery-fixture", settings=settings)
    assert calls[0] == calls[1]
    assert calls[0][1]["headers"]["Idempotency-Key"] == "news/delivery-fixture"
    assert calls[0][1]["json"] is payload
    settings.resend_api_key = ""
    settings.smtp_password = "fixture-smtp-only"
    with pytest.raises(RuntimeError):
        resend_key(settings)
    settings.smtp_host = "smtp.resend.com"
    assert resend_key(settings) == "fixture-smtp-only"


def test_enabled_production_delivery_requires_verified_receiver_and_https():
    settings = replace(get_settings(), server="COM", resend_api_key="fixture-only",
                       smtp_from_email="a@example.invalid", public_webpage_url="https://example.invalid",
                       resend_webhook_secret="")
    with pytest.raises(RuntimeError, match="webhook"):
        ensure_news_delivery_configured(settings)
    settings = replace(settings, resend_webhook_secret="whsec_Zml4dHVyZSBzaWduaW5nIHNlY3JldA==")
    ensure_news_delivery_configured(settings)
    with pytest.raises(RuntimeError, match="HTTPS"):
        ensure_news_delivery_configured(replace(settings, public_webpage_url="http://example.invalid"))
