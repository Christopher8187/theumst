"""Regular API keys made by the website itself: the Default key and the game's keys.

A key's full text exists only in the response that makes it; the database keeps
its hash and prefix.
"""
from __future__ import annotations

from typing import Any

from ..security import new_api_key


DEFAULT_KEY_NAME = "Default"
STANDARD_TIER = "standard"


class StandardTierMissing(RuntimeError):
    """The standard api_rate row is missing, so no regular key can be made."""


def create_regular_key(cur, user_id: int, name: str, *, client: str | None = None) -> dict[str, Any]:
    """Make a regular key at the standard tier and return it with its full text."""
    cur.execute(
        "SELECT api_rate_id, requests_per_minute, level_name FROM api_rate WHERE level_name = %s",
        (STANDARD_TIER,),
    )
    rate = cur.fetchone()
    if not rate:
        raise StandardTierMissing("Standard API rate is not configured")
    raw, prefix, digest = new_api_key("regular")
    cur.execute(
        """
        INSERT INTO api_key (
            user_id, api_rate_id, name, key_prefix, key_hash, key_type, client
        ) VALUES (%s, %s, %s, %s, %s, 'regular', %s)
        RETURNING api_key_id
        """,
        (user_id, rate["api_rate_id"], name, prefix, digest, client),
    )
    key_id = int(cur.fetchone()["api_key_id"])
    return {
        "api_key_id": key_id,
        "name": name,
        "key": raw,
        "key_prefix": prefix,
        "key_type": "regular",
        "client": client,
        "tier": rate["level_name"],
        "requests_per_minute": int(rate["requests_per_minute"]),
    }


def ensure_default_key(cur, user_id: int) -> dict[str, Any] | None:
    """Make the account's Default key unless it has had one; return it when made.

    Any key named "Default" outside a program counts, revoked ones included,
    because keys are revoked rather than deleted: revoking the Default key does
    not bring a new one. The account row lock keeps two page loads from both
    making one.
    """
    cur.execute('SELECT user_id FROM "user" WHERE user_id = %s FOR UPDATE', (user_id,))
    if not cur.fetchone():
        return None
    cur.execute(
        "SELECT 1 AS present FROM api_key WHERE user_id = %s AND name = %s AND client IS NULL LIMIT 1",
        (user_id, DEFAULT_KEY_NAME),
    )
    if cur.fetchone():
        return None
    return create_regular_key(cur, user_id, DEFAULT_KEY_NAME)
