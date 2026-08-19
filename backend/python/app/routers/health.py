from __future__ import annotations

from fastapi import APIRouter

from ..config import get_settings
from ..database import transaction
from ..services.qdrant import qdrant_service
from ..services import storage


router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"ok": True, "app": "theumst backend"}


@router.get("/health/db")
def health_db():
    with transaction() as (_, cur):
        cur.execute("SELECT 1 AS ok")
        return {"ok": cur.fetchone()["ok"] == 1}


@router.get("/health/qdrant")
def health_qdrant():
    settings = get_settings()
    if not settings.qdrant_enabled:
        return {"ok": True, "enabled": False}
    exists = qdrant_service.collection_exists(settings.qdrant_collection)
    return {"ok": bool(exists), "enabled": True, "collection": settings.qdrant_collection}


@router.get("/health/assets")
def health_assets():
    settings = get_settings()
    return {"ok": settings.public_images.exists(), "path": str(settings.public_images)}


@router.get("/health/storage")
def health_storage():
    return storage.health()
