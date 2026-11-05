"""Migration 014 and schema.sql delete a character's save with the character.

These checks read the SQL text and drive the readiness checks with scripted
cursors; they do not run the SQL. Running the migration on a restored copy of
COM's database is the release check for its PostgreSQL behaviour, including the
cascade from a deleted account (docs/game-accounts.md lists the queries).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from app import reviewed_migrations


ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = ROOT / "backend/sql/014_character_data_deletion.sql"
MIGRATION = MIGRATION_PATH.read_text(encoding="utf-8")
SCHEMA = (ROOT / "backend/sql/schema.sql").read_text(encoding="utf-8")
CHARACTER_DATA_DELETION = next(
    migration for migration in reviewed_migrations.REVIEWED_MIGRATIONS
    if migration.key == "character_data_deletion_v1"
)

FUNCTION = re.compile(r"CREATE OR REPLACE FUNCTION delete_character_data\(\)\n.*?\n\$\$;\n", re.DOTALL)
TRIGGER = (
    'DROP TRIGGER IF EXISTS character_delete_character_data ON "character";\n'
    "CREATE TRIGGER character_delete_character_data\n"
    'AFTER DELETE ON "character"\n'
    "FOR EACH ROW EXECUTE FUNCTION delete_character_data();\n"
)
CLEANUP = (
    "DELETE FROM character_data d\n"
    "WHERE NOT EXISTS (\n"
    '    SELECT 1 FROM "character" c WHERE c.character_data_id = d.character_data_id\n'
    ");\n"
)


def function_in(sql: str) -> str:
    matches = FUNCTION.findall(sql)
    assert len(matches) == 1
    return matches[0]


def test_the_migration_and_a_fresh_schema_make_the_same_function_and_trigger():
    assert function_in(MIGRATION) == function_in(SCHEMA)
    assert MIGRATION.count(TRIGGER) == 1 and SCHEMA.count(TRIGGER) == 1
    assert MIGRATION.index(function_in(MIGRATION)) < MIGRATION.index(TRIGGER)
    assert SCHEMA.index(function_in(SCHEMA)) < SCHEMA.index(TRIGGER)
    assert SCHEMA.index('CREATE TABLE IF NOT EXISTS "character" (') < SCHEMA.index(TRIGGER)


def test_deleting_a_character_row_deletes_the_save_it_points_at():
    body = function_in(MIGRATION)
    assert "RETURNS trigger\nLANGUAGE plpgsql\n" in body
    assert "    DELETE FROM character_data WHERE character_data_id = OLD.character_data_id;\n" in body
    # After the row is gone, so the foreign key's cascade from the deleted save
    # back to "character" finds nothing. A BEFORE trigger would delete the row
    # its own statement is deleting, which PostgreSQL refuses.
    for sql in (MIGRATION, SCHEMA):
        assert "BEFORE DELETE ON \"character\"" not in sql
        assert "AFTER DELETE ON \"character\"\nFOR EACH ROW" in sql


def test_the_foreign_key_still_deletes_a_character_with_its_save():
    # 014 adds the other direction and leaves the column as it is.
    character = SCHEMA.split('CREATE TABLE IF NOT EXISTS "character" (', 1)[1].split("\n);", 1)[0]
    assert (
        "character_data_id int NOT NULL UNIQUE REFERENCES character_data(character_data_id) ON DELETE CASCADE"
        in character
    )
    assert "ALTER TABLE" not in MIGRATION and "CONSTRAINT" not in MIGRATION


def test_saves_no_character_points_at_are_removed_by_the_migration_only():
    assert MIGRATION.endswith(CLEANUP)
    assert MIGRATION.index(TRIGGER) < MIGRATION.index(CLEANUP)
    # A fresh database has no saves to remove.
    assert "DELETE FROM character_data d" not in SCHEMA


def test_every_statement_of_the_migration_can_run_again():
    statements = [
        line.strip() for line in MIGRATION.splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]
    starts = [line for line in statements if line.split()[0] in {"CREATE", "DROP", "ALTER", "DELETE", "INSERT", "UPDATE"}]
    assert starts == [
        "CREATE OR REPLACE FUNCTION delete_character_data()",
        "DELETE FROM character_data WHERE character_data_id = OLD.character_data_id;",
        'DROP TRIGGER IF EXISTS character_delete_character_data ON "character";',
        "CREATE TRIGGER character_delete_character_data",
        "DELETE FROM character_data d",
    ]
    # Executed without parameters, but keep the file free of % placeholders anyway.
    assert "%" not in MIGRATION


def test_the_pin_is_the_sha256_of_the_file_as_git_checks_it_out():
    data = MIGRATION_PATH.read_bytes()
    assert b"\r" not in data  # .gitattributes keeps *.sql at LF on every machine
    assert hashlib.sha256(data).hexdigest() == CHARACTER_DATA_DELETION.sha256
    assert reviewed_migrations.REVIEWED_MIGRATIONS[-1] is CHARACTER_DATA_DELETION
    assert reviewed_migrations.REVIEWED_MIGRATIONS[-2].key == "game_accounts_v1"


def test_the_readiness_markers_are_the_function_and_the_trigger():
    assert [(marker.kind, marker.name, marker.parent) for marker in CHARACTER_DATA_DELETION.exclusive_markers] == [
        ("function", "public.delete_character_data()", ""),
        ("trigger", "character_delete_character_data", "public.character"),
    ]
    assert not CHARACTER_DATA_DELETION.shared_markers


class CatalogueCursor:
    def __init__(self, present=True):
        self.present = present
        self.executions: list[tuple[str, object]] = []

    def execute(self, sql, params=None):
        self.executions.append((" ".join(sql.split()), params))

    def fetchone(self):
        return {"present": self.present}


def test_the_markers_are_looked_up_in_the_catalogue_by_signature_and_table():
    cursor = CatalogueCursor()
    function, trigger = CHARACTER_DATA_DELETION.exclusive_markers
    assert reviewed_migrations._marker_present(cursor, function)
    assert reviewed_migrations._marker_present(cursor, trigger)
    (function_sql, function_params), (trigger_sql, trigger_params) = cursor.executions
    assert function_sql == "SELECT to_regprocedure(%s) IS NOT NULL AS present"
    assert function_params == ("public.delete_character_data()",)
    assert "FROM pg_trigger trigger_row" in trigger_sql and "AND NOT trigger_row.tgisinternal" in trigger_sql
    # pg_class holds the table's name without quotes.
    assert trigger_params == ("public", "character", "character_delete_character_data")


@pytest.mark.parametrize(
    ("present", "state"),
    [((False, False), "missing"), ((True, True), "applied")],
)
def test_a_database_before_014_is_missing_it_and_one_after_has_it(monkeypatch, present, state):
    answers = iter(present)
    monkeypatch.setattr(reviewed_migrations, "_marker_present", lambda *args: next(answers))
    assert reviewed_migrations._migration_state(object(), CHARACTER_DATA_DELETION) == state


@pytest.mark.parametrize("present", [(True, False), (False, True)])
def test_a_function_without_its_trigger_or_the_reverse_is_refused_as_partial(monkeypatch, present):
    answers = iter(present)
    monkeypatch.setattr(reviewed_migrations, "_marker_present", lambda *args: next(answers))
    with pytest.raises(reviewed_migrations.MigrationSafetyError, match="Partial migration catalogue"):
        reviewed_migrations._migration_state(object(), CHARACTER_DATA_DELETION)
