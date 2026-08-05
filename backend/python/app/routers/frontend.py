from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

from ..config import get_settings
from ..dependencies import current_user


router = APIRouter(include_in_schema=False)
WEBPAGE_HTML_ROUTES = {"news", "about", "wiki", "get", "login", "signup"}
BLOCKED_PREFIXES = ("backend/", "config/", "dev/")
DASHBOARD_ACCESS = {
    "profile": "profile",
    "api-keys": "api-keys",
    "admin": "admin",
    "superadmin": "superadmin",
}


def _safe_file(dist: Path, path: str) -> Path | None:
    target = (dist / path).resolve()
    return target if target.is_file() and dist.resolve() in target.parents else None


def _serve_vue(dist: Path, path: str, detail: str):
    index = dist / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail=detail)
    target = _safe_file(dist, path) if path else None
    return FileResponse(target or index)


@router.get("/dashboard")
def dashboard_redirect():
    return RedirectResponse("/dashboard/profile/", status_code=307)


@router.get("/dashboard/{path:path}")
def dashboard(path: str, request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    first = (path.strip("/").split("/") or ["profile"])[0] or "profile"
    access = DASHBOARD_ACCESS.get(first, "profile")
    if access not in set(user.get("access_points") or []):
        return RedirectResponse("/dashboard/profile/", status_code=303)
    return _serve_vue(
        get_settings().dashboard_dist,
        path,
        "Dashboard Vue app is not built; use Vite on localhost:5174 during development",
    )


@router.get("/")
def homepage():
    settings = get_settings()
    if not (settings.webpage_dist / "index.html").exists():
        return {
            "app": "theumst backend", "health": "/health", "api": "/docs",
            "local_webpage": "http://localhost:5173", "local_dashboard": "http://localhost:5174/dashboard",
        }
    return _serve_vue(settings.webpage_dist, "", "Webpage app not built")


@router.get("/index.html")
def old_index():
    return RedirectResponse("/", status_code=301)


@router.get("/{page_name}.html")
def old_page(page_name: str):
    if page_name not in WEBPAGE_HTML_ROUTES:
        raise HTTPException(status_code=404)
    return RedirectResponse(f"/{page_name}", status_code=301)


@router.get("/{path:path}")
def webpage(path: str):
    clean = path.strip("/")
    if clean.startswith(BLOCKED_PREFIXES) or any(part.startswith(".") for part in clean.split("/") if part):
        raise HTTPException(status_code=404)
    return _serve_vue(
        get_settings().webpage_dist,
        path,
        "Webpage Vue app is not built; use Vite on localhost:5173 during development",
    )
