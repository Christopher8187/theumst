"""The game's search over every book the reader may see (0.0.19).

Four questions the game's agents ask theumst.com, answered here and never on the reader's PC:

- search_objects: a name, a statement and keywords; objects ranked by meaning and by words, merged by rank,
  with a crystal's members folded by the logarithmic hiding;
- neighbours: the objects nearest one object's stored statement vector, across books;
- latcher_candidates: the objects a note or a found problem may use, from the labels and names it mentions
  and from the search;
- which_crystals: the crystals a statement may belong to (how an object kept on the PC is matched).

Search by meaning turns the words into a vector with theumst.com's embedding settings (EMBEDDING_API_URL,
EMBEDDING_API_KEY, EMBEDDING_MODEL: OpenRouter's `qwen/qwen3-embedding-4b`) and searches the store of the
model the books' vectors were made with, read from `embedding_model`, not the configured default store. The
query's text is built as the pipeline built each stored text: `name. statement`, after the instruction the
pipeline put before every text it embedded. The vector is used here and never returned. Search by words is
BM25 in the word store (word_index). The two rankings merge by reciprocal rank in this module.

What a reader may see is filtered inside each query: Qdrant's filter names the books that are hidden (or,
when fewer, the books that are shown), and PostgreSQL reads only the hits' own rows, again only from books
the Web Demo shows. No request reads every row of every book. Nothing a request sends is stored or logged.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import httpx
from fastapi import HTTPException

from ..config import get_settings
from ..database import transaction
from . import word_index
from .qdrant import qdrant_service

LANGUAGE_ID = 1
RRF_K = 60
# The instruction the pipeline's embed node put before every text it embedded (Kaic3
# node/embed/input/embedding.json, "maths"); sentence-transformers joins it to the text with nothing between.
QUERY_INSTRUCTION = "Instruct: Given a mathematical statement, retrieve statements of the same result\nQuery:"
EMBED_TIMEOUT_SECONDS = 30
# A filter names at most this many books; beyond it the hits are filtered by PostgreSQL alone.
SCOPE_LIST_LIMIT = 1000
OVERSAMPLE = 5
MAX_CANDIDATES = 250
LATCHER_PIECES = 8
LATCHER_PIECE_CHARACTERS = 600
NAME_MATCH_LIMIT = 256

MEANING = "meaning"
WORDS = "words"
LABEL = "label"
NAME = "name"
_FOUND_ORDER = (LABEL, NAME, MEANING, WORDS)

USED = "used"
OFF = "off"
FAILED = "failed"

# The embedding call, replaced by tests.
_post = httpx.post


class ObjectNotFound(Exception):
    """The object does not exist, is inactive, or is in a book the reader may not see."""


class NoVector(Exception):
    """The object has no stored statement vector."""


class SearchUnavailable(Exception):
    """Neither ranking could answer."""


# --- the text a query is embedded from -----------------------------------------------------------------

def query_text(name: str | None, statement: str | None) -> str:
    """The pipeline's own stored text for a name and a statement (Kaic3 utils/statements.embedding_text)."""
    name = " ".join(str(name or "").split()).rstrip(".")
    statement = " ".join(str(statement or "").split())
    return f"{name}. {statement}" if name else statement


def _same_model(configured: str | None, stored: str | None) -> bool:
    """Whether the configured provider model is the books' model: OpenRouter's `qwen/qwen3-embedding-4b`
    names Modal's `Qwen/Qwen3-Embedding-4B`."""
    def tail(value: str | None) -> str:
        return str(value or "").strip().lower().rsplit("/", 1)[-1]
    return bool(tail(configured)) and tail(configured) == tail(stored)


@dataclass
class Meaning:
    state: str
    reason: str | None
    vectors: list[list[float]]


def meaning_ready(model: dict[str, Any] | None) -> Meaning:
    """Whether search by meaning can run, from the books' model and the settings, without calling out."""
    if model is None:
        return Meaning(OFF, "no_vectors", [])
    settings = get_settings()
    if not settings.embedding_api_url or not settings.embedding_model:
        return Meaning(OFF, "not_configured", [])
    if not _same_model(settings.embedding_model, model.get("model_name")):
        return Meaning(OFF, "other_model", [])
    return Meaning(USED, None, [])


def embed(texts: Sequence[str], model: dict[str, Any] | None) -> Meaning:
    """Vectors for the texts from the configured provider, each after QUERY_INSTRUCTION, or why not."""
    ready = meaning_ready(model)
    if ready.state != USED or not texts:
        return ready
    settings = get_settings()
    headers = {"Content-Type": "application/json"}
    if settings.embedding_api_key:
        headers["Authorization"] = f"Bearer {settings.embedding_api_key}"
    try:
        response = _post(
            settings.embedding_api_url,
            headers=headers,
            json={"model": settings.embedding_model, "input": [QUERY_INSTRUCTION + text for text in texts]},
            timeout=EMBED_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = sorted(response.json()["data"], key=lambda item: int(item.get("index", 0)))
        vectors = [[float(value) for value in item["embedding"]] for item in data]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        # The provider's answer is not echoed: it could hold the request's text.
        return Meaning(FAILED, "provider_failed", [])
    size = int(model["vector_size"])
    if len(vectors) != len(texts) or any(len(vector) != size for vector in vectors):
        return Meaning(FAILED, "wrong_size", [])
    if any(not all(math.isfinite(value) for value in vector) for vector in vectors):
        return Meaning(FAILED, "provider_failed", [])
    return Meaning(USED, None, vectors)


# --- what the reader may see ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Scope:
    """Which books a query may return. `only` lists the books allowed (None: every book not in `never`);
    `never` lists books refused. `exact` is False when the lists would be too long to send, and the hits
    are then filtered by PostgreSQL alone."""
    only: tuple[int, ...] | None = None
    never: tuple[int, ...] = ()
    exact: bool = True

    @property
    def empty(self) -> bool:
        return self.only is not None and not self.only


def book_scope(cur, books: Sequence[int] | None = None) -> Scope:
    """The books the Web Demo shows, as the shorter of the hidden and the shown lists; with `books`, only
    those of them that are shown."""
    if books:
        cur.execute(
            "SELECT grimoire_id FROM grimoire WHERE grimoire_id = ANY(%s) AND source_metadata->>'demo' = 'true' "
            "ORDER BY grimoire_id",
            (sorted({int(book) for book in books}),),
        )
        return Scope(only=tuple(int(row["grimoire_id"]) for row in cur.fetchall()))
    cur.execute(
        "SELECT grimoire_id FROM grimoire WHERE (source_metadata->>'demo') IS DISTINCT FROM 'true' "
        "ORDER BY grimoire_id LIMIT %s",
        (SCOPE_LIST_LIMIT + 1,),
    )
    hidden = tuple(int(row["grimoire_id"]) for row in cur.fetchall())
    if len(hidden) <= SCOPE_LIST_LIMIT:
        return Scope(never=hidden)
    cur.execute(
        "SELECT grimoire_id FROM grimoire WHERE source_metadata->>'demo' = 'true' ORDER BY grimoire_id LIMIT %s",
        (SCOPE_LIST_LIMIT + 1,),
    )
    shown = tuple(int(row["grimoire_id"]) for row in cur.fetchall())
    if len(shown) <= SCOPE_LIST_LIMIT:
        return Scope(only=shown)
    return Scope(exact=False)


def _match(key: str, value: Any) -> dict[str, Any]:
    return {"key": key, "match": {"value": value}}


def scope_filter(scope: Scope, must: Iterable[dict] = (), must_not: Iterable[dict] = ()) -> dict[str, Any] | None:
    must, must_not = list(must), list(must_not)
    if scope.only is not None:
        must.append({"key": "grimoire_id", "match": {"any": list(scope.only)}})
    if scope.never:
        must_not.append({"key": "grimoire_id", "match": {"any": list(scope.never)}})
    found: dict[str, Any] = {}
    if must:
        found["must"] = must
    if must_not:
        found["must_not"] = must_not
    return found or None


def _statement_points() -> list[dict[str, Any]]:
    return [_match("projection_type", "statement"), _match("direction", "self"),
            _match("language_id", LANGUAGE_ID), _match("is_active", True)]


def books_model(cur) -> dict[str, Any] | None:
    """The model and store of the books' statement vectors: the newest active model that indexed any."""
    cur.execute(
        """
        SELECT em.embedding_model_id, em.model_name, em.vector_size, em.distance_metric, em.qdrant_collection
        FROM embedding_model em
        WHERE em.is_active AND em.distance_metric = 'cosine'
          AND EXISTS (SELECT 1 FROM embedding e
                      WHERE e.embedding_model_id = em.embedding_model_id AND e.status = 'indexed')
        ORDER BY em.embedding_model_id DESC
        LIMIT 1
        """
    )
    return cur.fetchone()


# --- the two rankings -----------------------------------------------------------------------------------

Ranked = list[tuple[int, float]]


def _ranked(points: list[dict[str, Any]], *, skip: int | None = None) -> Ranked:
    """(knowledge_id, score) in Qdrant's order, each object once, malformed points left out."""
    seen: set[int] = set()
    ranked: Ranked = []
    for point in points:
        payload = point.get("payload") or {}
        raw = payload.get("knowledge_id", point.get("id"))
        try:
            knowledge_id = int(raw)
            score = float(point.get("score"))
        except (TypeError, ValueError):
            continue
        if isinstance(raw, bool) or not math.isfinite(score) or knowledge_id in seen or knowledge_id == skip:
            continue
        seen.add(knowledge_id)
        ranked.append((knowledge_id, score))
    return ranked


def dense_ranking(vector: Sequence[float], model: dict[str, Any], scope: Scope, limit: int) -> Ranked:
    points = qdrant_service.query_raw(collection=model["qdrant_collection"], body={
        "query": list(vector),
        "filter": scope_filter(scope, _statement_points()),
        "limit": limit,
        "with_payload": ["knowledge_id"],
    })
    return _ranked(points)


def word_store_ready() -> bool:
    try:
        return qdrant_service.collection_exists(word_index.COLLECTION)
    except HTTPException:
        return False


def word_ranking(texts: Iterable[str], scope: Scope, limit: int) -> Ranked:
    sparse = word_index.query_vector(texts)
    if not sparse["indices"]:
        return []
    points = qdrant_service.query_raw(collection=word_index.COLLECTION, body={
        "query": sparse,
        "using": word_index.SPARSE_NAME,
        "filter": scope_filter(scope),
        "limit": limit,
        "with_payload": ["knowledge_id"],
    })
    return _ranked(points)


@dataclass
class Rankings:
    lists: list[tuple[str, Ranked]]
    meaning: str
    meaning_reason: str | None
    words: str

    def states(self) -> dict[str, str]:
        return {MEANING: self.meaning, WORDS: self.words}


def run_rankings(*, meaning_texts: Sequence[str], word_texts: Sequence[Sequence[str]], model: dict | None,
                 scope: Scope, limit: int) -> Rankings:
    """One meaning ranking per meaning text and one word ranking per group of word texts."""
    lists: list[tuple[str, Ranked]] = []
    meaning = embed(meaning_texts, model)
    meaning_state, meaning_reason = meaning.state, meaning.reason
    if meaning.state == USED:
        try:
            lists += [(MEANING, dense_ranking(vector, model, scope, limit)) for vector in meaning.vectors]
        except (HTTPException, ValueError, TypeError):
            meaning_state, meaning_reason = FAILED, "store_failed"
    words_state = USED if word_store_ready() else OFF
    if words_state == USED:
        try:
            lists += [(WORDS, word_ranking(group, scope, limit)) for group in word_texts]
        except (HTTPException, ValueError, TypeError):
            words_state = FAILED
    return Rankings([item for item in lists if item[0] == MEANING] + [item for item in lists if item[0] == WORDS],
                    meaning_state, meaning_reason, words_state)


def notice(rankings: Rankings) -> str | None:
    meaning, words = rankings.meaning, rankings.words
    if meaning == USED and words == USED:
        return None
    parts = []
    if meaning == OFF and rankings.meaning_reason == "other_model":
        parts.append("Search by meaning is off: theumst.com's embedding settings name another model than the "
                     "one the books' vectors were made with.")
    elif meaning == OFF and rankings.meaning_reason == "no_vectors":
        parts.append("Search by meaning is off: no book on theumst.com has vectors yet.")
    elif meaning == OFF:
        parts.append("Search by meaning is off on theumst.com until its embedding settings are set.")
    elif meaning == FAILED:
        parts.append("Search by meaning did not answer this time.")
    if words == OFF:
        parts.append("Search by words is off until theumst.com's word index is filled.")
    elif words == FAILED:
        parts.append("Search by words did not answer this time.")
    if meaning == USED:
        parts.append("These results come from search by meaning only.")
    elif words == USED:
        parts.append("These results come from search by words only.")
    return " ".join(parts)


def fuse(lists: Iterable[tuple[str, Ranked]], *, first: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Merge rankings by reciprocal rank, sum of 1/(RRF_K + rank). Objects found by a ranking named in
    `first` come before the rest; ties go to the lower knowledge_id."""
    entries: dict[int, dict[str, Any]] = {}
    for name, ranked in lists:
        for rank, (knowledge_id, score) in enumerate(ranked, 1):
            entry = entries.setdefault(knowledge_id, {
                "knowledge_id": knowledge_id, "found_by": set(),
                "scores": {MEANING: None, WORDS: None, "fused": 0.0},
            })
            entry["found_by"].add(name)
            if name in (MEANING, WORDS):
                best = entry["scores"][name]
                entry["scores"][name] = score if best is None else max(best, score)
            entry["scores"]["fused"] += 1.0 / (RRF_K + rank)
    first = set(first)
    ordered = sorted(entries.values(), key=lambda entry: (
        not (entry["found_by"] & first), -entry["scores"]["fused"], entry["knowledge_id"],
    ))
    for entry in ordered:
        entry["found_by"] = [name for name in _FOUND_ORDER if name in entry["found_by"]]
        entry["scores"] = {key: (None if value is None else round(value, 6)) for key, value in entry["scores"].items()}
    return ordered


# --- the hits' rows, read only for the hits -------------------------------------------------------------

_HIT_SQL = """
    SELECT k.knowledge_id, COALESCE(k.source_key, '') AS source_key, k.type,
           k.knowledge_crystal_id AS crystal_id, COALESCE(btrim(k.name), '') AS name,
           COALESCE(btrim(lk.label), '') AS label, lk.statement, s.grimoire_id, lg.title AS book_title
    FROM knowledge k
    JOIN section s ON s.section_id = k.section_id
    JOIN grimoire g ON g.grimoire_id = s.grimoire_id
    JOIN language_knowledge lk ON lk.knowledge_id = k.knowledge_id AND lk.language_id = %(language)s
    JOIN language_grimoire lg ON lg.grimoire_id = g.grimoire_id AND lg.language_id = %(language)s
    WHERE k.knowledge_id = ANY(%(ids)s) AND k.is_active AND g.source_metadata->>'demo' = 'true'
"""

_CRYSTAL_SIZE_SQL = """
    SELECT k.knowledge_crystal_id AS crystal_id, count(*)::int AS size
    FROM knowledge k
    JOIN section s ON s.section_id = k.section_id
    JOIN grimoire g ON g.grimoire_id = s.grimoire_id
    WHERE k.knowledge_crystal_id = ANY(%s) AND k.is_active AND g.source_metadata->>'demo' = 'true'
    GROUP BY k.knowledge_crystal_id
"""


def hit_rows(cur, knowledge_ids: Iterable[int], books: Sequence[int] | None = None) -> dict[int, dict[str, Any]]:
    """The visible, active objects among `knowledge_ids` (only of `books` when given), by id."""
    ids = sorted({int(value) for value in knowledge_ids})
    if not ids:
        return {}
    sql = _HIT_SQL
    values: dict[str, Any] = {"language": LANGUAGE_ID, "ids": ids}
    if books is not None:
        sql += " AND s.grimoire_id = ANY(%(books)s)"
        values["books"] = list(books)
    cur.execute(sql, values)
    return {int(row["knowledge_id"]): dict(row) for row in cur.fetchall()}


def crystal_sizes(cur, crystal_ids: Iterable[int]) -> dict[int, int]:
    """Each crystal's active members in every book the Web Demo shows."""
    ids = sorted({int(value) for value in crystal_ids})
    if not ids:
        return {}
    cur.execute(_CRYSTAL_SIZE_SQL, (ids,))
    return {int(row["crystal_id"]): int(row["size"]) for row in cur.fetchall()}


def shown_members(size: int) -> int:
    """max(1, floor(log3 m)), in integers: 1 to 8 members show 1, 9 to 26 show 2, 27 to 80 show 3."""
    shown, power = 0, 3
    while power <= size:
        shown += 1
        power *= 3
    return max(1, shown)


_HIT_KEYS = ("knowledge_id", "source_key", "grimoire_id", "book_title", "label", "name", "statement", "type",
             "crystal_id")


def _hit(row: dict[str, Any], size: int) -> dict[str, Any]:
    hit = {key: row[key] for key in _HIT_KEYS}
    hit["crystal_size"] = size
    return hit


def hydrate(entries: list[dict[str, Any]], books: Sequence[int] | None = None) -> tuple[list[dict], dict[int, int]]:
    """The entries whose objects the reader may see, in order, with their rows; and their crystals' sizes."""
    with transaction() as (_, cur):
        cur.execute("SET TRANSACTION READ ONLY")
        rows = hit_rows(cur, (entry["knowledge_id"] for entry in entries), books)
        sizes = crystal_sizes(cur, (row["crystal_id"] for row in rows.values()))
    kept = []
    for entry in entries:
        row = rows.get(entry["knowledge_id"])
        if row is None:
            continue
        size = sizes.get(int(row["crystal_id"]), 1)
        kept.append({**_hit(row, size), **{key: entry[key] for key in entry if key != "knowledge_id"}})
    return kept, sizes


def hide_crystals(hits: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    """The first `count` hits in order, at most shown_members(m) of a crystal of m members, ranked from 1."""
    shown: Counter = Counter()
    kept = []
    for hit in hits:
        crystal = hit["crystal_id"]
        if shown[crystal] >= shown_members(hit["crystal_size"]):
            continue
        shown[crystal] += 1
        kept.append(hit)
        if len(kept) == count:
            break
    for rank, hit in enumerate(kept, 1):
        hit["crystal_shown"] = shown[hit["crystal_id"]]
        hit["rank"] = rank
    return [_ordered_hit(hit) for hit in kept]


_ANSWER_ORDER = ("knowledge_id", "source_key", "grimoire_id", "book_title", "label", "name", "statement", "type",
                 "crystal_id", "crystal_size", "crystal_shown", "found_by", "mentions", "rank", "scores")


def _ordered_hit(hit: dict[str, Any]) -> dict[str, Any]:
    return {key: hit[key] for key in _ANSWER_ORDER if key in hit}


def _candidates(count: int, scope: Scope, factor: int = OVERSAMPLE) -> int:
    return min(MAX_CANDIDATES, count * factor * (1 if scope.exact else 2))


def _prepare(books: Sequence[int] | None) -> tuple[Scope, dict[str, Any] | None]:
    with transaction() as (_, cur):
        cur.execute("SET TRANSACTION READ ONLY")
        scope = book_scope(cur, books)
        model = books_model(cur)
    return scope, model


def _answer(rankings: Rankings, **body: Any) -> dict[str, Any]:
    return {**body, "rankings": rankings.states(), "notice": notice(rankings)}


def _require_a_ranking(rankings: Rankings) -> None:
    if rankings.meaning != USED and rankings.words != USED:
        raise SearchUnavailable(notice(rankings) or "Search is unavailable")


# --- 1. search ------------------------------------------------------------------------------------------

def search_objects(*, name: str, statement: str, keywords: Sequence[str], count: int,
                   books: Sequence[int] | None = None) -> dict[str, Any]:
    scope, model = _prepare(books)
    if scope.empty:
        ready = meaning_ready(model)
        rankings = Rankings([], ready.state, ready.reason, USED if word_store_ready() else OFF)
        return {"results": [], "count": 0, "rankings": rankings.states(),
                "notice": "None of the books asked for is shown on theumst.com."}
    rankings = run_rankings(
        meaning_texts=[query_text(name, statement)],
        word_texts=[[name, statement, *keywords]],
        model=model, scope=scope, limit=_candidates(count, scope),
    )
    _require_a_ranking(rankings)
    hits, _ = hydrate(fuse(rankings.lists), scope.only if books else None)
    results = hide_crystals(hits, count)
    return _answer(rankings, results=results, count=len(results))


# --- 2. neighbours --------------------------------------------------------------------------------------

_SOURCE_BY_KEY_SQL = """
    SELECT k.knowledge_id
    FROM knowledge k
    JOIN section s ON s.section_id = k.section_id
    JOIN grimoire g ON g.grimoire_id = s.grimoire_id
    WHERE k.source_key = %s AND k.is_active AND g.source_metadata->>'demo' = 'true'
    ORDER BY k.knowledge_id
    LIMIT 1
"""

_STATEMENT_POINT_SQL = """
    SELECT e.embedding_id::text AS embedding_id, em.qdrant_collection, em.vector_size
    FROM semantic_projection sp
    JOIN embedding e ON e.semantic_projection_id = sp.semantic_projection_id AND e.status = 'indexed'
    JOIN embedding_model em ON em.embedding_model_id = e.embedding_model_id AND em.is_active
    WHERE sp.knowledge_id = %s AND sp.language_id = %s AND sp.is_active
      AND sp.projection_type = 'statement' AND sp.direction = 'self' AND em.distance_metric = 'cosine'
    ORDER BY e.embedding_model_id DESC
    LIMIT 1
"""


def neighbours(*, knowledge_id: int | None = None, source_key: str | None = None, count: int) -> dict[str, Any]:
    with transaction() as (_, cur):
        cur.execute("SET TRANSACTION READ ONLY")
        if source_key is not None:
            cur.execute(_SOURCE_BY_KEY_SQL, (source_key,))
            found = cur.fetchone()
            if not found:
                raise ObjectNotFound()
            knowledge_id = int(found["knowledge_id"])
        source = hit_rows(cur, [knowledge_id]).get(int(knowledge_id))
        if source is None:
            raise ObjectNotFound()
        source_size = crystal_sizes(cur, [source["crystal_id"]]).get(int(source["crystal_id"]), 1)
        cur.execute(_STATEMENT_POINT_SQL, (knowledge_id, LANGUAGE_ID))
        statement_point = cur.fetchone()
        if not statement_point:
            raise NoVector()
        scope = book_scope(cur)
    try:
        points = qdrant_service.query_raw(collection=statement_point["qdrant_collection"], body={
            "query": statement_point["embedding_id"],
            "filter": scope_filter(scope, _statement_points(), [_match("knowledge_id", int(knowledge_id))]),
            "limit": _candidates(count, scope, 2),
            "with_payload": ["knowledge_id"],
        })
    except (HTTPException, ValueError, TypeError) as exc:
        raise SearchUnavailable("Neighbours are unavailable this time") from exc
    ranked = _ranked(points, skip=int(knowledge_id))
    hits, _ = hydrate(fuse([(MEANING, ranked)]))
    hits = hits[:count]
    for rank, hit in enumerate(hits, 1):
        hit["rank"] = rank
    return {
        "object": _ordered_hit(_hit(source, source_size)),
        "results": [_ordered_hit(hit) for hit in hits],
        "count": len(hits),
    }


# --- 3. the latcher's candidates ------------------------------------------------------------------------

_LABEL_WORDS = (
    "theorem", "lemma", "proposition", "corollary", "definition", "exercise", "example", "remark", "problem",
    "claim", "conjecture", "axiom", "notation", "fact", "observation", "algorithm", "construction", "question",
    "property", "principle", "law", "equation",
)
_LABEL_MENTION = re.compile(
    r"\b(" + "|".join(_LABEL_WORDS) + r")s?\.?\s+(\d+(?:\.\d+)*[a-z]?(?:\s*\([a-z0-9]{1,4}\))?)",
    re.IGNORECASE,
)


def label_key(label: str) -> str:
    """A label compared by its words: lower case, no spaces, no `<part n>`, no full stop at the end."""
    return re.sub(r"<[^>]*>|\s+", "", str(label or "").lower()).rstrip(".")


def label_mentions(text: str) -> dict[str, str]:
    """label key -> the words of the text that named it, first mention first."""
    found: dict[str, str] = {}
    for match in _LABEL_MENTION.finditer(text):
        words = f"{match.group(1)} {match.group(2)}"
        found.setdefault(label_key(words), " ".join(words.split()))
    return found


_LABELS_IN_BOOK_SQL = """
    SELECT k.knowledge_id, rtrim(regexp_replace(lower(lk.label), '<[^>]*>|\\s+', '', 'g'), '.') AS label_key
    FROM section s
    JOIN grimoire g ON g.grimoire_id = s.grimoire_id AND g.source_metadata->>'demo' = 'true'
    JOIN knowledge k ON k.section_id = s.section_id AND k.is_active
    JOIN language_knowledge lk ON lk.knowledge_id = k.knowledge_id AND lk.language_id = %s
    WHERE s.grimoire_id = %s
      AND rtrim(regexp_replace(lower(lk.label), '<[^>]*>|\\s+', '', 'g'), '.') = ANY(%s)
    ORDER BY k.knowledge_id
"""


def text_pieces(text: str, *, pieces: int = LATCHER_PIECES, size: int = LATCHER_PIECE_CHARACTERS) -> list[str]:
    """The text cut at sentence ends into at most `pieces` pieces of about `size` characters or more, so the
    whole text is covered."""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n\s*\n", text) if part and part.strip()]
    if not sentences:
        return []
    target = max(size, math.ceil(sum(len(sentence) + 1 for sentence in sentences) / pieces))
    found: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + 1 + len(sentence) > target and len(found) < pieces - 1:
            found.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}" if current else sentence
    if current:
        found.append(current)
    return found


def _name_matches(text: str, scope: Scope) -> tuple[Ranked, dict[int, str]]:
    """Objects of any visible book whose whole name the text mentions, longest names first."""
    grams = word_index.name_ngrams(text)
    if not grams:
        return [], {}
    points, _ = qdrant_service.scroll_points(
        collection=word_index.COLLECTION,
        filter=scope_filter(scope, [{"key": "name_key", "match": {"any": grams}}]),
        limit=NAME_MATCH_LIMIT,
        with_payload=["knowledge_id", "name_key"],
    )
    named: dict[int, str] = {}
    for point in points:
        payload = point.get("payload") or {}
        try:
            named.setdefault(int(payload.get("knowledge_id", point.get("id"))), str(payload.get("name_key") or ""))
        except (TypeError, ValueError):
            continue
    ordered = sorted(named, key=lambda kid: (-len(named[kid].split()), kid))
    return [(kid, 1.0) for kid in ordered], named


def _mention_of(name_key: str, text_words: str) -> str:
    return name_key if name_key and f" {name_key} " in f" {text_words} " else ""


def latcher_candidates(*, text: str, grimoire_id: int | None, count: int) -> dict[str, Any]:
    scope, model = _prepare(None)
    mentions = label_mentions(text)
    lists: list[tuple[str, Ranked]] = []
    labelled: dict[int, str] = {}
    if grimoire_id is not None and mentions:
        with transaction() as (_, cur):
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(_LABELS_IN_BOOK_SQL, (LANGUAGE_ID, int(grimoire_id), sorted(mentions)))
            for row in cur.fetchall():
                labelled.setdefault(int(row["knowledge_id"]), mentions.get(row["label_key"], row["label_key"]))
        lists.append((LABEL, [(kid, 1.0) for kid in labelled]))
    named: dict[int, str] = {}
    pieces = text_pieces(text)
    limit = _candidates(count, scope, 3)
    rankings = run_rankings(meaning_texts=pieces, word_texts=[[piece] for piece in pieces], model=model,
                            scope=scope, limit=limit)
    if rankings.words == USED:
        try:
            ranked_names, named = _name_matches(text, scope)
            lists.append((NAME, ranked_names))
        except (HTTPException, ValueError, TypeError):
            rankings.words = FAILED
    if rankings.meaning != USED and rankings.words != USED and not labelled:
        raise SearchUnavailable(notice(rankings) or "Search is unavailable")
    entries = fuse(lists + rankings.lists, first=(LABEL, NAME))
    text_words = " ".join(word_index.raw_words(text))
    for entry in entries:
        found = []
        if entry["knowledge_id"] in labelled:
            found.append(labelled[entry["knowledge_id"]])
        mention = _mention_of(named.get(entry["knowledge_id"], ""), text_words)
        if mention:
            found.append(mention)
        entry["mentions"] = found
    hits, _ = hydrate(entries)
    results = hide_crystals(hits, count)
    return _answer(rankings, results=results, count=len(results))


# --- 4. which crystal -----------------------------------------------------------------------------------

def which_crystals(*, name: str, statement: str, keywords: Sequence[str], count: int) -> dict[str, Any]:
    scope, model = _prepare(None)
    rankings = run_rankings(
        meaning_texts=[query_text(name, statement)],
        word_texts=[[name, statement, *keywords]],
        model=model, scope=scope, limit=_candidates(count, scope, 10),
    )
    _require_a_ranking(rankings)
    hits, _ = hydrate(fuse(rankings.lists))
    crystals: dict[int, dict[str, Any]] = {}
    for hit in hits:
        crystal = crystals.get(hit["crystal_id"])
        if crystal is None:
            if len(crystals) == count:
                continue
            crystal = crystals[hit["crystal_id"]] = {
                "crystal_id": hit["crystal_id"], "crystal_size": hit["crystal_size"], "rank": len(crystals) + 1,
                "found_by": [], "scores": {MEANING: None, WORDS: None, "fused": hit["scores"]["fused"]},
                "members": [],
            }
        for name_found in hit["found_by"]:
            if name_found not in crystal["found_by"]:
                crystal["found_by"].append(name_found)
        for key in (MEANING, WORDS):
            value = hit["scores"][key]
            if value is not None and (crystal["scores"][key] is None or value > crystal["scores"][key]):
                crystal["scores"][key] = value
        if len(crystal["members"]) < shown_members(hit["crystal_size"]):
            crystal["members"].append(hit)
    answer = []
    for crystal in crystals.values():
        crystal["found_by"] = [name for name in _FOUND_ORDER if name in crystal["found_by"]]
        for rank, member in enumerate(crystal["members"], 1):
            member["crystal_shown"] = len(crystal["members"])
            member["rank"] = rank
        crystal["members"] = [_ordered_hit(member) for member in crystal["members"]]
        answer.append(crystal)
    return _answer(rankings, crystals=answer, count=len(answer))
