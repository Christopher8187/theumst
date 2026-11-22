"""The game's search over every book (0.0.19): /api/game/search.

Four routes for the game's key, for the UMST agents' book tools: search by meaning and by words merged with
the crystal hiding, an object's neighbours, the latcher's candidates, and which crystal a statement may
belong to. docs/game-agents.md gives the shapes. The work is in services/game_search.py.

A key reads here as it reads books: any active regular key of an account with Web Demo access, master keys
refused, each call counted once in the key's per-minute allowance of kind 'search', no tighter limit. Only
objects of books the Web Demo shows are answered. Nothing sent here is stored or logged. Refusals have the
game's shape, {"code", "detail"}, through game.GameError and its handlers.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from ..dependencies import DEMO_ACCESS_POINT
from ..services import game_search
from .game import GameError, _install_id, _invalid, _key, _no_store

SEARCH_KIND = "search"

NAME_MAX = 300
STATEMENT_MAX = 4000
KEYWORDS_MAX = 20
KEYWORD_MAX = 60
COUNT_MAX = 50
BOOKS_MAX = 100
TEXT_MAX = 20000
LATCHER_COUNT_MAX = 100
CRYSTALS_MAX = 20
SOURCE_KEY_MAX = 512
_INT_MAX = 2_147_483_647


router = APIRouter(
    prefix="/api/game/search", tags=["game"], dependencies=[Depends(_no_store), Depends(_install_id)],
)

Keyword = Annotated[str, Field(min_length=1, max_length=KEYWORD_MAX)]
BookId = Annotated[int, Field(ge=1, le=_INT_MAX)]


class SearchBody(BaseModel):
    name: str = Field(default="", max_length=NAME_MAX)
    statement: str = Field(min_length=1, max_length=STATEMENT_MAX)
    keywords: list[Keyword] = Field(default_factory=list, max_length=KEYWORDS_MAX)
    count: int = Field(default=10, ge=1, le=COUNT_MAX)
    books: list[BookId] | None = Field(default=None, min_length=1, max_length=BOOKS_MAX)


class LatcherBody(BaseModel):
    text: str = Field(min_length=1, max_length=TEXT_MAX)
    grimoire_id: int | None = Field(default=None, ge=1, le=_INT_MAX)
    count: int = Field(default=30, ge=1, le=LATCHER_COUNT_MAX)


class CrystalsBody(BaseModel):
    name: str = Field(default="", max_length=NAME_MAX)
    statement: str = Field(min_length=1, max_length=STATEMENT_MAX)
    keywords: list[Keyword] = Field(default_factory=list, max_length=KEYWORDS_MAX)
    count: int = Field(default=5, ge=1, le=CRYSTALS_MAX)


def _search_key(request: Request) -> dict[str, Any]:
    """The calling key, counted once as kind 'search'; it needs Web Demo access and may not be a master key.
    game._key maps the key's refusals to the game's codes, as for the graph reads."""
    return _key(request, kind=SEARCH_KIND, access_point=DEMO_ACCESS_POINT)


def _unavailable(exc: Exception) -> GameError:
    return GameError(503, "search_unavailable", str(exc) or "Search is unavailable this time")


def _blank(value: str) -> bool:
    return not value or not value.strip()


@router.post("/objects")
def search_objects(body: SearchBody, request: Request):
    """Objects of every visible book for a name, a statement and keywords, by meaning and by words."""
    _search_key(request)
    if _blank(body.statement):
        raise _invalid("A statement has words", "statement")
    try:
        return game_search.search_objects(name=body.name, statement=body.statement, keywords=body.keywords,
                                          count=body.count, books=body.books)
    except game_search.SearchUnavailable as exc:
        raise _unavailable(exc) from None


@router.get("/neighbours")
def neighbours(
    request: Request,
    knowledge_id: int | None = Query(default=None, ge=1, le=_INT_MAX),
    source_key: str | None = Query(default=None, min_length=1, max_length=SOURCE_KEY_MAX),
    count: int = Query(default=10, ge=1, le=COUNT_MAX),
):
    """The objects of any visible book nearest one object's stored statement vector."""
    _search_key(request)
    if (knowledge_id is None) == (source_key is None):
        raise _invalid("Give exactly one of knowledge_id and source_key", "knowledge_id")
    try:
        return game_search.neighbours(knowledge_id=knowledge_id, source_key=source_key, count=count)
    except game_search.ObjectNotFound:
        raise GameError(404, "not_found", "theumst.com shows no such object") from None
    except game_search.NoVector:
        raise GameError(409, "no_vector", "This object has no stored vector") from None
    except game_search.SearchUnavailable as exc:
        raise _unavailable(exc) from None


@router.post("/latcher-candidates")
def latcher_candidates(body: LatcherBody, request: Request):
    """The objects a note or a found problem may use. Nothing of the text is stored."""
    _search_key(request)
    if _blank(body.text):
        raise _invalid("A text has words", "text")
    try:
        return game_search.latcher_candidates(text=body.text, grimoire_id=body.grimoire_id, count=body.count)
    except game_search.SearchUnavailable as exc:
        raise _unavailable(exc) from None


@router.post("/crystals")
def which_crystals(body: CrystalsBody, request: Request):
    """The crystals a statement may belong to. Nothing of it is stored."""
    _search_key(request)
    if _blank(body.statement):
        raise _invalid("A statement has words", "statement")
    try:
        return game_search.which_crystals(name=body.name, statement=body.statement, keywords=body.keywords,
                                          count=body.count)
    except game_search.SearchUnavailable as exc:
        raise _unavailable(exc) from None
