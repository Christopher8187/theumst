from __future__ import annotations

import io
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from ..database import transaction
from ..dependencies import require_access
from ..schemas import IdentifierRequest, QdrantSearchRequest, StorageFolderCreate, StorageTextWrite
from ..services import storage
from ..services.qdrant import qdrant_service
from ..services.corpus_access import (
    actor_user_id,
    corpus_visibility_params,
    corpus_visibility_sql,
    ensure_policy_ready,
    filter_storage_items,
    require_storage_key_access,
    revision_headers,
)


router = APIRouter(prefix="/api/admin", tags=["admin"])


def _admin(request: Request):
    return require_access(request, "admin")


@router.get("/users")
def list_users(request: Request):
    """Return dashboard-safe account information without exposing internal role names."""
    _admin(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT
                u.user_id,
                u.username,
                u.email,
                COALESCE(u.alias, '') AS alias,
                COALESCE(u.description, '') AS description,
                u.created_at,
                CASE a.name
                    WHEN 'user' THEN 'user'
                    WHEN 'betatester' THEN 'betatester'
                    WHEN 'manager' THEN 'manager'
                    ELSE 'staff'
                END AS account_type,
                COALESCE(keys.active_api_keys, 0) AS active_api_keys,
                sessions.last_session_at,
                requests.demo_status
            FROM "user" u
            JOIN authority a ON a.authority_id = u.authority_id
            LEFT JOIN LATERAL (
                SELECT count(*) AS active_api_keys
                FROM api_key
                WHERE user_id = u.user_id AND revoked_at IS NULL
            ) keys ON true
            LEFT JOIN LATERAL (
                SELECT max(created_at) AS last_session_at
                FROM web_session
                WHERE user_id = u.user_id
            ) sessions ON true
            LEFT JOIN LATERAL (
                SELECT status AS demo_status
                FROM demo_access_request
                WHERE user_id = u.user_id
                LIMIT 1
            ) requests ON true
            ORDER BY u.created_at DESC, u.user_id DESC
            """
        )
        users = list(cur.fetchall())
    return {"users": users}


@router.post("/make-manager")
def make_manager(payload: IdentifierRequest, request: Request):
    """Promote a regular user to manager without allowing privilege downgrades."""
    _admin(request)
    identifier = payload.identifier.strip()
    with transaction() as (_, cur):
        cur.execute(
            """
            UPDATE "user" SET authority_id = (
                SELECT authority_id FROM authority WHERE name = 'manager'
            )
            WHERE (lower(username) = lower(%s) OR lower(email) = lower(%s))
              AND authority_id IN (
                  SELECT authority_id FROM authority WHERE name IN ('user', 'betatester', 'manager')
              )
            RETURNING user_id, username, email
            """,
            (identifier, identifier),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail="User not found, or this account already has higher authority",
        )
    return {"ok": True, "user": row}


@router.post("/qdrant/search")
def qdrant_search(payload: QdrantSearchRequest, request: Request):
    user = _admin(request)
    user_id = actor_user_id(user)
    if not ensure_policy_ready(
        user_id=user_id,
        surface="index",
        list_request=True,
    ):
        return {"collection": qdrant_service.settings.qdrant_collection, "results": []}
    vector = payload.query_vector or qdrant_service.embed_query(payload.query_text or "")
    hits = qdrant_service.search(
        vector,
        limit=payload.limit,
        score_threshold=payload.score_threshold,
        filters=payload.filters,
    )
    point_ids = []
    for hit in hits:
        try:
            point_ids.append(str(UUID(str(hit.get("id") or ""))))
        except (TypeError, ValueError, AttributeError):
            continue
    allowed_points: set[str] = set()
    if point_ids:
        with transaction() as (_, cur):
            visibility = corpus_visibility_sql("s.grimoire_id")
            cur.execute(
                f"""
                SELECT e.embedding_id::text AS embedding_id
                FROM embedding e
                JOIN semantic_projection sp
                  ON sp.semantic_projection_id = e.semantic_projection_id
                JOIN knowledge k ON k.knowledge_id = sp.knowledge_id
                JOIN section s ON s.section_id = k.section_id
                WHERE e.embedding_id = ANY(%s::uuid[]) AND {visibility}
                """,
                (sorted(set(point_ids)), *corpus_visibility_params(user_id)),
            )
            allowed_points = {str(row["embedding_id"]) for row in cur.fetchall()}
    return {
        "collection": qdrant_service.settings.qdrant_collection,
        "results": [hit for hit in hits if str(hit.get("id")) in allowed_points],
    }


@router.get("/storage")
def list_storage(request: Request, path: str = ""):
    user = _admin(request)
    user_id = actor_user_id(user)
    clean_path = storage.clean_key(path)
    with transaction() as (_, cur):
        require_storage_key_access(cur, storage_key=clean_path, user_id=user_id)
    # Do not touch local/cloud storage until configuration and the requested
    # prefix have passed the central database policy.
    items = storage.list_items(clean_path)
    with transaction() as (_, cur):
        items = filter_storage_items(cur, items=items, user_id=user_id)
    return {"path": clean_path, "mode": storage.storage_mode(), "items": items}


@router.get("/storage/read")
def read_storage(request: Request, path: str):
    user = _admin(request)
    user_id = actor_user_id(user)
    clean_path = storage.clean_key(path)
    with transaction() as (_, cur):
        require_storage_key_access(cur, storage_key=clean_path, user_id=user_id)
    return {"path": clean_path, "content": storage.read_bytes(clean_path).decode("utf-8")}


@router.get("/storage/download")
def download_storage(request: Request, path: str):
    user = _admin(request)
    user_id = actor_user_id(user)
    clean_path = storage.clean_key(path)
    with transaction() as (_, cur):
        protected = require_storage_key_access(cur, storage_key=clean_path, user_id=user_id)
        access_headers = revision_headers(cur, user_id) if protected else {}
    data = storage.read_bytes(clean_path)
    name = storage.clean_key(path).split("/")[-1]
    return StreamingResponse(
        io.BytesIO(data), media_type=storage.media_type_for(path),
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            **access_headers,
        },
    )


@router.post("/storage/write")
def write_storage(payload: StorageTextWrite, request: Request):
    user = _admin(request)
    with transaction() as (_, cur):
        require_storage_key_access(
            cur,
            storage_key=storage.clean_key(payload.path),
            user_id=actor_user_id(user),
        )
    return {"ok": True, "path": storage.write_bytes(payload.path, payload.content.encode("utf-8"))}


@router.post("/storage/folder")
def create_storage_folder(payload: StorageFolderCreate, request: Request):
    user = _admin(request)
    key = storage.child_key(payload.path, payload.name)
    with transaction() as (_, cur):
        require_storage_key_access(cur, storage_key=key, user_id=actor_user_id(user))
    return {"ok": True, "path": storage.create_folder(key)}


@router.post("/storage/upload")
async def upload_storage_file(
    request: Request,
    file: UploadFile = File(...),
    folder: str = Form(""),
):
    user = _admin(request)
    key = storage.child_key(folder, file.filename or "upload.bin")
    with transaction() as (_, cur):
        require_storage_key_access(cur, storage_key=key, user_id=actor_user_id(user))
    return {"ok": True, "path": storage.write_bytes(key, await file.read())}


@router.delete("/storage")
def delete_storage(request: Request, path: str):
    user = _admin(request)
    clean_path = storage.clean_key(path)
    with transaction() as (_, cur):
        require_storage_key_access(
            cur,
            storage_key=clean_path,
            user_id=actor_user_id(user),
            destructive=True,
        )
    storage.delete(clean_path)
    return {"ok": True}
