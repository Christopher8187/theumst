from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from ..database import transaction
from ..dependencies import require_user
from ..schemas import ApiKeyCreate
from ..services.api_keys import StandardTierMissing, create_regular_key, ensure_default_key


router = APIRouter(prefix="/api/api-keys", tags=["api keys"])


@router.get("")
def list_api_keys(request: Request):
    user = require_user(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT k.api_key_id, k.name, k.key_prefix, k.key_type, k.client,
                   k.created_at, k.last_used_at, k.revoked_at, k.upgraded_at,
                   r.requests_per_minute, r.level_name
            FROM api_key k
            LEFT JOIN api_rate r ON r.api_rate_id = k.api_rate_id
            WHERE k.user_id = %s
            ORDER BY k.created_at DESC
            """,
            (user["user_id"],),
        )
        keys = list(cur.fetchall())
    can_upgrade = user["authority_type"] in {"admin", "superadmin"}
    for item in keys:
        item["can_upgrade_to_master"] = bool(can_upgrade and item["key_type"] == "regular" and not item["revoked_at"])
    return {"keys": keys}


@router.post("/default")
def ensure_default_api_key(request: Request, response: Response):
    """Make the account's Default key the first time its API Keys page opens.

    The response carries the key's full text only when this call made it.
    """
    user = require_user(request)
    try:
        with transaction() as (_, cur):
            made = ensure_default_key(cur, int(user["user_id"]))
    except StandardTierMissing as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from None
    response.headers["Cache-Control"] = "no-store"
    if not made:
        return {"created": False}
    response.status_code = 201
    return {"created": True, "key": made}


@router.post("", status_code=201)
def create_api_key(payload: ApiKeyCreate, request: Request, response: Response):
    user = require_user(request)
    try:
        with transaction() as (_, cur):
            made = create_regular_key(cur, int(user["user_id"]), payload.name.strip())
    except StandardTierMissing as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from None
    response.headers["Cache-Control"] = "no-store"
    return {"api_key_id": made["api_key_id"], "name": made["name"], "key": made["key"], "key_type": "regular"}


@router.post("/{api_key_id}/upgrade-master")
def upgrade_master_key(api_key_id: int, request: Request):
    user = require_user(request)
    if user["authority_type"] not in {"admin", "superadmin"}:
        raise HTTPException(status_code=403, detail="This account is not permitted to create master keys")
    with transaction() as (_, cur):
        cur.execute(
            """
            UPDATE api_key
            SET key_type = 'master', api_rate_id = NULL,
                upgraded_at = now(), upgraded_by_user_id = %s
            WHERE api_key_id = %s AND user_id = %s
              AND revoked_at IS NULL AND key_type = 'regular'
            RETURNING api_key_id, key_type, upgraded_at
            """,
            (user["user_id"], api_key_id, user["user_id"]),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Active regular API key not found")
    return {"ok": True, "key": row}


@router.delete("/{api_key_id}")
def revoke_api_key(api_key_id: int, request: Request):
    user = require_user(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            UPDATE api_key SET revoked_at = now()
            WHERE api_key_id = %s AND user_id = %s AND revoked_at IS NULL
            RETURNING api_key_id
            """,
            (api_key_id, user["user_id"]),
        )
        row = cur.fetchone()
        if row:
            # A revoked key can no longer heartbeat, so free what it had open
            # instead of making another computer wait for the lease to lapse.
            cur.execute(
                """
                UPDATE "character" SET lease_api_key_id = NULL, lease_expires_at = NULL
                WHERE lease_api_key_id = %s
                """,
                (api_key_id,),
            )
    if not row:
        raise HTTPException(status_code=404, detail="Active API key not found")
    return {"ok": True}
