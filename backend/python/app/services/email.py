from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from html import escape
from urllib.parse import urlsplit

from ..config import Settings, get_settings


class EmailConfigurationError(RuntimeError):
    """Raised when outbound email has not been configured."""


def ensure_email_configured(settings: Settings | None = None) -> Settings:
    settings = settings or get_settings()
    if not settings.smtp_host or not settings.smtp_from_email:
        raise EmailConfigurationError("Account email is not configured. Set SMTP_HOST and SMTP_FROM_EMAIL.")
    return settings


def _url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Email links must be absolute HTTP(S) URLs")
    return escape(value, quote=True)


def email_content(
    kind: str, action_url: str, *, settings=None, title: str = "",
    introduction: str = "", unsubscribe_url: str | None = None, preview: bool = False,
) -> dict[str, str]:
    """One warm-ivory layout; plain text always contains the same action."""
    settings = settings or get_settings()
    expiry = getattr(settings, "email_verification_ttl_hours", 24)
    reset_expiry = getattr(settings, "password_reset_ttl_minutes", 60)
    content = {
        "reset": (
            "Reset your theumst password", "YOUR ACCOUNT", "Reset your password.",
            "We received a request to reset the password for your theumst account.",
            f"This link expires in {reset_expiry} minutes and can only be used once.",
            "Choose a new password",
            "If you did not request this change, you can safely ignore this email. Your password has not been changed.",
        ),
        "verify": (
            "Confirm your theumst email address", "WELCOME TO THEUMST", "Confirm your email.",
            "Confirm this email address for your theumst account.",
            "Confirmation only shows that you can access this inbox. It does not verify your identity or grant access to restricted material. "
            f"This link expires in {expiry} hours and can only be used once.",
            "Confirm email address",
            "If you did not create this account, you can safely ignore this email.",
        ),
        "change": (
            "Confirm your new theumst email address", "YOUR ACCOUNT", "Confirm your new address.",
            "You asked to use this email address for your theumst account.",
            "Your existing address stays in place until you confirm. "
            f"This link expires in {expiry} hours and can only be used once.",
            "Confirm the new address",
            "If you did not request this change, do not confirm it. Review your account security using the website.",
        ),
        "news": (
            title.replace("\r", " ").replace("\n", " ").strip(), "FROM THE NEWSROOM", title,
            introduction, "Open the full story whenever you have a quiet moment.", "Read the news",
            "You receive these announcements because you subscribed to Theumst news.",
        ),
    }[kind]
    subject, eyebrow, heading, text, extra, action, note = content
    base = getattr(settings, "public_webpage_url", "https://theumst.com").rstrip("/")
    logo = _url(f"{base}/images/logo-email.png")
    href = _url(action_url)
    action_attribute = "" if preview else f'href="{href}"'
    preferences = f"{base}/?window=profile&tab=subscriptions"
    footer = ""
    plain_footer = ""
    if kind == "news":
        if not unsubscribe_url:
            raise ValueError("News mail requires an unsubscribe URL")
        preferences_attribute = "" if preview else f'href="{_url(preferences)}"'
        unsubscribe_attribute = "" if preview else f'href="{_url(unsubscribe_url)}"'
        footer = (
            '<p style="margin:12px 0 0;font:11px/1.8 Courier New,monospace">'
            f'<a style="color:#19384c" {preferences_attribute}>Manage subscriptions</a> &nbsp;·&nbsp; '
            f'<a style="color:#19384c" {unsubscribe_attribute}>Unsubscribe</a></p>'
        )
        plain_footer = "\n\nManage subscriptions: [preview]\nUnsubscribe: [preview]" if preview else f"\n\nManage subscriptions: {preferences}\nUnsubscribe: {unsubscribe_url}"
    plain = f"{heading}\n\n{text}\n\n{extra}\n\n{action}: {'[preview]' if preview else action_url}\n\n{note}{plain_footer}\n"
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(subject)}</title></head>
<body style="margin:0;background:#e3e2d9;color:#19384c">
<div style="display:none;max-height:0;overflow:hidden">{escape(text[:180])}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#e3e2d9">
<tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;border:1px solid #879b9d;background:#f1eddf">
<tr><td style="padding:20px 24px;border-bottom:1px solid #879b9d;background:#e8e5d7">
<table role="presentation" cellpadding="0" cellspacing="0"><tr><td><img src="{logo}" width="38" height="39" alt="UMST" style="display:block;border:0"></td>
<td style="padding-left:12px"><span style="font:28px Georgia,serif;color:#19384c">theumst</span><br>
<span style="font:8px Courier New,monospace;letter-spacing:2px;color:#526c71">A PLACE TO LEARN</span></td></tr></table></td></tr>
<tr><td style="padding:30px 24px;word-break:break-word">
<p style="margin:0 0 24px;font:10px Courier New,monospace;letter-spacing:2px;color:#5c7779">{escape(eyebrow)}</p>
<h1 style="margin:0 0 22px;font:32px/1.15 Georgia,serif;font-weight:normal">{escape(heading)}</h1>
<p style="margin:0 0 16px;font:17px/1.75 Georgia,serif">{escape(text).replace(chr(10), '<br>')}</p>
<p style="margin:0 0 28px;font:15px/1.75 Georgia,serif;color:#526a70">{escape(extra)}</p>
<table role="presentation" cellpadding="0" cellspacing="0"><tr><td style="background:#23485b;border:1px solid #123448">
<a {action_attribute} style="display:inline-block;padding:14px 21px;font:12px Courier New,monospace;color:#fff8e3;text-decoration:none">{escape(action)} &rarr;</a></td></tr></table>
<p style="margin:31px 0 0;font:14px/1.6 Georgia,serif;color:#597577">Until the next page,<br>Theumst <span style="color:#ad884d">✧</span></p>
</td></tr><tr><td style="padding:21px 24px;border-top:1px solid #b3bbaa;background:#e8e5d7">
<p style="margin:0;font:11px/1.8 Courier New,monospace;color:#526c71">{escape(note)}</p>{footer}
</td></tr></table></td></tr></table></body></html>"""
    return {"subject": subject, "html": html, "text": plain}


def _message(kind: str, recipient: str, action_url: str, *, settings=None) -> EmailMessage:
    settings = ensure_email_configured(settings)
    content = email_content(kind, action_url, settings=settings)
    message = EmailMessage()
    message["Subject"] = content["subject"]
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = recipient
    message["Date"] = formatdate(localtime=False, usegmt=True)
    message["Message-ID"] = make_msgid(domain=settings.smtp_from_email.rsplit("@", 1)[-1])
    message.set_content(content["text"])
    message.add_alternative(content["html"], subtype="html")
    return message


def build_password_reset_message(recipient: str, reset_url: str, *, settings=None) -> EmailMessage:
    return _message("reset", recipient, reset_url, settings=settings)


def build_email_verification_message(recipient: str, verification_url: str, *, settings=None) -> EmailMessage:
    return _message("verify", recipient, verification_url, settings=settings)


def build_email_change_message(recipient: str, verification_url: str, *, settings=None) -> EmailMessage:
    return _message("change", recipient, verification_url, settings=settings)


def _send(message: EmailMessage, settings) -> None:
    context = ssl.create_default_context()
    smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    kwargs = {"host": settings.smtp_host, "port": settings.smtp_port, "timeout": 15}
    if settings.smtp_use_ssl:
        kwargs["context"] = context
    with smtp_class(**kwargs) as server:
        if not settings.smtp_use_ssl and settings.smtp_starttls:
            server.starttls(context=context)
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)


def send_password_reset_email(recipient: str, reset_url: str, *, settings=None) -> None:
    settings = ensure_email_configured(settings)
    _send(build_password_reset_message(recipient, reset_url, settings=settings), settings)


def send_email_verification_email(recipient: str, verification_url: str, *, settings=None) -> None:
    settings = ensure_email_configured(settings)
    _send(build_email_verification_message(recipient, verification_url, settings=settings), settings)


def send_email_change_email(recipient: str, verification_url: str, *, settings=None) -> None:
    settings = ensure_email_configured(settings)
    _send(build_email_change_message(recipient, verification_url, settings=settings), settings)
