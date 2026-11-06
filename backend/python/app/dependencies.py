from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from .config import get_settings
from .database import transaction
from .security import hash_secret


# The Web Demo's access point. The Demo's proxy checks it for a session through
# /api/demo/auth-check; since 0.0.13 a key needs it to read books as well.
DEMO_ACCESS_POINT = "demo"

_ACCESS_REFUSALS = {
    DEMO_ACCESS_POINT: "Reading books needs Web Demo access; request it from the dashboard",
}


class AccessRefused(HTTPException):
    """403 for an account without the access point a request needs.

    Answered as {"code": "<access point>_access_required", "detail"}, so a client
    can tell it from a refused key or a missing master key.
    """

    def __init__(self, access_point: str):
        super().__init__(
            status_code=403,
            detail=_ACCESS_REFUSALS.get(access_point, f"Access to {access_point} is not permitted"),
        )
        self.code = f"{access_point}_access_required"


async def access_refused_response(request: Request, exc: AccessRefused) -> JSONResponse:
    return JSONResponse(
        {"code": exc.code, "detail": exc.detail},
        status_code=exc.status_code,
        headers={"Cache-Control": "no-store"},
    )


def current_user(request: Request) -> dict[str, Any] | None:
    # Authentication is DB-backed and revalidated at most once per request.
    # Reuse the same result if middleware and an endpoint both need the actor.
    if getattr(request.state, "_theumst_user_resolved", False):
        return getattr(request.state, "_theumst_user", None)
    settings = get_settings()
    token = request.cookies.get(settings.cookie_name)
    if not token:
        request.state._theumst_user = None
        request.state._theumst_user_resolved = True
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
              AND u.email_verified_at IS NOT NULL
            GROUP BY u.user_id, a.name
            """,
            (hash_secret(token),),
        )
        user = cur.fetchone()
    request.state._theumst_user = user
    request.state._theumst_user_resolved = True
    return user


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


def has_api_key(request: Request) -> bool:
    """Whether the request sends a key where authenticate_api_key looks for one."""
    if request.headers.get("x-api-key", "").strip():
        return True
    return request.headers.get("authorization", "").lower().startswith("bearer ")


def _raw_api_key(request: Request) -> str:
    value = request.headers.get("x-api-key", "").strip()
    if value:
        return value
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    raise HTTPException(status_code=401, detail="API key required")


# Book reads (/api/v1) and the game's calls (/api/game) are counted apart, so a
# long game session never uses up a key's book allowance.
API_REQUEST_KINDS = ("book", "character")
RATE_WINDOW_SECONDS = 60


def authenticate_api_key(
    request: Request,
    *,
    kind: str,
    master_required: bool = False,
    master_allowed: bool = True,
    access_point: str | None = None,
) -> dict[str, Any]:
    """Resolve an active key and count this request as `kind`.

    A regular key may make its tier's requests_per_minute requests of each kind
    in a one-minute window; beyond that, or on a tier without allowance, it gets
    429 with Retry-After in seconds. Master keys have no limit; a route that
    does not take them refuses them with 403 before anything is counted. With
    `access_point`, a regular key whose account lacks it gets AccessRefused
    (403 `<access point>_access_required`) before anything is counted: the same
    authority/access-point check a session gets from require_access. Master
    keys pass it. Every accepted request, master keys included, adds one to
    api_usage_daily for the key, UTC day and kind; a refused request rolls back
    and is counted nowhere.
    """
    if kind not in API_REQUEST_KINDS:
        raise ValueError(f"Unknown API request kind: {kind}")
    raw = _raw_api_key(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT k.api_key_id, k.user_id, k.name, k.key_prefix, k.key_type, k.client,
                   k.api_rate_id, r.requests_per_minute, r.level_name,
                   u.username, a.name AS authority_type,
                   ARRAY(
                       SELECT ac.access_point
                       FROM authority_access_map aam
                       JOIN access ac ON ac.access_id = aam.access_id
                       WHERE aam.authority_id = a.authority_id
                       ORDER BY ac.access_point
                   ) AS access_points
            FROM api_key k
            JOIN "user" u ON u.user_id = k.user_id
            JOIN authority a ON a.authority_id = u.authority_id
            LEFT JOIN api_rate r ON r.api_rate_id = k.api_rate_id
            WHERE k.key_hash = %s
              AND k.revoked_at IS NULL
              AND u.email_verified_at IS NOT NULL
            FOR UPDATE OF k
            """,
            (hash_secret(raw),),
        )
        key = cur.fetchone()
        if not key:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key")
        if master_required and key["key_type"] != "master":
            raise HTTPException(status_code=403, detail="A master API key is required")
        if not master_allowed and key["key_type"] == "master":
            raise HTTPException(status_code=403, detail="Master keys are not accepted here")
        if (
            access_point is not None
            and key["key_type"] != "master"
            and access_point not in set(key.get("access_points") or ())
        ):
            raise AccessRefused(access_point)

        if key["key_type"] != "master":
            limit = int(key.get("requests_per_minute") or 0)
            if limit <= 0:
                raise HTTPException(
                    status_code=429,
                    detail="This API key has no active rate allowance",
                    headers={"Retry-After": str(RATE_WINDOW_SECONDS)},
                )
            cur.execute(
                """
                INSERT INTO api_rate_window (api_key_id, kind, window_started_at, request_count)
                VALUES (%s, %s, now(), 1)
                ON CONFLICT (api_key_id, kind) DO UPDATE SET
                    window_started_at = CASE
                        WHEN api_rate_window.window_started_at <= now() - interval '1 minute'
                        THEN now() ELSE api_rate_window.window_started_at END,
                    request_count = CASE
                        WHEN api_rate_window.window_started_at <= now() - interval '1 minute'
                        THEN 1 ELSE api_rate_window.request_count + 1 END
                RETURNING request_count,
                    GREATEST(1, ceil(extract(epoch FROM
                        window_started_at + interval '1 minute' - now())))::int AS retry_after
                """,
                (key["api_key_id"], kind),
            )
            window = cur.fetchone()
            count = int(window["request_count"])
            if count > limit:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded: {limit} {kind} requests per minute",
                    headers={"Retry-After": str(int(window["retry_after"]))},
                )
            key["rate_limit"] = limit
            key["rate_remaining"] = max(0, limit - count)
        else:
            key["rate_limit"] = None
            key["rate_remaining"] = None

        cur.execute(
            """
            INSERT INTO api_usage_daily (api_key_id, day, kind, request_count)
            VALUES (%s, (now() AT TIME ZONE 'UTC')::date, %s, 1)
            ON CONFLICT (api_key_id, day, kind)
            DO UPDATE SET request_count = api_usage_daily.request_count + 1
            """,
            (key["api_key_id"], kind),
        )
        cur.execute("UPDATE api_key SET last_used_at = now() WHERE api_key_id = %s", (key["api_key_id"],))
        key["kind"] = kind
        return key
