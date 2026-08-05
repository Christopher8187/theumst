from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..database import transaction
from ..dependencies import require_access
from ..schemas import IdentifierRequest, SqlRequest


router = APIRouter(prefix="/api/superadmin", tags=["superadmin"])


def _superadmin(request: Request):
    return require_access(request, "superadmin")


@router.post("/make-admin")
def make_admin(payload: IdentifierRequest, request: Request):
    _superadmin(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            UPDATE "user" SET authority_id = (
                SELECT authority_id FROM authority WHERE name = 'admin'
            )
            WHERE (lower(username) = lower(%s) OR lower(email) = lower(%s))
              AND authority_id <> (
                  SELECT authority_id FROM authority WHERE name = 'superadmin'
              )
            RETURNING user_id, username, email
            """,
            (payload.identifier.strip(), payload.identifier.strip()),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found, or user is already a superadmin")
    return {"ok": True, "user": row}


@router.post("/sql")
def run_sql(payload: SqlRequest, request: Request):
    """Execute arbitrary PostgreSQL as a superadmin-only dashboard operation."""
    _superadmin(request)
    with transaction() as (_, cur):
        cur.execute(payload.sql)
        if cur.description:
            rows = list(cur.fetchall())
            return {"ok": True, "rows": rows, "row_count": len(rows), "status": cur.statusmessage}
        return {"ok": True, "rows": [], "row_count": cur.rowcount, "status": cur.statusmessage}
