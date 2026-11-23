"""UMST's agents' graph reads (0.0.19), for the game's key.

The agents' tools (the door, on the reader's PC) ask theumst.com about any book here: an object with
its load, a crystal's members across books, what an object uses and what uses it, closures over
crystals, a section in book order and the objects around one, the source's pages, and objects matched
by their source key. Nothing about books is kept on the PC, and nothing sent here is stored.

Every route takes the game's key, as every /api/game call does, and needs Web Demo access. Each call
counts once as the `graph` kind of the key's per-minute allowance, the tier's number, as `book` and
`character` do. Only active objects of the books the Web Demo shows are read, inside each query
(services/game_graph.py). Errors are /api/game's {"code", "detail"}. docs/game-agents.md gives the
shapes.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from ..database import transaction
from ..dependencies import DEMO_ACCESS_POINT
from ..services import game_graph
from ..services.game_graph import SqlGraph
from .game import GameError, _install_id, _invalid, _key, _no_store

GRAPH_KIND = "graph"
SOURCE_KEY_MAX_CHARACTERS = 200

router = APIRouter(
    prefix="/api/game/graph", tags=["game"], dependencies=[Depends(_no_store), Depends(_install_id)],
)

KnowledgeId = Annotated[int | None, Query(ge=1, le=2_147_483_647)]
SourceKey = Annotated[str | None, Query(min_length=1, max_length=SOURCE_KEY_MAX_CHARACTERS)]
BookId = Annotated[int | None, Query(ge=1, le=2_147_483_647)]
# 0.0.20: an answer's size as the door hands it on, and which page of a long answer.
MaxChars = Annotated[int | None, Query(ge=game_graph.CHARS_LEAST, le=game_graph.CHARS_MOST)]
Page = Annotated[int | None, Query(ge=1, le=game_graph.PAGE_MOST)]


class MatchItem(BaseModel):
    source_key: str = Field(min_length=1, max_length=SOURCE_KEY_MAX_CHARACTERS)
    grimoire_id: int | None = Field(default=None, ge=1, le=2_147_483_647)


class MatchBody(BaseModel):
    objects: list[MatchItem] = Field(min_length=1, max_length=game_graph.MATCH_MOST)


def _reader(request: Request) -> dict[str, Any]:
    """The key, counted once as a `graph` request; it needs Web Demo access."""
    return _key(request, kind=GRAPH_KIND, access_point=DEMO_ACCESS_POINT)


def _named(knowledge_id: int | None, source_key: str | None) -> None:
    if (knowledge_id is None) == (source_key is None):
        raise _invalid("Send exactly one of knowledge_id and source_key", "knowledge_id")


def _object(source: SqlGraph, knowledge_id: int | None, source_key: str | None,
            grimoire_id: int | None) -> dict[str, Any]:
    try:
        return game_graph.resolve(source, knowledge_id=knowledge_id, source_key=source_key, grimoire_id=grimoire_id)
    except game_graph.NotFound as exc:
        raise GameError(404, "not_found", str(exc)) from None
    except game_graph.Ambiguous as exc:
        raise GameError(409, "ambiguous", str(exc)) from None


def _answer(read, *args, **kwargs) -> dict[str, Any]:
    try:
        return read(*args, **kwargs)
    except game_graph.NotFound as exc:
        raise GameError(404, "not_found", str(exc)) from None
    except game_graph.TooSmall as exc:
        raise _invalid(str(exc), "max_chars") from None


@router.get("/object")
def get_object(request: Request, knowledge_id: KnowledgeId = None, source_key: SourceKey = None,
               grimoire_id: BookId = None):
    """One object in full with its support component in full and what the component uses (history A4)."""
    _named(knowledge_id, source_key)
    _reader(request)
    with transaction() as (_, cur):
        source = SqlGraph(cur)
        obj = _object(source, knowledge_id, source_key, grimoire_id)
        return _answer(game_graph.load, source, obj)


@router.get("/crystal")
def get_crystal(request: Request, crystal_id: KnowledgeId = None, knowledge_id: KnowledgeId = None,
                source_key: SourceKey = None, grimoire_id: BookId = None, reader_grimoire_id: BookId = None,
                max_chars: MaxChars = None, page: Page = None):
    """A crystal's members in every visible book, by the crystal's id or one of its members."""
    if crystal_id is not None and (knowledge_id is not None or source_key is not None):
        raise _invalid("Send crystal_id, or one of knowledge_id and source_key", "crystal_id")
    if crystal_id is None:
        _named(knowledge_id, source_key)
    _reader(request)
    with transaction() as (_, cur):
        source = SqlGraph(cur)
        if crystal_id is None:
            crystal_id = int(_object(source, knowledge_id, source_key, grimoire_id)["crystal_id"])
        return _answer(game_graph.crystal, source, crystal_id, reader_grimoire_id=reader_grimoire_id,
                       max_chars=max_chars, page=page)


def _arrows(request: Request, direction: str, knowledge_id, source_key, grimoire_id, max_chars, page):
    _named(knowledge_id, source_key)
    _reader(request)
    with transaction() as (_, cur):
        source = SqlGraph(cur)
        obj = _object(source, knowledge_id, source_key, grimoire_id)
        return _answer(game_graph.arrows, source, obj, direction, max_chars=max_chars, page=page)


@router.get("/uses")
def get_uses(request: Request, knowledge_id: KnowledgeId = None, source_key: SourceKey = None,
             grimoire_id: BookId = None, max_chars: MaxChars = None, page: Page = None):
    """What the object uses directly, in book order."""
    return _arrows(request, "uses", knowledge_id, source_key, grimoire_id, max_chars, page)


@router.get("/used-by")
def get_used_by(request: Request, knowledge_id: KnowledgeId = None, source_key: SourceKey = None,
                grimoire_id: BookId = None, max_chars: MaxChars = None, page: Page = None):
    """What uses the object directly, in book order."""
    return _arrows(request, "used_by", knowledge_id, source_key, grimoire_id, max_chars, page)


@router.get("/closure")
def get_closure(
    request: Request,
    knowledge_id: KnowledgeId = None,
    source_key: SourceKey = None,
    grimoire_id: BookId = None,
    direction: Literal["down", "up"] = "down",
    reader_grimoire_id: BookId = None,
    words: Annotated[int, Query(ge=game_graph.WORDS_LEAST, le=game_graph.WORDS_MOST)] = game_graph.WORDS_DEFAULT,
    max_chars: MaxChars = None,
    page: Page = None,
):
    """The closure over crystals, down or up, across books, nearest first inside a budget of words."""
    _named(knowledge_id, source_key)
    _reader(request)
    with transaction() as (_, cur):
        source = SqlGraph(cur)
        obj = _object(source, knowledge_id, source_key, grimoire_id)
        return _answer(game_graph.closure, source, obj, direction=direction,
                       reader_grimoire_id=reader_grimoire_id, budget=words, max_chars=max_chars, page=page)


@router.get("/section")
def get_section(request: Request, section_id: KnowledgeId = None, knowledge_id: KnowledgeId = None,
                source_key: SourceKey = None, grimoire_id: BookId = None):
    """A section's own objects in book order, by the section's id or one of its objects."""
    if section_id is not None and (knowledge_id is not None or source_key is not None):
        raise _invalid("Send section_id, or one of knowledge_id and source_key", "section_id")
    if section_id is None:
        _named(knowledge_id, source_key)
    _reader(request)
    with transaction() as (_, cur):
        source = SqlGraph(cur)
        if section_id is None:
            section_id = int(_object(source, knowledge_id, source_key, grimoire_id)["section_id"])
        return _answer(game_graph.section, source, section_id)


@router.get("/around")
def get_around(
    request: Request,
    knowledge_id: KnowledgeId = None,
    source_key: SourceKey = None,
    grimoire_id: BookId = None,
    before: Annotated[int, Query(ge=0, le=game_graph.AROUND_MOST)] = 5,
    after: Annotated[int, Query(ge=0, le=game_graph.AROUND_MOST)] = 5,
):
    """The objects just before and after one in its book's reader order."""
    _named(knowledge_id, source_key)
    _reader(request)
    with transaction() as (_, cur):
        source = SqlGraph(cur)
        obj = _object(source, knowledge_id, source_key, grimoire_id)
        return _answer(game_graph.around, source, obj, before, after)


@router.get("/pages")
def get_pages(request: Request, knowledge_id: KnowledgeId = None, source_key: SourceKey = None,
              grimoire_id: BookId = None):
    """The scans of the pages the object appeared on."""
    _named(knowledge_id, source_key)
    _reader(request)
    with transaction() as (_, cur):
        source = SqlGraph(cur)
        obj = _object(source, knowledge_id, source_key, grimoire_id)
        return _answer(game_graph.pages, source, obj)


@router.post("/match")
def post_match(body: MatchBody, request: Request):
    """Objects named by source key, with an optional book each, matched to their ids in one request."""
    _reader(request)
    with transaction() as (_, cur):
        return game_graph.match(SqlGraph(cur), [item.model_dump() for item in body.objects])
