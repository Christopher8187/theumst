from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from ..config import get_settings
from ..database import transaction
from ..schemas import ForgotPasswordRequest, ResetPasswordRequest
from ..security import (
    hash_password,
    hash_secret,
    new_password_reset_token,
    new_session_token,
    session_expiry,
    verify_password,
)
from ..services.email import EmailConfigurationError, ensure_email_configured, send_password_reset_email


router = APIRouter(tags=["authentication"])
logger = logging.getLogger(__name__)


def _wants_json(request: Request) -> bool:
    return "application/json" in request.headers.get("accept", "") or request.headers.get("x-requested-with") == "fetch"


def _success(request: Request, redirect: str):
    if _wants_json(request):
        return JSONResponse({"ok": True, "redirect": redirect})
    return RedirectResponse(redirect, status_code=303)


def _error(request: Request, redirect: str, detail: str, status: int = 400):
    if _wants_json(request):
        return JSONResponse({"ok": False, "detail": detail}, status_code=status)
    return RedirectResponse(redirect, status_code=303)


def _set_session(response, user_id: int) -> None:
    settings = get_settings()
    token = new_session_token()
    with transaction() as (_, cur):
        cur.execute(
            "INSERT INTO web_session (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
            (user_id, hash_secret(token), session_expiry(settings.session_days)),
        )
    response.set_cookie(
        settings.cookie_name,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


@router.post("/auth/signup")
async def signup(request: Request):
    form = await request.form()
    username = str(form.get("username", "")).strip()
    email = str(form.get("email", "")).strip().lower()
    password = str(form.get("password", ""))
    if not username or not email or len(password) < 8:
        return _error(request, "/signup?error=invalid", "Username, email, and an 8-character password are required")
    try:
        with transaction() as (_, cur):
            cur.execute("SELECT authority_id FROM authority WHERE name = 'user'")
            authority_id = cur.fetchone()["authority_id"]
            cur.execute(
                """
                INSERT INTO "user" (authority_id, username, email, password_hash)
                VALUES (%s, %s, %s, %s) RETURNING user_id
                """,
                (authority_id, username, email, hash_password(password)),
            )
            user_id = int(cur.fetchone()["user_id"])
    except Exception as exc:
        if getattr(exc, "pgcode", None) == "23505":
            return _error(request, "/signup?error=exists", "Username or email already exists", 409)
        raise
    response = _success(request, "/dashboard/profile/")
    _set_session(response, user_id)
    return response


@router.post("/auth/login")
async def login(request: Request):
    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    with transaction() as (_, cur):
        cur.execute(
            "SELECT user_id, password_hash FROM \"user\" WHERE lower(username) = lower(%s)",
            (username,),
        )
        row = cur.fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return _error(request, "/login?error=bad-login", "Incorrect username or password", 401)
    response = _success(request, "/dashboard/profile/")
    _set_session(response, int(row["user_id"]))
    return response


@router.post("/auth/forgot-password", status_code=202)
async def forgot_password(payload: ForgotPasswordRequest, request: Request):
    """Email a one-use reset link without revealing whether an account exists."""

    settings = get_settings()
    try:
        ensure_email_configured(settings)
    except EmailConfigurationError as exc:
        logger.error("Password recovery configuration error: %s", exc)
        raise HTTPException(status_code=503, detail="Password recovery is temporarily unavailable") from exc

    email = payload.email.strip().lower()
    requested_ip = request.client.host if request.client else None
    raw_token: str | None = None
    recipient: str | None = None

    with transaction() as (_, cur):
        cur.execute(
            'SELECT user_id, email FROM "user" WHERE lower(email) = lower(%s)',
            (email,),
        )
        user = cur.fetchone()
        if user:
            # Limit delivery per account while retaining the same public response.
            cur.execute(
                """
                SELECT count(*) AS recent_requests
                FROM password_reset_token
                WHERE user_id = %s AND created_at > now() - interval '2 minutes'
                """,
                (user["user_id"],),
            )
            recent_requests = int(cur.fetchone()["recent_requests"])
            if recent_requests == 0:
                raw_token = new_password_reset_token()
                recipient = str(user["email"])
                cur.execute(
                    """
                    UPDATE password_reset_token
                    SET used_at = now()
                    WHERE user_id = %s AND used_at IS NULL
                    """,
                    (user["user_id"],),
                )
                cur.execute(
                    """
                    INSERT INTO password_reset_token
                        (user_id, token_hash, expires_at, requested_ip)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        user["user_id"],
                        hash_secret(raw_token),
                        datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_ttl_minutes),
                        requested_ip,
                    ),
                )

    if raw_token and recipient:
        reset_url = f"{settings.public_webpage_url}/reset-password?{urlencode({'token': raw_token})}"
        try:
            await run_in_threadpool(
                send_password_reset_email,
                recipient,
                reset_url,
                settings=settings,
            )
            with transaction() as (_, cur):
                cur.execute(
                    "UPDATE password_reset_token SET sent_at = now() WHERE token_hash = %s",
                    (hash_secret(raw_token),),
                )
        except Exception:
            # Keep the outward response account-neutral. The failure is logged and
            # the undelivered token is invalidated so it cannot later be used.
            logger.exception("Could not deliver password reset email")
            with transaction() as (_, cur):
                cur.execute(
                    "UPDATE password_reset_token SET used_at = now() WHERE token_hash = %s",
                    (hash_secret(raw_token),),
                )

    return {
        "ok": True,
        "detail": "If an account matches that email address, a reset link has been sent.",
    }


@router.post("/auth/reset-password")
def reset_password(payload: ResetPasswordRequest):
    token_hash = hash_secret(payload.token)
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT password_reset_token_id, user_id
            FROM password_reset_token
            WHERE token_hash = %s
              AND used_at IS NULL
              AND sent_at IS NOT NULL
              AND expires_at > now()
            FOR UPDATE
            """,
            (token_hash,),
        )
        token = cur.fetchone()
        if not token:
            raise HTTPException(status_code=400, detail="This reset link is invalid or has expired")

        cur.execute(
            'UPDATE "user" SET password_hash = %s WHERE user_id = %s',
            (hash_password(payload.new_password), token["user_id"]),
        )
        cur.execute(
            "UPDATE password_reset_token SET used_at = now() WHERE user_id = %s AND used_at IS NULL",
            (token["user_id"],),
        )
        cur.execute(
            "UPDATE web_session SET revoked_at = now() WHERE user_id = %s AND revoked_at IS NULL",
            (token["user_id"],),
        )

    return {"ok": True, "redirect": "/login?reset=success"}


@router.post("/auth/signout")
def signout(request: Request):
    settings = get_settings()
    token = request.cookies.get(settings.cookie_name)
    if token:
        with transaction() as (_, cur):
            cur.execute(
                "UPDATE web_session SET revoked_at = now() WHERE token_hash = %s AND revoked_at IS NULL",
                (hash_secret(token),),
            )
    response = JSONResponse({"ok": True})
    response.delete_cookie(settings.cookie_name)
    return response
