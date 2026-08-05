from pathlib import Path

from app.main import create_app


ROOT = Path(__file__).resolve().parents[3]


def test_expected_routes_and_sql_is_superadmin_only():
    application = create_app(initialize_services=False)
    paths = {route.path for route in application.routes}
    assert "/api/admin/qdrant/search" in paths
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
        "app/routers/superadmin.py", "app/routers/public_api.py",
        "app/services/qdrant.py", "app/services/storage.py", "app/services/knowledge.py",
    ]
    backend = ROOT / "backend" / "python"
    assert all((backend / path).is_file() for path in expected)
