"""Migration 015 and schema.sql keep the install that took a character's lease.

These checks read the SQL text and drive the readiness checks with scripted
cursors; they do not run the SQL. test_key_access_postgres.py runs 015 against
PostgreSQL, and docs/game-accounts.md lists the release checks for a restored
copy of COM's database.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from app import reviewed_migrations
from app.routers import game


ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = ROOT / "backend/sql/015_character_lease_install.sql"
MIGRATION = MIGRATION_PATH.read_text(encoding="utf-8")
SCHEMA = (ROOT / "backend/sql/schema.sql").read_text(encoding="utf-8")
LEASE_INSTALL = next(
    migration for migration in reviewed_migrations.REVIEWED_MIGRATIONS
    if migration.key == "character_lease_install_v1"
)
CHECK = "CHECK (lease_install_id ~ '^[A-Za-z0-9_-]{1,64}$')"


def character_table() -> str:
    match = re.search(r'CREATE TABLE IF NOT EXISTS "character" \((.*?)\n\);', SCHEMA, re.DOTALL)
    assert match
    return match.group(1)


def statements() -> list[str]:
    return [line.strip() for line in MIGRATION.splitlines() if line.strip() and not line.strip().startswith("--")]


def test_the_migration_and_a_fresh_schema_make_the_same_column_and_check():
    assert statements() == [
        'ALTER TABLE "character" ADD COLUMN IF NOT EXISTS lease_install_id text;',
        'ALTER TABLE "character" DROP CONSTRAINT IF EXISTS character_lease_install_id_check;',
        'ALTER TABLE "character" ADD CONSTRAINT character_lease_install_id_check',
        f"{CHECK};",
    ]
    # The fresh table's last column, after the lease's other two. PostgreSQL names
    # its inline check character_lease_install_id_check, the name 015 gives its own.
    lines = [line.strip() for line in character_table().splitlines() if line.strip()]
    assert lines[-3:] == [
        "lease_expires_at timestamptz,",
        "-- The game install that took the lease, when its call named one (X-Install-Id).",
        f"lease_install_id text {CHECK}",
    ]


def test_the_check_is_the_pattern_the_api_takes():
    assert f"'^{game.INSTALL_ID_PATTERN.pattern}$'" in CHECK
    assert game.INSTALL_ID_HEADER == "X-Install-Id"


def test_the_column_is_nullable_without_a_default_or_index():
    # Null when the call that took the lease named no install, as the game before 0.0.13 sends none.
    assert "NOT NULL" not in MIGRATION and "DEFAULT" not in MIGRATION
    assert "CREATE INDEX" not in MIGRATION and "lease_install_id" not in SCHEMA.split(character_table(), 1)[1]


def test_every_statement_of_the_migration_can_run_again():
    added = statements()[0]
    assert "ADD COLUMN IF NOT EXISTS" in added and "CHECK" not in added  # no inline constraint on an added column
    assert MIGRATION.index("DROP CONSTRAINT IF EXISTS character_lease_install_id_check") < MIGRATION.index(
        "ADD CONSTRAINT character_lease_install_id_check"
    )
    # Executed without parameters, but keep the file free of % placeholders anyway.
    assert "%" not in MIGRATION


def test_the_migration_changes_no_rows():
    for line in statements():
        assert not line.upper().startswith(("INSERT ", "UPDATE ", "DELETE ", "TRUNCATE ")), line


def test_the_pin_is_the_sha256_of_the_file_as_git_checks_it_out():
    data = MIGRATION_PATH.read_bytes()
    assert b"\r" not in data  # .gitattributes keeps *.sql at LF on every machine
    assert hashlib.sha256(data).hexdigest() == LEASE_INSTALL.sha256
    migrations = reviewed_migrations.REVIEWED_MIGRATIONS
    position = migrations.index(LEASE_INSTALL)
    assert migrations[position - 1].key == "character_data_deletion_v1"
    assert migrations[position + 1].key == "book_read_v1"


def test_the_readiness_marker_is_the_column():
    assert [(marker.kind, marker.name) for marker in LEASE_INSTALL.exclusive_markers] == [
        ("column", "public.character.lease_install_id"),
    ]
    assert not LEASE_INSTALL.shared_markers


class CatalogueCursor:
    def __init__(self, present=True):
        self.present = present
        self.executions: list[tuple[str, object]] = []

    def execute(self, sql, params=None):
        self.executions.append((" ".join(sql.split()), params))

    def fetchone(self):
        return {"present": self.present}


def test_the_marker_is_looked_up_in_information_schema():
    cursor = CatalogueCursor()
    assert reviewed_migrations._marker_present(cursor, LEASE_INSTALL.exclusive_markers[0])
    sql, params = cursor.executions[0]
    assert "FROM information_schema.columns" in sql
    assert params == ("public", "character", "lease_install_id")


@pytest.mark.parametrize(("present", "state"), [(False, "missing"), (True, "applied")])
def test_a_database_before_015_is_missing_it_and_one_after_has_it(monkeypatch, present, state):
    monkeypatch.setattr(reviewed_migrations, "_marker_present", lambda *args: present)
    assert reviewed_migrations._migration_state(object(), LEASE_INSTALL) == state
