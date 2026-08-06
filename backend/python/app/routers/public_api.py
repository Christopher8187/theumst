from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, Response, UploadFile

from ..config import get_settings
from ..dependencies import authenticate_api_key
from ..schemas import EmbeddingBatchInput, KnowledgeSubmission, StorageFolderCreate, StorageTextWrite
from ..services import storage
from ..services.knowledge import get_knowledge, list_knowledge, submit_embeddings, submit_knowledge
from ..services.book_ingestion import ingest_book_archive


router = APIRouter(prefix="/api/v1", tags=["public API"])


@router.get("/storage/{path:path}", include_in_schema=False)
def read_public_local_storage(path: str):
    if storage.storage_mode() != "LOCAL":
        raise HTTPException(status_code=404, detail="Local storage serving is disabled")
    return Response(
        content=storage.read_bytes(path),
        media_type=storage.media_type_for(path),
    )


@router.get("/knowledge")
def read_knowledge_collection(
    request: Request,
    language_id: int = Query(1, gt=0),
    limit: int | None = Query(default=None, gt=0),
    offset: int = Query(0, ge=0),
    grimoire_id: int | None = Query(default=None, gt=0),
    section_id: int | None = Query(default=None, gt=0),
    type: str | None = Query(default=None, max_length=80),
):
    key = authenticate_api_key(request)
    settings = get_settings()
    maximum = settings.master_read_max_page_size if key["key_type"] == "master" else settings.regular_read_max_page_size
    requested = limit or settings.regular_read_page_size
    if requested > maximum:
        raise HTTPException(status_code=422, detail=f"limit may not exceed {maximum} for this key")
    rows = list_knowledge(
        language_id=language_id, limit=requested, offset=offset,
        grimoire_id=grimoire_id, section_id=section_id, working_type=type,
    )
    return {
        "items": rows, "limit": requested, "offset": offset,
        "key_type": key["key_type"], "rate_remaining": key.get("rate_remaining"),
    }


@router.get("/knowledge/{knowledge_id}")
def read_one_knowledge(knowledge_id: int, request: Request, language_id: int = Query(1, gt=0)):
    key = authenticate_api_key(request)
    return {
        "item": get_knowledge(knowledge_id, language_id),
        "key_type": key["key_type"], "rate_remaining": key.get("rate_remaining"),
    }


@router.post("/books/ingest-archive", status_code=201)
async def create_book_archive(
    request: Request,
    archive: UploadFile = File(...),
):
    key = authenticate_api_key(request, master_required=True)
    result = await ingest_book_archive(archive)
    result["submitted_by"] = {"user_id": key["user_id"], "api_key_id": key["api_key_id"]}
    return result


@router.post("/knowledge", status_code=201)
def create_knowledge(payload: KnowledgeSubmission, request: Request):
    key = authenticate_api_key(request, master_required=True)
    result = submit_knowledge(payload)
    result["submitted_by"] = {"user_id": key["user_id"], "api_key_id": key["api_key_id"]}
    return result


@router.post("/knowledge/{knowledge_id}/embeddings", status_code=201)
def add_knowledge_embeddings(
    knowledge_id: int,
    payload: EmbeddingBatchInput,
    request: Request,
):
    key = authenticate_api_key(request, master_required=True)
    result = submit_embeddings(knowledge_id, payload)
    result["submitted_by"] = {"user_id": key["user_id"], "api_key_id": key["api_key_id"]}
    return result


@router.post("/storage/folders", status_code=201)
def add_storage_folder(payload: StorageFolderCreate, request: Request):
    authenticate_api_key(request, master_required=True)
    key = storage.child_key(payload.path, payload.name)
    return {"ok": True, "path": storage.create_folder(key)}


@router.post("/storage/text", status_code=201)
def add_storage_text(payload: StorageTextWrite, request: Request):
    authenticate_api_key(request, master_required=True)
    return {"ok": True, "path": storage.write_bytes(payload.path, payload.content.encode("utf-8"))}


@router.post("/storage/files", status_code=201)
async def add_storage_file(
    request: Request,
    file: UploadFile = File(...),
    folder: str = Form(""),
):
    authenticate_api_key(request, master_required=True)
    key = storage.child_key(folder, file.filename or "upload.bin")
    return {"ok": True, "path": storage.write_bytes(key, await file.read())}
