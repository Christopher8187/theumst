from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from ..config import get_settings
from ..database import transaction
from ..dependencies import require_user
from ..schemas import (
    EmailChangeRequest,
    EmailVerificationRequest,
    EmailVerificationResendRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from ..security import (
    hash_password,
    hash_secret,
    new_email_verification_token,
    new_password_reset_token,
    new_session_token,
    session_expiry,
    verify_password,
)
from ..services.email import (
    EmailConfigurationError,
    ensure_email_configured,
    send_email_verification_email,
    send_password_reset_email,
)


router = APIRouter(tags=["authentication"])
logger = logging.getLogger(__name__)


def _wants_json(request: Request) -> bool:
    return "application/json" in request.headers.get("accept", "") or request.headers.get("x-requested-with") == "fetch"


def _success(request: Request, redirect: str):
    if _wants_json(request):
        return JSONResponse({"ok": True, "redirect": redirect})
    return RedirectResponse(redirect, status_code=303)


def _error(
    request: Request,
    redirect: str,
    detail: str,
    status: int = 400,
    code: str | None = None,
):
    if _wants_json(request):
        payload = {"ok": False, "detail": detail}
        if code:
            payload["code"] = code
        return JSONResponse(payload, status_code=status)
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


def _issue_email_verification(cur, user_id: int, ttl_hours: int) -> str:
    raw_token = new_email_verification_token()
    cur.execute(
        """
        UPDATE email_verification_token
        SET used_at = now()
        WHERE user_id = %s AND used_at IS NULL
        """,
        (user_id,),
    )
    cur.execute(
        """
        INSERT INTO email_verification_token (user_id, token_hash, expires_at)
        VALUES (%s, %s, %s)
        """,
        (
            user_id,
            hash_secret(raw_token),
            datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
        ),
    )
    return raw_token


async def _deliver_email_verification(recipient: str, raw_token: str) -> bool:
    settings = get_settings()
    verification_url = f"{settings.public_webpage_url}/verify-email?{urlencode({'token': raw_token})}"
    try:
        await run_in_threadpool(
            send_email_verification_email,
            recipient,
            verification_url,
            settings=settings,
        )
        with transaction() as (_, cur):
            cur.execute(
                "UPDATE email_verification_token SET sent_at = now() WHERE token_hash = %s",
                (hash_secret(raw_token),),
            )
        return True
    except Exception:
        logger.exception("Could not deliver email verification message")
        with transaction() as (_, cur):
            cur.execute(
                "UPDATE email_verification_token SET used_at = now() WHERE token_hash = %s",
                (hash_secret(raw_token),),
            )
        return False


def _issue_email_change(cur, user_id: int, new_email: str, ttl_hours: int) -> str:
    raw_token = new_email_verification_token()
    cur.execute(
        "UPDATE email_change_token SET used_at = now() WHERE user_id = %s AND used_at IS NULL",
        (user_id,),
    )
    cur.execute(
        """
        INSERT INTO email_change_token (user_id, new_email, token_hash, expires_at)
        VALUES (%s, %s, %s, %s)
        """,
        (
            user_id,
            new_email,
            hash_secret(raw_token),
            datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
        ),
    )
    return raw_token


async def _deliver_email_change(recipient: str, raw_token: str) -> bool:
    settings = get_settings()
    verification_url = (
        f"{settings.public_webpage_url}/verify-email?"
        f"{urlencode({'token': raw_token, 'kind': 'change'})}"
    )
    try:
        await run_in_threadpool(
            send_email_verification_email,
            recipient,
            verification_url,
            settings=settings,
        )
        with transaction() as (_, cur):
            cur.execute(
                "UPDATE email_change_token SET sent_at = now() WHERE token_hash = %s",
                (hash_secret(raw_token),),
            )
        return True
    except Exception:
        logger.exception("Could not deliver email-change confirmation message")
        with transaction() as (_, cur):
            cur.execute(
                "UPDATE email_change_token SET used_at = now() WHERE token_hash = %s",
                (hash_secret(raw_token),),
            )
        return False


@router.post("/auth/signup")
async def signup(request: Request):
    form = await request.form()
    username = str(form.get("username", "")).strip()
    email = str(form.get("email", "")).strip().lower()
    password = str(form.get("password", ""))
    if not username or not email or len(password) < 8:
        return _error(request, "/signup?error=invalid", "Username, email, and an 8-character password are required")
    settings = get_settings()
    try:
        ensure_email_configured(settings)
    except EmailConfigurationError as exc:
        logger.error("Email verification configuration error: %s", exc)
        return _error(
            request,
            "/signup?error=email-unavailable",
            "Account registration is temporarily unavailable",
            503,
        )
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
            raw_token = _issue_email_verification(
                cur,
                user_id,
                settings.email_verification_ttl_hours,
            )
    except Exception as exc:
        if getattr(exc, "pgcode", None) == "23505":
            return _error(request, "/signup?error=exists", "Username or email already exists", 409)
        raise
    delivered = await _deliver_email_verification(email, raw_token)
    if not delivered:
        return _error(
            request,
            "/verify-email?delivery=failed",
            "Your account was created, but the confirmation email could not be sent. Please resend it.",
            503,
            code="email_delivery_failed",
        )
    if _wants_json(request):
        return JSONResponse({
            "ok": True,
            "requires_email_verification": True,
            "redirect": "/verify-email?sent=1",
        })
    return RedirectResponse("/verify-email?sent=1", status_code=303)


@router.post("/auth/login")
async def login(request: Request):
    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT user_id, password_hash, email_verified_at
            FROM "user"
            WHERE lower(username) = lower(%s)
            """,
            (username,),
        )
        row = cur.fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return _error(request, "/login?error=bad-login", "Incorrect username or password", 401)
    if row["email_verified_at"] is None:
        return _error(
            request,
            "/login?error=email-unverified",
            "Confirm your email address before logging in",
            403,
            code="email_unverified",
        )
    response = _success(request, "/dashboard/profile/")
    _set_session(response, int(row["user_id"]))
    return response


@router.post("/auth/email-verification/resend", status_code=202)
async def resend_email_verification(payload: EmailVerificationResendRequest):
    """Send a replacement link without revealing whether an account exists."""
    settings = get_settings()
    try:
        ensure_email_configured(settings)
    except EmailConfigurationError as exc:
        logger.error("Email verification configuration error: %s", exc)
        raise HTTPException(status_code=503, detail="Email confirmation is temporarily unavailable") from exc

    recipient: str | None = None
    raw_token: str | None = None
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT user_id, email
            FROM "user"
            WHERE lower(email) = lower(%s) AND email_verified_at IS NULL
            """,
            (payload.email.strip().lower(),),
        )
        user = cur.fetchone()
        if user:
            cur.execute(
                """
                SELECT count(*) AS recent_requests
                FROM email_verification_token
                WHERE user_id = %s AND created_at > now() - interval '2 minutes'
                """,
                (user["user_id"],),
            )
            if int(cur.fetchone()["recent_requests"]) == 0:
                recipient = str(user["email"])
                raw_token = _issue_email_verification(
                    cur,
                    int(user["user_id"]),
                    settings.email_verification_ttl_hours,
                )

    if recipient and raw_token:
        await _deliver_email_verification(recipient, raw_token)
    return {
        "ok": True,
        "detail": "If an unconfirmed account matches that address, a new confirmation link has been sent.",
    }


@router.post("/auth/email-verification/confirm")
def confirm_email_verification(payload: EmailVerificationRequest):
    token_hash = hash_secret(payload.token)
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT email_verification_token_id, user_id
            FROM email_verification_token
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
            raise HTTPException(status_code=400, detail="This confirmation link is invalid or has expired")
        cur.execute(
            'UPDATE "user" SET email_verified_at = now() WHERE user_id = %s',
            (token["user_id"],),
        )
        cur.execute(
            "UPDATE email_verification_token SET used_at = now() WHERE user_id = %s AND used_at IS NULL",
            (token["user_id"],),
        )
    return {"ok": True, "redirect": "/login?verified=success"}


@router.post("/auth/email-change/request", status_code=202)
async def request_email_change(payload: EmailChangeRequest, request: Request):
    user = require_user(request)
    settings = get_settings()
    try:
        ensure_email_configured(settings)
    except EmailConfigurationError as exc:
        logger.error("Email change configuration error: %s", exc)
        raise HTTPException(status_code=503, detail="Email changes are temporarily unavailable") from exc

    new_email = payload.new_email.strip().lower()
    if "@" not in new_email or new_email == str(user["email"]).lower():
        raise HTTPException(status_code=400, detail="Enter a different valid email address")

    with transaction() as (_, cur):
        cur.execute(
            'SELECT password_hash FROM "user" WHERE user_id = %s FOR UPDATE',
            (user["user_id"],),
        )
        account = cur.fetchone()
        if not account or not verify_password(payload.current_password, account["password_hash"]):
            raise HTTPException(status_code=403, detail="Current password is incorrect")
        cur.execute('SELECT 1 FROM "user" WHERE lower(email) = lower(%s)', (new_email,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="That email address is already in use")
        cur.execute(
            """
            SELECT count(*) AS recent_requests
            FROM email_change_token
            WHERE user_id = %s AND created_at > now() - interval '2 minutes'
            """,
            (user["user_id"],),
        )
        if int(cur.fetchone()["recent_requests"]) > 0:
            raise HTTPException(status_code=429, detail="Please wait before requesting another email change")
        raw_token = _issue_email_change(
            cur,
            int(user["user_id"]),
            new_email,
            settings.email_verification_ttl_hours,
        )

    if not await _deliver_email_change(new_email, raw_token):
        raise HTTPException(status_code=503, detail="The confirmation email could not be sent")
    return {
        "ok": True,
        "detail": "A confirmation link has been sent to the new email address. Your current address remains active until it is confirmed.",
    }


@router.post("/auth/email-change/confirm")
def confirm_email_change(payload: EmailVerificationRequest):
    token_hash = hash_secret(payload.token)
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT email_change_token_id, user_id, new_email
            FROM email_change_token
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
            raise HTTPException(status_code=400, detail="This email-change link is invalid or has expired")
        cur.execute(
            'SELECT 1 FROM "user" WHERE lower(email) = lower(%s) AND user_id <> %s',
            (token["new_email"], token["user_id"]),
        )
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="That email address is already in use")
        cur.execute(
            'UPDATE "user" SET email = %s, email_verified_at = now() WHERE user_id = %s',
            (token["new_email"], token["user_id"]),
        )
        cur.execute(
            "UPDATE email_change_token SET used_at = now() WHERE user_id = %s AND used_at IS NULL",
            (token["user_id"],),
        )
        cur.execute(
            "UPDATE web_session SET revoked_at = now() WHERE user_id = %s AND revoked_at IS NULL",
            (token["user_id"],),
        )
    return {"ok": True, "redirect": "/login?email-changed=success"}


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
