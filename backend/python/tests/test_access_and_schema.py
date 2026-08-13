from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCHEMA = (ROOT / "backend/sql/schema.sql").read_text(encoding="utf-8")
CONTENT_MIGRATION = (ROOT / "backend/sql/003_manager_content.sql").read_text(encoding="utf-8")


def test_dashboard_pages_are_database_access_points():
    for point in ("profile", "api-keys", "books", "media", "admin", "superadmin"):
        assert f"('{point}')" in SCHEMA
    assert "a.name = 'manager' AND p.access_point IN ('profile', 'api-keys', 'books', 'media')" in SCHEMA
    assert "a.name = 'admin' AND p.access_point IN ('profile', 'api-keys', 'admin', 'books', 'media')" in SCHEMA
    assert "a.name = 'superadmin' AND p.access_point IN ('profile', 'api-keys', 'admin', 'superadmin', 'books', 'media')" in SCHEMA


def test_embedding_and_rate_limit_tables_are_integrated():
    for table in ("semantic_projection", "embedding_model", "embedding", "api_rate_window"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in SCHEMA
    assert "embedding_id uuid PRIMARY KEY" in SCHEMA
    assert "CREATE OR REPLACE VIEW embedding_queue" in SCHEMA


def test_manager_and_media_schema_are_integrated():
    assert "(4, 'manager')" in SCHEMA
    assert "CREATE TABLE IF NOT EXISTS media_post" in CONTENT_MIGRATION
    assert "status IN ('draft', 'published')" in CONTENT_MIGRATION


def test_case_insensitive_christopher_uniqueness_is_enforced():
    assert "user_username_casefold_unique" in SCHEMA
    script = (ROOT / "dev/sh/make_christopher_superadmin.sh").read_text(encoding="utf-8")
    assert "lower(username) = 'christopher'" in script
    assert "matching_accounts > 1" in script
    assert "name = 'superadmin'" in script
