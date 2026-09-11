from __future__ import annotations

import json
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from ..config import get_settings
from ..database import transaction
from ..dependencies import require_access, require_user
from ..schemas import NewsEmailPreview, SubscriptionUpdate
from ..services.email import email_content
from ..services.news import record_provider_event, set_subscription, subscription_state, unsubscribe, verify_webhook


router = APIRouter(tags=["news subscriptions"])


@router.get("/api/me/subscriptions")
def get_subscriptions(request: Request):
    user = require_user(request)
    with transaction() as (_, cur):
        return subscription_state(cur, user["user_id"])


@router.put("/api/me/subscriptions")
def update_subscriptions(payload: SubscriptionUpdate, request: Request):
    user = require_user(request)
    with transaction() as (_, cur):
        return set_subscription(cur, user["user_id"], payload.news, "profile")


@router.post("/api/content/media/email-preview")
def preview_news_email(payload: NewsEmailPreview, request: Request):
    require_access(request, "media")
    # Preview is pure rendering with no navigable anchors or delivery side effects.
    return email_content(
        "news", "https://example.invalid/news/preview", title=payload.title,
        introduction=payload.email_introduction,
        unsubscribe_url="https://example.invalid/unsubscribe/preview",
        preview=True,
    )


def _unsubscribe_page(token: str, *, complete: bool = False) -> HTMLResponse:
    valid = bool(re.fullmatch(r"[A-Za-z0-9_-]{32,100}", token))
    content = '<h1>You have been unsubscribed.</h1><p>You will no longer receive Theumst news at this subscription address. Account and security emails remain available.</p>' if complete else (
        '<h1>Unsubscribe from Theumst news?</h1><p>This stops news announcements. Account and security emails remain available.</p>'
        + (f'<form method="post" action="/api/news/unsubscribe/{token}"><button type="submit">Unsubscribe from news</button></form>' if valid else '<p>This subscription link is not valid.</p>')
    )
    return HTMLResponse(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Theumst news subscription</title><style>body{margin:0;padding:32px 20px;background:#e3e2d9;color:#19384c;font:18px/1.7 Georgia,serif}main{max-width:560px;margin:auto;padding:28px;background:#f1eddf;border:1px solid #879b9d}h1{font-weight:normal;font-size:30px}button{background:#23485b;color:#fff8e3;padding:14px 20px;border:0;font:14px monospace;cursor:pointer}</style><main>'
        + content + '</main></html>',
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                 "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"},
    )


@router.get("/api/news/unsubscribe/{token}", response_class=HTMLResponse)
def confirm_news_unsubscribe(token: str):
    # GET is safe for link scanners. The page reveals neither identity nor consent.
    return _unsubscribe_page(token)


@router.post("/api/news/unsubscribe/{token}", response_class=HTMLResponse)
def perform_news_unsubscribe(token: str):
    # The unguessable URL is the authority, including RFC 8058's one-click POST.
    if re.fullmatch(r"[A-Za-z0-9_-]{32,100}", token):
        with transaction() as (_, cur):
            unsubscribe(cur, token)
    return _unsubscribe_page(token, complete=True)


@router.post("/api/email/events/resend")
async def resend_event(request: Request):
    secret = get_settings().resend_webhook_secret
    if not secret:
        raise HTTPException(status_code=503, detail="Email event receiver is not configured")
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 256_000:
            raise HTTPException(status_code=413, detail="Event is too large")
        chunks.append(chunk)
    body = b"".join(chunks)
    try:
        event_id = verify_webhook(body, request.headers, secret)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid event signature") from exc
    try:
        event = json.loads(body)
        if not isinstance(event, dict):
            raise ValueError("Expected event object")
        with transaction() as (_, cur):
            record_provider_event(cur, event_id, event)
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid email event") from exc
    return {"ok": True}
