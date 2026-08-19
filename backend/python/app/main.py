from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import initialize_database, transaction
from .dependencies import current_user
from .routers import admin, api_keys, auth, content, demo, frontend, health, public_api, superadmin, users
from .services.qdrant import qdrant_service
from .services.corpus_access import (
    actor_user_id,
    assert_public_image_mount_isolated,
    revision_headers,
)


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
    application.add_middleware(GZipMiddleware, minimum_size=1_000)

    @application.middleware("http")
    async def protected_access_revision(request, call_next):
        protected_client_path = (
            request.url.path.startswith("/api/demo")
            or request.url.path.startswith("/api/v1/storage/")
        )
        captured_headers: dict[str, str] = {}
        if protected_client_path:
            try:
                user = current_user(request)
                if user:
                    with transaction() as (_, cur):
                        captured_headers = revision_headers(cur, actor_user_id(user))
            except Exception:
                # A route will independently authenticate and fail closed. A
                # pre-response lookup failure must never be repaired by reading
                # a newer policy revision after the body has been produced.
                captured_headers = {}
        request.state.protected_access_headers = captured_headers

        response = await call_next(request)
        if not protected_client_path:
            return response

        if response.status_code == 401:
            if "X-Theumst-Access-Revision" in response.headers:
                del response.headers["X-Theumst-Access-Revision"]
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["Vary"] = "Authorization, Cookie, Accept-Encoding"
            return response

        if ((200 <= response.status_code < 300) or response.status_code == 404) and captured_headers:
            # The token labels the authorization snapshot captured before the
            # response body was generated. Never overwrite an old body with a
            # newer, post-response policy token.
            for name, value in captured_headers.items():
                response.headers[name] = value
        return response
    assert_public_image_mount_isolated(settings)
    if settings.public_images.exists():
        application.mount("/images", StaticFiles(directory=settings.public_images), name="images")

    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(users.router)
    application.include_router(api_keys.router)
    application.include_router(content.router)
    application.include_router(demo.router)
    application.include_router(admin.router)
    application.include_router(superadmin.router)
    application.include_router(public_api.router)
    application.include_router(frontend.router)
    return application


app = create_app()
