"""Migration 018 (0.0.19) and schema.sql describe the same kinds and indexes for UMST's agents' reads.

These checks read the SQL text; they do not run it. The migration's PostgreSQL run is the release check
on COM's database through the reviewed runner, and docs/game-agents.md lists the read-only queries.
"""
from __future__ import annotations

import hashlib
import inspect
import re
from pathlib import Path

from app import dependencies, reviewed_migrations
from app.routers import game_graph as graph_router
from app.routers import game_search as search_router
from app.services import game_search

ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = ROOT / "backend/sql/018_game_agent_reads.sql"
MIGRATION = MIGRATION_PATH.read_text(encoding="utf-8")
SCHEMA = (ROOT / "backend/sql/schema.sql").read_text(encoding="utf-8")
GAME_AGENT_READS = next(
    migration for migration in reviewed_migrations.REVIEWED_MIGRATIONS if migration.key == "game_agent_reads_v1"
)
KINDS = "kind IN ('book', 'character', 'search', 'graph')"
INDEXES = {
    "knowledge_active_crystal_idx": "ON knowledge (knowledge_crystal_id) WHERE is_active;",
    "knowledge_active_source_key_idx": "ON knowledge (source_key) WHERE is_active;",
    "grimoire_hidden_idx": "ON grimoire (grimoire_id) WHERE (source_metadata->>'demo') IS DISTINCT FROM 'true';",
}


def statements(sql: str) -> list[str]:
    """The file's statements, comments dropped and whitespace collapsed."""
    text = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    return [" ".join(part.split()) + ";" for part in text.split(";") if part.strip()]


def create_table(sql: str, table: str) -> str:
    match = re.search(rf"CREATE TABLE IF NOT EXISTS {re.escape(table)} \((.*?)\n\);", sql, re.DOTALL)
    assert match, f"no CREATE TABLE for {table}"
    return match.group(1)


def test_the_kinds_are_the_apis_and_both_checks_take_them_in_the_migration_and_the_fresh_schema():
    assert dependencies.API_REQUEST_KINDS == ("book", "character", "search", "graph")
    assert search_router.SEARCH_KIND in dependencies.API_REQUEST_KINDS
    assert graph_router.GRAPH_KIND in dependencies.API_REQUEST_KINDS
    for table in ("api_rate_window", "api_usage_daily"):
        name = f"{table}_kind_check"
        # The name PostgreSQL gave schema.sql's inline check, read on COM on 22 November 2026.
        assert f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name};" in statements(MIGRATION)
        assert f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({KINDS});" in statements(MIGRATION)
        assert MIGRATION.index(f"DROP CONSTRAINT IF EXISTS {name}") < MIGRATION.index(f"ADD CONSTRAINT {name}")
        assert f"kind text NOT NULL CHECK ({KINDS})" in create_table(SCHEMA, table)


def test_the_migration_and_the_fresh_schema_make_the_same_three_indexes():
    made = [statement for statement in statements(MIGRATION) if statement.startswith("CREATE INDEX")]
    fresh = statements(SCHEMA)
    assert len(made) == len(INDEXES)
    for name, definition in INDEXES.items():
        statement = f"CREATE INDEX IF NOT EXISTS {name} {definition}"
        assert statement in made
        assert statement in fresh


def test_every_statement_can_run_again_and_none_changes_a_row():
    for statement in statements(MIGRATION):
        assert statement.startswith(("ALTER TABLE", "CREATE INDEX IF NOT EXISTS")), statement
        if "DROP CONSTRAINT" in statement:
            assert "DROP CONSTRAINT IF EXISTS" in statement
        assert not re.search(r"\b(INSERT|UPDATE|DELETE|TRUNCATE)\b", statement), statement
    assert "%" not in MIGRATION


def test_018_is_pinned_last_with_its_three_indexes_as_the_markers():
    data = MIGRATION_PATH.read_bytes()
    assert b"\r" not in data  # .gitattributes keeps *.sql at LF on every machine
    assert hashlib.sha256(data).hexdigest() == GAME_AGENT_READS.sha256
    migrations = reviewed_migrations.REVIEWED_MIGRATIONS
    assert migrations[-1] is GAME_AGENT_READS
    assert migrations[-2].key == "book_game_read_v1"
    assert GAME_AGENT_READS.filename == "018_game_agent_reads.sql"
    assert [(marker.kind, marker.name) for marker in GAME_AGENT_READS.exclusive_markers] == [
        ("relation", f"public.{name}") for name in INDEXES
    ]
    assert not GAME_AGENT_READS.shared_markers


def test_the_hidden_books_index_has_the_predicate_the_search_asks_with():
    # A partial index serves only a query whose WHERE implies its predicate.
    assert "WHERE (source_metadata->>'demo') IS DISTINCT FROM 'true'" in inspect.getsource(game_search.book_scope)
