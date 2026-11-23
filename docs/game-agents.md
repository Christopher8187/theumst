# Game agents' reads

Since 0.0.19 UMST's agents ask theumst.com about every book through thirteen routes for the game's key: four under `/api/game/search` (`routers/game_search.py`, `services/game_search.py`) and nine under `/api/game/graph` (`routers/game_graph.py`, `services/game_graph.py`). The agents' tools, the door, run on the reader's PC and keep nothing about books: whatever reaches across books is asked here and answered here. The PC sends words or an object's id and gets back a short list of objects. No vector ever leaves theumst.com. [Game accounts](game-accounts.md) owns the game's keys, characters, books and notes; this page owns these thirteen routes.

0.0.20 adds parameters, each optional: [`max_chars` and `page`](#pages-and-a-cap-on-characters) on five graph routes, the whole support component on the object route, [`objects` and `leave_out`](#closures-over-crystals) on the closure, `reader_grimoire_id` on the crystal route and `grimoire_id` on neighbours. A request without them answers as in 0.0.19, with one exception: neighbours by a `source_key` that two books share now answers 409 instead of the first book's neighbours.

## Common to every route

- **Key**: the game's key, or any other active regular key of the account, in `X-API-Key` or `Authorization: Bearer`, as for the game's books. The account needs Web Demo access. A master key is refused. `X-Install-Id` is checked as on every `/api/game` call and changes nothing here.
- **What the reader may see**: only active objects of books the Web Demo shows (`grimoire.source_metadata.demo = true`), every such book. The filter is inside each query, PostgreSQL's and Qdrant's; no request reads every row of every book. An object of a hidden book answers as one that does not exist.
- **Counting**: each call counts once in the key's per-minute allowance, the tier's `requests_per_minute` (600 for `standard`), in a kind of its own: `search` for the search routes, `graph` for the graph routes, beside `book` and `character` (migration 018). No tighter limit applies. `api_usage_daily` counts them by key, day and kind.
- **Language**: English (language 1), the only one the books have. Texts are as stored, TeX left as TeX.
- **Nothing is stored**: no text sent to these routes is kept, logged or written anywhere. The embedding provider's answer is never passed on.
- **Deterministic**: the same request over the same books gives the same answer. Search ties go by `knowledge_id`, graph ties by book order, then `knowledge_id`. The latcher's prompt can therefore keep its fixed part first and put the candidates after it.
- **Answers** are JSON with `Cache-Control: no-store`. Errors have the game's shape, `{"code", "detail"}`, and the listed fields:

| Status | Code | Routes | When |
| --- | --- | --- | --- |
| 401 | `invalid_key` | all | no key, or an unknown or revoked one |
| 403 | `master_key_not_allowed` | all | a master key |
| 403 | `demo_access_required` | all | the account has no Web Demo access; nothing counted |
| 404 | `not_found` | neighbours, graph | the object or section does not exist, is inactive, or is in a book the reader may not see |
| 409 | `no_vector` | neighbours | the object has no stored statement vector |
| 409 | `ambiguous` | neighbours, graph | a `source_key` without `grimoire_id` names objects in two books; send `grimoire_id` |
| 422 | `invalid_request` | all | a field missing, too long or out of range, or a malformed `X-Install-Id`; `max_chars` too small for even the answer's frame and one item, which `detail` says with the least that fits; `errors` names the field |
| 429 | `rate_limited` | all | over the key's minute; `retry_after` and `Retry-After` |
| 503 | `search_unavailable` | search, which crystal, latcher | neither ranking could run; `detail` says why in one plain sentence |

The key is checked in [game accounts'](game-accounts.md#errors) order: 401, a master key, Web Demo access, the minute. Before 0.0.19 every path here answers 404 `{"detail": "API route not found"}`.

## One object

The routes give objects in one flat shape. A search hit:

```json
{"knowledge_id": 3619, "source_key": "scope-365af70d720fc2106831:138", "grimoire_id": 5,
 "book_title": "Algebra (Artin), Kaic4 test branch", "label": "Exercise 10.4(b)", "name": "Degree of two consecutive thirteenth roots",
 "statement": "Let $\\zeta=\\zeta_{13}$. Determine the degree of $\\zeta+\\zeta^2$ over $\\mathbb{Q}$.",
 "type": "exercise", "crystal_id": 841, "crystal_size": 1, "crystal_shown": 1,
 "found_by": ["meaning", "words"], "rank": 1, "scores": {"meaning": 0.8312, "words": 14.07, "fused": 0.03279}}
```

- `source_key` is the object's `object_source_key`, the same key in a build's own copy of the book. The [match route](#matching-by-source-key) turns keys into theumst.com's ids; in 0.0.20 nothing calls it. `label` is the label the source prints (`Theorem 2.4.1`), `name` the object's heading, each `""` when it has none. `type` is the object's type in its book (`theorem`, `definition`, `exercise`, `proof`, ...).
- `crystal_size` is m, the crystal's active members in every book the reader may see. `crystal_shown` is how many of its members this answer shows: at most max(1, floor(log3 m)), so a crystal of 1 to 8 members shows 1, 9 to 26 show 2, 27 to 80 show 3. The others are hidden from a search; the graph's crystal route lists them all.
- `found_by` lists the rankings that found the hit: `meaning` (the books' vectors), `words` (BM25 over label, name and statement) and, on the latcher's route, `label` and `name`. `scores.meaning` is the cosine of the query's vector and the object's stored statement vector, `scores.words` the BM25 score, each null when that ranking did not find it, and `scores.fused` the merged score, the sum of 1/(60 + rank) over the rankings that found it. `rank` is the hit's place in the answer, from 1, after the crystal hiding.

The graph routes give the same object without `crystal_shown`, `found_by`, `rank` and `scores`, and with `section_id`.

## Search

Search by meaning turns the words into a vector through theumst.com's embedding settings (`EMBEDDING_API_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL`: OpenRouter's `qwen/qwen3-embedding-4b`) and searches the store of the model the books' vectors were made with, read from `embedding_model` (`Qwen/Qwen3-Embedding-4B`, 2,560 numbers, the Qdrant collection `knowledge-qwen3-embedding-4b`), not the configured `QDRANT_COLLECTION`. The configured model counts as the books' model when the names after their last `/` agree, case ignored; another model turns search by meaning off. The vector is used on theumst.com and never returned.

The query's text is built as the pipeline built each stored text: `name. statement` with spaces collapsed, after the instruction line the pipeline put before every text it embedded, `Instruct: Given a mathematical statement, retrieve statements of the same result\nQuery:` (`game_search.QUERY_INSTRUCTION`, joined with nothing between). The instruction must always come first. Measured on 22 November 2026 on 20 stored statements of 20 books: with the instruction first, OpenRouter's vectors match the stored ones at cosine 0.99978 to 0.99989 (mean 0.99986); the plain `name. statement` gives about 0.93 (0.933 to 0.942). Keywords join only the search by words, since the stored texts have none.

Search by words is BM25 over each object's label, name and statement in the [word index](architecture/data.md): since 0.0.20 each upload writes its book's words and each submission its object's, and `python -m scripts.fill_word_index` fills the books uploaded before ([operations](operations.md#word-index)). The two rankings merge by reciprocal rank, then the crystal hiding keeps a crystal's best-ranked members.

Every search answer says which rankings ran:

```json
{"rankings": {"meaning": "off", "words": "used"},
 "notice": "Search by meaning is off on theumst.com until its embedding settings are set. These results come from search by words only."}
```

Each ranking is `used`, `off` (not configured: no embedding settings or another model, or no word index yet) or `failed` (configured, and it did not answer this time). `notice` is plain sentences when either is not `used`, else null. When neither is `used` the answer is 503 `search_unavailable`, except on the latcher's route when the text names a label of its book.

### Objects

`POST /api/game/search/objects`

```json
{"name": "Degree of a sum of roots of unity",
 "statement": "Let zeta be a primitive 13th root of unity. The degree of zeta + zeta^2 over Q is 12.",
 "keywords": ["cyclotomic", "degree", "field extension"], "count": 10, "books": [7, 12]}
```

| Field | Rule |
| --- | --- |
| `name` | 0 to 300 characters; default `""` |
| `statement` | 1 to 4,000 characters, not blank |
| `keywords` | 0 to 20, each 1 to 60 characters; default `[]` |
| `count` | 1 to 50; default 10: hits returned after the crystal hiding |
| `books` | optional, 1 to 100 book ids: only these, among the books the reader may see |

The answer is `{"results": [hit], "count", "rankings", "notice"}`. With `books` naming only books the reader may not see, `results` is empty and `notice` says so.

### Neighbours

`GET /api/game/search/neighbours?knowledge_id=3619&count=10`, or `?source_key=...&grimoire_id=7&count=10`

Exactly one of `knowledge_id` and `source_key`; `grimoire_id` (0.0.20) names the book of a `source_key`, which two books may share: without it such a key answers 409 `ambiguous`. `count` 1 to 50, default 10. The nearest objects of any book the reader may see, by the object's own stored statement vector, the object itself left out. Nothing is turned into a vector, so it needs no embedding settings and no word index. No crystal hiding: a neighbour list is what is nearest, and each hit still gives its crystal and size.

```json
{"object": { /* the object: a hit's fields up to crystal_size */ },
 "results": [ /* hits without crystal_shown; found_by ["meaning"]; scores.meaning the cosine */ ], "count": 10}
```

### The latcher's candidates

`POST /api/game/search/latcher-candidates`

```json
{"text": "By Lemma 2.1 the map is continuous, and compactness of [0,1] gives a maximum ...",
 "grimoire_id": 7, "count": 30}
```

`text` is a note's text or a found problem, 1 to 20,000 characters, never stored. `grimoire_id` is optional: the book whose labels the text may cite. `count` is 1 to 100, default 30. In order:

1. **Labels** the text cites, such as "Theorem 3.2", "Lemma 2.1" or "Exercise 10.4(b)", matched to the labels of `grimoire_id`'s objects with their prefix, so "Lemma 2.1" is not "Theorem 2.1".
2. **Names** the text contains: an object of any visible book whose whole name appears in the text, a one-word name only from five letters, longer names first, then among names of one length those whose label, name and statement share most words with the text (BM25), at most 256. It needs the word index. Before 0.0.20 the 256 were the first in the word index's order, so a common name such as "Group" gave the oldest books' objects.
3. **Search**: the text is cut at sentence ends into at most 8 pieces covering it, and each piece is searched by meaning and by words, all pieces in one call to the embedding provider.
4. The lists merge by rank, labels and names first, with the crystal hiding.

The answer is that of objects, and each hit adds `mentions`: the label as the text wrote it (`"Lemma 2.1"`) or the name in index form, lower case, words only (`"heine borel theorem"`), `[]` when only the search found it.

### Which crystal

`POST /api/game/search/crystals`, how an object kept on the reader's PC is matched to a crystal. It takes `name`, `statement` and `keywords` as objects does, and `count` 1 to 20 crystals, default 5. Crystals come best first, a crystal's place that of its best member in the merged ranking, each with at most max(1, floor(log3 m)) members, its best matches:

```json
{"crystals": [{"crystal_id": 2210, "crystal_size": 9, "rank": 1, "found_by": ["meaning", "words"],
               "scores": {"meaning": 0.9412, "words": 21.5, "fused": 0.03279}, "members": [ /* hits */ ]}],
 "count": 5, "rankings": {"meaning": "used", "words": "used"}, "notice": null}
```

## Graph reads

Every graph route reads PostgreSQL only and touches no vector. A route that takes an object takes `knowledge_id`, or `source_key` with an optional `grimoire_id`, exactly one of the two. Arrows are the stored `dependency` and `supports` rows of `knowledge_graph_edge`, never the legacy `relation` table ([data architecture](architecture/data.md)). A graph object:

```json
{"knowledge_id": 44630, "source_key": "scope-d515e2c8d1b387c583d7:15", "grimoire_id": 18,
 "book_title": "Topological Spaces, Part IB lecture notes (Randal-Williams, 2026)", "section_id": 1731,
 "label": "Proposition", "name": "Continuous surjections preserve connectedness",
 "statement": "If $f:X\\to Y$ is a continuous surjection and $X$ is connected, then $Y$ is connected.",
 "type": "theorem", "crystal_id": 26895, "crystal_size": 8}
```

### Pages and a cap on characters

Since 0.0.20 the object, crystal, uses, used-by and closure routes take `max_chars` (2,000 to 200,000) and `page` (1 to 100,000, default 1). Without either, each answers as in 0.0.19. With either:

- The answer comes a page at a time. Every page has `page` and `more` (a later page exists); a page past the last is empty with `more: false`. Pages follow each other: page 2 starts where page 1 stopped.
- With `max_chars`, the answer is at most that many characters as `json.dumps(answer, ensure_ascii=False)` counts them, what the door hands an agent. Its shape is then compact: a book's title is given once, under `"books": {"<grimoire_id>": "<title>"}`, and left out of each object; the object asked about is only named (`knowledge_id`, `source_key`, `grimoire_id`, `label`, `name`, `type`, `crystal_id`), except on the object route's page 1; a closure crystal's `shown` and a crystal's members leave out `crystal_id` and `crystal_size`, which the crystal itself gives.
- An item too big for a page alone is shortened: its working, then its working's summary, then its statement are cut, each ending in ` [cut]`, then its lists; `"cut": ["working", ...]` names what was cut. A `max_chars` too small for even that answers 422 with the least that fits.
- Without `max_chars`, a page holds at most 500 crystal members, uses or used-by results, or 100 items of an object's load, and a closure page holds what fits the word budget.

A list of ids is sent as repeated parameters (`objects=1&objects=2`) or with commas (`objects=1,2`).

### One object with its load

`GET /api/game/graph/object?knowledge_id=44630`, or `?source_key=...&grimoire_id=18`: what the tutor loads at a claim.

```json
{"object": { /* one object */ "working": "*Proof.* ...", "working_summary": "...", "position": 193, "book_count": 1408 },
 "component": [{ /* one object */ "working": "...", "working_summary": "", "why": "supports", "of": 44630,
                "far": false, "away": {"objects": 3, "direction": "earlier", "chapter": ""}}],
 "component_truncated": false,
 "dependencies": [{ /* one object */ "used_by": [44630, 44628]}], "dependencies_truncated": false}
```

- `component`: the object's support component, the object itself left out, each member with its workings. It is found in the object's book by the `supports` arrows both ways and the detached proofs, level by level, until no more are found or 24 objects are held with the object, as the game's tutor stage reads it (`component_truncated`). `why` and `of` say how a member joined: `supports` (it supports `of`), `supported_by`, `proof_of` (it is a detached proof of `of`) or `proved_by`.
- A detached proof proves the last object before it in book order, among what it uses, that is a theorem, a semantic theorem or a supporting lemma: the game's own rule.
- `far` is true for a detached proof always, and for a member in another chapter (top-level section) or more than 10 objects away in book order. `away` gives the distance in objects, `earlier` or `later`, and the other chapter's name, `""` for the same chapter.
- `dependencies`: what any member of the component, the object included, uses directly by the `dependency` arrows, less the members, in book order, without workings; `used_by` names the members that use it. At most 300 (`dependencies_truncated`).
- `position` and `book_count`: the object's place in its book's reader order, from 1, and the book's count.

With `max_chars` or `page` (0.0.20) the load is the whole support component, not 24 objects: up to 2,000 members, found as above, then what they use, all in pages. Page 1 gives the object in full (with `max_chars`, cut to at most half of it if it must be), later pages name it. Each page gives members first, then dependencies, and adds `component_size`, `dependencies_size` (all of them, on every page) and `later: {"component": n, "dependencies": m}`, how many are on later pages. `component_truncated` is true only past 2,000 members; `dependencies_truncated` is false.

### A crystal's members

`GET /api/game/graph/crystal?crystal_id=26895`, or by one member's `knowledge_id` or `source_key`: `{"crystal_id", "crystal_size", "members": [object with "default"], "truncated"}`. Every active member in every book the reader may see: the crystal's preferred member first, then by book and book order, at most 500. The search's hidden members are all here. With `reader_grimoire_id` (0.0.20) the reader's book's members come right after the preferred one. With `max_chars` or `page`, every member comes in pages of at most 500, in the same order, and `truncated` equals `more`.

### What an object uses, and what uses it

`GET /api/game/graph/uses` and `GET /api/game/graph/used-by`, by object: `{"object", "results": [object], "count", "truncated"}`. The direct `dependency` arrows of the object's own book, in book order, at most 500. Each result carries its crystal, so an agent steps to another book through the crystal route. With `max_chars` or `page`, all of them come in pages of at most 500; `count` is the page's count and `truncated` equals `more`.

### Closures over crystals

`GET /api/game/graph/closure?knowledge_id=44630&direction=down&reader_grimoire_id=18&words=3000`

`direction` is `down` (what it rests on, the default) or `up` (what is built on it); `reader_grimoire_id` the reader's book, by default the start's own; `words` the budget, 100 to 10,000, default 3,000.

The walk's nodes are crystals, starting at the start's crystal. At each crystal it follows the arrows of the crystal's proper members (any type but `reference`) in the reader's book; where the reader's book has none, those in the book it came through; else those of one proper member. A crystal the reader's book holds only as a `reference` is listed and not walked below. Down follows what the followed members use, up what uses them. Crystals come nearest first, by depth, then in the order found. Each is given in full while the words so far (the name and statement of its shown object, a formula counted as one word) stay inside the budget; the rest are counted by depth. Past ten times the budget, or 4,000 crystals, the walk gives up and says so, keeping what it found.

```json
{"object": { /* one object */ }, "direction": "down", "reader_grimoire_id": 18, "start_crystal_id": 26895,
 "crystals": [{"crystal_id": 26895, "crystal_size": 8, "depth": 0, "walked": true, "transfers": 0,
               "shown": { /* one object */ }, "reader_members": [44630, 44631], "reader_reference": false,
               "followed": [44630, 44631], "next": [30188, 30107]}],
 "counted": [{"depth": 4, "crystals": 61, "words": 2140}],
 "words": {"shown": 2950, "walked": 5090, "budget": 3000}, "gave_up": null}
```

- `shown` stands for the crystal: the reader's book's proper member if there is one; for a crystal the reader's book only references, that reference; else the first member the walk followed; else the member it reached.
- `reader_members` are the crystal's members in the reader's book, references included; empty when the reader's book lacks it. The door joins them with the reader's marks on the PC: fully seen is known, seen and pseudoseen get a reminder, unseen is a gap. `reader_reference` says the reader's book holds it only as a reference.
- `followed` are the members whose arrows were followed, `next` the crystals those arrows reach, so an agent can cancel a branch; both are empty for a crystal not walked. `transfers` counts the changes of book on the way to it. `gave_up` is null or `{"reason", "depth"}`.

Since 0.0.20:

- `objects` (1 to 100 knowledge ids) in place of `knowledge_id` or `source_key` starts one walk from all of them: their crystals are all at depth 0, so a crystal several of them rest on is found and counted once, the shared closure of a set of questions. The answer has `objects` and `start_crystal_ids` (lists) in place of `object` and `start_crystal_id`. An id that is not shown answers 404 naming it. `reader_grimoire_id` defaults to the first object's book.
- `leave_out` (up to 500 crystal ids) cancels branches: such a crystal is never entered and is missing from every `next`, so what only it led to is left out, while what a kept crystal leads to stays. A start's own crystal is never left out. The answer repeats them in `left_out`. Commas keep a long list inside the address's length limit.
- With `page`, page 2 holds the crystals nearest after page 1's, again inside the word budget, and so on; `counted` counts the crystals after the page. With `max_chars` each page also stays inside that many characters.
- The walk reads a crystal's members only in the reader's book and in the books it came through, else the crystal's first proper member and first reference, so a closure costs what those books hold, not what every book holds. The crystal route reads its members a page at a time.

### A section, and the objects around one

`GET /api/game/graph/section?section_id=1731`, or by one of its objects:

```json
{"section": {"section_id": 1731, "number": "001", "name": "2.1 Connectedness", "grimoire_id": 18, "book_title": "..."},
 "path": [{"section_id": 1726, "number": "002", "name": "2 Connectedness and components"},
          {"section_id": 1731, "number": "001", "name": "2.1 Connectedness"}], "children": [],
 "previous": { /* a section, or null */ }, "next": { /* a section, or null */ },
 "objects": [{ /* one object */ "position": 190}], "truncated": false}
```

The section's own objects, not its subsections', in reader order, at most 400. `path` runs from the top-level section down to this one, and `previous` and `next` are its neighbours in contents order, null at the ends.

`GET /api/game/graph/around?knowledge_id=44630&before=5&after=5` (each 0 to 25, default 5) gives `{"object", "book_count", "before", "after"}`: the objects just before and after it in its book's reader order, across section borders, both lists in book order, each object with its `position`.

### The source's pages

`GET /api/game/graph/pages?knowledge_id=44630`:

```json
{"object": { /* one object */ },
 "pages": [{"image": "p0221", "url": "/api/v1/storage/books/18/pages/p0221.png", "page": 221, "printed_page": "207"}],
 "source_pages": [220, 221]}
```

The scans of the pages the object appeared on, in page order; `GET <url>` with the same key gives the bytes, as for the game's books. theumst.com holds no text of a page, only these scans and `source_pages`, the page numbers its upload gave.

### Matching by source key

`POST /api/game/graph/match` with `{"objects": [{"source_key": "scope-...", "grimoire_id": 25}]}`, 1 to 200 entries, `grimoire_id` optional in each. The answer keeps the order asked, `{"objects": [{"source_key", "grimoire_id", "knowledge_id"}]}`; `knowledge_id` is null where no active object of a visible book matches, or where two books match and no `grimoire_id` was sent. In 0.0.20 nothing in the door or the game calls this route: the door sends `knowledge_id`, or `source_key` with `grimoire_id`, to each route itself. It stays for a build that keeps its own copy of a book.

## Checking migration 018

Migration 018 widens the two kind checks and adds three partial indexes ([data architecture](architecture/data.md)). It changes no row, and the runner marks it by the three indexes. Read-only queries for a database after the migration:

```sql
BEGIN TRANSACTION READ ONLY;
SELECT conrelid::regclass, conname, pg_get_constraintdef(oid) FROM pg_constraint
WHERE conname IN ('api_rate_window_kind_check', 'api_usage_daily_kind_check') ORDER BY 1;
SELECT indexrelid::regclass, pg_get_indexdef(indexrelid) FROM pg_index
WHERE indexrelid::regclass::text IN ('knowledge_active_crystal_idx', 'knowledge_active_source_key_idx', 'grimoire_hidden_idx');
SELECT kind, count(*) FROM api_usage_daily GROUP BY kind ORDER BY kind;
COMMIT;
```

Both checks read `CHECK ((kind = ANY (ARRAY['book'::text, 'character'::text, 'search'::text, 'graph'::text])))`. The three indexes read `ON public.knowledge USING btree (knowledge_crystal_id) WHERE is_active`, `ON public.knowledge USING btree (source_key) WHERE is_active` and `ON public.grimoire USING btree (grimoire_id) WHERE ((source_metadata ->> 'demo'::text) IS DISTINCT FROM 'true'::text)`. The usage counts are those from before until a key calls the new routes.
