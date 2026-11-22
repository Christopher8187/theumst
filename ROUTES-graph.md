# ROUTES-graph: theumst.com's graph routes for the game's key

Lane 2 (`theumst-graph`), branch `agents-graph-0.0.19`. The door lane builds its book tools from this file. Kept true
as the code lands; the last section says what is built and what is not.

## Common to every route

- Base: `https://theumst.com/api/game/graph/...` (the server's address is the door's setting).
- The key: the game's key, in `X-API-Key` or `Authorization: Bearer`, as every `/api/game` call. Master keys are
  refused. The key's account needs Web Demo access, else `403 demo_access_required`.
- `X-Install-Id` may be sent, as on every `/api/game` call; a malformed one is `422 invalid_request`.
- Each call counts as one request of the kind `agent` against the key's per-minute allowance (the tier's
  `requests_per_minute`, the same number the `book` and `character` kinds get). Past it: `429 rate_limited` with
  `Retry-After` and `retry_after`.
- Only books the Web Demo shows (`grimoire.source_metadata.demo = 'true'`) and only active objects are ever read
  or returned. An object of a hidden book is `404 object_not_found`, exactly as one that does not exist.
- Answers are JSON with `Cache-Control: no-store`. Errors are `{"code", "detail", ...}` as every `/api/game` error.
- Texts are as stored: TeX stays TeX. Nothing a call sends is stored.

### An object, short form (`brief`)

Every list below gives objects in this form.

```json
{
  "id": 44630,
  "book": {"id": 18, "title": "Topological Spaces, Part IB lecture notes (Randal-Williams, 2026)"},
  "section_id": 5120,
  "type": "theorem",
  "name": "Continuous surjections preserve connectedness",
  "label": "Proposition",
  "statement": "If $f:X\\to Y$ is a continuous surjection and $X$ is connected, then $Y$ is connected.",
  "source_key": "scope-192f3b0ecbe61ac6a56f:41",
  "crystal": {"id": 30211, "size": 8}
}
```

- `name` is `knowledge.name` (null when blank). `label` is the label the source prints (`Theorem 2.4.1`,
  `Proposition`), null when blank. `source_key` is the object's `object_source_key` from its upload.
- `crystal.size` counts the crystal's active members in every visible book.

## 1. One object with its load

`GET /api/game/graph/objects/{id}`

`GET /api/game/graph/objects/by-source-key?book={book}&key={object_source_key}`, where `book` is the book's
`grimoire_id` or its source key (`Munkres-Topology`). `404 object_not_found` when no active object of a visible book
has that key; `422 invalid_request` without both.

```json
{
  "object": {"...brief...": "", "working": "*Proof.* ...", "working_summary": "...", "position": 193, "of": 1408},
  "component": {
    "members": [
      {"...brief...": "", "working": "...", "working_summary": null,
       "why": "supports", "of": 44630,
       "far": false, "away": {"objects": 3, "direction": "earlier", "chapter": null}}
    ],
    "truncated": false
  },
  "dependencies": [
    {"...brief...": "", "used_by": [44630, 44628]}
  ],
  "dependencies_truncated": false
}
```

- `component.members`: the object's support component, the object itself left out, everything in full (label,
  name, statement, workings). It is found in the object's book by the stored `supports` arrows, both ways, and the
  detached proofs, until no more are found or 24 members are held (`truncated` says the walk stopped there).
- `why` and `of` say how a member joined: `supports` (it supports `of`), `supported_by` (`of` supports it),
  `proof_of` (it is a detached proof of `of`), `proved_by` (`of` is a detached proof of it).
- A detached proof proves the last object before it in book order, among what it uses, that is a theorem, a
  semantic theorem or a supporting lemma: the game's own rule (`star_model.gd`).
- `far` is true for a detached proof always, and for a member in another chapter (top-level section) or more than
  10 objects away in book order. `away` gives the distance and, when in another chapter, that chapter's name.
- `dependencies`: the union of what any member of the component (the object included) uses directly, by the
  stored `dependency` arrows, less the members themselves, in book order, with label, name and statement only.
  `used_by` names the members that use it. At most 300; `dependencies_truncated` says when more were left out.
- `position` and `of`: the object's place in its book's reader order (1-based) and the book's count.

## 2. A crystal's members, across books

`GET /api/game/graph/objects/{id}/crystal`

```json
{"crystal": {"id": 30211, "size": 8}, "members": [{"...brief...": "", "default": true}]}
```

Every active member in every visible book, the crystal's preferred member first, then by book and book order.

## 3. What an object uses, and what uses it

`GET /api/game/graph/objects/{id}/uses` and `GET /api/game/graph/objects/{id}/used-by`

```json
{"object": {"...brief...": ""}, "uses": [{"...brief...": ""}], "truncated": false}
```

(`used_by` in place of `uses` for the second.) Direct `dependency` arrows of the object's own book, in book order.
Each one carries its crystal, so an agent steps to another book with route 2. At most 500.

## 4. Closures over crystals

`GET /api/game/graph/objects/{id}/closure?direction=down&reader_book={grimoire_id}&words=3000`

- `direction`: `down` (what it rests on) or `up` (what is built on it). Default `down`.
- `reader_book`: the reader's book. Default: the object's own book.
- `words`: the budget, 100 to 10000, default 3000.

The walk (history A7.5 steps 6, 7 and 12; round 3's `xbook.py`): nodes are crystals. It starts at the object's
crystal. At each crystal it follows the arrows of the crystal's proper members (any type but `reference`) in the
reader's book; where the reader's book has none, those of the members in the book it came through; else of one
proper member. A crystal the reader's book holds only as a `reference` is listed and not walked below
(`walked: false`). Down follows what the followed members use; up follows what uses them.

Crystals come nearest first (by depth, then in the order found). Each is given in full while the words so far
(name and statement of its shown object) stay inside `words`; the rest are counted by depth. Past ten times the
budget the walk gives up and says so.

```json
{
  "object": {"...brief...": ""},
  "direction": "down",
  "reader_book": 18,
  "start": 30211,
  "crystals": [
    {"crystal": {"id": 30211, "size": 8}, "depth": 0, "walked": true, "transfers": 0,
     "shown": {"...brief...": ""},
     "reader_members": [44630, 44631], "reader_reference": false,
     "followed": [44630, 44631], "next": [30188, 30107]}
  ],
  "counted": [{"depth": 4, "crystals": 61, "words": 2140}],
  "words": {"shown": 2950, "walked": 5090, "budget": 3000},
  "gave_up": null
}
```

- `shown`: the object that stands for the crystal: the reader's book's member if there is one, else the member the
  walk followed, else the one it reached.
- `reader_members`: the ids of the crystal's members in the reader's book (proper and references), which the door
  joins with the reader's marks. Empty: a gap in the reader's book. `reader_reference`: the reader's book holds it
  only as a reference.
- `followed`: the members whose arrows were followed. `next`: the crystals those arrows reach, listed or counted,
  so an agent can cancel a branch.
- `transfers`: how many times the walk changed book to reach it.
- `gave_up`: null, or `{"reason": "...", "depth": n}` when the walk passed ten times the budget (or the safety limit
  of 4000 crystals); what was found until then is still given.

## 5. A section in book order, and the objects before and after one object

`GET /api/game/graph/sections/{section_id}`

```json
{
  "section": {"id": 5120, "number": "4", "name": "Connectedness", "book": {"id": 18, "title": "..."},
              "path": [{"id": 5100, "number": "2", "name": "..."}, {"id": 5120, "number": "4", "name": "..."}]},
  "children": [{"id": 5121, "number": "1", "name": "..."}],
  "previous": {"id": 5119, "number": "3", "name": "..."},
  "next": {"id": 5122, "number": "5", "name": "..."},
  "objects": [{"...brief...": "", "position": 190}],
  "truncated": false
}
```

The section's own objects (not its subsections') in reader order, at most 400. `path` runs from the top-level
section down to this one. `previous` and `next` are its neighbours in the contents' order, null at the ends.

`GET /api/game/graph/objects/{id}/around?before=5&after=5` (each 0 to 25, default 5)

```json
{"object": {"...brief...": "", "position": 193}, "of": 1408,
 "before": [{"...brief...": "", "position": 188}], "after": [{"...brief...": "", "position": 194}]}
```

The objects just before and after it in its book's reader order, across section borders, nearest last in `before`
and nearest first in `after` (both in book order).

## 6. The source's pages

`GET /api/game/graph/objects/{id}/pages`

```json
{"object": {"...brief...": ""},
 "pages": [{"image": "p0221", "url": "/api/v1/storage/books/18/pages/p0221.png", "page": 221, "printed_page": "207"}],
 "source_pages": [220, 221]}
```

The scans of the pages the object appeared on, in page order. The bytes are served by
`GET /api/v1/storage/<key>` (the `url`) to the same key. theumst.com holds no text of the pages, only these scans
and `source_pages`, the page numbers its upload gave (`knowledge.source_metadata.pages`).

## 7. Matching objects by source key

`POST /api/game/graph/match` with `{"objects": [{"book": "Munkres-Topology", "key": "scope-..."}]}` (1 to 200)

```json
{"objects": [{"book": "Munkres-Topology", "key": "scope-...", "id": 51234}]}
```

`id` is null where no active object of a visible book matches. Counts as one request. For the door's stand-in book,
whose objects it matches to theumst.com's by `object_source_key`.

## Errors

| Status | code | When |
| --- | --- | --- |
| 401 | `invalid_key` | No key, or an unknown or revoked one. |
| 403 | `master_key_not_allowed` | A master key. |
| 403 | `demo_access_required` | The account has no Web Demo access. |
| 404 | `object_not_found` | No active object of a visible book by that id or key. |
| 404 | `section_not_found` | No section of a visible book by that id. |
| 422 | `invalid_request` | A parameter out of range, with `errors`. |
| 429 | `rate_limited` | Past the key's per-minute allowance of `agent` requests. |

## What is built

Nothing yet: this file is the interface, written before the code (13:15).
