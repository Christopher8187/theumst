"""Slow repeated wrong passwords at the game's sign-in, per username and per address.

Each attempt is kept for a day as the SHA-256 of the casefolded username (never
the typed text), the client's address when it is a public one, and whether the
password was right. A username may fail MAX_FAILURES_PER_USERNAME times in
WINDOW since its last right password; an address may fail
MAX_FAILURES_PER_ADDRESS times in WINDOW whatever the usernames.
"""
from __future__ import annotations

import ipaddress
from datetime import timedelta

from ..security import hash_secret


WINDOW = timedelta(minutes=15)
MAX_FAILURES_PER_USERNAME = 10
MAX_FAILURES_PER_ADDRESS = 30
KEEP = timedelta(days=1)

_USERNAME_FAILURES = """
    SELECT count(*) AS failures,
           COALESCE(ceil(extract(epoch FROM min(attempted_at) + %(window)s - now()))::int, 0)
               AS wait_seconds
    FROM sign_in_attempt
    WHERE username_hash = %(subject)s
      AND NOT succeeded
      AND attempted_at > now() - %(window)s
      AND attempted_at > COALESCE(
          (SELECT max(attempted_at) FROM sign_in_attempt
           WHERE username_hash = %(subject)s AND succeeded),
          '-infinity'::timestamptz)
"""

_ADDRESS_FAILURES = """
    SELECT count(*) AS failures,
           COALESCE(ceil(extract(epoch FROM min(attempted_at) + %(window)s - now()))::int, 0)
               AS wait_seconds
    FROM sign_in_attempt
    WHERE address = %(address)s
      AND NOT succeeded
      AND attempted_at > now() - %(window)s
"""


def username_hash(username: str) -> str:
    return hash_secret(username.strip().casefold())


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


def retry_after(cur, subject_hash: str, address: str | None) -> int:
    """Seconds before another attempt may be made, or 0 when one may be made now."""
    waits = []
    cur.execute(_USERNAME_FAILURES, {"subject": subject_hash, "window": WINDOW})
    row = cur.fetchone()
    if int(row["failures"]) >= MAX_FAILURES_PER_USERNAME:
        waits.append(int(row["wait_seconds"]))
    if address:
        cur.execute(_ADDRESS_FAILURES, {"address": address, "window": WINDOW})
        row = cur.fetchone()
        if int(row["failures"]) >= MAX_FAILURES_PER_ADDRESS:
            waits.append(int(row["wait_seconds"]))
    return max(1, *waits) if waits else 0


def record(cur, subject_hash: str, address: str | None, *, succeeded: bool) -> None:
    """Keep this attempt and forget those older than a day."""
    cur.execute("DELETE FROM sign_in_attempt WHERE attempted_at < now() - %s", (KEEP,))
    cur.execute(
        "INSERT INTO sign_in_attempt (username_hash, address, succeeded) VALUES (%s, %s, %s)",
        (subject_hash, address, succeeded),
    )
