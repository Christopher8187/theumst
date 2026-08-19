from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    return password_context.verify(plain, hashed)


def hash_password(value: str) -> str:
    return password_context.hash(value)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def new_password_reset_token() -> str:
    return secrets.token_urlsafe(32)


def new_email_verification_token() -> str:
    return secrets.token_urlsafe(32)


def session_expiry(days: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


def new_api_key(key_type: str = "regular") -> tuple[str, str, str]:
    if key_type not in {"regular", "master"}:
        raise ValueError("Invalid API key type")
    marker = "mstr" if key_type == "master" else "read"
    raw = f"umst_{marker}_{secrets.token_urlsafe(32)}"
    return raw, raw[:16], hash_secret(raw)
