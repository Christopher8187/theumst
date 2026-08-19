from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import frontend


def test_unknown_api_route_is_json_404_not_public_spa():
    application = FastAPI()
    application.include_router(frontend.router)
    response = TestClient(application).get("/api/v1/demo/books")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"detail": "API route not found"}


def test_real_public_page_still_uses_the_spa_fallback(monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>Public</title>", encoding="utf-8")
    monkeypatch.setattr(frontend, "get_settings", lambda: type(
        "Settings", (), {"webpage_dist": tmp_path}
    )())
    application = FastAPI()
    application.include_router(frontend.router)

    response = TestClient(application).get("/about")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
