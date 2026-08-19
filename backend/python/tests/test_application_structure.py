from pathlib import Path

from app.main import create_app


ROOT = Path(__file__).resolve().parents[3]


def test_expected_routes_and_sql_is_superadmin_only():
    application = create_app(initialize_services=False)
    paths = {route.path for route in application.routes}
    assert "/api/admin/qdrant/search" in paths
    assert "/api/admin/make-manager" in paths
    assert "/api/content/books" in paths
    assert "/api/content/books/{grimoire_id}" in paths
    assert "/api/content/books/{grimoire_id}/demo-visibility" in paths
    assert "/api/admin/users" in paths
    assert "/api/content/media" in paths
    assert "/api/content/media/{media_post_id}" in paths
    assert "/api/news" in paths
    assert "/api/demo/access" in paths
    assert "/api/demo/access/request" in paths
    assert "/api/demo/access/requests/{user_id}/approve" in paths
    assert "/api/demo/grimoires/{grimoire_id}/knowledge" in paths
    assert "/api/demo/notes" in paths
    assert "/api/demo/crystallize/{knowledge_id}" in paths
    assert "/auth/forgot-password" in paths
    assert "/auth/reset-password" in paths
    assert "/auth/email-verification/resend" in paths
    assert "/auth/email-verification/confirm" in paths
    assert "/auth/email-change/request" in paths
    assert "/auth/email-change/confirm" in paths
    assert "/api/superadmin/sql" in paths
    assert "/api/admin/sql" not in paths
    assert "/api/v1/knowledge" in paths
    assert "/api/v1/knowledge/{knowledge_id}/embeddings" in paths
    assert "/api/v1/storage/files" in paths
    assert "/api/api-keys/{api_key_id}/upgrade-master" in paths


def test_backend_is_refactored_into_conventional_modules():
    expected = [
        "app/main.py", "app/config.py", "app/database.py", "app/dependencies.py",
        "app/schemas.py", "app/security.py", "app/routers/admin.py",
        "app/routers/superadmin.py", "app/routers/public_api.py", "app/routers/content.py",
        "app/routers/demo.py",
        "app/services/qdrant.py", "app/services/storage.py", "app/services/knowledge.py",
    ]
    backend = ROOT / "backend" / "python"
    assert all((backend / path).is_file() for path in expected)
