from __future__ import annotations

import io

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from ..database import transaction
from ..dependencies import require_access
from ..schemas import IdentifierRequest, QdrantSearchRequest, StorageFolderCreate, StorageTextWrite
from ..services import storage
from ..services.qdrant import qdrant_service


router = APIRouter(prefix="/api/admin", tags=["admin"])


def _admin(request: Request):
    return require_access(request, "admin")


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
                  SELECT authority_id FROM authority WHERE name IN ('user', 'manager')
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
    _admin(request)
    vector = payload.query_vector or qdrant_service.embed_query(payload.query_text or "")
    return {
        "collection": qdrant_service.settings.qdrant_collection,
        "results": qdrant_service.search(
            vector,
            limit=payload.limit,
            score_threshold=payload.score_threshold,
            filters=payload.filters,
        ),
    }


@router.get("/storage")
def list_storage(request: Request, path: str = ""):
    _admin(request)
    return {"path": storage.clean_key(path), "mode": storage.storage_mode(), "items": storage.list_items(path)}


@router.get("/storage/read")
def read_storage(request: Request, path: str):
    _admin(request)
    return {"path": storage.clean_key(path), "content": storage.read_bytes(path).decode("utf-8")}


@router.get("/storage/download")
def download_storage(request: Request, path: str):
    _admin(request)
    data = storage.read_bytes(path)
    name = storage.clean_key(path).split("/")[-1]
    return StreamingResponse(
        io.BytesIO(data), media_type=storage.media_type_for(path),
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/storage/write")
def write_storage(payload: StorageTextWrite, request: Request):
    _admin(request)
    return {"ok": True, "path": storage.write_bytes(payload.path, payload.content.encode("utf-8"))}


@router.post("/storage/folder")
def create_storage_folder(payload: StorageFolderCreate, request: Request):
    _admin(request)
    key = storage.child_key(payload.path, payload.name)
    return {"ok": True, "path": storage.create_folder(key)}


@router.post("/storage/upload")
async def upload_storage_file(
    request: Request,
    file: UploadFile = File(...),
    folder: str = Form(""),
):
    _admin(request)
    key = storage.child_key(folder, file.filename or "upload.bin")
    return {"ok": True, "path": storage.write_bytes(key, await file.read())}


@router.delete("/storage")
def delete_storage(request: Request, path: str):
    _admin(request)
    storage.delete(path)
    return {"ok": True}
