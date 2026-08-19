from __future__ import annotations

import json
import os
import re

from app.database import transaction


def _required_digest() -> str:
    value = os.environ.get("THEUMST_PUBLISHER_KEY_HASH", "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise RuntimeError("THEUMST_PUBLISHER_KEY_HASH must be a SHA-256 hex digest")
    return value


def _required_prefix() -> str:
    value = os.environ.get("THEUMST_PUBLISHER_KEY_PREFIX", "").strip()
    if not 8 <= len(value) <= 32:
        raise RuntimeError("THEUMST_PUBLISHER_KEY_PREFIX must contain 8 to 32 characters")
    return value


def main() -> None:
    digest = _required_digest()
    prefix = _required_prefix()
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT u.user_id, u.username
            FROM "user" u
            JOIN authority a ON a.authority_id = u.authority_id
            WHERE a.name = 'superadmin'
            ORDER BY
                CASE WHEN lower(u.username) LIKE 'christopher%' THEN 0 ELSE 1 END,
                u.user_id
            LIMIT 1
            FOR UPDATE OF u
            """
        )
        owner = cur.fetchone()
        if not owner:
            raise RuntimeError("No active superadmin is available to own the publisher key")
        cur.execute(
            """
            INSERT INTO api_key (
                user_id, api_rate_id, name, password_hash, key_prefix, key_hash, key_type,
                revoked_at, upgraded_at, upgraded_by_user_id
            ) VALUES (%s, NULL, %s, '', %s, %s, 'master', NULL, now(), %s)
            ON CONFLICT (key_hash) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                api_rate_id = NULL,
                name = EXCLUDED.name,
                key_prefix = EXCLUDED.key_prefix,
                key_type = 'master',
                revoked_at = NULL,
                upgraded_at = now(),
                upgraded_by_user_id = EXCLUDED.upgraded_by_user_id
            RETURNING api_key_id, key_prefix, key_type
            """,
            (
                owner["user_id"],
                "Kaicenat StoreDatabase publisher",
                prefix,
                digest,
                owner["user_id"],
            ),
        )
        key = dict(cur.fetchone())
    print(json.dumps({
        "ok": True,
        "owner": owner["username"],
        "api_key_id": key["api_key_id"],
        "key_prefix": key["key_prefix"],
        "key_type": key["key_type"],
    }))


if __name__ == "__main__":
    main()
