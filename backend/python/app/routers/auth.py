from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from ..config import get_settings
from ..database import transaction
from ..security import (
    hash_password,
    hash_secret,
    new_session_token,
    session_expiry,
    verify_password,
)


router = APIRouter(tags=["authentication"])


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
