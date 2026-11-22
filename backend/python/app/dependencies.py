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
# long game session never uses up a key's book allowance. Since 0.0.19 the game
# agents' search (/api/game/search) and graph reads (/api/game/graph) have kinds
# of their own (migration 018).
API_REQUEST_KINDS = ("book", "character", "search", "graph")
RATE_WINDOW_SECONDS = 60


def authenticate_api_key(
    request: Request,
    *,
    kind: str,
    master_required: bool = False,
    master_allowed: bool = True,
    access_point: str | None = None,
    cost: int = 1,
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

    `cost` is how many requests this one counts as, in the window and in
    api_usage_daily: a figure batch counts one for each figure it asks for, as
    fetching each alone would (0.0.18). A regular key is refused when the
    window's count would pass its limit. return_api_requests gives back what a
    request did not use.
    """
    if kind not in API_REQUEST_KINDS:
        raise ValueError(f"Unknown API request kind: {kind}")
    if cost < 1:
        raise ValueError(f"An API request counts at least once, not {cost}")
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
            # now() is the transaction's start, so usage_day is the day api_usage_daily counts this in below.
            cur.execute(
                """
                INSERT INTO api_rate_window (api_key_id, kind, window_started_at, request_count)
                VALUES (%s, %s, now(), %s)
                ON CONFLICT (api_key_id, kind) DO UPDATE SET
                    window_started_at = CASE
                        WHEN api_rate_window.window_started_at <= now() - interval '1 minute'
                        THEN now() ELSE api_rate_window.window_started_at END,
                    request_count = CASE
                        WHEN api_rate_window.window_started_at <= now() - interval '1 minute'
                        THEN EXCLUDED.request_count
                        ELSE api_rate_window.request_count + EXCLUDED.request_count END
                RETURNING request_count, window_started_at, (now() AT TIME ZONE 'UTC')::date AS usage_day,
                    GREATEST(1, ceil(extract(epoch FROM
                        window_started_at + interval '1 minute' - now())))::int AS retry_after
                """,
                (key["api_key_id"], kind, cost),
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
            key["rate_window_started_at"] = window.get("window_started_at")
            key["usage_day"] = window.get("usage_day")
        else:
            key["rate_limit"] = None
            key["rate_remaining"] = None

        cur.execute(
            """
            INSERT INTO api_usage_daily (api_key_id, day, kind, request_count)
            VALUES (%s, (now() AT TIME ZONE 'UTC')::date, %s, %s)
            ON CONFLICT (api_key_id, day, kind)
            DO UPDATE SET request_count = api_usage_daily.request_count + EXCLUDED.request_count
            """,
            (key["api_key_id"], kind, cost),
        )
        cur.execute("UPDATE api_key SET last_used_at = now() WHERE api_key_id = %s", (key["api_key_id"],))
        key["kind"] = kind
        return key


def return_api_requests(key: dict[str, Any], count: int) -> None:
    """Give back count of what authenticate_api_key counted for a regular key's request (key as it
    returned it), for work the request did not do: a figure batch's figures it named `later` without
    reading them (0.0.18). The window gets them back while it is still the window they were counted in,
    and api_usage_daily's day loses them. A master key's request, which no window counts, is left as
    counted."""
    window_started_at = key.get("rate_window_started_at")
    day = key.get("usage_day")
    if count <= 0 or window_started_at is None or day is None:
        return
    with transaction() as (_, cur):
        cur.execute(
            """
            UPDATE api_rate_window SET request_count = GREATEST(0, request_count - %s)
            WHERE api_key_id = %s AND kind = %s AND window_started_at = %s
            """,
            (count, key["api_key_id"], key["kind"], window_started_at),
        )
        cur.execute(
            """
            UPDATE api_usage_daily SET request_count = GREATEST(0, request_count - %s)
            WHERE api_key_id = %s AND kind = %s AND day = %s
            """,
            (count, key["api_key_id"], key["kind"], day),
        )
