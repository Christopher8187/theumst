"""Slow repeated wrong passwords, per account and per address.

The game's sign-in (/api/game/sign-in) and the website's login (/auth/login)
both check passwords through attempt(), so they share these limits and the
sign_in_attempt table: wrong passwords at either count toward both.

An attempt first looks the account up. Attempts on an account are counted by
its user_id, so only that account's own right password, or a reset of its
password, resets its count. Attempts on a username no account has are counted
by the SHA-256 of the username as the lookup normalises it, lower(btrim(...))
in PostgreSQL. The client's public address is counted too. Rows are kept for a
day.

The subject's and the address's advisory locks are held from counting to
recording, so parallel attempts cannot all pass the limit.
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from typing import Any

from ..security import hash_password, verify_password


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


def clear_account(cur, user_id: int) -> None:
    """Clear the account's wrong-password count, inside the caller's
    transaction. A successful password reset calls this.

    It records a right password for the account with no address, so the
    account's count starts again, as after its own right password. The wrong
    passwords stay recorded, so each address keeps its count. Unlike record()
    it forgets no old rows: that delete could wait on a game sign-in that is
    itself waiting on the keys the reset revoked.
    """
    cur.execute(
        """
        INSERT INTO sign_in_attempt (user_id, username_hash, address, succeeded)
        VALUES (%s, NULL, NULL, true)
        """,
        (user_id,),
    )


@lru_cache(maxsize=1)
def decoy_hash() -> str:
    # Checking an unknown username's password against this takes as long as a
    # real check, so the answer's timing does not tell which usernames exist.
    return hash_password("theumst-unknown-account")


@dataclass(frozen=True)
class Attempt:
    """What one attempt found.

    `account` is find_account's row; its user_id is None for an unknown
    username. `wait` is the seconds to wait when the attempt was refused past a
    limit, and then the password was not checked; otherwise it is 0. `correct`
    is true when the password was the account's, whether or not its email is
    confirmed.
    """

    account: dict[str, Any]
    wait: int
    correct: bool


def attempt(cur, username: str, password: str, address: str | None) -> Attempt:
    """Check a password under the limits, inside the caller's transaction.

    Looks the account up, takes the locks, and refuses past a limit without
    checking the password or recording anything. Otherwise it checks the
    password, against a decoy for an unknown username, and records the attempt.
    The locks are held until the caller's transaction ends, and the caller must
    commit that transaction even when it then refuses the attempt, so that a
    wrong password counts.
    """
    account = find_account(cur, username)
    user_id = account["user_id"]
    subject = {
        "user_id": user_id,
        "username_hash": None if user_id is not None else account["username_hash"],
        "address": address,
    }
    lock(cur, **subject)
    wait = retry_after(cur, **subject)
    if wait:
        return Attempt(account, wait, False)
    if user_id is not None:
        correct = verify_password(password, account["password_hash"])
    else:
        verify_password(password, decoy_hash())
        correct = False
    record(cur, **subject, succeeded=correct)
    return Attempt(account, 0, correct)
