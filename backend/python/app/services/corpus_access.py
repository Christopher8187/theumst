from __future__ import annotations

import logging
import os
import re
import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

from fastapi import HTTPException


logger = logging.getLogger("theumst.security.corpus_access")

POLICY_MODE_ENV = "RESEARCH_CORPUS_POLICY_MODE"
POLICY_MODE_DATABASE = "database"
ASSET_TTL_ENV = "RESEARCH_ASSET_URL_TTL_SECONDS"
AUDIT_OWNER_ENV = "RESEARCH_ACCESS_AUDIT_OWNER"
AUDIT_RETENTION_ENV = "RESEARCH_ACCESS_AUDIT_RETENTION_DAYS"
AUDIT_KEY_ENV = "RESEARCH_ACCESS_AUDIT_KEY"
ACCESS_REVISION_HEADER = "X-Theumst-Access-Revision"

_SAFE_SURFACES = {
    "asset",
    "bulk",
    "cache",
    "content_book",
    "demo_book",
    "demo_graph",
    "demo_knowledge",
    "demo_note",
    "demo_progress",
    "demo_search",
    "demo_state",
    "developer_api",
    "export",
    "index",
    "ingestion",
    "predeployment",
}
_SAFE_REASONS = {
    "configuration_unavailable",
    "invalid_actor",
    "not_allowlisted",
    "policy_store_unavailable",
}
_SAFE_SQL_EXPRESSIONS = {
    "bi.grimoire_id",
    "g.grimoire_id",
    "mp.grimoire_id",
    "n.grimoire_id",
    "s.grimoire_id",
    "target_section.grimoire_id",
}


@dataclass(frozen=True)
class CorpusAccessAuditContract:
    owner: str
    retention_days: int
    event_name: str = "protected_corpus_access_denied"


def _bounded_int(raw: str | None, *, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def audit_contract() -> CorpusAccessAuditContract:
    owner = (os.getenv(AUDIT_OWNER_ENV) or "security").strip()
    if not owner or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", owner):
        owner = "security"
    return CorpusAccessAuditContract(
        owner=owner,
        retention_days=_bounded_int(
            os.getenv(AUDIT_RETENTION_ENV),
            default=90,
            minimum=1,
            maximum=365,
        ),
    )


def policy_is_configured() -> bool:
    return (os.getenv(POLICY_MODE_ENV) or "").strip().lower() == POLICY_MODE_DATABASE


def assert_public_image_mount_isolated(settings) -> None:
    """Prevent the static public mount from overlapping private book storage."""
    if settings.server != "LOCAL":
        return
    raw = settings.local_storage_dir
    storage_root = (
        Path.home() / "theumst_storage"
        if not raw or raw == "__AUTO__"
        else Path(os.path.expandvars(raw)).expanduser()
    ).resolve()
    public_root = settings.public_images.resolve()
    if (
        storage_root == public_root
        or storage_root in public_root.parents
        or public_root in storage_root.parents
    ):
        raise RuntimeError("Public images and private book storage must be isolated")


def actor_user_id(actor: dict[str, Any] | None) -> int | None:
    """Return only the stable internal user ID; authority never enters policy."""
    if not actor:
        return None
    value = actor.get("user_id")
    if isinstance(value, bool):
        return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def audit_denied_access(*, user_id: int | None, surface: str, reason: str) -> None:
    """Emit a deliberately data-minimal event suitable for alerting.

    Never include corpus IDs, passages, vectors, URLs, request bodies, secrets,
    names, email addresses, IP addresses, or arbitrary exception text here.
    """
    contract = audit_contract()
    safe_surface = surface if surface in _SAFE_SURFACES else "other"
    safe_reason = reason if reason in _SAFE_REASONS else "not_allowlisted"
    audit_key = os.getenv(AUDIT_KEY_ENV) or ""
    if user_id is None:
        actor_reference = "anonymous"
    elif len(audit_key.encode("utf-8")) >= 32:
        digest = hmac.new(
            audit_key.encode("utf-8"),
            str(user_id).encode("ascii"),
            hashlib.sha256,
        ).hexdigest()[:16]
        actor_reference = f"pseudonymous:{digest}"
    else:
        # Never substitute an unsalted hash: without a protected audit key it
        # would be reversible across the small internal-ID space.
        actor_reference = "authenticated"
    logger.warning(
        "%s actor=%s surface=%s reason=%s owner=%s retention_days=%s",
        contract.event_name,
        actor_reference,
        safe_surface,
        safe_reason,
        contract.owner,
        contract.retention_days,
    )


def access_revision_token(cur, user_id: int | None) -> str:
    audit_key = os.getenv(AUDIT_KEY_ENV) or ""
    if not policy_is_configured() or len(audit_key.encode("utf-8")) < 32:
        return "v1.unavailable"
    if user_id is None:
        subject = "anonymous"
    else:
        subject = str(user_id)
    try:
        cur.execute(
            """
            SELECT protected.grimoire_id, protected.policy_revision,
                   allowed.access_revision,
                   (allowed.revoked_at IS NULL AND allowed.user_id IS NOT NULL) AS active
            FROM research_corpus_policy protected
            LEFT JOIN research_corpus_user_access allowed
              ON allowed.grimoire_id = protected.grimoire_id
             AND allowed.user_id = %s
            WHERE protected.is_protected
            ORDER BY protected.grimoire_id
            """,
            (user_id,),
        )
        rows = [
            (
                int(row["grimoire_id"]),
                str(row["policy_revision"]),
                int(row["access_revision"]) if row.get("access_revision") is not None else 0,
                bool(row.get("active")),
            )
            for row in cur.fetchall()
        ]
    except Exception:
        return "v1.unavailable"
    payload = json.dumps(
        {"subject": subject, "policies": rows},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = hmac.new(
        audit_key.encode("utf-8"),
        b"theumst-access-revision-v1\0" + payload,
        hashlib.sha256,
    ).hexdigest()[:32]
    return f"v1.{digest}"


def revision_headers(cur, user_id: int | None) -> dict[str, str]:
    return {
        ACCESS_REVISION_HEADER: access_revision_token(cur, user_id),
        "Cache-Control": "private, no-store",
        "Vary": "Authorization, Cookie, Accept-Encoding",
    }


def hidden_not_found(*, headers: dict[str, str] | None = None) -> HTTPException:
    return HTTPException(status_code=404, detail="Resource not found", headers=headers)


def ensure_policy_ready(
    *,
    user_id: int | None,
    surface: str,
    list_request: bool = False,
) -> bool:
    """Fail closed when the protected-corpus policy mode is absent/malformed."""
    if policy_is_configured():
        return True
    audit_denied_access(
        user_id=user_id,
        surface=surface,
        reason="configuration_unavailable",
    )
    if list_request:
        return False
    raise hidden_not_found(headers={ACCESS_REVISION_HEADER: "v1.unavailable"})


def corpus_visibility_sql(corpus_expression: str) -> str:
    """Return the centralized DB allowlist predicate for a trusted SQL alias."""
    if corpus_expression not in _SAFE_SQL_EXPRESSIONS:
        raise ValueError("Unsupported corpus SQL expression")
    return f"""
        (
            NOT EXISTS (
                SELECT 1
                FROM research_corpus_policy rcp
                WHERE rcp.grimoire_id = {corpus_expression}
                  AND rcp.is_protected
            )
            OR EXISTS (
                SELECT 1
                FROM research_corpus_user_access rcua
                JOIN research_corpus_policy rcp_allowed
                  ON rcp_allowed.grimoire_id = rcua.grimoire_id
                 AND rcp_allowed.is_protected
                WHERE rcua.grimoire_id = {corpus_expression}
                  AND rcua.user_id = %s
                  AND rcua.revoked_at IS NULL
            )
        )
    """


def corpus_visibility_params(user_id: int | None) -> tuple[int | None]:
    return (user_id,)


def demo_corpus_visibility_sql(corpus_expression: str) -> str:
    """Return the learner-demo visibility rule for a trusted corpus alias.

    Public/demo visibility and research authorization are deliberately
    independent: an unprotected corpus must be opted into the demo, while an
    allowlisted protected corpus remains available to its researchers even
    when its public demo flag is false.
    """
    if corpus_expression not in _SAFE_SQL_EXPRESSIONS:
        raise ValueError("Unsupported corpus SQL expression")
    return f"""
        EXISTS (
            SELECT 1
            FROM grimoire visible_corpus
            WHERE visible_corpus.grimoire_id = {corpus_expression}
              AND (
                  (
                      COALESCE(visible_corpus.source_metadata->>'demo', 'false') = 'true'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM research_corpus_policy public_policy
                          WHERE public_policy.grimoire_id = visible_corpus.grimoire_id
                            AND public_policy.is_protected
                      )
                  )
                  OR EXISTS (
                      SELECT 1
                      FROM research_corpus_policy research_policy
                      JOIN research_corpus_user_access allowed
                        ON allowed.grimoire_id = research_policy.grimoire_id
                       AND allowed.user_id = %s
                       AND allowed.revoked_at IS NULL
                      WHERE research_policy.grimoire_id = visible_corpus.grimoire_id
                        AND research_policy.is_protected
                  )
              )
        )
    """


def _protected_target_exists(cur, query: str, values: tuple[Any, ...]) -> bool:
    try:
        cur.execute(query, values)
        row = cur.fetchone()
        return bool(row and row.get("protected"))
    except Exception:
        # The request remains fail-closed. Never serialize DB exception text,
        # target identifiers, or policy markers into an audit record.
        return False


def raise_hidden_grimoire_miss(
    cur,
    *,
    grimoire_id: int,
    user_id: int | None,
    surface: str,
) -> None:
    protected = _protected_target_exists(
        cur,
        """
        SELECT EXISTS (
            SELECT 1 FROM research_corpus_policy
            WHERE grimoire_id = %s AND is_protected
        ) AS protected
        """,
        (grimoire_id,),
    )
    if protected:
        audit_denied_access(user_id=user_id, surface=surface, reason="not_allowlisted")
    raise hidden_not_found(headers=revision_headers(cur, user_id))


def raise_hidden_knowledge_miss(
    cur,
    *,
    knowledge_id: int,
    user_id: int | None,
    surface: str,
) -> None:
    protected = _protected_target_exists(
        cur,
        """
        SELECT EXISTS (
            SELECT 1
            FROM knowledge k
            JOIN section s ON s.section_id = k.section_id
            JOIN research_corpus_policy protected
              ON protected.grimoire_id = s.grimoire_id
             AND protected.is_protected
            WHERE k.knowledge_id = %s
        ) AS protected
        """,
        (knowledge_id,),
    )
    if protected:
        audit_denied_access(user_id=user_id, surface=surface, reason="not_allowlisted")
    raise hidden_not_found(headers=revision_headers(cur, user_id))


def raise_hidden_asset_miss(
    cur,
    *,
    storage_key: str,
    user_id: int | None,
) -> None:
    protected = _protected_target_exists(
        cur,
        """
        SELECT EXISTS (
            SELECT 1
            FROM research_corpus_policy protected
            WHERE protected.is_protected
              AND (
                  protected.object_key_prefix = %s
                  OR %s LIKE protected.object_key_prefix || '/%%'
              )
        ) AS protected
        """,
        (storage_key, storage_key),
    )
    if protected:
        audit_denied_access(user_id=user_id, surface="asset", reason="not_allowlisted")
    raise hidden_not_found(headers=revision_headers(cur, user_id))


def raise_hidden_note_miss(
    cur,
    *,
    note_id: int,
    owner_user_id: int,
    user_id: int | None,
) -> None:
    protected = _protected_target_exists(
        cur,
        """
        SELECT EXISTS (
            SELECT 1
            FROM demo_note n
            JOIN research_corpus_policy protected
              ON protected.grimoire_id = n.grimoire_id
             AND protected.is_protected
            WHERE n.demo_note_id = %s AND n.user_id = %s
        ) AS protected
        """,
        (note_id, owner_user_id),
    )
    if protected:
        audit_denied_access(user_id=user_id, surface="demo_note", reason="not_allowlisted")
    raise hidden_not_found(headers=revision_headers(cur, user_id))


def pure_access_decision(
    *,
    protected: bool,
    user_id: int | None,
    active_user_ids: Iterable[int],
) -> bool:
    """Pure mirror of the SQL rule, used for deterministic policy tests."""
    if not protected:
        return True
    if user_id is None:
        return False
    return user_id in {int(value) for value in active_user_ids}


def protected_asset_path(storage_key: str) -> str:
    clean = str(storage_key or "").replace("\\", "/").strip("/")
    if not clean or ".." in clean.split("/"):
        raise hidden_not_found()
    return f"/api/v1/storage/{quote(clean, safe='/')}"


def require_storage_key_access(
    cur,
    *,
    storage_key: str,
    user_id: int | None,
    destructive: bool = False,
) -> bool:
    """Authorize a concrete key using DB-owned protected prefixes.

    Returns whether the key is protected. Deletion of a protected prefix, a
    child, or an ancestor that would contain one is always blocked so ordinary
    storage tooling cannot destroy research material.
    """
    ensure_policy_ready(user_id=user_id, surface="asset")
    clean = str(storage_key or "").replace("\\", "/").strip("/")
    cur.execute(
        """
        SELECT protected.object_key_prefix,
               (
                   protected.object_key_prefix = %s
                   OR %s LIKE protected.object_key_prefix || '/%%'
               ) AS target_inside,
               (
                   %s = ''
                   OR protected.object_key_prefix LIKE %s || '/%%'
               ) AS target_contains,
               EXISTS (
                   SELECT 1
                   FROM research_corpus_user_access allowed
                   WHERE allowed.grimoire_id = protected.grimoire_id
                     AND allowed.user_id = %s
                     AND allowed.revoked_at IS NULL
               ) AS authorized
        FROM research_corpus_policy protected
        WHERE protected.is_protected
          AND (
              protected.object_key_prefix = %s
              OR %s LIKE protected.object_key_prefix || '/%%'
              OR %s = ''
              OR protected.object_key_prefix LIKE %s || '/%%'
          )
        ORDER BY length(protected.object_key_prefix) DESC
        LIMIT 1
        """,
        (clean, clean, clean, clean, user_id, clean, clean, clean, clean),
    )
    row = cur.fetchone()
    if not row:
        return False
    if destructive and (row["target_inside"] or row["target_contains"]):
        audit_denied_access(user_id=user_id, surface="asset", reason="not_allowlisted")
        raise hidden_not_found(headers=revision_headers(cur, user_id))
    if row["target_inside"] and not row["authorized"]:
        audit_denied_access(user_id=user_id, surface="asset", reason="not_allowlisted")
        raise hidden_not_found(headers=revision_headers(cur, user_id))
    return bool(row["target_inside"])


def filter_storage_items(
    cur,
    *,
    items: Iterable[dict[str, Any]],
    user_id: int | None,
) -> list[dict[str, Any]]:
    """Hide denied protected prefixes from generic storage directory lists."""
    if not ensure_policy_ready(user_id=user_id, surface="asset", list_request=True):
        return []
    cur.execute(
        """
        SELECT protected.object_key_prefix,
               EXISTS (
                   SELECT 1
                   FROM research_corpus_user_access allowed
                   WHERE allowed.grimoire_id = protected.grimoire_id
                     AND allowed.user_id = %s
                     AND allowed.revoked_at IS NULL
               ) AS authorized
        FROM research_corpus_policy protected
        WHERE protected.is_protected
        ORDER BY protected.object_key_prefix
        """,
        (user_id,),
    )
    denied = [
        str(row["object_key_prefix"])
        for row in cur.fetchall()
        if not row["authorized"]
    ]
    result = []
    for original in items:
        key = str(original.get("key") or "").replace("\\", "/").strip("/")
        if any(key == prefix or key.startswith(prefix + "/") for prefix in denied):
            continue
        result.append(dict(original))
    return result


def secure_image_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace stored/direct URLs with the policy-enforcing application path."""
    secured: list[dict[str, Any]] = []
    for original in rows:
        row = dict(original)
        storage_key = row.get("storage_key")
        if not storage_key:
            # A protected response must never fall back to an ungoverned URL.
            continue
        row["url"] = protected_asset_path(str(storage_key))
        secured.append(row)
    return secured


def signed_asset_ttl_seconds() -> int:
    return _bounded_int(
        os.getenv(ASSET_TTL_ENV),
        default=300,
        minimum=60,
        maximum=900,
    )


def assert_protected_corpus_policy_ready(cur) -> None:
    """Private predeployment gate; never includes protected markers in errors."""
    if not policy_is_configured():
        audit_denied_access(
            user_id=None,
            surface="predeployment",
            reason="configuration_unavailable",
        )
        raise RuntimeError("Protected corpus policy is not ready")
    try:
        cur.execute(
            """
            SELECT
                EXISTS (
                    SELECT 1 FROM research_corpus_policy WHERE is_protected
                )
                AND NOT EXISTS (
                    SELECT 1
                    FROM research_corpus_policy protected
                    WHERE protected.is_protected
                      AND (
                          SELECT count(*)
                          FROM research_corpus_user_access allowed
                          WHERE allowed.grimoire_id = protected.grimoire_id
                            AND allowed.revoked_at IS NULL
                      ) <> protected.required_active_user_count
                )
                AND NOT EXISTS (
                    SELECT 1
                    FROM research_corpus_policy left_prefix
                    JOIN research_corpus_policy right_prefix
                      ON left_prefix.grimoire_id < right_prefix.grimoire_id
                     AND left_prefix.is_protected
                     AND right_prefix.is_protected
                     AND (
                         left_prefix.object_key_prefix = right_prefix.object_key_prefix
                         OR left_prefix.object_key_prefix LIKE right_prefix.object_key_prefix || '/%%'
                         OR right_prefix.object_key_prefix LIKE left_prefix.object_key_prefix || '/%%'
                     )
                ) AS ready
            """
        )
        row = cur.fetchone()
        if not row or not bool(row.get("ready")):
            raise RuntimeError("Protected corpus policy is not ready")
    except Exception:
        audit_denied_access(
            user_id=None,
            surface="predeployment",
            reason="policy_store_unavailable",
        )
        raise RuntimeError("Protected corpus policy is not ready") from None
