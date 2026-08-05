from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from .config import get_settings
from .database import transaction
from .security import hash_secret


def current_user(request: Request) -> dict[str, Any] | None:
    settings = get_settings()
    token = request.cookies.get(settings.cookie_name)
    if not token:
        return None
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT u.user_id, u.username, u.email, u.alias, u.description,
                   a.name AS authority_type,
                   COALESCE(array_agg(DISTINCT ac.access_point)
                       FILTER (WHERE ac.access_point IS NOT NULL), ARRAY[]::text[]) AS access_points
            FROM web_session s
            JOIN "user" u ON u.user_id = s.user_id
            JOIN authority a ON a.authority_id = u.authority_id
            LEFT JOIN authority_access_map aam ON aam.authority_id = a.authority_id
            LEFT JOIN access ac ON ac.access_id = aam.access_id
            WHERE s.token_hash = %s
              AND s.revoked_at IS NULL
              AND s.expires_at > now()
            GROUP BY u.user_id, a.name
            """,
            (hash_secret(token),),
        )
        return cur.fetchone()


def require_user(request: Request) -> dict[str, Any]:
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_access(request: Request, access_point: str) -> dict[str, Any]:
    user = require_user(request)
    if access_point not in set(user.get("access_points") or []):
        raise HTTPException(status_code=403, detail=f"Access to {access_point} is not permitted")
    return user


def require_role(request: Request, roles: set[str]) -> dict[str, Any]:
    user = require_user(request)
    if user["authority_type"] not in roles:
        raise HTTPException(status_code=403, detail="Insufficient authority")
    return user


def _raw_api_key(request: Request) -> str:
    value = request.headers.get("x-api-key", "").strip()
    if value:
        return value
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    raise HTTPException(status_code=401, detail="API key required")


def authenticate_api_key(request: Request, *, master_required: bool = False) -> dict[str, Any]:
    raw = _raw_api_key(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT k.api_key_id, k.user_id, k.name, k.key_type, k.api_rate_id,
                   r.searches_per_hour, r.level_name,
                   u.username, a.name AS authority_type
            FROM api_key k
            JOIN "user" u ON u.user_id = k.user_id
            JOIN authority a ON a.authority_id = u.authority_id
            LEFT JOIN api_rate r ON r.api_rate_id = k.api_rate_id
            WHERE k.key_hash = %s AND k.revoked_at IS NULL
            FOR UPDATE OF k
            """,
            (hash_secret(raw),),
        )
        key = cur.fetchone()
        if not key:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key")
        if master_required and key["key_type"] != "master":
            raise HTTPException(status_code=403, detail="A master API key is required")

        if key["key_type"] != "master":
            limit = int(key.get("searches_per_hour") or 0)
            if limit <= 0:
                raise HTTPException(status_code=429, detail="This API key has no active rate allowance")
            cur.execute(
                """
                INSERT INTO api_rate_window (api_key_id, window_started_at, request_count)
                VALUES (%s, now(), 1)
                ON CONFLICT (api_key_id) DO UPDATE SET
                    window_started_at = CASE
                        WHEN api_rate_window.window_started_at <= now() - interval '1 hour'
                        THEN now() ELSE api_rate_window.window_started_at END,
                    request_count = CASE
                        WHEN api_rate_window.window_started_at <= now() - interval '1 hour'
                        THEN 1 ELSE api_rate_window.request_count + 1 END
                RETURNING window_started_at, request_count
                """,
                (key["api_key_id"],),
            )
            window = cur.fetchone()
            if int(window["request_count"]) > limit:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded: {limit} requests per hour",
                    headers={"Retry-After": "3600"},
                )
            key["rate_remaining"] = max(0, limit - int(window["request_count"]))
        else:
            key["rate_remaining"] = None

        cur.execute("UPDATE api_key SET last_used_at = now() WHERE api_key_id = %s", (key["api_key_id"],))
        return key
