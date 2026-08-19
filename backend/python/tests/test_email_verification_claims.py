from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.services.email import build_email_verification_message


def test_email_confirmation_proves_inbox_access_not_identity_or_entitlement():
    settings = SimpleNamespace(
        smtp_host="smtp.invalid",
        smtp_port=587,
        smtp_username="",
        smtp_password="",
        smtp_from_email="accounts@example.invalid",
        smtp_from_name="theumst",
        smtp_starttls=True,
        smtp_use_ssl=False,
        email_verification_ttl_hours=24,
    )
    message = build_email_verification_message(
        "learner@example.invalid",
        "https://example.invalid/verify-email?token=synthetic",
        settings=settings,
    )
    plain = message.get_body(preferencelist=("plain",)).get_content().lower()
    html = message.get_body(preferencelist=("html",)).get_content().lower()
    rendered = plain + "\n" + html

    assert "access this inbox" in rendered
    assert "does not verify your identity" in rendered
    assert "does not verify your identity or grant access to restricted material" in rendered
    assert "really you" not in rendered
    assert "belongs to the person" not in rendered


def test_every_web_locale_avoids_identity_and_entitlement_claims():
    root = Path(__file__).resolve().parents[3]
    translations = (root / "frontend" / "webpage" / "src" / "utils" / "language.js").read_text(
        encoding="utf-8"
    )
    privacy = (root / "frontend" / "webpage" / "src" / "pages" / "PrivacyPage.vue").read_text(
        encoding="utf-8"
    )

    assert "Confirm it is really you" not in translations
    assert "belongs to the person registering" not in privacy
    assert translations.count('"verify.note"') == 3
    assert "does not verify your identity or grant access to restricted material" in translations
    assert "不会核实你的身份，也不会授予受限内容的访问权限" in translations
    assert "本人確認ではなく、制限された資料へのアクセス権も付与しません" in translations
