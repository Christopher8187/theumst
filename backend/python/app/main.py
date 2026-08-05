from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import initialize_database
from .routers import admin, api_keys, auth, frontend, health, public_api, superadmin, users
from .services.qdrant import qdrant_service


def create_app(*, initialize_services: bool = True) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if initialize_services:
            initialize_database()
            try:
                qdrant_service.ensure_collection()
            except Exception as exc:
                # The SQL application remains available if Qdrant is temporarily
                # offline; /health/qdrant exposes the degraded dependency.
                print(f"Qdrant initialization warning: {exc}")
        yield

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
    if settings.public_images.exists():
        application.mount("/images", StaticFiles(directory=settings.public_images), name="images")

    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(users.router)
    application.include_router(api_keys.router)
    application.include_router(admin.router)
    application.include_router(superadmin.router)
    application.include_router(public_api.router)
    application.include_router(frontend.router)
    return application


app = create_app()
