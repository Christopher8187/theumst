from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import frontend


@pytest.fixture
def frontend_client(monkeypatch, tmp_path):
    webpage = tmp_path / "webpage"
    dashboard = tmp_path / "dashboard"
    for dist in (webpage, dashboard):
        (dist / "assets").mkdir(parents=True)
        (dist / "index.html").write_text(
            '<!doctype html><script src="/assets/app-OLDHASH1.js"></script>', encoding="utf-8",
        )
        (dist / "assets" / "app-OLDHASH1.js").write_text("export const version = 'old';", encoding="utf-8")
    settings = SimpleNamespace(webpage_dist=webpage, dashboard_dist=dashboard)
    monkeypatch.setattr(frontend, "get_settings", lambda: settings)
    monkeypatch.setattr(frontend, "current_user", lambda request: {"access_points": ["profile", "media"]})
    application = FastAPI()
    application.include_router(frontend.router)
    with TestClient(application) as client:
        yield client, settings


@pytest.mark.parametrize("path", ["/", "/about", "/news/a-story", "/login", "/dashboard/profile/", "/dashboard/media/", "/dashboard/index.html"])
def test_frontend_html_requires_revalidation_on_every_navigation(frontend_client, path):
    client, _ = frontend_client
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    directives = {item.strip() for item in response.headers.get("cache-control", "").split(",")}
    assert "no-cache" in directives
    assert "must-revalidate" in directives
    assert response.headers["etag"] and response.headers["last-modified"]


def test_html_revalidation_returns_the_updated_build(frontend_client):
    client, settings = frontend_client
    before = client.get("/")
    assert "no-cache" in before.headers.get("cache-control", "")
    (settings.webpage_dist / "index.html").write_text(
        '<!doctype html><title>Updated site</title><script src="/assets/app-NEWHASH2.js"></script>', encoding="utf-8",
    )
    after = client.get("/", headers={"If-None-Match": before.headers["etag"]})
    assert after.status_code == 200
    assert "app-NEWHASH2.js" in after.text and "app-OLDHASH1.js" not in after.text
    assert after.headers["etag"] != before.headers["etag"]
    assert "no-cache" in after.headers["cache-control"]


@pytest.mark.parametrize("path", ["/assets/app-OLDHASH1.js", "/dashboard/assets/app-OLDHASH1.js"])
def test_hashed_assets_retain_their_existing_file_cache_behavior(frontend_client, path):
    client, _ = frontend_client
    response = client.get(path)
    assert response.status_code == 200 and response.text == "export const version = 'old';"
    assert "javascript" in response.headers["content-type"]
    assert response.headers["etag"] and response.headers["last-modified"]
    assert "no-cache" not in response.headers.get("cache-control", "")


def test_asset_shaped_spa_fallback_is_still_revalidated_html(frontend_client):
    client, _ = frontend_client
    response = client.get("/assets/no-longer-present-HASH1234.js")
    assert response.headers["content-type"].startswith("text/html")
    assert "no-cache" in response.headers.get("cache-control", "")
    assert "immutable" not in response.headers.get("cache-control", "")


def test_cache_policy_does_not_bypass_frontend_boundaries(frontend_client, monkeypatch, tmp_path):
    client, settings = frontend_client
    monkeypatch.setattr(frontend, "current_user", lambda request: None)
    denied = client.get("/dashboard/profile/", follow_redirects=False)
    assert denied.status_code == 303 and denied.headers["location"] == "/login"
    missing_api = client.get("/api/no-such-route")
    assert missing_api.status_code == 404
    assert missing_api.headers["content-type"].startswith("application/json")
    assert missing_api.headers["cache-control"] == "no-store"
    for path in ("/backend/python/app/main.py", "/config/nginx.docker.conf", "/.env"):
        assert client.get(path).status_code == 404
    outside = tmp_path / "private.txt"
    outside.write_text("outside the frontend build", encoding="utf-8")
    assert frontend._safe_file(settings.webpage_dist, "../private.txt") is None
