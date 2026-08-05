from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..database import transaction
from ..dependencies import require_user
from ..schemas import ProfileUpdate


router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/me")
def get_me(request: Request):
    return {"user": require_user(request)}


@router.put("/me")
def update_me(payload: ProfileUpdate, request: Request):
    user = require_user(request)
    try:
        with transaction() as (_, cur):
            cur.execute(
                """
                UPDATE "user" SET username = %s, email = %s, alias = %s, description = %s
                WHERE user_id = %s
                RETURNING username, email, alias, description
                """,
                (
                    payload.username.strip(), payload.email.strip().lower(),
                    payload.alias, payload.description, user["user_id"],
                ),
            )
            updated = cur.fetchone()
    except Exception as exc:
        if getattr(exc, "pgcode", None) == "23505":
            raise HTTPException(status_code=409, detail="Username or email already exists") from exc
        raise
    return {"ok": True, "user": updated}
