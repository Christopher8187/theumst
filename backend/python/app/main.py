from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import initialize_database
from .reviewed_migrations import assert_database_schema_ready
from .routers import admin, api_keys, auth, content, demo, frontend, health, news, public_api, superadmin, users
from .services.news import delivery_loop, ensure_news_delivery_configured
from .services.qdrant import qdrant_service


def _assert_public_image_mount_isolated(settings) -> None:
    """Prevent the public static mount from overlapping book object storage."""
    if settings.server != "LOCAL":
        return
    raw = settings.local_storage_dir
    storage_root = (
        Path.home() / "theumst_storage"
        if not raw or raw == "__AUTO__"
        else Path(os.path.expandvars(raw)).expanduser()
    ).resolve()
    public_root = settings.public_images.resolve()
    if (
        storage_root == public_root
        or storage_root in public_root.parents
        or public_root in storage_root.parents
    ):
        raise RuntimeError("Public images and book storage must be isolated")


def create_app(*, initialize_services: bool = True) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if initialize_services:
            if settings.db_schema_startup_mode == "replay":
                initialize_database()
            else:
                # Production startup is read-only with respect to PostgreSQL.
                # A release operator must apply reviewed migrations explicitly
                # after a verified backup before this process can listen.
                assert_database_schema_ready()
            try:
                qdrant_service.ensure_collection()
            except Exception as exc:
                # The SQL application remains available if Qdrant is temporarily
                # offline; /health/qdrant exposes the degraded dependency.
                print(f"Qdrant initialization warning: {exc}")
        worker = None
        if initialize_services and settings.news_delivery_enabled:
            ensure_news_delivery_configured(settings)
            worker = asyncio.create_task(delivery_loop(settings))
        try:
            yield
        finally:
            if worker:
                worker.cancel()
                try:
                    await worker
                except asyncio.CancelledError:
                    pass

    application = FastAPI(
        title="UMST API",
        version="1.0.0",
        description=(
            "Dashboard, read API, master ingestion API, object storage, "
            "and semantic projection/Qdrant integration."
        ),
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(GZipMiddleware, minimum_size=1_000)
    _assert_public_image_mount_isolated(settings)
    if settings.public_images.exists():
        application.mount("/images", StaticFiles(directory=settings.public_images), name="images")

    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(users.router)
    application.include_router(api_keys.router)
    application.include_router(content.router)
    application.include_router(news.router)
    application.include_router(demo.router)
    application.include_router(admin.router)
    application.include_router(superadmin.router)
    application.include_router(public_api.router)
    application.include_router(frontend.router)
    return application


app = create_app()
