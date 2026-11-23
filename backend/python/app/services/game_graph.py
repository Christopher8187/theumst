"""The game's graph reads for UMST's agents (0.0.19): an object with its load, a crystal's members,
what an object uses and what uses it, closures over crystals across books, a section in book order,
the objects around one, and the source's pages.

Every read goes through a GraphSource. SqlGraph is the one theumst.com runs: each method is one
query, and every query keeps to active objects of books the Web Demo shows, inside the SQL. The
logic here (the support component, the detached proofs, the walk over crystals and its word budget)
only calls those methods, so the unit tests run it over an in-memory graph.

Arrows are the graph sidecar's (knowledge_graph_edge), kept per book: in `dependency` the target
uses the source, in `supports` the source supports the target. Crystals join books. An object's
place in its book is the reader order of the whole-book read (book_read._OBJECTS).

Since 0.0.20 the closure, the crystal, uses and used-by take `max_chars` and `page`: an answer then stays
within max_chars characters as the door hands it to an agent, and what does not fit comes on the next page.
A request without them answers as 0.0.19 did.
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator, Mapping, Protocol, Sequence
from urllib.parse import quote

from .book_read import contents_order

# --- limits -------------------------------------------------------------------------------

COMPONENT_MEMBERS = 24          # the game's MEMBERS (tutor_stage.gd), the object included
DEPENDENCIES_MOST = 300
ARROWS_MOST = 500
CRYSTAL_MEMBERS_MOST = 500
SECTION_OBJECTS_MOST = 400
AROUND_MOST = 25
MATCH_MOST = 200
FAR_OBJECTS = 10                # the game's FAR (tutor_stage.gd)
WORDS_DEFAULT = 3000
WORDS_LEAST = 100
WORDS_MOST = 10000
GIVE_UP_TIMES = 10              # history A7.5 step 12: past ten times the budget, give up
CLOSURE_CRYSTALS_MOST = 4000    # a safety limit for one processor
CLOSURE_DEPTH_MOST = 64
CHARS_LEAST = 2000              # max_chars, 0.0.20: an answer's size as the door hands it on
CHARS_MOST = 200000
PAGE_MOST = 100000
ROWS_A_READ = 500               # rows read at a time while a list is cut into pages

SUPPORT_TYPES = ("supporting_lemma", "supporting_exercise")
# What a detached proof may prove: the game's PROVABLE (star_model.gd).
PROVABLE = ("theorem", "semantic_theorem", "supporting_lemma")
DETACHED = "detachedproof"
REFERENCE = "reference"


class NotFound(Exception):
    """No active object or section of a visible book."""


class Ambiguous(Exception):
    """A source key names objects in more than one book."""


class TooSmall(Exception):
    """max_chars cannot hold even the answer's frame and one item."""

    def __init__(self, needed: int):
        super().__init__(f"max_chars is too small for this answer; send at least {needed}")
        self.needed = needed


# --- the source ---------------------------------------------------------------------------

class GraphSource(Protocol):
    """What the reads need of theumst.com's database. Every method sees only active objects of
    visible books; an id that is neither is simply absent from what it returns."""

    def find(self, *, knowledge_id: int | None = None, source_key: str | None = None,
             grimoire_id: int | None = None) -> list[dict[str, Any]]:
        """The object rows (short form) matching, at most two."""

    def objects(self, ids: Sequence[int], *, working: bool = False) -> dict[int, dict[str, Any]]:
        """Object rows by id; with working, each adds `working` and `working_summary`."""

    def arrows(self, ends: Sequence[tuple[int, int]], relation: str, side: str) -> list[dict[str, Any]]:
        """The arrows of `relation` at the (grimoire_id, knowledge_id) ends: side 'in' those whose target is
        an end, 'out' those whose source is. Rows {end, other, other_type, other_crystal_id, grimoire_id},
        ordered by end, then other."""

    def positions(self, grimoire_id: int, ids: Sequence[int]) -> tuple[dict[int, int], int]:
        """Each id's place in its book's reader order (from 1), and the book's count."""

    def window(self, grimoire_id: int, first: int, last: int) -> list[int]:
        """The ids at places first to last of the book's reader order, in that order."""

    def section_objects(self, grimoire_id: int, section_id: int, limit: int) -> list[tuple[int, int]]:
        """(id, place) of a section's own objects in reader order, at most limit."""

    def sections(self, grimoire_id: int) -> list[dict[str, Any]]:
        """Every section of a book: {section_id, parent_section, section_number, section_name}."""

    def section(self, section_id: int) -> dict[str, Any] | None:
        """{section_id, grimoire_id, book_title} for a section of a visible book."""

    def members(self, crystal_ids: Sequence[int]) -> list[dict[str, Any]]:
        """Crystal members {crystal_id, knowledge_id, grimoire_id, type, default}, by crystal, then book,
        then reader order."""

    def pages(self, knowledge_id: int) -> tuple[list[dict[str, Any]], Any]:
        """The object's page scans {source_image_id, storage_key, url, metadata} in page order, and its
        upload's page numbers (knowledge.source_metadata.pages)."""

    def match(self, source_keys: Sequence[str]) -> list[dict[str, Any]]:
        """{source_key, knowledge_id, grimoire_id} of the active objects of visible books with these keys."""


# --- SQL ----------------------------------------------------------------------------------

_VISIBLE = """
JOIN section s ON s.section_id = k.section_id
JOIN grimoire g ON g.grimoire_id = s.grimoire_id AND g.source_metadata->>'demo' = 'true'
"""

# book_read._OBJECTS' order: the reader order of the whole-book read and the Web Demo's list.
_ORDER = """COALESCE((k.source_metadata->>'demo_order')::int, 2147483647),
         k.source_metadata->'order' NULLS LAST, k.knowledge_id"""

_OBJECT_COLUMNS = """
k.knowledge_id, k.source_key, s.grimoire_id, COALESCE(lg.title, '') AS book_title, k.section_id,
COALESCE(btrim(lk.label), '') AS label, COALESCE(btrim(k.name), '') AS name, lk.statement, k.type,
k.knowledge_crystal_id AS crystal_id, COALESCE(z.crystal_size, 0) AS crystal_size
"""


def _objects_sql(where: str, *, working: bool = False, tail: str = "") -> str:
    """Object rows (OBJECT_KEYS) for the active objects of visible books that `where` picks (over k and s).
    Crystal sizes are counted once for the crystals picked, not once a row: one pass over the
    knowledge_active_crystal_idx (migration 018), or one scan of knowledge without it."""
    extra = ", lk.working, COALESCE(lk.working_summary, '') AS working_summary" if working else ""
    return f"""
    WITH chosen AS (
        SELECT k.knowledge_id, k.knowledge_crystal_id
        FROM knowledge k
        {_VISIBLE}
        WHERE {where} AND k.is_active
    ), sizes AS (
        SELECT m.knowledge_crystal_id, count(*)::int AS crystal_size
        FROM knowledge m
        JOIN section ms ON ms.section_id = m.section_id
        JOIN grimoire mg ON mg.grimoire_id = ms.grimoire_id AND mg.source_metadata->>'demo' = 'true'
        WHERE m.is_active AND m.knowledge_crystal_id IN (SELECT knowledge_crystal_id FROM chosen)
        GROUP BY m.knowledge_crystal_id
    )
    SELECT {_OBJECT_COLUMNS}{extra}
    FROM chosen c
    JOIN knowledge k ON k.knowledge_id = c.knowledge_id
    {_VISIBLE}
    JOIN language_knowledge lk ON lk.knowledge_id = k.knowledge_id AND lk.language_id = 1
    LEFT JOIN language_grimoire lg ON lg.grimoire_id = g.grimoire_id AND lg.language_id = 1
    LEFT JOIN sizes z ON z.knowledge_crystal_id = k.knowledge_crystal_id
    {tail}
    """

_RANKED = f"""
SELECT k.knowledge_id, k.section_id,
       row_number() OVER (ORDER BY {_ORDER}) AS position, count(*) OVER () AS total
FROM knowledge k
{_VISIBLE}
JOIN language_knowledge lk ON lk.knowledge_id = k.knowledge_id AND lk.language_id = 1
WHERE s.grimoire_id = %s AND k.is_active
"""

OBJECT_KEYS = (
    "knowledge_id", "source_key", "grimoire_id", "book_title", "section_id", "label", "name", "statement",
    "type", "crystal_id", "crystal_size",
)


class SqlGraph:
    """The GraphSource over theumst.com's PostgreSQL, one query a method, on the cursor given."""

    def __init__(self, cur):
        self.cur = cur

    def _all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        self.cur.execute(sql, tuple(params))
        return [dict(row) for row in self.cur.fetchall()]

    def find(self, *, knowledge_id=None, source_key=None, grimoire_id=None):
        if knowledge_id is not None:
            where, params = "k.knowledge_id = %s", [knowledge_id]
        else:
            where, params = "k.source_key = %s", [source_key]
            if grimoire_id is not None:
                where += " AND s.grimoire_id = %s"
                params.append(grimoire_id)
        return self._all(_objects_sql(where, tail="ORDER BY s.grimoire_id, k.knowledge_id LIMIT 2"), params)

    def objects(self, ids, *, working=False):
        if not ids:
            return {}
        rows = self._all(_objects_sql("k.knowledge_id = ANY(%s)", working=working), [list(ids)])
        return {int(row["knowledge_id"]): row for row in rows}

    def arrows(self, ends, relation, side):
        if not ends:
            return []
        end, other = ("target", "source") if side == "in" else ("source", "target")
        # An arrow's two ends are in its book (the sidecar's nodes are per book), so the book is checked once an
        # arrow; joining each far end's section instead made PostgreSQL compare every visible section with
        # every arrow (1.9 s for 400 ends on COM, against milliseconds this way).
        return self._all(
            f"""
            SELECT e.{end}_knowledge_id AS end, e.{other}_knowledge_id AS other, k.type AS other_type,
                   k.knowledge_crystal_id AS other_crystal_id, e.grimoire_id
            FROM unnest(%s::int[], %s::int[]) AS t(grimoire_id, knowledge_id)
            JOIN grimoire g ON g.grimoire_id = t.grimoire_id AND g.source_metadata->>'demo' = 'true'
            JOIN knowledge_graph_edge e
              ON e.grimoire_id = t.grimoire_id AND e.{end}_knowledge_id = t.knowledge_id
             AND e.relation_type = %s
            JOIN knowledge k ON k.knowledge_id = e.{other}_knowledge_id AND k.is_active
            ORDER BY 1, 2
            """,
            [[g for g, _ in ends], [i for _, i in ends], relation],
        )

    def positions(self, grimoire_id, ids):
        rows = self._all(
            f"SELECT knowledge_id, position, total FROM ({_RANKED}) ranked WHERE knowledge_id = ANY(%s)",
            [grimoire_id, list(ids)],
        )
        total = int(rows[0]["total"]) if rows else 0
        return {int(row["knowledge_id"]): int(row["position"]) for row in rows}, total

    def window(self, grimoire_id, first, last):
        rows = self._all(
            f"SELECT knowledge_id FROM ({_RANKED}) ranked WHERE position BETWEEN %s AND %s ORDER BY position",
            [grimoire_id, first, last],
        )
        return [int(row["knowledge_id"]) for row in rows]

    def section_objects(self, grimoire_id, section_id, limit):
        rows = self._all(
            f"SELECT knowledge_id, position FROM ({_RANKED}) ranked WHERE section_id = %s "
            "ORDER BY position LIMIT %s",
            [grimoire_id, section_id, limit],
        )
        return [(int(row["knowledge_id"]), int(row["position"])) for row in rows]

    def sections(self, grimoire_id):
        return self._all(
            """
            SELECT s.section_id, s.parent_section, s.section_number, ls.section_name
            FROM section s
            JOIN grimoire g ON g.grimoire_id = s.grimoire_id AND g.source_metadata->>'demo' = 'true'
            LEFT JOIN language_section ls ON ls.section_id = s.section_id AND ls.language_id = 1
            WHERE s.grimoire_id = %s
            ORDER BY s.section_id
            """,
            [grimoire_id],
        )

    def section(self, section_id):
        rows = self._all(
            """
            SELECT s.section_id, s.grimoire_id, COALESCE(lg.title, '') AS book_title
            FROM section s
            JOIN grimoire g ON g.grimoire_id = s.grimoire_id AND g.source_metadata->>'demo' = 'true'
            LEFT JOIN language_grimoire lg ON lg.grimoire_id = g.grimoire_id AND lg.language_id = 1
            WHERE s.section_id = %s
            """,
            [section_id],
        )
        return rows[0] if rows else None

    def members(self, crystal_ids):
        if not crystal_ids:
            return []
        return self._all(
            f"""
            SELECT k.knowledge_crystal_id AS crystal_id, k.knowledge_id, s.grimoire_id, k.type,
                   k.is_default_in_crystal AS "default"
            FROM knowledge k
            {_VISIBLE}
            WHERE k.knowledge_crystal_id = ANY(%s) AND k.is_active
            ORDER BY k.knowledge_crystal_id, s.grimoire_id, {_ORDER}
            """,
            [list(crystal_ids)],
        )

    def pages(self, knowledge_id):
        scans = self._all(
            """
            SELECT bi.source_image_id, bi.storage_key, bi.url, bi.metadata
            FROM book_image_knowledge l
            JOIN book_image bi ON bi.book_image_id = l.book_image_id
            JOIN grimoire g ON g.grimoire_id = bi.grimoire_id AND g.source_metadata->>'demo' = 'true'
            WHERE l.link_type = 'page' AND bi.is_active AND l.knowledge_id = %s
            ORDER BY CASE WHEN jsonb_typeof(bi.metadata->'page') = 'number'
                          THEN (bi.metadata->>'page')::numeric END NULLS LAST,
                     bi.book_image_id
            """,
            [knowledge_id],
        )
        rows = self._all("SELECT source_metadata->'pages' AS pages FROM knowledge WHERE knowledge_id = %s",
                         [knowledge_id])
        return scans, rows[0]["pages"] if rows else None

    def match(self, source_keys):
        if not source_keys:
            return []
        return self._all(
            f"""
            SELECT k.source_key, k.knowledge_id, s.grimoire_id
            FROM knowledge k
            {_VISIBLE}
            WHERE k.source_key = ANY(%s) AND k.is_active
            ORDER BY k.source_key, s.grimoire_id, k.knowledge_id
            """,
            [list(dict.fromkeys(source_keys))],
        )


# --- the answers --------------------------------------------------------------------------

def brief(row: Mapping[str, Any]) -> dict[str, Any]:
    """An object as every answer gives it: the search's hit without the search's fields (docs/game-agents.md)."""
    out = {key: row.get(key) for key in OBJECT_KEYS}
    for key in ("label", "name", "book_title"):
        out[key] = out[key] or ""
    out["crystal_size"] = int(out["crystal_size"] or 0)
    return out


def resolve(source: GraphSource, *, knowledge_id: int | None = None, source_key: str | None = None,
            grimoire_id: int | None = None) -> dict[str, Any]:
    """The one object a request names: by id, or by source key and, when two books share it, its book."""
    rows = source.find(knowledge_id=knowledge_id, source_key=source_key, grimoire_id=grimoire_id)
    if not rows:
        raise NotFound("No such knowledge object in a book the reader may see")
    if len(rows) > 1:
        raise Ambiguous("This source key names objects in more than one book; send grimoire_id")
    return rows[0]


# --- answers that fit, and their pages (0.0.20) ---------------------------------------------------

CUT_MARK = " [cut]"
_TEXTS = ("working", "working_summary", "statement")       # cut in this order when an item alone is too big
_LISTS = ("next", "followed", "reader_members", "used_by")
_REFERENCE_KEYS = ("knowledge_id", "source_key", "grimoire_id", "label", "name", "type", "crystal_id")


def chars(value: Any) -> int:
    """A value's size as the door hands it to an agent: JSON with ", " and ": " between, characters as they are."""
    return len(json.dumps(value, ensure_ascii=False))


def compact(row: Mapping[str, Any], titles: dict[int, str], *, drop: Sequence[str] = ()) -> dict[str, Any]:
    """brief(row) without its book's title, which the answer gives once under `books`, and without `drop`."""
    out = brief(row)
    titles[int(out["grimoire_id"])] = out.pop("book_title")
    for key in drop:
        out.pop(key, None)
    return out


def reference(row: Mapping[str, Any], titles: dict[int, str]) -> dict[str, Any]:
    """An object named, not given: what a compact answer says of the object asked about."""
    out = brief(row)
    titles[int(out["grimoire_id"])] = out["book_title"]
    return {key: out[key] for key in _REFERENCE_KEYS}


def _shorten(item: dict[str, Any], room: int) -> dict[str, Any] | None:
    """The item within room characters: its long texts cut, workings first, then the statement, each ending in
    CUT_MARK, then its long lists of ids, with `cut` naming what was cut; None when even that does not fit."""
    if chars(item) <= room:
        return item
    item = copy.deepcopy(item)
    item["cut"] = []
    holders = [item] + [item["shown"]] * isinstance(item.get("shown"), dict)
    for name in _TEXTS + _LISTS:
        for holder in holders:
            value = holder.get(name)
            if not value or not isinstance(value, (str, list)):
                continue
            if name not in item["cut"]:
                item["cut"].append(name)
            over = chars(item) - room
            if over <= 0:
                return item
            if isinstance(value, str):  # each character cut takes at least one off the JSON
                keep = len(value) - over - len(CUT_MARK)
                holder[name] = value[:keep] + CUT_MARK if keep > 0 else CUT_MARK.strip()
            else:  # each id cut takes at least three ("1, ")
                holder[name] = value[:max(0, len(value) - (over + 2) // 3 - 1)]
            if chars(item) <= room:
                return item
    return item if chars(item) <= room else None


@dataclass
class _Page:
    items: list[dict[str, Any]]
    first: int                      # the place of its first item in the whole list, from 0
    end: int                        # the place after its last
    more: bool = False              # an item follows it
    books: dict[str, str] = field(default_factory=dict)
    words: int = 0


def _page(entries: Iterable[tuple[dict[str, Any], int]], number: int, *, room: int | None = None,
          budget: int | None = None, most: int | None = None, titles: Mapping[int, str] | None = None,
          book: Callable[[dict[str, Any]], int] | None = None) -> _Page:
    """Page `number` (from 1) of the entries, each (item, words). Pages follow each other and each holds at least one
    item; an item joins the page while the page's characters stay within room (each item with the ", " before it,
    and its book's title the first time the page names that book), its words within budget, and its items at most
    `most`. A page past the last is empty."""
    def cost(item: dict[str, Any], books: Mapping[str, str]) -> int:
        if room is None:
            return 0
        size = chars(item) + 2
        if book is not None and titles is not None and str(book(item)) not in books:
            size += chars({str(book(item)): titles.get(book(item), "")})
        return size

    at, used, index = 1, 0, -1
    page = _Page([], 0, 0)
    for index, (item, words_) in enumerate(entries):
        size = cost(item, page.books)
        if page.items and ((room is not None and used + size > room)
                           or (budget is not None and page.words + words_ > budget)
                           or (most is not None and len(page.items) >= most)):
            if at == number:
                page.more = True
                return page
            at, used, page = at + 1, 0, _Page([], index, index)
            size = cost(item, page.books)
        page.items.append(item)
        page.end = index + 1
        page.words += words_
        used += size
        if book is not None and titles is not None:
            page.books.setdefault(str(book(item)), titles.get(book(item), ""))
    if at == number:
        return page
    return _Page([], index + 1, index + 1)


def _room(frame: Mapping[str, Any], max_chars: int) -> int:
    """What is left of max_chars for the items once the answer's frame is written."""
    room = max_chars - chars(frame)
    if room < 64:
        raise TooSmall(chars(frame) + 64)
    return room


def _fitted(items: Iterable[tuple[dict[str, Any], int]], room: int, max_chars: int, *,
            titles: Mapping[int, str] | None = None, book: Callable[[dict[str, Any]], int] | None = None
            ) -> Iterator[tuple[dict[str, Any], int]]:
    """Each item shortened, when it must be, so that it fits a page alone."""
    for item, words_ in items:
        own = 2 + (chars({str(book(item)): titles.get(book(item), "")}) if book and titles is not None else 0)
        short = _shorten(item, room - own)
        if short is None:
            raise TooSmall(max_chars + chars(item) + own - room)
        yield short, words_


def _rows_of(source: GraphSource, ids: Sequence[int]) -> Iterator[tuple[int, dict[str, Any]]]:
    """(id, row) for the ids in order, read ROWS_A_READ at a time, ids not visible left out."""
    for start in range(0, len(ids), ROWS_A_READ):
        chunk = ids[start:start + ROWS_A_READ]
        found = source.objects(chunk)
        for knowledge_id in chunk:
            if knowledge_id in found:
                yield knowledge_id, found[knowledge_id]


# --- 1. one object with its load ---------------------------------------------------------

@dataclass
class _Joined:
    knowledge_id: int
    why: str
    of: int


def load(source: GraphSource, obj: Mapping[str, Any]) -> dict[str, Any]:
    """The object in full, its support component in full, and what the component uses (history A4)."""
    book = int(obj["grimoire_id"])
    start = int(obj["knowledge_id"])
    joined, truncated = _component(source, book, start, {start: str(obj["type"])})
    member_ids = [start] + [item.knowledge_id for item in joined]

    uses: dict[int, list[int]] = {}
    for row in source.arrows([(book, member) for member in member_ids], "dependency", "in"):
        other = int(row["other"])
        if other in member_ids:
            continue
        users = uses.setdefault(other, [])
        if int(row["end"]) not in users:
            users.append(int(row["end"]))

    places, total = source.positions(book, member_ids + list(uses))
    full = source.objects(member_ids, working=True)
    if start not in full:
        raise NotFound("No such knowledge object in a book the reader may see")
    chapters = _chapters(source, book, {int(row["section_id"]) for row in full.values()})

    head = full[start]
    answer_object = {**brief(head), "working": head.get("working") or "",
                     "working_summary": head.get("working_summary") or "",
                     "position": places.get(start), "book_count": total}

    component = []
    for item in joined:
        row = full.get(item.knowledge_id)
        if row is None:
            continue
        away, far = _away(item, row, head, places, chapters)
        component.append({**brief(row), "working": row.get("working") or "",
                          "working_summary": row.get("working_summary") or "",
                          "why": item.why, "of": item.of, "far": far, "away": away})

    ordered = sorted(uses, key=lambda other: (places.get(other, 1 << 30), other))
    dependencies_truncated = len(ordered) > DEPENDENCIES_MOST
    ordered = ordered[:DEPENDENCIES_MOST]
    rows = source.objects(ordered)
    dependencies = [{**brief(rows[other]), "used_by": uses[other]} for other in ordered if other in rows]
    return {
        "object": answer_object,
        "component": component,
        "component_truncated": truncated,
        "dependencies": dependencies,
        "dependencies_truncated": dependencies_truncated,
    }


def _component(source: GraphSource, book: int, start: int, types: dict[int, str]) -> tuple[list[_Joined], bool]:
    """The support component of start, start left out, level by level as the game's tutor_stage.gd
    walks it: for each member, what supports it, what it supports, its detached proofs, and what it
    proves when it is one. At most COMPONENT_MEMBERS, start included; the bool says the walk stopped there."""
    held = [start]
    joined: list[_Joined] = []
    frontier = [start]
    truncated = False
    while frontier and not truncated:
        found: list[_Joined] = []
        ends = [(book, member) for member in frontier]
        supports_it = source.arrows(ends, "supports", "in")      # other supports end
        it_supports = source.arrows(ends, "supports", "out")     # end supports other
        users = source.arrows(ends, "dependency", "out")          # other uses end
        for row in supports_it + it_supports + users:
            types.setdefault(int(row["other"]), str(row["other_type"]))
        candidates = [int(row["other"]) for row in users if row["other_type"] == DETACHED]
        detached = [member for member in frontier if types.get(member) == DETACHED]
        proves = _proves(source, book, sorted(set(candidates + detached)))
        for member in frontier:
            found += [_Joined(int(row["other"]), "supports", member) for row in supports_it if int(row["end"]) == member]
            found += [_Joined(int(row["other"]), "supported_by", member) for row in it_supports if int(row["end"]) == member]
            found += [_Joined(proof, "proof_of", member) for proof in sorted(proves) if proves[proof] == member]
            if member in proves:
                found.append(_Joined(proves[member], "proved_by", member))
        frontier = []
        for item in found:
            if item.knowledge_id in held:
                continue
            if len(held) >= COMPONENT_MEMBERS:
                truncated = True
                break
            held.append(item.knowledge_id)
            joined.append(item)
            frontier.append(item.knowledge_id)
    return joined, truncated


def _proves(source: GraphSource, book: int, detached: Sequence[int]) -> dict[int, int]:
    """What each detached proof proves: the last object before it in book order, among what it uses,
    that a proof can be of (PROVABLE), as the game's star_model.gd reads it. A proof with none is absent."""
    if not detached:
        return {}
    used = [row for row in source.arrows([(book, proof) for proof in detached], "dependency", "in")
            if row["other_type"] in PROVABLE]
    if not used:
        return {}
    places, _ = source.positions(book, list(detached) + [int(row["other"]) for row in used])
    out: dict[int, int] = {}
    for proof in detached:
        at = places.get(proof)
        if at is None:
            continue
        before = [int(row["other"]) for row in used
                  if int(row["end"]) == proof and places.get(int(row["other"]), at) < at]
        if before:
            out[proof] = max(before, key=lambda other: places[other])
    return out


def _chapters(source: GraphSource, book: int, section_ids: Iterable[int]) -> dict[int, dict[str, Any]]:
    """Each section's top-level section (its chapter) in the book."""
    wanted = set(section_ids)
    if not wanted:
        return {}
    by_id = {int(row["section_id"]): row for row in source.sections(book)}
    out = {}
    for section_id in wanted:
        path = _path(by_id, section_id)
        if path:
            out[section_id] = path[0]
    return out


def _path(by_id: Mapping[int, Mapping[str, Any]], section_id: int) -> list[Mapping[str, Any]]:
    """The sections from the top level down to section_id; a cycle stops the climb."""
    path: list[Mapping[str, Any]] = []
    seen: set[int] = set()
    current: int | None = section_id
    while current is not None and current in by_id and current not in seen:
        seen.add(current)
        path.append(by_id[current])
        parent = by_id[current].get("parent_section")
        current = int(parent) if parent is not None else None
    path.reverse()
    return path


def _away(item: _Joined, row: Mapping[str, Any], head: Mapping[str, Any], places: Mapping[int, int],
          chapters: Mapping[int, Mapping[str, Any]]) -> tuple[dict[str, Any], bool]:
    """How far a member stands from the object, and whether it is far: a detached proof always (his
    words of 15 November), else another chapter or more than FAR_OBJECTS away, as tutor_stage.gd says."""
    here = places.get(int(head["knowledge_id"]))
    there = places.get(int(row["knowledge_id"]))
    apart = (there - here) if here is not None and there is not None else 0
    mine = chapters.get(int(head["section_id"]))
    theirs = chapters.get(int(row["section_id"]))
    other_chapter = mine is not None and theirs is not None and mine["section_id"] != theirs["section_id"]
    chapter = _section_title(theirs) if other_chapter else ""
    far = row["type"] == DETACHED or other_chapter or abs(apart) > FAR_OBJECTS
    away = {"objects": abs(apart), "direction": "later" if apart > 0 else "earlier" if apart < 0 else "",
            "chapter": chapter}
    return away, bool(far)


def _section_title(row: Mapping[str, Any] | None) -> str:
    if not row:
        return ""
    number = str(row.get("section_number") or "").strip()
    name = str(row.get("section_name") or "").strip()
    return ", ".join(part for part in (number, name) if part)


# --- 2. a crystal's members ----------------------------------------------------------------

def crystal(source: GraphSource, crystal_id: int, *, reader_grimoire_id: int | None = None,
            max_chars: int | None = None, page: int | None = None) -> dict[str, Any]:
    """Every member of the crystal in every visible book, the preferred one first, then the reader's book's
    (with reader_grimoire_id). With max_chars or page the members come a page at a time, at most
    CRYSTAL_MEMBERS_MOST a page and, with max_chars, within that many characters."""
    rows = source.members([crystal_id])
    if not rows:
        raise NotFound("No such crystal in a book the reader may see")
    if reader_grimoire_id is not None:
        rows.sort(key=lambda row: int(row["grimoire_id"]) != int(reader_grimoire_id))  # stable
    rows.sort(key=lambda row: not row["default"])  # stable: book, then reader order, kept
    size = len(rows)
    if max_chars is None and page is None:
        truncated = size > CRYSTAL_MEMBERS_MOST
        rows = rows[:CRYSTAL_MEMBERS_MOST]
        found = source.objects([int(row["knowledge_id"]) for row in rows])
        members = [{**brief(found[int(row["knowledge_id"])]), "default": bool(row["default"])}
                   for row in rows if int(row["knowledge_id"]) in found]
        return {"crystal_id": crystal_id, "crystal_size": size, "members": members, "truncated": truncated}

    number = page or 1
    default = {int(row["knowledge_id"]): bool(row["default"]) for row in rows}
    titles: dict[int, str] = {}

    def entries() -> Iterator[tuple[dict[str, Any], int]]:
        for knowledge_id, row in _rows_of(source, [int(row["knowledge_id"]) for row in rows]):
            if max_chars is None:
                yield {**brief(row), "default": default[knowledge_id]}, 0
            else:
                yield {**compact(row, titles, drop=("crystal_id", "crystal_size")), "default": default[knowledge_id]}, 0

    frame = {"crystal_id": crystal_id, "crystal_size": size, "members": [], "truncated": False,
             "page": number, "more": False}
    if max_chars is None:
        found = _page(entries(), number, most=CRYSTAL_MEMBERS_MOST)
        return {**frame, "members": found.items, "truncated": found.more, "more": found.more}
    frame["books"] = {}
    room = _room(frame, max_chars)
    book = lambda item: int(item["grimoire_id"])  # noqa: E731
    found = _page(_fitted(entries(), room, max_chars, titles=titles, book=book), number, room=room,
                  most=CRYSTAL_MEMBERS_MOST, titles=titles, book=book)
    return {**frame, "members": found.items, "truncated": found.more, "more": found.more, "books": found.books}


# --- 3. what an object uses, and what uses it ----------------------------------------------

def arrows(source: GraphSource, obj: Mapping[str, Any], direction: str, *, max_chars: int | None = None,
           page: int | None = None) -> dict[str, Any]:
    """What obj uses (direction 'uses') or what uses it ('used_by'), in book order. With max_chars or page they
    come a page at a time, at most ARROWS_MOST a page and, with max_chars, within that many characters."""
    book = int(obj["grimoire_id"])
    side = "in" if direction == "uses" else "out"
    others = list(dict.fromkeys(int(row["other"]) for row in
                                source.arrows([(book, int(obj["knowledge_id"]))], "dependency", side)))
    places, _ = source.positions(book, others) if others else ({}, 0)
    others.sort(key=lambda other: (places.get(other, 1 << 30), other))
    if max_chars is None and page is None:
        truncated = len(others) > ARROWS_MOST
        others = others[:ARROWS_MOST]
        rows = source.objects(others)
        results = [brief(rows[other]) for other in others if other in rows]
        return {"object": brief(obj), "results": results, "count": len(results), "truncated": truncated}

    number = page or 1
    titles: dict[int, str] = {}
    if max_chars is None:
        found = _page(((brief(row), 0) for _, row in _rows_of(source, others)), number, most=ARROWS_MOST)
        return {"object": brief(obj), "results": found.items, "count": len(found.items), "truncated": found.more,
                "page": number, "more": found.more}
    head = reference(obj, titles)
    # an arrow's two ends are in one book, so every result is in the object's book, named once under `books`
    frame = {"object": head, "results": [], "count": len(others), "truncated": False,
             "page": number, "more": False, "books": {str(book): titles[book]}}
    room = _room(frame, max_chars)
    items = ((compact(row, {}), 0) for _, row in _rows_of(source, others))
    found = _page(_fitted(items, room, max_chars), number, room=room, most=ARROWS_MOST)
    return {**frame, "results": found.items, "count": len(found.items), "truncated": found.more,
            "more": found.more}


# --- 4. closures over crystals ---------------------------------------------------------------

_MATHS = re.compile(r"\$[^$]*\$")
_WORD = re.compile(r"\S+")


def words(text: str | None) -> int:
    """Words as round 3's walks counted them (xbook.py): a formula between dollars is one word."""
    return len(_WORD.findall(_MATHS.sub(" x ", text or "")))


@dataclass
class _Crystal:
    crystal_id: int
    depth: int
    via_book: int
    transfers: int
    reached: int                       # the object the walk reached it by
    order: int
    walked: bool = False
    followed: list[int] = field(default_factory=list)
    next: list[int] = field(default_factory=list)
    reader_members: list[int] = field(default_factory=list)
    reader_reference: bool = False
    shown: int | None = None
    words: int = 0


def closure(source: GraphSource, obj: Mapping[str, Any], *, direction: str = "down",
            reader_grimoire_id: int | None = None, budget: int = WORDS_DEFAULT,
            max_chars: int | None = None, page: int | None = None) -> dict[str, Any]:
    """The closure over crystals from obj's crystal (history A7.5, round 3's xbook.py reader_first and
    r3stop.py): at each crystal follow the reader's book's proper members, else the proper members of
    the book the walk came through, else one proper member; list and do not walk a crystal the reader's
    book only references. Nearest first inside `budget` words, the rest counted by depth; past
    GIVE_UP_TIMES the budget, or CLOSURE_CRYSTALS_MOST crystals, give up and say why.

    With max_chars or page (0.0.20) the crystals come in pages: each page nearest first inside the budget and,
    with max_chars, within that many characters, so page 2 shows the crystals past the first budget; `counted`
    counts those after the page, and `more` says a page follows."""
    reader = int(reader_grimoire_id if reader_grimoire_id is not None else obj["grimoire_id"])
    side = "in" if direction == "down" else "out"
    start = int(obj["crystal_id"])
    found: dict[int, _Crystal] = {start: _Crystal(start, 0, int(obj["grimoire_id"]), 0, int(obj["knowledge_id"]), 0)}
    frontier = [start]
    depth = 0
    walked_words = 0
    gave_up: dict[str, Any] | None = None
    rows_by_id: dict[int, dict[str, Any]] = {}
    while frontier:
        members: dict[int, list[dict[str, Any]]] = {}
        for row in source.members(frontier):
            members.setdefault(int(row["crystal_id"]), []).append(row)
        follow_ends: list[tuple[int, int]] = []
        for crystal_id in frontier:
            node = found[crystal_id]
            mine = [row for row in members.get(crystal_id, []) if int(row["grimoire_id"]) == reader]
            proper_mine = [row for row in mine if row["type"] != REFERENCE]
            node.reader_members = [int(row["knowledge_id"]) for row in mine]
            node.reader_reference = bool(mine) and not proper_mine
            if node.reader_reference and crystal_id != start:
                node.shown = int(mine[0]["knowledge_id"])
                continue
            proper = [row for row in members.get(crystal_id, []) if row["type"] != REFERENCE]
            via = [row for row in proper if int(row["grimoire_id"]) == node.via_book]
            follow = proper_mine or via or proper[:1] or members.get(crystal_id, [])[:1]
            node.followed = [int(row["knowledge_id"]) for row in follow]
            node.shown = node.followed[0] if node.followed else node.reached
            follow_ends += [(int(row["grimoire_id"]), int(row["knowledge_id"])) for row in follow]

        shown = [found[crystal_id].shown or found[crystal_id].reached for crystal_id in frontier]
        rows_by_id.update(source.objects([knowledge_id for knowledge_id in shown if knowledge_id not in rows_by_id]))
        for crystal_id in frontier:
            node = found[crystal_id]
            row = rows_by_id.get(node.shown or node.reached)
            node.words = words(row.get("name")) + words(row.get("statement")) if row else 0
            walked_words += node.words

        if walked_words > GIVE_UP_TIMES * budget:
            gave_up = {"reason": f"The closure passed {GIVE_UP_TIMES * budget} words at depth {depth}, "
                                 f"{GIVE_UP_TIMES} times the budget, so the walk stopped there.",
                       "depth": depth}
        elif depth >= CLOSURE_DEPTH_MOST:
            gave_up = {"reason": f"The closure went {CLOSURE_DEPTH_MOST} crystals deep, so the walk stopped there.",
                       "depth": depth}
        if gave_up:
            for crystal_id in frontier:  # found, but their arrows are not followed
                found[crystal_id].followed = []
            break

        reached = source.arrows(follow_ends, "dependency", side) if follow_ends else []
        by_end: dict[int, list[dict[str, Any]]] = {}
        for row in reached:
            by_end.setdefault(int(row["end"]), []).append(row)
        new: list[int] = []
        for crystal_id in frontier:
            node = found[crystal_id]
            for member in node.followed:
                for row in by_end.get(member, []):
                    other_crystal = int(row["other_crystal_id"])
                    if other_crystal == crystal_id:
                        continue
                    if other_crystal not in node.next:
                        node.next.append(other_crystal)
                    if other_crystal in found:
                        continue
                    if len(found) >= CLOSURE_CRYSTALS_MOST:
                        gave_up = gave_up or {
                            "reason": f"The closure passed {CLOSURE_CRYSTALS_MOST} crystals at depth {depth + 1}, "
                                      "so the walk stopped there.",
                            "depth": depth + 1}
                        continue
                    book = int(row["grimoire_id"])
                    found[other_crystal] = _Crystal(other_crystal, depth + 1, book,
                                                    node.transfers + (1 if book != node.via_book else 0),
                                                    int(row["other"]), len(found))
                    new.append(other_crystal)
            node.walked = bool(node.followed)
        if gave_up:
            # the crystals just found are counted, unwalked, as found
            for crystal_id in new:
                found[crystal_id].shown = found[crystal_id].reached
            rows_by_id.update(source.objects([found[c].reached for c in new if found[c].reached not in rows_by_id]))
            for crystal_id in new:
                row = rows_by_id.get(found[crystal_id].reached)
                found[crystal_id].words = words(row.get("name")) + words(row.get("statement")) if row else 0
            break
        frontier = new
        depth += 1

    ordered = sorted(found.values(), key=lambda node: (node.depth, node.order))
    walked_total = sum(node.words for node in found.values())
    paged = max_chars is not None or page is not None
    titles: dict[int, str] = {}

    def entry(node: _Crystal, row: Mapping[str, Any]) -> dict[str, Any]:
        shown = brief(row) if max_chars is None else compact(row, titles, drop=("crystal_id", "crystal_size"))
        return {
            "crystal_id": node.crystal_id, "crystal_size": int(row.get("crystal_size") or 0),
            "depth": node.depth, "walked": node.walked, "transfers": node.transfers,
            "shown": shown, "reader_members": node.reader_members,
            "reader_reference": node.reader_reference, "followed": node.followed, "next": node.next,
        }

    def counted_of(nodes: Iterable[_Crystal]) -> list[dict[str, int]]:
        counted: dict[int, dict[str, int]] = {}
        for node in nodes:
            item = counted.setdefault(node.depth, {"depth": node.depth, "crystals": 0, "words": 0})
            item["crystals"] += 1
            item["words"] += node.words
        return [counted[depth] for depth in sorted(counted)]

    # A crystal whose shown object has no row (it cannot be read) is never shown, only counted.
    showable = [node for node in ordered if rows_by_id.get(node.shown or node.reached) is not None]
    unshowable = [node for node in ordered if rows_by_id.get(node.shown or node.reached) is None]
    if not paged:
        # 0.0.19: in full while inside the budget; from the first that does not fit, every crystal counted
        crystals: list[dict[str, Any]] = []
        shown_words = 0
        full = True
        rest: list[_Crystal] = []
        for node in ordered:
            row = rows_by_id.get(node.shown or node.reached)
            if full and row is not None and (not crystals or shown_words + node.words <= budget):
                shown_words += node.words
                crystals.append(entry(node, row))
                continue
            full = False
            rest.append(node)
        return {
            "object": brief(obj),
            "direction": direction,
            "reader_grimoire_id": reader,
            "start_crystal_id": start,
            "crystals": crystals,
            "counted": counted_of(rest),
            "words": {"shown": shown_words, "walked": walked_total, "budget": budget},
            "gave_up": gave_up,
        }

    # 0.0.20: pages, each nearest first inside the budget and, with max_chars, within that many characters.
    number = page or 1
    head = brief(obj) if max_chars is None else reference(obj, titles)
    frame = {
        "object": head, "direction": direction, "reader_grimoire_id": reader, "start_crystal_id": start,
        "crystals": [], "counted": counted_of(ordered),
        "words": {"shown": walked_total, "walked": walked_total, "budget": budget},
        "gave_up": gave_up, "page": number, "more": False,
    }
    items = [(entry(node, rows_by_id[node.shown or node.reached]), node.words) for node in showable]
    if max_chars is None:
        found_page = _page(items, number, budget=budget)
        books: dict[str, str] | None = None
    else:
        frame["books"] = {str(key): title for key, title in titles.items() if key == int(obj["grimoire_id"])}
        room = _room(frame, max_chars)
        book = lambda item: int(item["shown"]["grimoire_id"])  # noqa: E731
        found_page = _page(_fitted(items, room, max_chars, titles=titles, book=book), number, room=room,
                           budget=budget, titles=titles, book=book)
        books = {**frame["books"], **found_page.books}
    answer = {
        **frame,
        "crystals": found_page.items,
        "counted": counted_of(showable[found_page.end:] + unshowable),
        "words": {"shown": found_page.words, "walked": walked_total, "budget": budget},
        "more": found_page.more,
    }
    if books is not None:
        answer["books"] = books
    return answer


# --- 5. a section in book order, and the objects around one --------------------------------

def _section_brief(row: Mapping[str, Any]) -> dict[str, Any]:
    return {"section_id": int(row["section_id"]), "number": row.get("section_number") or "",
            "name": row.get("section_name") or ""}


def section(source: GraphSource, section_id: int) -> dict[str, Any]:
    """A section's own objects in reader order, where it stands, its children and its neighbours."""
    head = source.section(section_id)
    if head is None:
        raise NotFound("No such section in a book the reader may see")
    book = int(head["grimoire_id"])
    rows = source.sections(book)
    by_id = {int(row["section_id"]): row for row in rows}
    order = [int(row["section_id"]) for row, _ in contents_order(rows)]
    at = order.index(section_id) if section_id in order else -1
    children = [_section_brief(by_id[child]) for child in order
                if by_id[child].get("parent_section") is not None and int(by_id[child]["parent_section"]) == section_id]
    placed = source.section_objects(book, section_id, SECTION_OBJECTS_MOST + 1)
    truncated = len(placed) > SECTION_OBJECTS_MOST
    placed = placed[:SECTION_OBJECTS_MOST]
    found = source.objects([knowledge_id for knowledge_id, _ in placed])
    own = by_id.get(section_id, {"section_id": section_id})
    return {
        "section": {**_section_brief(own), "grimoire_id": book, "book_title": head.get("book_title") or ""},
        "path": [_section_brief(row) for row in _path(by_id, section_id)],
        "children": children,
        "previous": _section_brief(by_id[order[at - 1]]) if at > 0 else None,
        "next": _section_brief(by_id[order[at + 1]]) if 0 <= at < len(order) - 1 else None,
        "objects": [{**brief(found[knowledge_id]), "position": place}
                    for knowledge_id, place in placed if knowledge_id in found],
        "truncated": truncated,
    }


def around(source: GraphSource, obj: Mapping[str, Any], before: int, after: int) -> dict[str, Any]:
    """The objects just before and after obj in its book's reader order, across sections."""
    book = int(obj["grimoire_id"])
    start = int(obj["knowledge_id"])
    places, total = source.positions(book, [start])
    at = places.get(start)
    if at is None:
        raise NotFound("No such knowledge object in a book the reader may see")
    ids = source.window(book, max(1, at - before), at + after)
    found = source.objects([knowledge_id for knowledge_id in ids if knowledge_id != start])
    placed = list(zip(ids, range(max(1, at - before), at + after + 1)))
    return {
        "object": {**brief(obj), "position": at},
        "book_count": total,
        "before": [{**brief(found[i]), "position": p} for i, p in placed if p < at and i in found],
        "after": [{**brief(found[i]), "position": p} for i, p in placed if p > at and i in found],
    }


# --- 6. the source's pages -----------------------------------------------------------------

def _number(value: Any) -> int | float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def pages(source: GraphSource, obj: Mapping[str, Any]) -> dict[str, Any]:
    """The scans of the pages the object appeared on, and its upload's page numbers."""
    scans, numbers = source.pages(int(obj["knowledge_id"]))
    out = []
    for row in scans:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        printed = meta.get("printed_page")
        key = row.get("storage_key")
        out.append({
            "image": str(row.get("source_image_id") or ""),
            "url": f"/api/v1/storage/{quote(str(key), safe='/')}" if key else row.get("url"),
            "page": _number(meta.get("page")),
            "printed_page": printed if isinstance(printed, str) or _number(printed) is not None else None,
        })
    numbers = [n for n in numbers if _number(n) is not None] if isinstance(numbers, list) else []
    return {"object": brief(obj), "pages": out, "source_pages": numbers}


# --- 7. matching by source key --------------------------------------------------------------

def match(source: GraphSource, wanted: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Each {source_key, grimoire_id?} with its knowledge_id, or null where none or two books match."""
    rows = source.match([str(item["source_key"]) for item in wanted])
    by_key: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_key.setdefault(str(row["source_key"]), []).append(row)
    out = []
    for item in wanted:
        book = item.get("grimoire_id")
        hits = [row for row in by_key.get(str(item["source_key"]), [])
                if book is None or int(row["grimoire_id"]) == int(book)]
        out.append({"source_key": item["source_key"], "grimoire_id": book,
                    "knowledge_id": int(hits[0]["knowledge_id"]) if len(hits) == 1 else None})
    return {"objects": out}
