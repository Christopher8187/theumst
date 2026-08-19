from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCHEMA = (ROOT / "backend/sql/schema.sql").read_text(encoding="utf-8")
CONTENT_MIGRATION = (ROOT / "backend/sql/003_manager_content.sql").read_text(encoding="utf-8")
DEMO_MIGRATION = (ROOT / "backend/sql/005_demo_beta.sql").read_text(encoding="utf-8")


def test_dashboard_pages_are_database_access_points():
    for point in ("profile", "api-keys", "books", "media", "demo", "admin", "superadmin"):
        assert f"('{point}')" in SCHEMA
    assert "a.name = 'betatester' AND p.access_point IN ('profile', 'api-keys', 'demo')" in SCHEMA
    assert "a.name = 'manager' AND p.access_point IN ('profile', 'api-keys', 'books', 'media', 'demo')" in SCHEMA
    assert "a.name = 'admin' AND p.access_point IN ('profile', 'api-keys', 'admin', 'books', 'media', 'demo')" in SCHEMA
    assert "a.name = 'superadmin' AND p.access_point IN ('profile', 'api-keys', 'admin', 'superadmin', 'books', 'media', 'demo')" in SCHEMA


def test_embedding_and_rate_limit_tables_are_integrated():
    for table in ("semantic_projection", "embedding_model", "embedding", "api_rate_window"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in SCHEMA
    assert "embedding_id uuid PRIMARY KEY" in SCHEMA
    assert "CREATE OR REPLACE VIEW embedding_queue" in SCHEMA


def test_manager_and_media_schema_are_integrated():
    assert "(4, 'manager')" in SCHEMA
    assert "CREATE TABLE IF NOT EXISTS media_post" in CONTENT_MIGRATION
    assert "status IN ('draft', 'published')" in CONTENT_MIGRATION


def test_demo_beta_schema_is_durable_and_idempotent():
    assert "(5, 'betatester')" in DEMO_MIGRATION
    for table in (
        "demo_access_request", "user_grimoire", "demo_knowledge_progress",
        "demo_study_state", "demo_note", "demo_similarity",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in DEMO_MIGRATION
    assert "note_type IN ('attached', 'scribble')" in DEMO_MIGRATION
    assert "demo-linear-algebra-001" in DEMO_MIGRATION
    assert "demo-calculus-001" in DEMO_MIGRATION
    assert "INSERT INTO grimoire" not in DEMO_MIGRATION
    assert "IF v_section_id IS NULL" in DEMO_MIGRATION


def test_case_insensitive_christopher_uniqueness_is_enforced():
    assert "user_username_casefold_unique" in SCHEMA
    script = (ROOT / "dev/sh/make_christopher_superadmin.sh").read_text(encoding="utf-8")
    assert "lower(username) = 'christopher'" in script
    assert "matching_accounts > 1" in script
    assert "name = 'superadmin'" in script


def test_email_verification_schema_preserves_existing_accounts_and_blocks_new_unverified_sessions():
    assert "email_verified_at timestamptz" in SCHEMA
    assert "CREATE TABLE IF NOT EXISTS email_verification_token" in SCHEMA
    assert "CREATE TABLE IF NOT EXISTS email_change_token" in SCHEMA
    assert 'UPDATE "user" SET email_verified_at = COALESCE(created_at, now())' in SCHEMA
    dependencies = (ROOT / "backend/python/app/dependencies.py").read_text(encoding="utf-8")
    assert "u.email_verified_at IS NOT NULL" in dependencies
