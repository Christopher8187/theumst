# Routes of lane 1 (theumst-search)

The door lane (3) builds its book tools for search, neighbours, the latcher's candidates and which crystal from
this file. Everything here is answered on theumst.com. The PC sends words or an object's id and gets objects back.
No vector ever leaves theumst.com.

Status: written before the code (13:10, 22 November). Each route below says whether it is built and tested.

## Common to every route

- **Base**: `https://theumst.com` (a setting of the door). Prefix `/api/game/search`.
- **Key**: the game's key in `X-API-Key: <key>` or `Authorization: Bearer <key>`, as for `/api/game/grimoires`.
  The key's account needs Web Demo access. A master key is refused. `X-Install-Id` is accepted as on every
  `/api/game` call and changes nothing here.
- **What the reader may see**: only active objects of books the Web Demo shows (`source_metadata.demo = true`),
  every such book, as for the game's book list. Filtered inside the query.
- **Counting**: each call counts once against the key's per-minute allowance, in its own kind `search` (MERGE.md
  adds the kind). No tighter limit.
- **Language**: English (language 1), the only one the books have.
- **Nothing is stored**: no text sent to these routes is kept, logged or written anywhere.
- **Answers are deterministic** for the same request and the same books: ties are broken by `knowledge_id`. The
  latcher's prompt can keep its fixed part first and put this list after it ("keeps the original prefix").
- **Errors** have the game's shape, `{"code": "...", "detail": "..."}`:

| Status | code | When |
|---|---|---|
| 401 | `invalid_key` | No key, or a revoked or unknown key. |
| 403 | `demo_access_required` | The key's account has no Web Demo access. |
| 403 | `master_key_not_allowed` | A master key. |
| 404 | `not_found` | The object does not exist, is inactive, or is in a book the reader may not see. |
| 422 | `invalid_request` | A field is missing, too long or out of range; `errors` names the field. |
| 429 | `rate_limited` | Over the per-minute allowance; `retry_after` in seconds. |
| 503 | `search_unavailable` | Neither ranking could answer (the vector store is down). |

### One hit

Every route returns objects in this shape.

```json
{
  "knowledge_id": 3619,
  "source_key": "scope-365af70d720fc2106831:138",
  "grimoire_id": 7,
  "book_title": "Algebra",
  "label": "Exercise 10.4(b)",
  "name": "Degree of two consecutive thirteenth roots",
  "statement": "Let $\\zeta=\\zeta_{13}$. Determine the degree of $\\zeta+\\zeta^2$ over $\\mathbb{Q}$.",
  "type": "exercise",
  "crystal_id": 841,
  "crystal_size": 3,
  "crystal_shown": 1,
  "found_by": ["meaning", "words"],
  "rank": 1,
  "scores": {"meaning": 0.8312, "words": 14.07, "fused": 0.03279}
}
```

- `source_key` is the object's `object_source_key`; the door matches the build's stand-in book by it.
- `label` may be empty; `name` may be empty for older objects. `type` is the object's type in its book
  (`theorem`, `definition`, `exercise`, `proof`, ...).
- `crystal_size` is m, the crystal's active members in every book the reader may see. `crystal_shown` is how many of
  its members this answer shows: at most max(1, floor(log3 m)). A crystal of 1 to 8 members shows 1, 9 to 26 show 2,
  27 to 80 show 3. The rest are hidden; the graph lane's crystal members route lists them.
- `found_by` lists the rankings that found it: `meaning` (the books' vectors), `words` (BM25 over label, name and
  statement); the latcher's route adds `label` and `name` (a label or a name the text mentions).
- `scores.meaning` is the cosine of the query's vector and the object's stored statement vector (null when that
  ranking did not find it). `scores.words` is the BM25 score. `scores.fused` is the merged rank score,
  sum of 1/(60 + rank) over the rankings that found it.
- `rank` is the hit's place in this answer, from 1, after the crystal hiding.

### Which rankings ran

Every answer has `rankings` and `notice`:

```json
{"rankings": {"meaning": "off", "words": "used"},
 "notice": "Search by meaning is off on theumst.com until its embedding settings are set. These results come from search by words only."}
```

Each ranking is `used`, `off` (not configured: no embedding settings, or no word index yet) or `failed` (it was
configured and did not answer this time). `notice` is one plain sentence when either is not `used`, else null.
When both fail the answer is 503 `search_unavailable`.

## 1. Search

`POST /api/game/search/objects` (built: no, tested: no)

Request:

```json
{
  "name": "Degree of a sum of roots of unity",
  "statement": "Let zeta be a primitive 13th root of unity. The degree of zeta + zeta^2 over Q is 12.",
  "keywords": ["cyclotomic", "degree", "field extension"],
  "count": 10,
  "books": [7, 12]
}
```

| Field | Type | Rule |
|---|---|---|
| `name` | string | 0 to 300 characters. |
| `statement` | string | 1 to 4,000 characters. |
| `keywords` | list of strings | 0 to 20, each 1 to 60 characters. Default `[]`. |
| `count` | integer | 1 to 50. Default 10. Hits returned after the crystal hiding. |
| `books` | list of integers | Optional, 1 to 100 book ids. Only these books, among those the reader may see. Omitted means every book the reader may see. |

What it does: the name and statement become one text the way the pipeline built each object's stored text
(`name. statement`, the instruction the pipeline put before every text in front). theumst.com turns it into a vector
through its embedding settings (OpenRouter, `qwen/qwen3-embedding-4b`), and searches the store and model the books'
vectors were made with (`embedding_model`: `Qwen/Qwen3-Embedding-4B`, 2,560 numbers). Name, statement and keywords
also go to the word index (BM25). The two rankings are merged by rank, then grouped by crystal with the hiding.

Answer:

```json
{
  "results": [ /* hits, as "One hit" */ ],
  "count": 10,
  "rankings": {"meaning": "used", "words": "used"},
  "notice": null
}
```

## 2. Neighbours

`GET /api/game/search/neighbours?knowledge_id=3619&count=10` (built: no, tested: no)
or `GET /api/game/search/neighbours?source_key=scope-365af70d720fc2106831:138&count=10`

| Parameter | Rule |
|---|---|
| `knowledge_id` or `source_key` | Exactly one. The object whose neighbours are wanted. |
| `count` | 1 to 50. Default 10. |

The nearest objects of any book the reader may see, by the object's own stored statement vector. Needs no
embedding settings: nothing is turned into a vector. The object itself is left out. No crystal hiding: a neighbour
list is what is nearest, and each hit still says its crystal and its size.

Answer:

```json
{
  "object": { /* the asked object, as a hit without rank, found_by and scores */ },
  "results": [ /* hits; found_by ["meaning"]; scores.meaning the cosine */ ],
  "count": 10
}
```

`404 not_found` when the object is not visible. `409 no_vector` when it has no stored statement vector.

## 3. The latcher's candidates

`POST /api/game/search/latcher-candidates` (built: no, tested: no)

```json
{
  "text": "By Lemma 2.1 the map is continuous, and compactness of [0,1] gives a maximum ...",
  "grimoire_id": 7,
  "count": 30
}
```

| Field | Type | Rule |
|---|---|---|
| `text` | string | A note's text or a found problem. 1 to 20,000 characters. Never stored. |
| `grimoire_id` | integer | Optional. The book the note is about: labels it mentions ("Lemma 2.1") are looked up there. |
| `count` | integer | 1 to 100. Default 30. |

What it does, in order, all on theumst.com:

1. **Labels** the text mentions, like "Theorem 3.2", "Lemma 2.1", "Exercise 10.4(b)", "Definition 1.3", matched to
   the labels of `grimoire_id`'s objects, word for word with the label's own prefix ("Lemma 2.1" is not "Theorem
   2.1").
2. **Names** the text mentions: an object of any visible book whose whole name appears in the text.
3. **Search**: the text is cut into pieces of a few sentences each (at most 8), and each piece is searched by
   meaning and by words as in route 1.
4. Merged by rank (labels and names first), grouped by crystal with the same hiding as route 1.

Answer: as route 1, and each hit has `mentions`, the words of the text that named it (`[]` when found by search
only).

```json
{
  "results": [ { /* hit */ "found_by": ["label"], "mentions": ["Lemma 2.1"] } ],
  "count": 30,
  "rankings": {"meaning": "used", "words": "used"},
  "notice": null
}
```

## 4. Which crystal

`POST /api/game/search/crystals` (built: no, tested: no)

How an object kept on the PC is matched to a crystal. Nothing of it is stored.

```json
{
  "name": "Compact image of a continuous map",
  "statement": "The continuous image of a compact space is compact.",
  "keywords": [],
  "count": 5
}
```

| Field | Type | Rule |
|---|---|---|
| `name` | string | 0 to 300 characters. |
| `statement` | string | 1 to 4,000 characters. |
| `keywords` | list of strings | 0 to 20, each 1 to 60 characters. Default `[]`. |
| `count` | integer | 1 to 20 crystals. Default 5. |

Answer: crystals, best first. A crystal's place is that of its best member in the merged ranking. Each shows at most
max(1, floor(log3 m)) members, its best matches.

```json
{
  "crystals": [
    {
      "crystal_id": 2210,
      "crystal_size": 9,
      "rank": 1,
      "found_by": ["meaning", "words"],
      "scores": {"meaning": 0.9412, "words": 21.5, "fused": 0.03279},
      "members": [ /* hits, at most max(1, floor(log3 m)) */ ]
    }
  ],
  "count": 5,
  "rankings": {"meaning": "used", "words": "used"},
  "notice": null
}
```

## What the door should know

- With the embedding settings empty (today), routes 1, 3 and 4 answer by words and labels and say so in `notice`.
  Route 2 works without them.
- Until the word index is filled on the server (MERGE.md), `rankings.words` is `off` and the search answers by
  meaning only, or 503 when meaning is off too.
- A crystal's hidden members are not lost: the graph lane's crystal members route lists them all.
