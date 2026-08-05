from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCHEMA = (ROOT / "backend/sql/schema.sql").read_text(encoding="utf-8")


def test_dashboard_pages_are_database_access_points():
    for point in ("profile", "api-keys", "admin", "superadmin"):
        assert f"('{point}')" in SCHEMA
    assert "a.name = 'admin' AND p.access_point IN ('profile', 'api-keys', 'admin')" in SCHEMA
    assert "a.name = 'superadmin' AND p.access_point IN ('profile', 'api-keys', 'admin', 'superadmin')" in SCHEMA


def test_embedding_and_rate_limit_tables_are_integrated():
    for table in ("semantic_projection", "embedding_model", "embedding", "api_rate_window"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in SCHEMA
    assert "embedding_id uuid PRIMARY KEY" in SCHEMA
    assert "CREATE OR REPLACE VIEW embedding_queue" in SCHEMA


def test_case_insensitive_christopher_uniqueness_is_enforced():
    assert "user_username_casefold_unique" in SCHEMA
    script = (ROOT / "dev/sh/make_christopher_superadmin.sh").read_text(encoding="utf-8")
    assert "lower(username) = 'christopher'" in script
    assert "matching_accounts > 1" in script
    assert "name = 'superadmin'" in script
