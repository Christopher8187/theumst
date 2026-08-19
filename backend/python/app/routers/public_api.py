from __future__ import annotations

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import RedirectResponse

from ..config import get_settings
from ..database import transaction
from ..dependencies import authenticate_api_key, current_user
from ..schemas import (
    EmbeddingBatchInput,
    KnowledgeSubmission,
    StorageFolderCreate,
    StorageTextWrite,
)
from ..services import storage
from ..services.corpus_access import (
    actor_user_id,
    corpus_visibility_params,
    corpus_visibility_sql,
    ensure_policy_ready,
    raise_hidden_asset_miss,
    require_storage_key_access,
    revision_headers,
    signed_asset_ttl_seconds,
)
from ..services.book_ingestion import ingest_book_archive
from ..services.knowledge import (
    get_knowledge,
    list_knowledge,
    submit_embeddings,
    submit_knowledge,
)

router = APIRouter(prefix="/api/v1", tags=["public API"])


def _optional_storage_actor(request: Request) -> int | None:
    session_user = current_user(request)
    if session_user:
        return actor_user_id(session_user)
    has_key = bool(
        request.headers.get("x-api-key", "").strip()
        or request.headers.get("authorization", "").strip()
    )
    if not has_key:
        return None
    try:
        return actor_user_id(authenticate_api_key(request))
    except HTTPException:
        return None


@router.get("/storage/{path:path}", include_in_schema=False)
def read_public_storage(path: str, request: Request):
    key = storage.clean_key(path)
    user_id = _optional_storage_actor(request)
    ensure_policy_ready(user_id=user_id, surface="asset")
    with transaction() as (_, cur):
        protected = require_storage_key_access(
            cur,
            storage_key=key,
            user_id=user_id,
        )
        visibility = corpus_visibility_sql("bi.grimoire_id")
        cur.execute(
            f"""
            SELECT bi.grimoire_id
            FROM book_image bi
            WHERE bi.storage_key = %s AND bi.is_active AND {visibility}
            LIMIT 1
            """,
            (key, *corpus_visibility_params(user_id)),
        )
        if cur.fetchone() is None:
            raise_hidden_asset_miss(cur, storage_key=key, user_id=user_id)
        response_headers = (
            revision_headers(cur, user_id)
            if protected
            else {"Cache-Control": "public, max-age=300"}
        )
    if storage.storage_mode() == "LOCAL":
        return Response(
            content=storage.read_bytes(key),
            media_type=storage.media_type_for(key),
            headers=response_headers,
        )
    return RedirectResponse(
        storage.signed_read_url(key, expires_seconds=signed_asset_ttl_seconds()),
        status_code=307,
        headers=response_headers,
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
    user_id = actor_user_id(key)
    settings = get_settings()
    maximum = settings.master_read_max_page_size if key["key_type"] == "master" else settings.regular_read_max_page_size
    requested = limit or settings.regular_read_page_size
    if requested > maximum:
        raise HTTPException(status_code=422, detail=f"limit may not exceed {maximum} for this key")
    rows = list_knowledge(
        language_id=language_id, limit=requested, offset=offset,
        grimoire_id=grimoire_id, section_id=section_id, working_type=type,
        actor_user_id=user_id,
    )
    return {
        "items": rows, "limit": requested, "offset": offset,
        "key_type": key["key_type"], "rate_remaining": key.get("rate_remaining"),
    }


@router.get("/knowledge/{knowledge_id}")
def read_one_knowledge(knowledge_id: int, request: Request, language_id: int = Query(1, gt=0)):
    key = authenticate_api_key(request)
    return {
        "item": get_knowledge(
            knowledge_id,
            language_id,
            actor_user_id=actor_user_id(key),
        ),
        "key_type": key["key_type"], "rate_remaining": key.get("rate_remaining"),
    }


@router.post("/books/ingest-archive", status_code=201)
async def create_book_archive(
    request: Request,
    archive: UploadFile = File(...),
):
    key = authenticate_api_key(request, master_required=True)
    result = await ingest_book_archive(archive, actor_user_id=actor_user_id(key))
    result["submitted_by"] = {"user_id": key["user_id"], "api_key_id": key["api_key_id"]}
    return result


@router.post("/knowledge", status_code=201)
def create_knowledge(payload: KnowledgeSubmission, request: Request):
    key = authenticate_api_key(request, master_required=True)
    result = submit_knowledge(payload, actor_user_id=actor_user_id(key))
    result["submitted_by"] = {"user_id": key["user_id"], "api_key_id": key["api_key_id"]}
    return result


@router.post("/knowledge/{knowledge_id}/embeddings", status_code=201)
def add_knowledge_embeddings(
    knowledge_id: int,
    payload: EmbeddingBatchInput,
    request: Request,
):
    key = authenticate_api_key(request, master_required=True)
    result = submit_embeddings(
        knowledge_id,
        payload,
        actor_user_id=actor_user_id(key),
    )
    result["submitted_by"] = {"user_id": key["user_id"], "api_key_id": key["api_key_id"]}
    return result


@router.post("/storage/folders", status_code=201)
def add_storage_folder(payload: StorageFolderCreate, request: Request):
    actor = authenticate_api_key(request, master_required=True)
    key = storage.child_key(payload.path, payload.name)
    with transaction() as (_, cur):
        require_storage_key_access(
            cur,
            storage_key=key,
            user_id=actor_user_id(actor),
        )
    return {"ok": True, "path": storage.create_folder(key)}


@router.post("/storage/text", status_code=201)
def add_storage_text(payload: StorageTextWrite, request: Request):
    actor = authenticate_api_key(request, master_required=True)
    with transaction() as (_, cur):
        require_storage_key_access(
            cur,
            storage_key=storage.clean_key(payload.path),
            user_id=actor_user_id(actor),
        )
    return {"ok": True, "path": storage.write_bytes(payload.path, payload.content.encode("utf-8"))}


@router.post("/storage/files", status_code=201)
async def add_storage_file(
    request: Request,
    file: UploadFile = File(...),
    folder: str = Form(""),
):
    actor = authenticate_api_key(request, master_required=True)
    key = storage.child_key(folder, file.filename or "upload.bin")
    with transaction() as (_, cur):
        require_storage_key_access(
            cur,
            storage_key=key,
            user_id=actor_user_id(actor),
        )
    return {"ok": True, "path": storage.write_bytes(key, await file.read())}
