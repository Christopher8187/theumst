"""UMST's account, character, book and notes API.

The game signs in with a username and password and receives its own key, named
"UMST · <computer>" with client 'umst'. Every other call sends that key, or any
other active regular key of the same account, in X-API-Key or Authorization:
Bearer. Account and character calls count as the 'character' kind of the key's
per-minute allowance; the book and notes calls (0.0.16) count as 'book', shared
with /api/v1. Master keys are refused.

Since 0.0.16 the game reads whole books here, once per book version, and keeps
the account's Web Demo notes. Reading a book and its notes needs Web Demo
access, as the Web Demo and /api/v1 do (0.0.13); the list of grimoires does not,
so an account without it learns that it may not read.

A character is open on one computer at a time: opening it takes a lease held by
the opening key for LEASE_SECONDS, renewed by heartbeats and saves. The game
names its install in the X-Install-Id header, and the lease keeps the install
that took it, so the same key on a second computer is refused like another key
while the lease lives. A call without the header is judged by its key alone, as
before 0.0.13. Each save names the revision it was loaded at and is refused
unless that is the current one. docs/game-accounts.md describes the request and
response shapes.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import psycopg2
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..database import transaction
from ..dependencies import DEMO_ACCESS_POINT, AccessRefused, authenticate_api_key
from ..schemas import GameNoteCreate, GameNoteDelete, GameNoteUpdate
from ..services import book_read, sign_in_attempts
from ..services.api_keys import GAME_CLIENT, create_regular_key, revoke_game_keys


LEASE_SECONDS = 120
MAX_CHARACTERS = 6
NAME_MAX_CHARACTERS = 50
COMPUTER_MAX_CHARACTERS = 100
SAVE_MAX_BYTES = 64 * 1024
SUMMARY_MAX_BYTES = 2 * 1024
# The game keeps a short id per install and names its keys "UMST · <computer> ·
# <install id>". The same pattern is "character".lease_install_id's check.
INSTALL_ID_HEADER = "X-Install-Id"
INSTALL_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")
_INT_MAX = 2_147_483_647
_LEASE = timedelta(seconds=LEASE_SECONDS)


class GameError(Exception):
    """An /api/game refusal, answered as {"code", "detail", ...extra}."""

    def __init__(self, status_code: int, code: str, detail: str, *, headers: dict[str, str] | None = None, **extra: Any):
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.headers = headers or {}
        self.extra = extra


def _no_store(response: Response) -> None:
    # Keys and saves are private to their account.
    response.headers["Cache-Control"] = "no-store"


def _install_id(request: Request) -> str | None:
    """The game install making the call, from X-Install-Id; None without the header.

    Checked before anything else on every game call, so a malformed id is
    refused with 422 invalid_request before the key is looked up or counted.
    """
    values = request.headers.getlist(INSTALL_ID_HEADER)
    if not values:
        return None
    if len(values) > 1 or not INSTALL_ID_PATTERN.fullmatch(values[0]):
        raise _invalid(
            f"{INSTALL_ID_HEADER} is one install id of 1 to 64 letters, digits, hyphens or underscores",
            INSTALL_ID_HEADER,
        )
    return values[0]


router = APIRouter(
    prefix="/api/game", tags=["game"], dependencies=[Depends(_no_store), Depends(_install_id)],
)


class SignInBody(BaseModel):
    username: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=256)
    computer: str = Field(min_length=1, max_length=200)


class CharacterCreateBody(BaseModel):
    name: str = Field(max_length=200)
    sex: Literal["female", "male"]
    save: dict[str, Any]
    save_version: int = Field(ge=0, le=_INT_MAX)
    summary: dict[str, Any] | None = None


class CharacterSaveBody(BaseModel):
    save: dict[str, Any]
    save_version: int = Field(ge=0, le=_INT_MAX)
    revision: int = Field(ge=1, le=_INT_MAX)
    summary: dict[str, Any] | None = None


class CharacterDeleteBody(BaseModel):
    name: str = Field(max_length=200)


# --- errors -----------------------------------------------------------------

async def _game_error_response(request: Request, exc: GameError) -> JSONResponse:
    return JSONResponse(
        {"code": exc.code, "detail": exc.detail, **exc.extra},
        status_code=exc.status_code,
        headers={"Cache-Control": "no-store", **exc.headers},
    )


async def _validation_error_response(request: Request, exc: RequestValidationError):
    if not request.url.path.startswith(router.prefix + "/"):
        return await request_validation_exception_handler(request, exc)
    errors = [
        {
            "field": ".".join(str(part) for part in error.get("loc", ()) if part not in ("body", "path")),
            "message": str(error.get("msg", "")),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        {"code": "invalid_request", "detail": "The request is not valid", "errors": errors},
        status_code=422,
        headers={"Cache-Control": "no-store"},
    )


def install_error_handlers(application: FastAPI) -> None:
    application.add_exception_handler(GameError, _game_error_response)
    application.add_exception_handler(RequestValidationError, _validation_error_response)


def _invalid(detail: str, field: str | None = None) -> GameError:
    """422 invalid_request; `errors` names the field when there is one."""
    errors = [{"field": field, "message": detail}] if field else []
    return GameError(422, "invalid_request", detail, errors=errors)


# Check constraints the database enforces after the request's own checks.
_CONSTRAINT_ERRORS = {
    "character_data_data_check": (413, "save_too_large", "The save is larger than 64 KiB", {"limit_bytes": SAVE_MAX_BYTES}),
    "character_summary_check": (413, "summary_too_large", "The summary is larger than 2 KiB", {"limit_bytes": SUMMARY_MAX_BYTES}),
    "character_name_check": (422, "invalid_name", "A name has 1 to 50 characters", {}),
}


def _stored_error(exc: Exception) -> GameError | None:
    code = str(getattr(exc, "pgcode", "") or "")
    if code == "23514":
        constraint = getattr(getattr(exc, "diag", None), "constraint_name", None)
        known = _CONSTRAINT_ERRORS.get(constraint or "")
        if known:
            status, error_code, detail, extra = known
            return GameError(status, error_code, detail, **extra)
    if code.startswith("22"):
        # For example a "\u0000" in a string, which PostgreSQL's jsonb refuses.
        return _invalid("The save or summary cannot be stored as JSON")
    return None


def _game_key(request: Request) -> dict[str, Any]:
    return _key(request, kind="character")


def _reader_key(request: Request, *, demo_access: bool = True) -> dict[str, Any]:
    """A key reading books or notes, counted as 'book'; it needs Web Demo access unless told otherwise."""
    return _key(request, kind="book", access_point=DEMO_ACCESS_POINT if demo_access else None)


def _key(request: Request, *, kind: str, access_point: str | None = None) -> dict[str, Any]:
    try:
        return authenticate_api_key(request, kind=kind, master_allowed=False, access_point=access_point)
    except AccessRefused as exc:
        # 403 <access point>_access_required, checked after a master key and before anything is counted.
        raise GameError(403, exc.code, str(exc.detail)) from None
    except HTTPException as exc:
        headers = dict(exc.headers or {})
        if exc.status_code == 429:
            retry = headers.get("Retry-After")
            raise GameError(429, "rate_limited", str(exc.detail), headers=headers,
                            retry_after=int(retry) if retry else None) from None
        if exc.status_code == 403:
            raise GameError(403, "master_key_not_allowed", "Use a regular key of this account, not a master key",
                            headers=headers) from None
        raise GameError(exc.status_code, "invalid_key", str(exc.detail), headers=headers) from None


def _live_key(cur, key_id: int) -> None:
    """Hold the key against revocation for this transaction, or refuse a revoked one.

    The key row is locked before any character row, the order every path that
    revokes a key follows.
    """
    cur.execute(
        "SELECT api_key_id FROM api_key WHERE api_key_id = %s AND revoked_at IS NULL FOR SHARE",
        (key_id,),
    )
    if cur.fetchone() is None:
        raise GameError(401, "invalid_key", "This API key was revoked")


def _not_found() -> GameError:
    return GameError(404, "not_found", "This account has no such character")


def _open_elsewhere(row: dict[str, Any]) -> GameError:
    return GameError(
        409, "open_elsewhere", "This character is open on another computer",
        seconds_left=max(1, int(row["lease_seconds_left"] or 0)),
    )


# --- values -----------------------------------------------------------------

def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _plain(value: str) -> str:
    """Trim and collapse whitespace, as names are stored and compared."""
    return " ".join(value.split())


def _has_control(value: str) -> bool:
    return any(unicodedata.category(character) == "Cc" for character in value)


def _valid_name(value: str) -> str:
    name = _plain(value)
    if not name or len(name) > NAME_MAX_CHARACTERS or _has_control(name):
        raise GameError(422, "invalid_name", f"A name has 1 to {NAME_MAX_CHARACTERS} characters and no control characters")
    return name


def _computer(value: str) -> str:
    computer = "".join(character for character in _plain(value) if not _has_control(character))
    computer = computer[:COMPUTER_MAX_CHARACTERS].strip()
    if not computer:
        raise _invalid("Send the computer's name", "computer")
    return computer


def _json_text(value: dict[str, Any], *, limit: int, code: str, what: str) -> str:
    """JSON text for PostgreSQL, refused early when already over the database's limit.

    The separators match the text form of jsonb that the size check measures.
    """
    try:
        text = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(", ", ": "))
        size = len(text.encode("utf-8"))
    except ValueError:
        # NaN and Infinity are not JSON, and a lone surrogate ("\ud800") cannot be encoded.
        raise _invalid(f"The {what} is not valid JSON", what) from None
    if size > limit:
        raise GameError(413, code, f"The {what} is {size} bytes; the limit is {limit}", limit_bytes=limit)
    return text


def _key_info(key: dict[str, Any]) -> dict[str, Any]:
    return {
        "api_key_id": key["api_key_id"],
        "name": key["name"],
        "key_prefix": key["key_prefix"],
        "key_type": key["key_type"],
        "client": key.get("client"),
        "tier": key.get("level_name"),
        "requests_per_minute": key.get("requests_per_minute"),
    }


_CHARACTER_COLUMNS = """
    c.character_id, c.name, c.sex, c.summary, c.created_at, c.last_played_at,
    c.lease_api_key_id, c.lease_install_id,
    COALESCE(c.lease_expires_at > now(), false) AS lease_live,
    GREATEST(0, ceil(extract(epoch FROM c.lease_expires_at - now())))::int AS lease_seconds_left
"""


def _character(row: dict[str, Any], key_id: int, install: str | None) -> dict[str, Any]:
    elsewhere = _lease_state(row, key_id, install) == "elsewhere"
    return {
        "character_id": row["character_id"],
        "name": row["name"],
        "sex": row["sex"],
        "summary": row["summary"] if row["summary"] is not None else {},
        "created_at": _iso(row["created_at"]),
        "last_played_at": _iso(row["last_played_at"]),
        "open_elsewhere": elsewhere,
        "open_elsewhere_seconds_left": max(1, int(row["lease_seconds_left"] or 0)) if elsewhere else None,
    }


def _lease_state(row: dict[str, Any], key_id: int, install: str | None) -> str:
    """'mine' when this key holds the lease (even lapsed: nobody took it since)
    and the install that took it is this call's, or either is unknown;
    'elsewhere' when another key, or this key from another install, holds a
    live one; else 'free'. Without an install this is the key-only rule of 0.0.12."""
    holder = row["lease_api_key_id"]
    if holder is None:
        return "free"
    held_by = row.get("lease_install_id")
    if holder == key_id and (install is None or held_by is None or held_by == install):
        return "mine"
    if row["lease_live"]:
        return "elsewhere"
    return "free"


def _lease_install(row: dict[str, Any], key_id: int, install: str | None) -> str | None:
    """The install to keep beside a lease this key takes or renews: the call's,
    or when it names none, the one already there if this key held the lease."""
    if install is not None:
        return install
    return row.get("lease_install_id") if row["lease_api_key_id"] == key_id else None


def _locked_character(cur, character_id: int, user_id: int, *, with_save: bool = False) -> dict[str, Any] | None:
    save_columns = "d.data, d.save_version, d.revision, d.updated_at" if with_save else "d.revision"
    cur.execute(
        f"""
        SELECT {_CHARACTER_COLUMNS}, c.character_data_id, {save_columns}
        FROM "character" c
        JOIN character_data d ON d.character_data_id = c.character_data_id
        WHERE c.character_id = %s AND c.user_id = %s
        FOR UPDATE
        """,
        (character_id, user_id),
    )
    return cur.fetchone()


def _take_lease(cur, row: dict[str, Any], key_id: int, install: str | None) -> dict[str, Any]:
    cur.execute(
        """
        UPDATE "character" SET lease_api_key_id = %s, lease_install_id = %s, lease_expires_at = now() + %s
        WHERE character_id = %s
        RETURNING lease_expires_at
        """,
        (key_id, _lease_install(row, key_id, install), _LEASE, row["character_id"]),
    )
    taken = cur.fetchone()
    return {"lease_seconds": LEASE_SECONDS, "lease_expires_at": _iso(taken["lease_expires_at"])}


def _require_lease(row: dict[str, Any], key_id: int, install: str | None) -> None:
    state = _lease_state(row, key_id, install)
    if state == "elsewhere":
        raise _open_elsewhere(row)
    if state != "mine":
        raise GameError(409, "not_open", "Open the character on this computer first")


# --- account ----------------------------------------------------------------

@router.post("/sign-in")
def sign_in(body: SignInBody, request: Request):
    """Check the password and make this computer's game key."""
    computer = _computer(body.computer)
    key_name = f"UMST · {computer}"
    address = sign_in_attempts.public_address(request)
    issued = None
    with transaction() as (_, cur):
        # The website's login checks passwords the same way, under the same limits.
        attempt = sign_in_attempts.attempt(cur, body.username, body.password, address)
        account = attempt.account
        if attempt.correct and account["email_verified_at"] is not None:
            # One key per computer: the one this computer had before goes.
            revoke_game_keys(cur, int(account["user_id"]), name=key_name)
            issued = create_regular_key(cur, int(account["user_id"]), key_name, client=GAME_CLIENT)
    # The attempt is committed before any refusal below.
    if attempt.wait:
        raise GameError(
            429, "too_many_attempts", "Too many wrong passwords; wait before trying again",
            headers={"Retry-After": str(attempt.wait)}, retry_after=attempt.wait,
        )
    if not attempt.correct:
        raise GameError(401, "wrong_credentials", "Incorrect username or password")
    if issued is None:
        raise GameError(403, "email_unverified", "Confirm your email address before signing in")
    return {"user_id": account["user_id"], "username": account["username"], "key": issued}


@router.get("/me")
def me(request: Request):
    """The account and key behind the key sent."""
    key = _game_key(request)
    return {"user_id": key["user_id"], "username": key["username"], "key": _key_info(key)}


@router.post("/sign-out")
def sign_out(request: Request):
    """Close what this key has open and revoke it when it is a game key."""
    key = _game_key(request)
    with transaction() as (_, cur):
        # Lock the key before the characters, as every revoking path does.
        cur.execute("SELECT api_key_id FROM api_key WHERE api_key_id = %s FOR UPDATE", (key["api_key_id"],))
        cur.execute(
            """
            UPDATE "character" SET lease_api_key_id = NULL, lease_expires_at = NULL, lease_install_id = NULL
            WHERE lease_api_key_id = %s
            RETURNING character_id
            """,
            (key["api_key_id"],),
        )
        released = len(cur.fetchall())
        cur.execute(
            """
            UPDATE api_key SET revoked_at = now()
            WHERE api_key_id = %s AND client = %s AND revoked_at IS NULL
            RETURNING api_key_id
            """,
            (key["api_key_id"], GAME_CLIENT),
        )
        revoked = cur.fetchone() is not None
    return {"revoked": revoked, "released_characters": released}


# --- characters ---------------------------------------------------------------

@router.get("/characters")
def list_characters(request: Request, install: str | None = Depends(_install_id)):
    key = _game_key(request)
    with transaction() as (_, cur):
        cur.execute(
            f"""
            SELECT {_CHARACTER_COLUMNS}
            FROM "character" c
            WHERE c.user_id = %s
            ORDER BY c.created_at, c.character_id
            """,
            (key["user_id"],),
        )
        rows = cur.fetchall()
    return {
        "characters": [_character(row, key["api_key_id"], install) for row in rows],
        "limit": MAX_CHARACTERS,
    }


@router.post("/characters", status_code=201)
def create_character(body: CharacterCreateBody, request: Request):
    key = _game_key(request)
    name = _valid_name(body.name)
    save_text = _json_text(body.save, limit=SAVE_MAX_BYTES, code="save_too_large", what="save")
    summary_text = _json_text(body.summary or {}, limit=SUMMARY_MAX_BYTES, code="summary_too_large", what="summary")
    try:
        with transaction() as (_, cur):
            _live_key(cur, key["api_key_id"])
            # One creation per account at a time, so two cannot both pass the limit.
            cur.execute("SELECT pg_advisory_xact_lock(hashtext('theumst.characters'), %s)", (key["user_id"],))
            cur.execute('SELECT count(*) AS characters FROM "character" WHERE user_id = %s', (key["user_id"],))
            if int(cur.fetchone()["characters"]) >= MAX_CHARACTERS:
                raise GameError(409, "full", f"An account has at most {MAX_CHARACTERS} characters", limit=MAX_CHARACTERS)
            cur.execute(
                """
                INSERT INTO character_data (data, save_version)
                VALUES (%s::jsonb, %s)
                RETURNING character_data_id, revision
                """,
                (save_text, body.save_version),
            )
            data = cur.fetchone()
            cur.execute(
                """
                INSERT INTO "character" (user_id, character_data_id, name, sex, summary)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                RETURNING character_id, name, sex, summary, created_at, last_played_at,
                          lease_api_key_id, lease_install_id, false AS lease_live, 0 AS lease_seconds_left
                """,
                (key["user_id"], data["character_data_id"], name, body.sex, summary_text),
            )
            row = cur.fetchone()
    except psycopg2.Error as exc:
        stored = _stored_error(exc)
        if stored:
            raise stored from None
        raise
    # A new character has no lease, whichever install made it.
    return {"character": _character(row, key["api_key_id"], None), "revision": data["revision"]}


@router.post("/characters/{character_id}/open")
def open_character(character_id: int, request: Request, install: str | None = Depends(_install_id)):
    """Take the lease and return the save; the same key may reopen its own,
    unless another install of it holds a live lease."""
    key = _game_key(request)
    with transaction() as (_, cur):
        _live_key(cur, key["api_key_id"])
        row = _locked_character(cur, character_id, key["user_id"], with_save=True)
        if row is None:
            raise _not_found()
        if _lease_state(row, key["api_key_id"], install) == "elsewhere":
            raise _open_elsewhere(row)
        lease = _take_lease(cur, row, key["api_key_id"], install)
    return {
        "character": _character(row, key["api_key_id"], install),
        "save": row["data"],
        "save_version": row["save_version"],
        "revision": row["revision"],
        "updated_at": _iso(row["updated_at"]),
        **lease,
    }


@router.post("/characters/{character_id}/heartbeat")
def heartbeat(character_id: int, request: Request, install: str | None = Depends(_install_id)):
    """Renew this key's lease."""
    key = _game_key(request)
    with transaction() as (_, cur):
        _live_key(cur, key["api_key_id"])
        row = _locked_character(cur, character_id, key["user_id"])
        if row is None:
            raise _not_found()
        _require_lease(row, key["api_key_id"], install)
        lease = _take_lease(cur, row, key["api_key_id"], install)
    return lease


@router.post("/characters/{character_id}/close")
def close_character(character_id: int, request: Request, install: str | None = Depends(_install_id)):
    """Release this key's lease; anything else, another install's lease of this key included, is left as it is."""
    key = _game_key(request)
    with transaction() as (_, cur):
        _live_key(cur, key["api_key_id"])
        row = _locked_character(cur, character_id, key["user_id"])
        if row is None:
            raise _not_found()
        released = _lease_state(row, key["api_key_id"], install) == "mine"
        if released:
            cur.execute(
                """
                UPDATE "character" SET lease_api_key_id = NULL, lease_expires_at = NULL, lease_install_id = NULL
                WHERE character_id = %s
                """,
                (character_id,),
            )
    return {"released": released}


@router.put("/characters/{character_id}/data")
def save_character(
    character_id: int, body: CharacterSaveBody, request: Request, install: str | None = Depends(_install_id),
):
    """Store a save made from the current revision; renews the lease."""
    key = _game_key(request)
    save_text = _json_text(body.save, limit=SAVE_MAX_BYTES, code="save_too_large", what="save")
    summary_text = (
        None if body.summary is None
        else _json_text(body.summary, limit=SUMMARY_MAX_BYTES, code="summary_too_large", what="summary")
    )
    try:
        with transaction() as (_, cur):
            _live_key(cur, key["api_key_id"])
            row = _locked_character(cur, character_id, key["user_id"])
            if row is None:
                raise _not_found()
            _require_lease(row, key["api_key_id"], install)
            if body.revision != row["revision"]:
                raise GameError(
                    409, "stale", "This save was made from an older revision; open the character again",
                    revision=row["revision"],
                )
            cur.execute(
                """
                UPDATE character_data
                SET data = %s::jsonb, save_version = %s, revision = revision + 1, updated_at = now()
                WHERE character_data_id = %s
                RETURNING revision, updated_at
                """,
                (save_text, body.save_version, row["character_data_id"]),
            )
            saved = cur.fetchone()
            cur.execute(
                """
                UPDATE "character"
                SET last_played_at = now(), lease_expires_at = now() + %s, lease_install_id = %s,
                    summary = COALESCE(%s::jsonb, summary)
                WHERE character_id = %s
                RETURNING last_played_at, lease_expires_at
                """,
                (_LEASE, _lease_install(row, key["api_key_id"], install), summary_text, character_id),
            )
            played = cur.fetchone()
    except psycopg2.Error as exc:
        stored = _stored_error(exc)
        if stored:
            raise stored from None
        raise
    return {
        "revision": saved["revision"],
        "updated_at": _iso(saved["updated_at"]),
        "last_played_at": _iso(played["last_played_at"]),
        "lease_seconds": LEASE_SECONDS,
        "lease_expires_at": _iso(played["lease_expires_at"]),
    }


@router.delete("/characters/{character_id}")
def delete_character(
    character_id: int, body: CharacterDeleteBody, request: Request, install: str | None = Depends(_install_id),
):
    """Delete a character and its save once its name is typed."""
    key = _game_key(request)
    typed = _plain(body.name)
    with transaction() as (_, cur):
        _live_key(cur, key["api_key_id"])
        row = _locked_character(cur, character_id, key["user_id"])
        if row is None:
            raise _not_found()
        if typed != row["name"]:
            raise GameError(409, "name_mismatch", "Type the character's name exactly to delete it")
        if _lease_state(row, key["api_key_id"], install) == "elsewhere":
            raise _open_elsewhere(row)
        cur.execute('DELETE FROM "character" WHERE character_id = %s', (character_id,))
        cur.execute("DELETE FROM character_data WHERE character_data_id = %s", (row["character_data_id"],))
    return {"deleted": True, "character_id": character_id}


# --- books (0.0.16) -----------------------------------------------------------------
#
# The game downloads a whole book once per version and lays it out itself, so a page turn never
# reaches theumst.com. The answer is book_read's game row (services/book_read.py), built at
# upload; no request builds it.

BOOK_VARY = "X-API-Key, Authorization, Accept-Encoding"
# A grimoire's title ends with its credit, as "(Randal-Williams, 2026)"; the author is the credit
# less its year, as shared/topics/build_topics.py reads it in UMST.
_CREDIT = re.compile(r"\(([^()]*)\)\s*$")
_CREDIT_YEAR = re.compile(r",\s*(\d{4})$")


def _author(stored: Any, title: str | None) -> str | None:
    """source_metadata's author when a non-empty string, else the title's credit less its year, else None."""
    if isinstance(stored, str) and stored.strip():
        return stored.strip()
    match = _CREDIT.search(title or "")
    credit = match.group(1) if match else ""
    year = _CREDIT_YEAR.search(credit)
    return (credit[:year.start()] if year else credit) or None


def _book_not_found() -> GameError:
    return GameError(404, "book_not_found", "theumst.com has no such grimoire")


def _book_not_computed() -> GameError:
    return GameError(409, "book_read_not_computed", "This book's whole read has not been computed yet")


@router.get("/grimoires")
def list_grimoires(request: Request):
    """The grimoires the Web Demo shows, with the version, size and object count of each one's game
    answer, and whether this account may read them. Needs no Web Demo access."""
    key = _reader_key(request, demo_access=False)
    may_read = DEMO_ACCESS_POINT in set(key.get("access_points") or ())
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT g.grimoire_id, lg.title, g.source_metadata->'author' AS author,
                   r.version, r.object_count, octet_length(r.body_gzip) AS bytes
            FROM grimoire g
            JOIN language_grimoire lg ON lg.grimoire_id = g.grimoire_id AND lg.language_id = 1
            LEFT JOIN book_game_read r ON r.grimoire_id = g.grimoire_id AND r.format = %s
            WHERE g.source_metadata->>'demo' = 'true'
            ORDER BY g.grimoire_id
            """,
            (book_read.FORMAT,),
        )
        rows = cur.fetchall()
    return {
        "may_read": may_read,
        "grimoires": [
            {
                "grimoire_id": row["grimoire_id"],
                "title": row["title"],
                "author": _author(row["author"], row["title"]),
                "version": row["version"],
                "objects": row["object_count"],
                "bytes": row["bytes"],
                "may_read": may_read,
            }
            for row in rows
        ],
    }


@router.get("/grimoires/{grimoire_id}/book")
def get_book(grimoire_id: int, request: Request):
    """A whole book for the game, revalidated by its ETag: 304 when the version sent is current.

    The stored gzip goes as it is to a client that accepts gzip, as the Web Demo's book-read
    does. A 200 or 304 is a Response of its own, so it carries the two weeks of private caching
    and never the router's no-store; every refusal is a GameError with no-store.
    """
    _reader_key(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT (COALESCE(g.source_metadata->>'demo', 'false') = 'true') AS visible, r.format, r.version
            FROM grimoire g
            LEFT JOIN book_game_read r USING (grimoire_id)
            WHERE g.grimoire_id = %s
            """,
            (grimoire_id,),
        )
        book = cur.fetchone()
        if not book or not book["visible"]:
            raise _book_not_found()
        if book["format"] != book_read.FORMAT:
            raise _book_not_computed()
        if book_read.etag_matches(request.headers.get("if-none-match"), f'"{book["version"]}"'):
            return Response(status_code=304, headers=book_read.cache_headers(book["version"], BOOK_VARY))
        cur.execute(
            "SELECT version, body_gzip FROM book_game_read WHERE grimoire_id = %s AND format = %s",
            (grimoire_id, book_read.FORMAT),
        )
        stored = cur.fetchone()
    if not stored:  # deleted by a failed rebuild since the first read
        raise _book_not_computed()
    content, headers = book_read.served(
        stored["version"], bytes(stored["body_gzip"]), request.headers.get("accept-encoding"), BOOK_VARY,
    )
    return Response(content=content, media_type="application/json", headers=headers)


# --- notes (0.0.16) -------------------------------------------------------------------
#
# The Web Demo's own notes (demo_note), so a note made in the game shows in the Web Demo's
# notebook and one made there shows in the game. Only the key's account's notes are ever read
# or changed. An update or delete names the updated_at it was read at and is refused with the
# current note when the note changed since, so the game never overwrites an edit made on the
# website. The Web Demo's own PUT has no such check.

_NOTE_COLUMNS = "demo_note_id, grimoire_id, knowledge_id, note_type, tag, content, created_at, updated_at"


def _iso_micro(value: datetime) -> str:
    """UTC to the microsecond: updated_at is a note's edit token, and whole seconds could repeat."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _note(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "demo_note_id": row["demo_note_id"],
        "grimoire_id": row["grimoire_id"],
        "knowledge_id": row["knowledge_id"],
        "note_type": row["note_type"],
        "tag": row["tag"],
        "content": row["content"],
        "created_at": _iso_micro(row["created_at"]),
        "updated_at": _iso_micro(row["updated_at"]),
    }


def _visible_book(cur, grimoire_id: int) -> None:
    cur.execute(
        "SELECT 1 FROM grimoire WHERE grimoire_id = %s AND source_metadata->>'demo' = 'true'",
        (grimoire_id,),
    )
    if cur.fetchone() is None:
        raise _book_not_found()


def _locked_note(cur, grimoire_id: int, note_id: int, user_id: int) -> dict[str, Any]:
    """This account's note in this book, locked for the change; another account's is not found."""
    cur.execute(
        f"""
        SELECT {_NOTE_COLUMNS} FROM demo_note
        WHERE demo_note_id = %s AND user_id = %s AND grimoire_id = %s
        FOR UPDATE
        """,
        (note_id, user_id, grimoire_id),
    )
    row = cur.fetchone()
    if row is None:
        raise GameError(404, "note_not_found", "This account has no such note in this book")
    return row


def _unchanged(row: dict[str, Any], if_updated_at: datetime) -> None:
    if row["updated_at"] != if_updated_at:
        raise GameError(409, "note_changed", "The note was changed since it was read", note=_note(row))


@router.get("/grimoires/{grimoire_id}/notes")
def list_book_notes(grimoire_id: int, request: Request):
    """The account's notes in one book, attached and scribbles, most recently changed first."""
    key = _reader_key(request)
    with transaction() as (_, cur):
        _visible_book(cur, grimoire_id)
        cur.execute(
            f"""
            SELECT {_NOTE_COLUMNS} FROM demo_note
            WHERE user_id = %s AND grimoire_id = %s
            ORDER BY updated_at DESC, demo_note_id DESC
            """,
            (key["user_id"], grimoire_id),
        )
        rows = cur.fetchall()
    return {"notes": [_note(row) for row in rows]}


@router.post("/grimoires/{grimoire_id}/notes", status_code=201)
def create_book_note(grimoire_id: int, body: GameNoteCreate, request: Request):
    """A note in this book: attached to one of its active objects, or a scribble. Unlike the Web
    Demo's, it does not need the book in My grimoires, and it adds nothing there."""
    key = _reader_key(request)
    with transaction() as (_, cur):
        _visible_book(cur, grimoire_id)
        if body.knowledge_id is not None:
            cur.execute(
                """
                SELECT 1 FROM knowledge k JOIN section s ON s.section_id = k.section_id
                WHERE k.knowledge_id = %s AND s.grimoire_id = %s AND k.is_active
                """,
                (body.knowledge_id, grimoire_id),
            )
            if cur.fetchone() is None:
                raise GameError(404, "object_not_found", "This book has no such knowledge object")
        cur.execute(
            f"""
            INSERT INTO demo_note (user_id, grimoire_id, knowledge_id, note_type, tag, content)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING {_NOTE_COLUMNS}
            """,
            (key["user_id"], grimoire_id, body.knowledge_id, body.note_type, body.tag.strip(), body.content),
        )
        row = cur.fetchone()
    return {"note": _note(row)}


@router.put("/grimoires/{grimoire_id}/notes/{note_id}")
def update_book_note(grimoire_id: int, note_id: int, body: GameNoteUpdate, request: Request):
    """New tag and content for a note; its book, object and type stay."""
    key = _reader_key(request)
    with transaction() as (_, cur):
        _visible_book(cur, grimoire_id)
        row = _locked_note(cur, grimoire_id, note_id, key["user_id"])
        _unchanged(row, body.if_updated_at)
        cur.execute(
            f"""
            UPDATE demo_note SET tag = %s, content = %s
            WHERE demo_note_id = %s AND user_id = %s
            RETURNING {_NOTE_COLUMNS}
            """,
            (body.tag.strip(), body.content, note_id, key["user_id"]),
        )
        row = cur.fetchone()
    return {"note": _note(row)}


@router.delete("/grimoires/{grimoire_id}/notes/{note_id}")
def delete_book_note(grimoire_id: int, note_id: int, body: GameNoteDelete, request: Request):
    key = _reader_key(request)
    with transaction() as (_, cur):
        _visible_book(cur, grimoire_id)
        row = _locked_note(cur, grimoire_id, note_id, key["user_id"])
        _unchanged(row, body.if_updated_at)
        cur.execute("DELETE FROM demo_note WHERE demo_note_id = %s AND user_id = %s", (note_id, key["user_id"]))
    return {"deleted": True, "demo_note_id": note_id}
