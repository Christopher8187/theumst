"""Slow repeated wrong passwords at the game's sign-in, per account and per address.

A sign-in first looks the account up. Attempts on an account are counted by its
user_id, so only that account's own right password resets its count. Attempts
on a username no account has are counted by the SHA-256 of the username as the
lookup normalises it, lower(btrim(...)) in PostgreSQL. The client's public
address is counted too. Rows are kept for a day.

The subject's and the address's advisory locks are held from counting to
recording, so parallel attempts cannot all pass the limit.
"""
from __future__ import annotations

import ipaddress
from datetime import timedelta
from typing import Any


WINDOW = timedelta(minutes=15)
MAX_FAILURES_PER_USERNAME = 10
MAX_FAILURES_PER_ADDRESS = 30
KEEP = timedelta(days=1)

_FIND_ACCOUNT = """
    SELECT encode(sha256(convert_to(lower(btrim(%(username)s)), 'UTF8')), 'hex') AS username_hash,
           u.user_id, u.username, u.password_hash, u.email_verified_at
    FROM (SELECT 1) AS typed
    LEFT JOIN "user" u ON lower(u.username) = lower(btrim(%(username)s))
"""

_WAIT = "COALESCE(ceil(extract(epoch FROM min(attempted_at) + %(window)s - now()))::int, 0) AS wait_seconds"

_ACCOUNT_FAILURES = f"""
    SELECT count(*) AS failures, {_WAIT}
    FROM sign_in_attempt
    WHERE user_id = %(user_id)s
      AND NOT succeeded
      AND attempted_at > now() - %(window)s
      AND attempted_at > COALESCE(
          (SELECT max(attempted_at) FROM sign_in_attempt
           WHERE user_id = %(user_id)s AND succeeded),
          '-infinity'::timestamptz)
"""

_USERNAME_FAILURES = f"""
    SELECT count(*) AS failures, {_WAIT}
    FROM sign_in_attempt
    WHERE username_hash = %(username_hash)s
      AND NOT succeeded
      AND attempted_at > now() - %(window)s
"""

_ADDRESS_FAILURES = f"""
    SELECT count(*) AS failures, {_WAIT}
    FROM sign_in_attempt
    WHERE address = %(address)s
      AND NOT succeeded
      AND attempted_at > now() - %(window)s
"""


def find_account(cur, username: str) -> dict[str, Any]:
    """The account the typed username names, if any, and the SHA-256 of the
    username as the lookup normalises it. Always one row."""
    cur.execute(_FIND_ACCOUNT, {"username": username})
    return cur.fetchone()


def public_address(request) -> str | None:
    """The client's address when it is globally routable, else None.

    In deployment two proxies stand in front of the backend; uvicorn takes the
    client from X-Forwarded-For only when FORWARDED_ALLOW_IPS trusts them. A
    private, loopback or other special address is a proxy or a local tool, so
    it is never throttled as one address shared by everyone behind it.
    """
    client = getattr(request, "client", None)
    try:
        address = ipaddress.ip_address(client.host if client else "")
    except ValueError:
        return None
    return str(address) if address.is_global else None


def lock(cur, *, user_id: int | None, username_hash: str | None, address: str | None) -> None:
    """Wait for other attempts on the same account or username, then address."""
    if user_id is not None:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('theumst.sign-in.account'), %s)", (user_id,))
    else:
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtext('theumst.sign-in.username'), hashtext(%s))",
            (username_hash,),
        )
    if address:
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtext('theumst.sign-in.address'), hashtext(%s))",
            (address,),
        )


def retry_after(cur, *, user_id: int | None, username_hash: str | None, address: str | None) -> int:
    """Seconds before another attempt may be made, or 0 when one may be made now."""
    waits = []
    if user_id is not None:
        cur.execute(_ACCOUNT_FAILURES, {"user_id": user_id, "window": WINDOW})
    else:
        cur.execute(_USERNAME_FAILURES, {"username_hash": username_hash, "window": WINDOW})
    row = cur.fetchone()
    if int(row["failures"]) >= MAX_FAILURES_PER_USERNAME:
        waits.append(int(row["wait_seconds"]))
    if address:
        cur.execute(_ADDRESS_FAILURES, {"address": address, "window": WINDOW})
        row = cur.fetchone()
        if int(row["failures"]) >= MAX_FAILURES_PER_ADDRESS:
            waits.append(int(row["wait_seconds"]))
    return max(1, *waits) if waits else 0


def record(cur, *, user_id: int | None, username_hash: str | None, address: str | None, succeeded: bool) -> None:
    """Keep this attempt and forget those older than a day."""
    cur.execute("DELETE FROM sign_in_attempt WHERE attempted_at < now() - %s", (KEEP,))
    cur.execute(
        """
        INSERT INTO sign_in_attempt (user_id, username_hash, address, succeeded)
        VALUES (%s, %s, %s, %s)
        """,
        (user_id, None if user_id is not None else username_hash, address, succeeded),
    )
