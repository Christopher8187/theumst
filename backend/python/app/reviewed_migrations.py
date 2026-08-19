from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .config import Settings, get_settings
from .database import transaction


_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_MIGRATION_LOCK = "theumst.reviewed-migrations.v1"


class MigrationSafetyError(RuntimeError):
    """A fail-closed release precondition or catalogue check failed."""


@dataclass(frozen=True)
class Marker:
    kind: str
    name: str
    parent: str = ""


@dataclass(frozen=True)
class ReviewedMigration:
    key: str
    filename: str
    sha256: str
    exclusive_markers: tuple[Marker, ...]
    shared_markers: tuple[Marker, ...] = ()


_BASELINE_MARKERS = (
    Marker("column", "public.grimoire.source_key"),
    Marker("column", "public.section.source_key"),
    Marker("column", "public.knowledge.source_key"),
    Marker("column", "public.language_knowledge.label"),
    Marker("relation", "public.book_image"),
    Marker("relation", "public.media_post"),
    Marker("relation", "public.demo_access_request"),
    Marker("relation", "public.user_grimoire"),
    Marker("relation", "public.demo_knowledge_progress"),
    Marker("relation", "public.demo_study_state"),
    Marker("relation", "public.demo_note"),
    Marker("relation", "public.demo_similarity"),
)


REVIEWED_MIGRATIONS = (
    ReviewedMigration(
        key="knowledge_graph_v1",
        filename="006_knowledge_graph.sql",
        sha256="80ec5d15f619aa2db3745806bb8bc64a5d97f44054f63ba0c664d2426f6e6aba",
        exclusive_markers=(
            Marker("column", "public.grimoire.graph_contract_version"),
            Marker("column", "public.grimoire.graph_revision"),
            Marker("column", "public.grimoire.graph_capability"),
            Marker("column", "public.grimoire.graph_receipt_id"),
            Marker("relation", "public.knowledge_graph_node"),
            Marker("relation", "public.knowledge_graph_edge"),
            Marker("relation", "public.knowledge_graph_receipt"),
            Marker("relation", "public.knowledge_graph_edge_source_idx"),
            Marker("relation", "public.knowledge_graph_edge_target_idx"),
            Marker("relation", "public.knowledge_graph_receipt_book_idx"),
        ),
        shared_markers=(Marker("relation", "public.section_book_parent_idx"),),
    ),
)


def validate_backup_sha256(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _SHA256_RE.fullmatch(normalized):
        raise MigrationSafetyError("A verified 64-character backup SHA-256 is required")
    return normalized


def _migration_path(settings: Settings, migration: ReviewedMigration) -> Path:
    path = settings.sql_dir / migration.filename
    if not path.is_file():
        raise MigrationSafetyError(f"Reviewed migration source is missing: {migration.key}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != migration.sha256:
        raise MigrationSafetyError(f"Reviewed migration checksum mismatch: {migration.key}")
    return path


def validated_migration_sources(
    settings: Settings | None = None,
) -> tuple[tuple[ReviewedMigration, Path], ...]:
    resolved = settings or get_settings()
    return tuple(
        (migration, _migration_path(resolved, migration))
        for migration in REVIEWED_MIGRATIONS
    )


def _marker_present(cur, marker: Marker) -> bool:
    if marker.kind == "relation":
        cur.execute("SELECT to_regclass(%s) IS NOT NULL AS present", (marker.name,))
    elif marker.kind == "function":
        cur.execute("SELECT to_regprocedure(%s) IS NOT NULL AS present", (marker.name,))
    elif marker.kind == "column":
        relation, column = marker.name.rsplit(".", 1)
        schema, table = relation.split(".", 1)
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s AND column_name = %s
            ) AS present
            """,
            (schema, table, column),
        )
    elif marker.kind == "trigger":
        schema, table = marker.parent.split(".", 1)
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_trigger trigger_row
                JOIN pg_class relation_row ON relation_row.oid = trigger_row.tgrelid
                JOIN pg_namespace schema_row ON schema_row.oid = relation_row.relnamespace
                WHERE schema_row.nspname = %s
                  AND relation_row.relname = %s
                  AND trigger_row.tgname = %s
                  AND NOT trigger_row.tgisinternal
            ) AS present
            """,
            (schema, table, marker.name),
        )
    else:
        raise MigrationSafetyError("Unsupported migration catalogue marker")
    row = cur.fetchone()
    return bool(row and row.get("present"))


def _present_count(cur, markers: Iterable[Marker]) -> tuple[int, int]:
    marker_list = tuple(markers)
    return sum(_marker_present(cur, marker) for marker in marker_list), len(marker_list)


def _assert_markers_present(cur, markers: Iterable[Marker], *, label: str) -> None:
    present, expected = _present_count(cur, markers)
    if present != expected:
        raise MigrationSafetyError(f"Database catalogue is not ready: {label}")


def _migration_state(cur, migration: ReviewedMigration) -> str:
    present, expected = _present_count(cur, migration.exclusive_markers)
    if present == 0:
        return "missing"
    if present != expected:
        raise MigrationSafetyError(f"Partial migration catalogue detected: {migration.key}")
    _assert_markers_present(cur, migration.shared_markers, label=migration.key)
    return "applied"


def assert_database_schema_ready() -> None:
    """Read-only production startup gate; it never executes repository SQL."""
    with transaction() as (_, cur):
        cur.execute("SET TRANSACTION READ ONLY")
        _assert_markers_present(cur, _BASELINE_MARKERS, label="historical baseline")
        for migration, _ in validated_migration_sources():
            if _migration_state(cur, migration) != "applied":
                raise MigrationSafetyError(f"Reviewed migration is missing: {migration.key}")


def apply_reviewed_migrations(
    *,
    backup_sha256: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Apply only checksum-pinned, wholly missing migration 006."""
    backup_fingerprint = validate_backup_sha256(backup_sha256)
    sources = validated_migration_sources(settings)
    actions: list[dict[str, str]] = []

    with transaction() as (_, cur):
        cur.execute("SET LOCAL lock_timeout = '5s'")
        cur.execute("SET LOCAL statement_timeout = '120s'")
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (_MIGRATION_LOCK,))
        _assert_markers_present(cur, _BASELINE_MARKERS, label="historical baseline")

        for migration, path in sources:
            state = _migration_state(cur, migration)
            if state == "missing":
                cur.execute(path.read_text(encoding="utf-8"))
                _assert_markers_present(
                    cur,
                    (*migration.exclusive_markers, *migration.shared_markers),
                    label=migration.key,
                )
                action = "applied"
            else:
                action = "already_applied"
            actions.append(
                {
                    "migration": migration.key,
                    "sha256": migration.sha256,
                    "action": action,
                }
            )

    return {
        "status": "ok",
        "backup_sha256": backup_fingerprint,
        "migrations": actions,
    }
