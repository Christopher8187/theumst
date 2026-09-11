"""Explicit news consent and an immutable, resumable delivery outbox.

The publication transaction freezes both the message and its consenting audience.
The worker checks eligibility again under account/subscription locks before sending.
Provider retries reuse the saved payload and delivery ID for less than 24 hours;
an unresolved older attempt stops for reconciliation instead of risking a duplicate.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from ..config import get_settings
from ..database import transaction
from .email import email_content


logger = logging.getLogger(__name__)
RETRY_WINDOW = timedelta(hours=23)
TERMINAL_EVENTS = {
    "email.delivered": "delivered", "email.bounced": "bounced",
    "email.complained": "complained", "email.suppressed": "suppressed",
    "email.failed": "failed",
}
SUPPRESSION_EVENTS = {"email.bounced", "email.complained", "email.suppressed"}


def subscription_state(cur, user_id: int) -> dict:
    cur.execute(
        '''SELECT u.email, u.email_verified_at, s.enabled, s.email AS consent_email,
                  s.consent_at, s.consent_source, s.confirmed_at,
                  EXISTS (SELECT 1 FROM news_suppression ns WHERE ns.email = lower(u.email)) AS suppressed
           FROM "user" u LEFT JOIN news_subscription s ON s.user_id = u.user_id
           WHERE u.user_id = %s''', (user_id,),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError("Account not found")
    enabled = bool(row["enabled"] and row["consent_email"] == row["email"].lower())
    confirmed = row["confirmed_at"] if enabled and row["email_verified_at"] else None
    status = "off"
    if enabled:
        status = "suppressed" if row["suppressed"] else ("active" if confirmed else "pending_confirmation")
    return {
        "news": enabled, "status": status, "email": row["email"],
        "consent_at": row["consent_at"], "consent_source": row["consent_source"],
        "confirmed_at": confirmed,
    }


def set_subscription(cur, user_id: int, enabled: bool, source: str) -> dict:
    if source not in {"profile", "login"}:
        raise ValueError("Unsupported consent source")
    # All consent mutations and dispatch take the account lock first.
    cur.execute('SELECT email, email_verified_at FROM "user" WHERE user_id = %s FOR UPDATE', (user_id,))
    account = cur.fetchone()
    if not account:
        raise ValueError("Account not found")
    email = account["email"].lower()
    cur.execute("SELECT * FROM news_subscription WHERE user_id = %s FOR UPDATE", (user_id,))
    previous = cur.fetchone()
    if previous and previous["email"] == email and previous["enabled"] == enabled:
        return subscription_state(cur, user_id)
    token = previous["unsubscribe_token"] if previous and previous["email"] == email else secrets.token_urlsafe(32)
    cur.execute(
        '''INSERT INTO news_subscription
               (user_id, email, enabled, consent_id, consent_source, confirmed_at, unsubscribe_token)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (user_id) DO UPDATE SET
               email = EXCLUDED.email, enabled = EXCLUDED.enabled, consent_id = EXCLUDED.consent_id,
               consent_at = now(), consent_source = EXCLUDED.consent_source,
               confirmed_at = EXCLUDED.confirmed_at, unsubscribe_token = EXCLUDED.unsubscribe_token,
               updated_at = now()''',
        (user_id, email, enabled, str(uuid4()), source, account["email_verified_at"], token),
    )
    cur.execute(
        "INSERT INTO news_consent_event (user_id, email, enabled, source) VALUES (%s, %s, %s, %s)",
        (user_id, email, enabled, source),
    )
    return subscription_state(cur, user_id)


def confirm_subscription(cur, user_id: int) -> None:
    cur.execute(
        '''UPDATE news_subscription s SET confirmed_at = u.email_verified_at, updated_at = now()
           FROM "user" u WHERE s.user_id = u.user_id AND u.user_id = %s
               AND s.email = lower(u.email) AND s.enabled''', (user_id,),
    )


def stop_subscription_for_email_change(cur, user_id: int) -> None:
    # Caller already holds the account lock while replacing its email address.
    cur.execute(
        '''UPDATE news_subscription SET enabled = false, consent_source = 'email_change', consent_at = now(), updated_at = now()
           WHERE user_id = %s AND enabled RETURNING email''', (user_id,),
    )
    previous = cur.fetchone()
    if previous:
        cur.execute(
            "INSERT INTO news_consent_event (user_id, email, enabled, source) VALUES (%s, %s, false, 'email_change')",
            (user_id, previous["email"]),
        )


def unsubscribe(cur, token: str) -> None:
    # Token look-up is read-only; lock the account before rechecking the token.
    cur.execute("SELECT user_id FROM news_subscription WHERE unsubscribe_token = %s", (token,))
    row = cur.fetchone()
    if not row:
        return
    cur.execute('SELECT user_id FROM "user" WHERE user_id = %s FOR UPDATE', (row["user_id"],))
    cur.execute(
        '''UPDATE news_subscription SET enabled = false, consent_source = 'unsubscribe', consent_at = now(), updated_at = now()
           WHERE user_id = %s AND unsubscribe_token = %s AND enabled RETURNING user_id, email''',
        (row["user_id"], token),
    )
    changed = cur.fetchone()
    if changed:
        cur.execute(
            "INSERT INTO news_consent_event (user_id, email, enabled, source) VALUES (%s, %s, false, 'unsubscribe')",
            (changed["user_id"], changed["email"]),
        )


def queue_announcement(cur, *, media_post_id: int, user_id: int, title: str, introduction: str, slug: str, settings=None) -> dict:
    settings = settings or get_settings()
    announcement_id = str(uuid4())
    cur.execute(
        '''INSERT INTO news_announcement (announcement_id, media_post_id, title, introduction, created_by_user_id)
           VALUES (%s, %s, %s, %s, %s) ON CONFLICT (media_post_id) DO NOTHING RETURNING announcement_id''',
        (announcement_id, media_post_id, title, introduction, user_id),
    )
    if not cur.fetchone():
        cur.execute("SELECT announcement_id FROM news_announcement WHERE media_post_id = %s", (media_post_id,))
        return {"announcement_queued": False, "announcement_id": str(cur.fetchone()["announcement_id"])}
    cur.execute(
        '''SELECT s.user_id, s.email, s.consent_id, s.unsubscribe_token
           FROM news_subscription s JOIN "user" u ON u.user_id = s.user_id
           WHERE s.enabled AND s.confirmed_at IS NOT NULL AND u.email_verified_at IS NOT NULL
             AND s.email = lower(u.email)
             AND NOT EXISTS (SELECT 1 FROM news_suppression ns WHERE ns.email = s.email)''',
    )
    audience = list(cur.fetchall())
    base = settings.public_webpage_url.rstrip("/")
    for subscriber in audience:
        delivery_id = str(uuid4())
        unsubscribe_url = f"{base}/api/news/unsubscribe/{subscriber['unsubscribe_token']}"
        content = email_content("news", f"{base}/news/{slug}", settings=settings,
                                title=title, introduction=introduction, unsubscribe_url=unsubscribe_url)
        payload = {
            "from": f"{settings.smtp_from_name} <{settings.smtp_from_email}>",
            "to": [subscriber["email"]], **content,
            "headers": {
                "List-Unsubscribe": f"<{unsubscribe_url}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            },
        }
        cur.execute(
            '''INSERT INTO news_delivery (delivery_id, announcement_id, user_id, recipient_email, consent_id, payload)
               VALUES (%s, %s, %s, %s, %s, %s::jsonb)''',
            (delivery_id, announcement_id, subscriber["user_id"], subscriber["email"],
             str(subscriber["consent_id"]), json.dumps(payload)),
        )
    return {"announcement_queued": True, "announcement_id": announcement_id}


def resend_key(settings) -> str:
    # Resend SMTP uses the same provider API key. Only this exact provider may reuse it.
    key = settings.resend_api_key
    if not key and settings.smtp_host.lower() == "smtp.resend.com":
        key = settings.smtp_password
    if not key or not settings.smtp_from_email:
        raise RuntimeError("News delivery requires a Resend API key and sender address")
    return key


def ensure_news_delivery_configured(settings) -> None:
    resend_key(settings)
    if settings.server != "LOCAL" and urlsplit(settings.public_webpage_url).scheme != "https":
        raise RuntimeError("Production news delivery requires HTTPS public links")
    secret = settings.resend_webhook_secret
    try:
        if not secret.startswith("whsec_") or len(base64.b64decode(secret[6:], validate=True)) < 16:
            raise ValueError("Invalid signing secret")
    except ValueError as exc:
        raise RuntimeError("News delivery requires a verified Resend webhook signing secret") from exc


def send_resend(payload: dict, delivery_id: str, *, settings) -> str:
    response = httpx.post(
        "https://api.resend.com/emails", json=payload,
        headers={"Authorization": f"Bearer {resend_key(settings)}", "Idempotency-Key": f"news/{delivery_id}"},
        timeout=15,
    )
    response.raise_for_status()
    provider_id = response.json().get("id")
    if not isinstance(provider_id, str) or not provider_id:
        raise ValueError("Provider returned no email ID")
    return provider_id


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 409:
            try:
                return exc.response.json().get("name") == "concurrent_idempotent_requests"
            except ValueError:
                return False
        return code == 429 or code >= 500 or code in {401, 403}
    return isinstance(exc, (httpx.TransportError, ValueError))


def process_one(*, settings=None, sender=None) -> bool:
    """Process one due row; sender injection is used by real PostgreSQL tests."""
    settings = settings or get_settings()
    sender = sender or send_resend
    with transaction() as (_, cur):
        cur.execute(
            '''SELECT delivery_id FROM news_delivery
               WHERE (status = 'queued' AND next_attempt_at <= now())
                  OR (status = 'sending' AND lease_until < now())
               ORDER BY next_attempt_at FOR UPDATE SKIP LOCKED LIMIT 1''',
        )
        row = cur.fetchone()
        if not row:
            return False
        delivery_id = str(row["delivery_id"])
        cur.execute(
            '''UPDATE news_delivery SET status = 'sending', lease_until = now() + interval '2 minutes',
                   first_attempt_at = COALESCE(first_attempt_at, now()), attempts = attempts + 1, updated_at = now()
               WHERE delivery_id = %s''', (delivery_id,),
        )
    with transaction() as (_, cur):
        cur.execute("SELECT * FROM news_delivery WHERE delivery_id = %s FOR UPDATE", (delivery_id,))
        delivery = cur.fetchone()
        if not delivery or delivery["status"] != "sending":
            return True
        if datetime.now(timezone.utc) - delivery["first_attempt_at"] >= RETRY_WINDOW:
            cur.execute("UPDATE news_delivery SET status = 'uncertain', lease_until = NULL, last_error = 'idempotency_window_elapsed', updated_at = now() WHERE delivery_id = %s", (delivery_id,))
            return True
        cur.execute('SELECT email, email_verified_at FROM "user" WHERE user_id = %s FOR UPDATE', (delivery["user_id"],))
        account = cur.fetchone()
        cur.execute("SELECT * FROM news_subscription WHERE user_id = %s FOR UPDATE", (delivery["user_id"],))
        consent = cur.fetchone()
        cur.execute("SELECT 1 FROM news_suppression WHERE email = %s", (delivery["recipient_email"],))
        suppressed = bool(cur.fetchone())
        cur.execute(
            '''SELECT 1 FROM news_announcement a JOIN media_post p ON p.media_post_id = a.media_post_id
               WHERE a.announcement_id = %s AND p.status = 'published' AND p.published_at <= now()''',
            (delivery["announcement_id"],),
        )
        published = bool(cur.fetchone())
        eligible = bool(account and consent and account["email_verified_at"] and consent["confirmed_at"]
                        and consent["enabled"] and consent["consent_id"] == delivery["consent_id"]
                        and account["email"].lower() == consent["email"] == delivery["recipient_email"]
                        and not suppressed and published)
        if not eligible:
            cur.execute("UPDATE news_delivery SET status = 'skipped', lease_until = NULL, last_error = 'no_longer_eligible', updated_at = now() WHERE delivery_id = %s", (delivery_id,))
            return True
        # Eligibility locks may have waited behind a long account transaction.
        # Recheck immediately before dispatch so that wait cannot outlive the
        # provider's retained idempotency result and turn a retry into a new send.
        if datetime.now(timezone.utc) - delivery["first_attempt_at"] >= RETRY_WINDOW:
            cur.execute("UPDATE news_delivery SET status = 'uncertain', lease_until = NULL, last_error = 'idempotency_window_elapsed', updated_at = now() WHERE delivery_id = %s", (delivery_id,))
            return True
        try:
            provider_id = sender(delivery["payload"], delivery_id, settings=settings)
        except Exception as exc:
            retry = _retryable(exc)
            status = "queued" if retry else "failed"
            delay = min(3600, 30 * 2 ** min(delivery["attempts"], 7))
            # Never persist provider bodies, addresses, credentials, or account links in errors.
            error = f"http_{exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError) else type(exc).__name__
            cur.execute(
                '''UPDATE news_delivery SET status = %s, lease_until = NULL, last_error = %s,
                       next_attempt_at = now() + %s * interval '1 second', updated_at = now()
                   WHERE delivery_id = %s''', (status, error, delay, delivery_id),
            )
        else:
            # The webhook may beat the API response. Serialize receipt storage and
            # acknowledgement by provider ID so either ordering preserves its state.
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"news-provider/{provider_id}",))
            cur.execute(
                '''SELECT event_type FROM news_provider_event WHERE provider_email_id = %s
                   ORDER BY CASE WHEN event_type IN ('email.bounced', 'email.complained', 'email.suppressed') THEN 0
                                 WHEN event_type = 'email.failed' THEN 1 ELSE 2 END, created_at DESC LIMIT 1''',
                (provider_id,),
            )
            event = cur.fetchone()
            status = TERMINAL_EVENTS[event["event_type"]] if event else "sent"
            cur.execute(
                '''UPDATE news_delivery SET status = %s, provider_email_id = %s, lease_until = NULL,
                       last_error = NULL, updated_at = now() WHERE delivery_id = %s''', (status, provider_id, delivery_id),
            )
    return True


async def delivery_loop(settings) -> None:
    ensure_news_delivery_configured(settings)
    while True:
        try:
            processed = await asyncio.to_thread(process_one, settings=settings)
        except Exception:
            # Exception bodies can contain SQL parameters and tokens. Keep operational logs safe.
            logger.error("News worker could not complete a database delivery attempt")
            processed = False
        await asyncio.sleep(0.6 if processed else settings.news_poll_seconds)


def verify_webhook(body: bytes, headers, secret: str, *, now: float | None = None) -> str:
    """Verify Svix's documented raw-body HMAC and five-minute replay window."""
    try:
        event_id = headers["svix-id"]
        timestamp = headers["svix-timestamp"]
        if abs((time.time() if now is None else now) - int(timestamp)) > 300:
            raise ValueError("Expired signature")
        if not secret.startswith("whsec_"):
            raise ValueError("Missing signing secret")
        key = base64.b64decode(secret[6:], validate=True)
        signed = f"{event_id}.{timestamp}.".encode() + body
        expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
        valid = any(part.startswith("v1,") and hmac.compare_digest(part[3:], expected)
                    for part in headers["svix-signature"].split())
        if not valid:
            raise ValueError("Invalid signature")
        return event_id
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid webhook signature") from exc


def record_provider_event(cur, event_id: str, event: dict, *, settings=None) -> None:
    settings = settings or get_settings()
    event_type = event.get("type")
    data = event.get("data")
    if event_type not in TERMINAL_EVENTS or not isinstance(data, dict):
        return
    provider_id = data.get("email_id")
    if not isinstance(provider_id, str) or not provider_id:
        raise ValueError("Event requires an email ID")
    cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"news-provider/{provider_id}",))
    cur.execute(
        '''INSERT INTO news_provider_event (event_id, event_type, provider_email_id)
           VALUES (%s, %s, %s) ON CONFLICT (event_id) DO NOTHING RETURNING event_id''',
        (event_id, event_type, provider_id),
    )
    if not cur.fetchone():
        return
    if event_type in SUPPRESSION_EVENTS:
        # Signature authenticates the provider; From limits this to our configured sender.
        sender = parseaddr(str(data.get("from", "")))[1].lower()
        recipients = data.get("to", [])
        cur.execute("SELECT recipient_email FROM news_delivery WHERE provider_email_id = %s", (provider_id,))
        delivery = cur.fetchone()
        if delivery:
            recipients = [delivery["recipient_email"]]
        if (delivery or sender == settings.smtp_from_email.lower()) and isinstance(recipients, list):
            for recipient in recipients:
                if isinstance(recipient, str) and "@" in recipient:
                    cur.execute(
                        '''INSERT INTO news_suppression (email, reason, provider_email_id)
                           VALUES (%s, %s, %s) ON CONFLICT (email) DO NOTHING''',
                        (parseaddr(recipient)[1].lower(), event_type, provider_id),
                    )
    # Delivery can arrive after a complaint. Do not downgrade a suppression state.
    cur.execute(
        '''UPDATE news_delivery SET status = %s, updated_at = now()
           WHERE provider_email_id = %s AND status NOT IN ('bounced', 'complained', 'suppressed')''',
        (TERMINAL_EVENTS[event_type], provider_id),
    )
