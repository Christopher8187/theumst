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
    ReviewedMigration(
        key="study_positions_v1", filename="007_study_positions.sql", sha256="0d107f66c82a24ef01d6a3fb439c250e45526ca6ddafef0838d427ce2fbace97",
        exclusive_markers=(Marker("column", "public.demo_study_state.questions_knowledge_id"),),
    ),
    ReviewedMigration(
        key="news_subscriptions_v1", filename="008_news_subscriptions.sql",
        sha256="76cf6c87f1527ce1d1b62c554081c9a998fe361a77baa219447b03836f571a43",
        exclusive_markers=(
            Marker("column", "public.media_post.email_introduction"),
            Marker("relation", "public.news_subscription"),
            Marker("relation", "public.news_consent_event"),
            Marker("relation", "public.news_suppression"),
            Marker("relation", "public.news_announcement"),
            Marker("relation", "public.news_delivery"),
            Marker("relation", "public.news_delivery_due_idx"),
            Marker("relation", "public.news_provider_event"),
        ),
    ),
    ReviewedMigration(
        key="media_create_requests_v1", filename="009_media_create_requests.sql",
        sha256="d0dff232132ccab64be2ab95ccef36cf8dcaa6c2bea678a37a8be37c845330ea",
        exclusive_markers=(
            Marker("relation", "public.media_create_request"),
            Marker("relation", "public.media_create_request_pkey"),
            Marker("column", "public.media_create_request.user_id"),
            Marker("column", "public.media_create_request.request_id"),
            Marker("column", "public.media_create_request.payload_sha256"),
            Marker("column", "public.media_create_request.response"),
        ),
    ),
    ReviewedMigration(
        key="knowledge_names_v1", filename="010_knowledge_names.sql",
        sha256="71f1243e6955baf6810cbf484df11d8defe7ce3f7841be7af5b4cc0fa19f4e6a",
        exclusive_markers=(Marker("column", "public.knowledge.name"),),
    ),
    ReviewedMigration(
        key="crystal_source_keys_v1", filename="011_crystal_source_keys.sql",
        sha256="47071af559cdd98d9858200f137af204cbbd31d6c537d51e41902f84b7ad265b",
        exclusive_markers=(
            Marker("column", "public.knowledge_crystal.source_key"),
            Marker("relation", "public.knowledge_crystal_source_key_unique"),
        ),
    ),
    ReviewedMigration(
        key="book_image_objects_v1", filename="012_book_image_objects.sql",
        sha256="e85e4d9360c094cafd528b94316cf8dfdb1868c890579e9afd090ddeea23780a",
        exclusive_markers=(
            Marker("relation", "public.book_image_knowledge"),
            Marker("column", "public.book_image_knowledge.link_type"),
            Marker("relation", "public.book_image_knowledge_object_idx"),
        ),
    ),
    ReviewedMigration(
        key="game_accounts_v1", filename="013_game_accounts.sql",
        sha256="5d4950efc545bbbefbf381ac68f58a13aac52bb505488e70a736297e7aaac7c7",
        exclusive_markers=(
            Marker("column", "public.api_rate.requests_per_minute"),
            Marker("column", "public.api_rate_window.kind"),
            Marker("relation", "public.api_usage_daily"),
            Marker("column", "public.api_key.client"),
            Marker("column", "public.character.name"),
            Marker("column", "public.character.sex"),
            Marker("column", "public.character.summary"),
            Marker("column", "public.character.created_at"),
            Marker("column", "public.character.last_played_at"),
            Marker("column", "public.character.lease_api_key_id"),
            Marker("column", "public.character.lease_expires_at"),
            Marker("relation", "public.character_character_data_id_key"),
            Marker("relation", "public.character_user_idx"),
            Marker("relation", "public.character_lease_key_idx"),
            Marker("column", "public.character_data.data"),
            Marker("column", "public.character_data.save_version"),
            Marker("column", "public.character_data.revision"),
            Marker("column", "public.character_data.updated_at"),
            Marker("relation", "public.sign_in_attempt"),
            Marker("column", "public.sign_in_attempt.user_id"),
            Marker("relation", "public.sign_in_attempt_user_idx"),
            Marker("relation", "public.sign_in_attempt_username_idx"),
            Marker("relation", "public.sign_in_attempt_address_idx"),
            Marker("relation", "public.sign_in_attempt_time_idx"),
        ),
    ),
    ReviewedMigration(
        key="character_data_deletion_v1", filename="014_character_data_deletion.sql",
        sha256="9e9b6cac92c134897b97e96acf980e2ea00e30c73fcecb98fe25387c94444ebc",
        exclusive_markers=(
            Marker("function", "public.delete_character_data()"),
            Marker("trigger", "character_delete_character_data", "public.character"),
        ),
    ),
    ReviewedMigration(
        key="character_lease_install_v1", filename="015_character_lease_install.sql",
        sha256="c72e17fb85e69ff1c952c2a1e85ce2b2f2c043598b84d404eedc225fb27b4765",
        exclusive_markers=(Marker("column", "public.character.lease_install_id"),),
    ),
    ReviewedMigration(
        key="book_read_v1", filename="016_book_read.sql",
        sha256="ccb308ef61a9bb91c380c50557b8bbd716c761b5f607cc750d784ee88953f0f4",
        exclusive_markers=(Marker("relation", "public.book_read"),),
    ),
    ReviewedMigration(
        key="book_game_read_v1", filename="017_book_game_read.sql",
        sha256="6c3b22216b2449369427a7ec82e18b631f0a2f5a5a549b500f10edb09a90a960",
        exclusive_markers=(Marker("relation", "public.book_game_read"),),
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
    """Apply only checksum-pinned, wholly missing reviewed migrations."""
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
