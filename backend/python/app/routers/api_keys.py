from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..database import transaction
from ..dependencies import require_user
from ..schemas import ApiKeyCreate
from ..security import new_api_key


router = APIRouter(prefix="/api/api-keys", tags=["api keys"])


@router.get("")
def list_api_keys(request: Request):
    user = require_user(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT k.api_key_id, k.name, k.key_prefix, k.key_type,
                   k.created_at, k.last_used_at, k.revoked_at, k.upgraded_at,
                   r.searches_per_hour, r.level_name
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


@router.post("", status_code=201)
def create_api_key(payload: ApiKeyCreate, request: Request):
    user = require_user(request)
    raw, prefix, digest = new_api_key("regular")
    with transaction() as (_, cur):
        cur.execute("SELECT api_rate_id FROM api_rate WHERE level_name = 'standard'")
        rate = cur.fetchone()
        if not rate:
            raise HTTPException(status_code=500, detail="Standard API rate is not configured")
        cur.execute(
            """
            INSERT INTO api_key (
                user_id, api_rate_id, name, key_prefix, key_hash, key_type
            ) VALUES (%s, %s, %s, %s, %s, 'regular')
            RETURNING api_key_id
            """,
            (user["user_id"], rate["api_rate_id"], payload.name.strip(), prefix, digest),
        )
        key_id = int(cur.fetchone()["api_key_id"])
    return {"api_key_id": key_id, "key": raw, "key_type": "regular"}


@router.post("/{api_key_id}/upgrade-master")
def upgrade_master_key(api_key_id: int, request: Request):
    user = require_user(request)
    if user["authority_type"] not in {"admin", "superadmin"}:
        raise HTTPException(status_code=403, detail="Only admins and superadmins can create master keys")
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
    if not row:
        raise HTTPException(status_code=404, detail="Active API key not found")
    return {"ok": True}
