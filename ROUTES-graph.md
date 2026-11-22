# Routes of lane 2 (theumst-graph)

The door lane (3) builds its book tools for reading an object with its load, a crystal's members, what an object uses
and what uses it, the closures, sections and book order, and the source's pages from this file. Everything is
answered on theumst.com from its database; nothing here touches a vector.

Status: written before the code (13:10), aligned with `ROUTES-search.md` at 13:15 (same object fields, same error
codes). Every route below is built and unit tested (`backend/python/tests/test_game_graph.py`, no database). Routes
1, 2, 3 and 4 were also run read only against theumst.com's database through the service (STATUS.md). None is
registered or live until the merge and release (MERGE.md).

## Common to every route

- **Base**: `https://theumst.com` (a setting of the door). Prefix `/api/game/graph`.
- **Key**: the game's key in `X-API-Key: <key>` or `Authorization: Bearer <key>`, as for `/api/game/grimoires`.
  The key's account needs Web Demo access. A master key is refused. `X-Install-Id` is accepted as on every
  `/api/game` call and changes nothing here.
- **What the reader may see**: only active objects of books the Web Demo shows (`source_metadata.demo = true`),
  every such book. Filtered inside each query. An object of a hidden book is `404 not_found`, as one that does not
  exist.
- **Counting**: each call counts once against the key's per-minute allowance, in its own kind `graph` (MERGE.md adds
  the kind). No tighter limit.
- **Language**: English (language 1). Texts are as stored: TeX stays TeX.
- **Nothing is stored**: nothing sent to these routes is kept.
- **Deterministic**: the same request over the same books gives the same answer; ties go by book order, then
  `knowledge_id`.
- **Errors** have the game's shape, `{"code": "...", "detail": "..."}`:

| Status | code | When |
|---|---|---|
| 401 | `invalid_key` | No key, or a revoked or unknown key. |
| 403 | `demo_access_required` | The key's account has no Web Demo access. |
| 403 | `master_key_not_allowed` | A master key. |
| 404 | `not_found` | The object or section does not exist, is inactive, or is in a book the reader may not see. |
| 409 | `ambiguous` | A `source_key` without `grimoire_id` names objects in two books; send `grimoire_id`. |
| 422 | `invalid_request` | A field is missing or out of range; `errors` names the field. |
| 429 | `rate_limited` | Over the per-minute allowance; `retry_after` in seconds. |

### One object

Every list below gives objects in the shape of `ROUTES-search.md`'s hit, without the search's `found_by`, `rank`,
`scores` and `crystal_shown`, and with `section_id`:

```json
{
  "knowledge_id": 44630,
  "source_key": "scope-192f3b0ecbe61ac6a56f:41",
  "grimoire_id": 18,
  "book_title": "Topological Spaces, Part IB lecture notes (Randal-Williams, 2026)",
  "section_id": 5120,
  "label": "Proposition",
  "name": "Continuous surjections preserve connectedness",
  "statement": "If $f:X\\to Y$ is a continuous surjection and $X$ is connected, then $Y$ is connected.",
  "type": "theorem",
  "crystal_id": 30211,
  "crystal_size": 8
}
```

- `label` is the label the source prints (`Theorem 2.4.1`, `Proposition`), `""` when none. `name` is the object's
  heading, `""` when none. `source_key` is its `object_source_key`.
- `crystal_size` is the crystal's active members in every book the reader may see.

Routes that take an object take it as `knowledge_id`, or as `source_key` with an optional `grimoire_id`. Exactly one
of `knowledge_id` and `source_key`.

## 1. One object with its load

`GET /api/game/graph/object?knowledge_id=44630` or `?source_key=scope-...&grimoire_id=18`

```json
{
  "object": { /* one object */ "working": "*Proof.* ...", "working_summary": "...", "position": 193,
              "book_count": 1408 },
  "component": [
    { /* one object */ "working": "...", "working_summary": "",
      "why": "supports", "of": 44630,
      "far": false, "away": {"objects": 3, "direction": "earlier", "chapter": ""} }
  ],
  "component_truncated": false,
  "dependencies": [
    { /* one object */ "used_by": [44630, 44628] }
  ],
  "dependencies_truncated": false
}
```

- `component`: the object's support component, the object itself left out, each member in full (label, name,
  statement, workings). It is found in the object's book by the stored `supports` arrows, both ways, and the
  detached proofs, until no more are found or 24 objects are held, the object included, as the game's tutor
  stage reads it (`component_truncated`). Members come level by level: for each, what supports it, what it
  supports, its detached proofs, then what it proves.
- `why` and `of` say how a member joined: `supports` (it supports `of`), `supported_by` (`of` supports it),
  `proof_of` (it is a detached proof of `of`), `proved_by` (`of` is a detached proof of it).
- A detached proof proves the last object before it in book order, among what it uses, that is a theorem, a
  semantic theorem or a supporting lemma: the game's own rule (`star_model.gd`).
- `far` is true for a detached proof always, and for a member in another chapter (top-level section) or more than
  10 objects away in book order. `away` gives the distance in objects, `earlier` or `later`, and the chapter's name
  when it is another chapter (`""` when the same).
- `dependencies`: the union of what any member of the component, the object included, uses directly by the stored
  `dependency` arrows, less the members, in book order, with label, name and statement (no workings). `used_by`
  names the members that use it. At most 300 (`dependencies_truncated`).
- `position` and `book_count`: the object's place in its book's reader order, from 1, and the book's count.

## 2. A crystal's members, across books

`GET /api/game/graph/crystal?knowledge_id=44630` (or `source_key`), or `?crystal_id=30211`

```json
{"crystal_id": 30211, "crystal_size": 8, "members": [ { /* one object */ "default": true } ]}
```

Every active member in every book the reader may see: the crystal's preferred member first, then by book id and
book order. At most 500 (`truncated`). The search's hidden members are all here.

## 3. What an object uses, and what uses it

`GET /api/game/graph/uses?knowledge_id=44630` and `GET /api/game/graph/used-by?knowledge_id=44630`

```json
{"object": { /* one object */ }, "results": [ { /* one object */ } ], "count": 6, "truncated": false}
```

The direct `dependency` arrows of the object's own book, in book order. Each result carries its crystal, so an agent
steps to another book with route 2. At most 500.

## 4. Closures over crystals

`GET /api/game/graph/closure?knowledge_id=44630&direction=down&reader_grimoire_id=18&words=3000`

| Parameter | Rule |
|---|---|
| `knowledge_id` or `source_key` | The start. |
| `direction` | `down` (what it rests on) or `up` (what is built on it). Default `down`. |
| `reader_grimoire_id` | The reader's book. Default: the start's own book. |
| `words` | The budget, 100 to 10,000. Default 3,000. |

The walk (history A7.5 steps 6, 7 and 12, and round 3's `xbook.py`): its nodes are crystals. It starts at the
start's crystal. At each crystal it follows the arrows of the crystal's proper members (any type but `reference`) in
the reader's book; where the reader's book has none, those of the proper members in the book it came through; else
of one proper member. A crystal the reader's book holds only as a `reference` is listed and not walked below
(`walked: false`). Down follows what the followed members use; up follows what uses them.

Crystals come nearest first: by depth, then in the order found. Each is given in full while the words so far (the
name and statement of its shown object) stay inside `words`; the rest are counted by depth. Past ten times the
budget, or past 4,000 crystals, the walk gives up and says so.

```json
{
  "object": { /* one object */ },
  "direction": "down",
  "reader_grimoire_id": 18,
  "start_crystal_id": 30211,
  "crystals": [
    {"crystal_id": 30211, "crystal_size": 8, "depth": 0, "walked": true, "transfers": 0,
     "shown": { /* one object */ },
     "reader_members": [44630, 44631], "reader_reference": false,
     "followed": [44630, 44631], "next": [30188, 30107]}
  ],
  "counted": [{"depth": 4, "crystals": 61, "words": 2140}],
  "words": {"shown": 2950, "walked": 5090, "budget": 3000},
  "gave_up": null
}
```

- `shown`: the object that stands for the crystal: the reader's book's proper member if there is one; for a
  crystal the reader's book only references, that reference; else the first member the walk followed; else the
  member it reached.
- A crystal found when the walk gives up is counted, not walked: its arrows are not followed (`followed` and
  `next` empty).
- `reader_members`: the ids of the crystal's members in the reader's book, references included. The door joins
  these with the reader's marks (fully seen is known; seen and pseudoseen a reminder; unseen a gap). Empty: the
  reader's book lacks it. `reader_reference`: the reader's book holds it only as a reference.
- `followed`: the members whose arrows were followed (empty when `walked` is false). `next`: the crystals those
  arrows reach, given or counted, so an agent can cancel a branch.
- `transfers`: how many times the walk changed book on the way to it.
- `counted`: the crystals past the budget, by depth.
- `gave_up`: null, or `{"reason": "...", "depth": n}`; what was found until then is still given.

## 5. A section in book order, and the objects before and after one object

`GET /api/game/graph/section?section_id=5120`, or `?knowledge_id=44630` (or `source_key`) for that object's
section

```json
{
  "section": {"section_id": 5120, "number": "4", "name": "Connectedness", "grimoire_id": 18, "book_title": "..."},
  "path": [{"section_id": 5100, "number": "2", "name": "..."}, {"section_id": 5120, "number": "4", "name": "..."}],
  "children": [{"section_id": 5121, "number": "1", "name": "..."}],
  "previous": {"section_id": 5119, "number": "3", "name": "..."},
  "next": {"section_id": 5122, "number": "5", "name": "..."},
  "objects": [ { /* one object */ "position": 190 } ],
  "truncated": false
}
```

The section's own objects (not its subsections') in reader order, at most 400. `path` runs from the top-level
section down to this one. `previous` and `next` are its neighbours in the book's contents order, null at the ends.

`GET /api/game/graph/around?knowledge_id=44630&before=5&after=5` (each 0 to 25, default 5)

```json
{"object": { /* one object */ "position": 193 }, "book_count": 1408,
 "before": [ { /* one object */ "position": 188 } ], "after": [ { /* one object */ "position": 194 } ]}
```

The objects just before and after it in its book's reader order, across section borders, both lists in book order.

## 6. The source's pages

`GET /api/game/graph/pages?knowledge_id=44630`

```json
{"object": { /* one object */ },
 "pages": [{"image": "p0221", "url": "/api/v1/storage/books/18/pages/p0221.png", "page": 221, "printed_page": "207"}],
 "source_pages": [220, 221]}
```

The scans of the pages the object appeared on, in page order. `GET <base><url>` with the same key gives the bytes.
theumst.com holds no text of the pages: only these scans and `source_pages`, the page numbers its upload gave.

## 7. Matching objects by source key

`POST /api/game/graph/match`

```json
{"objects": [{"source_key": "scope-...", "grimoire_id": 25}]}
```

1 to 200 entries; `grimoire_id` optional in each. Answer, in the order asked:

```json
{"objects": [{"source_key": "scope-...", "grimoire_id": 25, "knowledge_id": 51234}]}
```

`knowledge_id` is null where no active object of a visible book matches, or where two books match and no
`grimoire_id` was sent. One request for the door's stand-in book.
