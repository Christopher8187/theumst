from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from ..config import Settings, get_settings


class EmailConfigurationError(RuntimeError):
    """Raised when outbound email has not been configured."""


def ensure_email_configured(settings: Settings | None = None) -> Settings:
    settings = settings or get_settings()
    if not settings.smtp_host or not settings.smtp_from_email:
        raise EmailConfigurationError(
            "Password recovery email is not configured. Set SMTP_HOST and SMTP_FROM_EMAIL."
        )
    return settings


def build_password_reset_message(
    recipient: str,
    reset_url: str,
    *,
    settings: Settings | None = None,
) -> EmailMessage:
    settings = ensure_email_configured(settings)
    message = EmailMessage()
    message["Subject"] = "Reset your theumst password"
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = recipient
    message.set_content(
        "We received a request to reset the password for your theumst account.\n\n"
        f"Reset your password: {reset_url}\n\n"
        f"This link expires in {settings.password_reset_ttl_minutes} minutes and can only be used once.\n\n"
        "If you did not request this change, you can safely ignore this email. "
        "Your password has not been changed.\n"
    )
    message.add_alternative(
        f"""
        <!doctype html>
        <html lang="en">
          <body style="margin:0;background:#070a12;color:#e9edff;font-family:Arial,sans-serif">
            <div style="max-width:560px;margin:0 auto;padding:40px 24px">
              <p style="color:#8da2ff;font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase">theumst account security</p>
              <h1 style="font-size:30px;line-height:1.15;margin:12px 0 18px">Reset your password</h1>
              <p style="color:#b9c2d8;line-height:1.7">We received a request to reset the password for your theumst account.</p>
              <p style="margin:28px 0">
                <a href="{reset_url}" style="display:inline-block;padding:14px 20px;border-radius:8px;background:#eef1ff;color:#0a1022;font-weight:700;text-decoration:none">Choose a new password</a>
              </p>
              <p style="color:#8d97ad;line-height:1.6;font-size:13px">This link expires in {settings.password_reset_ttl_minutes} minutes and can only be used once. If you did not request this, ignore this email; your password has not changed.</p>
            </div>
          </body>
        </html>
        """,
        subtype="html",
    )
    return message


def send_password_reset_email(
    recipient: str,
    reset_url: str,
    *,
    settings: Settings | None = None,
) -> None:
    settings = ensure_email_configured(settings)
    message = build_password_reset_message(recipient, reset_url, settings=settings)
    context = ssl.create_default_context()

    smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    smtp_kwargs = {"host": settings.smtp_host, "port": settings.smtp_port, "timeout": 15}
    if settings.smtp_use_ssl:
        smtp_kwargs["context"] = context

    with smtp_class(**smtp_kwargs) as server:
        if not settings.smtp_use_ssl and settings.smtp_starttls:
            server.starttls(context=context)
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)
