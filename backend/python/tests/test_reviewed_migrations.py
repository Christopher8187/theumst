from __future__ import annotations

import asyncio
import hashlib
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from app import reviewed_migrations
from app.config import Settings


ROOT = Path(__file__).resolve().parents[3]


def test_reviewed_sources_have_exact_checksums_and_exclude_historical_seeds():
    settings = SimpleNamespace(sql_dir=ROOT / "backend/sql")
    sources = reviewed_migrations.validated_migration_sources(settings)
    assert [migration.filename for migration, _ in sources] == ["006_knowledge_graph.sql", "007_study_positions.sql"]
    assert "007_research_corpus_access.sql" not in Path(
        reviewed_migrations.__file__
    ).read_text(encoding="utf-8")
    for migration, path in sources:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == migration.sha256
        statements = [
            line.strip().upper()
            for line in path.read_text(encoding="utf-8").splitlines()
        ]
        assert not any(
            line.startswith(("INSERT ", "UPDATE ", "DELETE ", "TRUNCATE "))
            for line in statements
        )


@pytest.mark.parametrize("value", ["", "abc", "g" * 64, "0" * 63, "0" * 65])
def test_backup_fingerprint_is_mandatory_and_strict(value: str):
    with pytest.raises(reviewed_migrations.MigrationSafetyError):
        reviewed_migrations.validate_backup_sha256(value)


def test_clean_schema_is_complete_and_contains_no_sample_content():
    schema = (ROOT / "backend/sql/schema.sql").read_text(encoding="utf-8")
    for table in (
        "book_image",
        "media_post",
        "demo_access_request",
        "user_grimoire",
        "demo_knowledge_progress",
        "demo_study_state",
        "demo_note",
        "demo_similarity",
        "knowledge_graph_node",
        "knowledge_graph_edge",
        "knowledge_graph_receipt",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in schema
    assert "CREATE TABLE IF NOT EXISTS research_corpus_policy" not in schema
    assert "CREATE TABLE IF NOT EXISTS research_corpus_user_access" not in schema
    for forbidden in (
        "Building a world from knowledge",
        "From learning graph to benchmarking ecosystem",
        "Foundations of Linear Algebra",
        "Geometry of Change",
        "demo-linear-algebra-001",
        "demo-calculus-001",
    ):
        assert forbidden not in schema


def test_compose_uses_clean_fresh_schema_and_disables_all_recurring_replay():
    deploy = yaml.safe_load((ROOT / "compose.deploy.yml").read_text(encoding="utf-8"))
    local = yaml.safe_load((ROOT / "compose.local.yml").read_text(encoding="utf-8"))
    assert deploy["services"]["db"]["volumes"][1].endswith(
        "schema.sql:/docker-entrypoint-initdb.d/000_schema.sql:ro"
    )
    assert local["services"]["db"]["volumes"][1].endswith(
        "schema.sql:/docker-entrypoint-initdb.d/000_schema.sql:ro"
    )
    assert (
        deploy["services"]["backend"]["environment"]["DB_SCHEMA_STARTUP_MODE"]
        == "disabled"
    )
    assert local["services"]["backend"]["environment"]["DB_SCHEMA_STARTUP_MODE"] == "disabled"
    for document in (deploy, local):
        assert not any(
            name.startswith("RESEARCH_")
            for name in document["services"]["backend"]["environment"]
        )


def test_nonlocal_settings_can_never_enable_historical_replay(monkeypatch):
    monkeypatch.setenv("SERVER", "COM")
    monkeypatch.setenv("DB_SCHEMA_STARTUP_MODE", "replay")
    with pytest.raises(ValueError, match="forbidden outside LOCAL"):
        Settings.from_environment()


def test_runner_applies_only_a_wholly_missing_reviewed_migration(monkeypatch):
    executed: list[str] = []

    class Cursor:
        def execute(self, sql, params=None):
            executed.append(str(sql))

    cursor = Cursor()

    @contextmanager
    def fake_transaction():
        yield object(), cursor

    migration = reviewed_migrations.REVIEWED_MIGRATIONS[0]
    sources = ((migration, ROOT / "backend/sql/006_knowledge_graph.sql"),)
    monkeypatch.setattr(reviewed_migrations, "transaction", fake_transaction)
    monkeypatch.setattr(
        reviewed_migrations,
        "validated_migration_sources",
        lambda settings=None: sources,
    )
    monkeypatch.setattr(
        reviewed_migrations,
        "_assert_markers_present",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        reviewed_migrations,
        "_migration_state",
        lambda *args: "missing",
    )

    result = reviewed_migrations.apply_reviewed_migrations(backup_sha256="a" * 64)
    combined = "\n".join(executed)
    assert "knowledge_graph_node" in combined
    assert "research_corpus_policy_revision_seq" not in combined
    assert "Building a world from knowledge" not in combined
    assert "Foundations of Linear Algebra" not in combined
    assert [entry["action"] for entry in result["migrations"]] == ["applied"]


def test_partial_catalogue_fails_closed(monkeypatch):
    migration = reviewed_migrations.REVIEWED_MIGRATIONS[0]
    answers = iter(
        [True, False, *([False] * (len(migration.exclusive_markers) - 2))]
    )
    monkeypatch.setattr(
        reviewed_migrations,
        "_marker_present",
        lambda *args: next(answers),
    )
    with pytest.raises(
        reviewed_migrations.MigrationSafetyError,
        match="Partial migration catalogue",
    ):
        reviewed_migrations._migration_state(object(), migration)


def test_deployment_support_requires_backup_and_runs_only_reviewed_cli():
    script = (ROOT / "dev/sh/_common.sh").read_text(encoding="utf-8")
    function = script.split("remote_apply_reviewed_migrations() {", 1)[1].split(
        "\nremote_stop() {",
        1,
    )[0]
    assert 'backup_sha256="${2:-}"' in function
    assert '"${#backup_sha256}" -eq 64' in function
    assert "python -m scripts.apply_reviewed_migrations" in function
    assert "006_knowledge_graph.sql" not in function
    assert "007_research_corpus_access.sql" not in function
    assert "005_demo_beta.sql" not in function
    build_env = script.split("build_remote_env() {", 1)[1].split(
        "\nremote_upload() {",
        1,
    )[0]
    assert "RESEARCH_" not in build_env


def test_full_release_sequences_backup_migration_start_and_retains_rollback():
    common = (ROOT / "dev/sh/_common.sh").read_text(encoding="utf-8")
    upload = common.split("remote_upload() {", 1)[1].split(
        "\nremote_start() {",
        1,
    )[0]
    start = common.split("remote_start() {", 1)[1].split(
        "\nremote_apply_reviewed_migrations() {",
        1,
    )[0]
    release = common.split("remote_full_deploy() {", 1)[1]
    agent = (ROOT / "dev/sh/agent_deploy.sh").read_text(encoding="utf-8")

    assert "PREDEPLOY_BACKUP_SHA256" in agent
    assert 'remote_full_deploy "$TARGET" "$BACKUP_SHA256"' in agent
    assert release.index("remote_upload") < release.index("remote_apply_reviewed_migrations")
    assert release.index("remote_apply_reviewed_migrations") < release.index("remote_start")
    assert "remote_setup" not in release
    assert "remote_certs" not in release
    assert "remote_install_nginx_site" not in release
    assert "retained previous release already exists" in upload
    assert "up --build -d --no-deps backend demo" in start
    assert "up -d --no-deps --force-recreate nginx" in start
    assert "--remove-orphans" not in start
    assert "up --build -d --no-deps db" not in start
    assert "up --build -d --no-deps qdrant" not in start
    assert upload.index("retained previous release already exists") < upload.index(
        'rm -rf \\"\\$incoming\\"'
    )
    for section in (upload, start, release):
        assert '$SUDO rm -rf \\"\\$previous\\"' not in section
        assert "$SUDO rm -rf '${REMOTE_ROOT}.previous'" not in section


def test_disabled_startup_calls_schema_gate_before_dependencies(monkeypatch, tmp_path):
    from app import main as app_main

    calls: list[str] = []

    settings = SimpleNamespace(
        db_schema_startup_mode="disabled",
        cors_origins=(),
        server="COM",
        local_storage_dir="__AUTO__",
        public_images=tmp_path / "public-images",
    )
    monkeypatch.setattr(app_main, "get_settings", lambda: settings)
    monkeypatch.setattr(
        app_main,
        "assert_database_schema_ready",
        lambda: calls.append("schema-ready"),
    )
    monkeypatch.setattr(
        app_main.qdrant_service,
        "ensure_collection",
        lambda: calls.append("qdrant"),
    )
    application = app_main.create_app()

    async def exercise_lifespan():
        async with application.router.lifespan_context(application):
            pass

    asyncio.run(exercise_lifespan())
    assert calls == ["schema-ready", "qdrant"]


def test_disabled_startup_fails_closed_when_schema_gate_rejects(monkeypatch, tmp_path):
    from app import main as app_main

    settings = SimpleNamespace(
        db_schema_startup_mode="disabled",
        cors_origins=(),
        server="COM",
        local_storage_dir="__AUTO__",
        public_images=tmp_path / "public-images",
    )
    monkeypatch.setattr(app_main, "get_settings", lambda: settings)

    def reject_schema():
        raise reviewed_migrations.MigrationSafetyError("Reviewed migration is missing")

    monkeypatch.setattr(app_main, "assert_database_schema_ready", reject_schema)
    application = app_main.create_app()

    async def exercise_lifespan():
        async with application.router.lifespan_context(application):
            pass

    with pytest.raises(
        reviewed_migrations.MigrationSafetyError,
        match="Reviewed migration is missing",
    ):
        asyncio.run(exercise_lifespan())
