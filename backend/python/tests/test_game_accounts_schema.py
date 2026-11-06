"""Migration 013 and schema.sql describe the same game-account tables.

These checks read the SQL text; they do not run it. Running the migration on a
restored copy of COM's database is the release check for its PostgreSQL
behaviour (docs/game-accounts.md lists the read-only queries).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import dependencies, reviewed_migrations
from app.routers import game


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = (ROOT / "backend/sql/013_game_accounts.sql").read_text(encoding="utf-8")
SCHEMA = (ROOT / "backend/sql/schema.sql").read_text(encoding="utf-8")
GAME_ACCOUNTS = next(
    migration for migration in reviewed_migrations.REVIEWED_MIGRATIONS if migration.key == "game_accounts_v1"
)


def create_table(sql: str, table: str) -> str:
    match = re.search(rf"CREATE TABLE IF NOT EXISTS {re.escape(table)} \((.*?)\n\);", sql, re.DOTALL)
    assert match, f"no CREATE TABLE for {table}"
    return match.group(1)


def column_lines(block: str) -> dict[str, str]:
    columns: dict[str, str] = {}
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith(("--", "PRIMARY KEY", "UNIQUE", "CHECK", "FOREIGN KEY", "CONSTRAINT")):
            continue
        name = line.split()[0].strip('"')
        columns[name] = line
    return columns


FRESH_SHAPES = {
    "api_rate": ["api_rate_id", "requests_per_minute", "level_name"],
    "api_rate_window": ["api_key_id", "kind", "window_started_at", "request_count"],
    "api_usage_daily": ["api_key_id", "day", "kind", "request_count"],
    # Migration 015 appends lease_install_id after 013's columns.
    '"character"': [
        "character_id", "user_id", "character_data_id", "class_id", "name", "sex", "summary",
        "created_at", "last_played_at", "lease_api_key_id", "lease_expires_at", "lease_install_id",
    ],
    "character_data": ["character_data_id", "level", "data", "save_version", "revision", "updated_at"],
    "sign_in_attempt": ["sign_in_attempt_id", "user_id", "username_hash", "address", "succeeded", "attempted_at"],
}


@pytest.mark.parametrize("table", sorted(FRESH_SHAPES))
def test_fresh_schema_has_the_columns_a_migrated_database_has_in_the_same_order(table):
    # The migration renames in place and appends, so a migrated table lists its
    # columns in this order too.
    assert list(column_lines(create_table(SCHEMA, table))) == FRESH_SHAPES[table]


def test_game_keys_are_marked_by_their_client_column():
    api_key = column_lines(create_table(SCHEMA, "api_key"))
    assert list(api_key)[-1] == "client"
    assert "CHECK (client ~ '^[a-z][a-z0-9_-]{0,31}$')" in api_key["client"]
    assert "ADD COLUMN IF NOT EXISTS client text;" in MIGRATION
    assert "CHECK (client ~ '^[a-z][a-z0-9_-]{0,31}$')" in MIGRATION
    assert re.fullmatch(r"^[a-z][a-z0-9_-]{0,31}$", game.GAME_CLIENT)


def test_standard_tier_allows_600_requests_a_minute_in_both():
    assert "searches_per_hour" not in SCHEMA
    assert "(1, 600, 'standard')" in SCHEMA
    assert "WHEN level_name = 'standard' THEN 600" in MIGRATION
    assert "ELSE ceil(requests_per_minute / 60.0)::int" in MIGRATION
    # The hourly column is only read by the guarded conversion.
    conversion = MIGRATION.split("DO $$", 2)[1]
    assert "column_name = 'searches_per_hour'" in conversion
    assert "RENAME COLUMN searches_per_hour TO requests_per_minute" in conversion


def test_limits_in_sql_match_the_api():
    character = create_table(SCHEMA, '"character"')
    character_data = create_table(SCHEMA, "character_data")
    assert game.SAVE_MAX_BYTES == 65536
    assert game.SUMMARY_MAX_BYTES == 2048
    assert game.NAME_MAX_CHARACTERS == 50
    assert game.MAX_CHARACTERS == 6
    assert game.LEASE_SECONDS == 120
    for check in (
        "jsonb_typeof(data) = 'object' AND octet_length(data::text) <= 65536",
        "CHECK (save_version >= 0)",
        "CHECK (revision >= 1)",
    ):
        assert check in MIGRATION and check in character_data
    for check in (
        "jsonb_typeof(summary) = 'object' AND octet_length(summary::text) <= 2048",
        "char_length(name) BETWEEN 1 AND 50",
        "sex IN ('female', 'male')",
    ):
        assert check in MIGRATION and check in character
    kinds = "kind IN ('book', 'character')"
    assert dependencies.API_REQUEST_KINDS == ("book", "character")
    assert MIGRATION.count(kinds) == 2
    assert kinds in create_table(SCHEMA, "api_rate_window") and kinds in create_table(SCHEMA, "api_usage_daily")


# Constraints the migration names explicitly carry the names PostgreSQL gives
# the same inline constraints in schema.sql, so later migrations can name them.
NAMED_CONSTRAINTS = {
    "api_rate_requests_per_minute_check": ("api_rate", "requests_per_minute", "CHECK"),
    "api_key_client_check": ("api_key", "client", "CHECK"),
    "character_name_check": ('"character"', "name", "CHECK"),
    "character_sex_check": ('"character"', "sex", "CHECK"),
    "character_summary_check": ('"character"', "summary", "CHECK"),
    "character_lease_api_key_id_fkey": ('"character"', "lease_api_key_id", "REFERENCES api_key(api_key_id) ON DELETE SET NULL"),
    "character_character_data_id_key": ('"character"', "character_data_id", "UNIQUE"),
    "character_data_data_check": ("character_data", "data", "CHECK"),
    "character_data_save_version_check": ("character_data", "save_version", "CHECK"),
    "character_data_revision_check": ("character_data", "revision", "CHECK"),
}


@pytest.mark.parametrize("constraint", sorted(NAMED_CONSTRAINTS))
def test_named_constraints_match_the_inline_constraints_of_a_fresh_schema(constraint):
    table, column, marker = NAMED_CONSTRAINTS[constraint]
    assert f"ADD CONSTRAINT {constraint}" in MIGRATION
    block = create_table(SCHEMA, table)
    lines = block.splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip().split()[:1] == [column])
    definition = lines[start]
    # A column's CHECK may continue on the next, more indented line.
    if start + 1 < len(lines) and lines[start + 1].startswith("        "):
        definition += lines[start + 1]
    assert marker in definition


def test_every_constraint_the_migration_adds_is_dropped_first_or_guarded():
    added = re.findall(r"ADD CONSTRAINT (\w+)", MIGRATION)
    assert added
    for name in added:
        if name == "character_character_data_id_key":
            assert "IF to_regclass('character_character_data_id_key') IS NULL THEN" in MIGRATION
        else:
            assert f"DROP CONSTRAINT IF EXISTS {name};" in MIGRATION
            assert MIGRATION.index(f"DROP CONSTRAINT IF EXISTS {name};") < MIGRATION.index(f"ADD CONSTRAINT {name}")


def test_every_statement_of_the_migration_can_run_again():
    statements = [line.strip() for line in MIGRATION.splitlines()]
    for line in statements:
        if line.startswith(("CREATE TABLE", "CREATE INDEX")):
            assert "IF NOT EXISTS" in line, line
        if "ADD COLUMN" in line:
            assert "ADD COLUMN IF NOT EXISTS" in line, line
        if line.startswith("ALTER TABLE") and "DROP CONSTRAINT" in line:
            assert "DROP CONSTRAINT IF EXISTS" in line, line
    # Renames and the table replacement run only on the old shapes.
    blocks = MIGRATION.split("DO $$")[1:]
    assert len(blocks) == 4
    assert "RENAME COLUMN searches_per_hour" in blocks[0] and "column_name = 'searches_per_hour'" in blocks[0]
    assert "DROP TABLE api_rate_window" in blocks[1] and "column_name = 'kind'" in blocks[1]
    assert "RENAME COLUMN alias TO name" in blocks[2] and "column_name = 'alias'" in blocks[2]
    # Added columns never carry inline constraints, which PostgreSQL would
    # process even when the column already exists in some versions.
    for line in statements:
        if "ADD COLUMN IF NOT EXISTS" in line:
            assert "REFERENCES" not in line and "CHECK" not in line and "UNIQUE" not in line, line


def test_the_old_alias_uniqueness_is_dropped_by_catalogue_lookup_not_by_a_guessed_name():
    block = MIGRATION.split("DO $$")[3]
    assert "con.contype = 'u'" in block
    assert "att.attname = 'alias'" in block
    assert "quote_ident(unique_name)" in block
    # Executed without parameters, but keep the file free of % placeholders anyway.
    assert "%" not in MIGRATION


def _schema_defines_relation(name: str) -> bool:
    if name == "public.character_character_data_id_key":
        return "character_data_id int NOT NULL UNIQUE" in create_table(SCHEMA, '"character"')
    bare = name.removeprefix("public.")
    return bool(re.search(rf"CREATE (TABLE|INDEX) IF NOT EXISTS {re.escape(bare)}\b", SCHEMA))


def _migration_defines_relation(name: str) -> bool:
    bare = name.removeprefix("public.")
    return bool(
        re.search(rf"CREATE (TABLE|INDEX) IF NOT EXISTS {re.escape(bare)}\b", MIGRATION)
        or re.search(rf"ADD CONSTRAINT {re.escape(bare)}\b", MIGRATION)
    )


def _table_for(marker_table: str) -> str:
    return '"character"' if marker_table == "character" else marker_table


@pytest.mark.parametrize("marker", GAME_ACCOUNTS.exclusive_markers, ids=lambda marker: marker.name)
def test_every_readiness_marker_exists_in_a_fresh_schema_and_is_made_by_the_migration(marker):
    # Startup refuses a database missing any marker, so a database created from
    # schema.sql must already have all of them.
    if marker.kind == "relation":
        assert _schema_defines_relation(marker.name)
        assert _migration_defines_relation(marker.name)
    else:
        assert marker.kind == "column"
        _, table, column = marker.name.split(".")
        assert column in column_lines(create_table(SCHEMA, _table_for(table)))
        created_by_migration = f"CREATE TABLE IF NOT EXISTS {table} (" in MIGRATION
        assert (
            f"ADD COLUMN IF NOT EXISTS {column} " in MIGRATION
            or f"TO {column};" in MIGRATION
            or (created_by_migration and column in column_lines(create_table(MIGRATION, table)))
        )


def test_markers_cover_each_reshaped_table():
    names = {marker.name for marker in GAME_ACCOUNTS.exclusive_markers}
    for expected in (
        "public.api_rate.requests_per_minute", "public.api_rate_window.kind", "public.api_usage_daily",
        "public.api_key.client", "public.character.name", "public.character.summary",
        "public.character_data.data", "public.sign_in_attempt",
    ):
        assert expected in names
    assert not GAME_ACCOUNTS.shared_markers


def test_sign_in_attempts_name_either_an_account_or_an_unknown_username():
    for sql in (create_table(SCHEMA, "sign_in_attempt"), create_table(MIGRATION, "sign_in_attempt")):
        assert 'user_id int REFERENCES "user"(user_id) ON DELETE CASCADE' in sql
        assert "username_hash text CHECK (username_hash ~ '^[0-9a-f]{64}$')" in sql
        assert "CONSTRAINT sign_in_attempt_subject_check CHECK ((user_id IS NULL) <> (username_hash IS NULL))" in sql
    for index in (
        "sign_in_attempt_user_idx\n    ON sign_in_attempt (user_id, attempted_at) WHERE user_id IS NOT NULL",
        "sign_in_attempt_username_idx\n    ON sign_in_attempt (username_hash, attempted_at) WHERE username_hash IS NOT NULL",
    ):
        assert index in SCHEMA and index in MIGRATION
