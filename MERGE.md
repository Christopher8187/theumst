# Lane 1 (theumst-search): what the merge and the release must do

The lane's branch is `agents-search-0.0.19`. Everything below is wanted in shared files this lane does not own, or
is an operation on theumst.com. The lane's code is built as if each change were in.

## 1. Register the router (`backend/python/app/main.py`)

```python
from .routers import (admin, api_keys, auth, content, demo, frontend, game, game_search, health, news,
                      public_api, superadmin, users)
...
    application.include_router(game.router)
    application.include_router(game_search.router)   # 0.0.19: /api/game/search
    game.install_error_handlers(application)
```

`game_search.router` has the prefix `/api/game/search` and the dependencies `_no_store` and `game._install_id`.
`game.install_error_handlers` already covers it: its `GameError` handler is global and its validation handler
takes every path under `/api/game/`. Nothing in `routers/game.py` changes; `game_search` imports `GameError` and
`_install_id` from it.

## 2. The rate-limit kind `search`

Each call counts once in the key's per-minute allowance of its own kind, `search`, with the same
`requests_per_minute` as `book` and `character` (no tighter limit, on his word). The graph lane asks for a kind
`graph` the same way; one migration can add both.

- `backend/python/app/dependencies.py`: `API_REQUEST_KINDS = ("book", "character", "search")` (plus `"graph"`).
- A reviewed migration, for example `backend/sql/018_game_agent_kinds.sql`, registered in
  `app/reviewed_migrations.py` with its sha256. The constraints' names on COM (read 22 November):
  `api_rate_window_kind_check` and `api_usage_daily_kind_check`.

```sql
ALTER TABLE api_rate_window DROP CONSTRAINT IF EXISTS api_rate_window_kind_check;
ALTER TABLE api_rate_window ADD CONSTRAINT api_rate_window_kind_check
    CHECK (kind IN ('book', 'character', 'search', 'graph'));
ALTER TABLE api_usage_daily DROP CONSTRAINT IF EXISTS api_usage_daily_kind_check;
ALTER TABLE api_usage_daily ADD CONSTRAINT api_usage_daily_kind_check
    CHECK (kind IN ('book', 'character', 'search', 'graph'));
```

- `backend/sql/schema.sql` lines 205 and 214: the same lists.
- Nothing else reads the kind: `dependencies.py` is the only code that writes or reads `api_rate_window` and
  `api_usage_daily` (checked 22 November). Until the kind is merged, `authenticate_api_key(kind="search")` raises
  `ValueError`, so the router must not be registered without it.

## 3. Indexes for the million-books rule (same migration, recommended)

Without them the routes are correct and fast enough for 28 books (a scan of 68,324 rows), but they do not stay
proportional as books are added.

```sql
-- A crystal's size in a search (game_search.crystal_sizes); the graph lane's crystal members use it too.
CREATE INDEX IF NOT EXISTS knowledge_active_crystal_idx ON knowledge (knowledge_crystal_id) WHERE is_active;
-- Neighbours by source_key (game_search.neighbours); the graph lane's ?source_key= uses it too.
CREATE INDEX IF NOT EXISTS knowledge_active_source_key_idx ON knowledge (source_key) WHERE is_active;
-- The hidden books a Qdrant filter leaves out (game_search.book_scope).
CREATE INDEX IF NOT EXISTS grimoire_hidden_idx ON grimoire (grimoire_id)
    WHERE (source_metadata->>'demo') IS DISTINCT FROM 'true';
```

Markers for `reviewed_migrations.py`: the three relations. If the graph lane's MERGE.md names the same indexes
under other names, keep one of each.

## 4. The embedding settings (only he sets them)

`compose.deploy.yml` already passes `EMBEDDING_API_URL`, `EMBEDDING_API_KEY` and `EMBEDDING_MODEL` to the
backend. With `EMBEDDING_MODEL=qwen/qwen3-embedding-4b` the routes match it to the books' model row
(`Qwen/Qwen3-Embedding-4B`) by the name after the last `/`, case ignored, and search the store that row names
(`knowledge-qwen3-embedding-4b`, 2,560 numbers), not `QDRANT_COLLECTION`. `QDRANT_COLLECTION` and
`QDRANT_VECTOR_SIZE` stay as they are: the admin search and `embed_query` still use them, and this lane does not
use `embed_query` (it checks the configured size, 1,024, which the books' vectors are not).

The embedding check (the coordinator's, 22 November): `scripts/dump_vector_sample.py` on COM and
`scripts/compare_embeddings.py` on the PC, with the commands in `STATUS.md`. The route sends
`QUERY_INSTRUCTION + "name. statement"`, the form the pipeline embedded every stored text in. If the check finds
that another form matches, `game_search.QUERY_INSTRUCTION` / `query_text` must change before the release.

## 5. Fill the word index on theumst.com (the release)

The word index is a new Qdrant collection, `knowledge-words-bm25` (sparse vectors with Qdrant's IDF modifier, kept
on disk). It changes nothing in `knowledge-qwen3-embedding-4b`. Order:

1. Snapshot Qdrant before the release (the brief's "snapshot the vector store before its first change").
2. Deploy 0.0.19 and apply the migration.
3. Fill it, in the backend container on COM (from `/var/www/theumst.com`):

   ```
   sudo docker compose --env-file .env -f compose.deploy.yml exec -T backend python -m scripts.fill_word_index
   sudo docker compose --env-file .env -f compose.deploy.yml exec -T backend python -m scripts.fill_word_index --check
   ```

   The first creates the collection and its payload indexes (`knowledge_id`, `grimoire_id` integer, `name_key`
   keyword), writes one point for each of the 68,324 active objects in 1,000-object batches (memory stays flat),
   deletes points of inactive objects, and prints `68,324 objects in 28 books; ...; 0 stale deleted; N terms an
   object on average (AVGDL 18.0)`. Running it twice changes nothing. Expected to take a minute or two on one
   processor. `--check` must print `0 missing; 0 stale found` and exit 0. If its average is far from 18, update
   `word_index.AVGDL` in a later release (a fixed constant, so no point is ever rewritten when books arrive).
4. After each later book upload: `python -m scripts.fill_word_index --book <grimoire_id>` (until an upload fills
   its own words: a later change to `services/book_ingestion.py` could call the same per-book fill after the
   vectors are indexed). Before that run, the new book is found by meaning only; a re-uploaded book keeps its old
   words, and the search drops any hit whose object is no longer active.

Until the index is filled, the routes answer `rankings.words = "off"`: by meaning only when the embedding settings
are in, otherwise 503 `search_unavailable` for search and which-crystal (neighbours need neither).

## 6. Documents to write

- `docs/game-search.md` (new), from `ROUTES-search.md`: the four routes, their shapes and errors, the crystal
  hiding, the rankings and notice, what is stored (nothing).
- `docs/game-accounts.md`: the kind `search` and the new routes beside the game's others.
- `docs/architecture/backend.md`: `routers/game_search.py`, `services/game_search.py`, `services/word_index.py`;
  `discovery.find_neighbors` now bounded (the source's own projections, a Qdrant filter, the hits' rows).
- `docs/architecture/data.md`: the Qdrant collection `knowledge-words-bm25` (what it holds: ids and the name
  key, no other text; hidden books included, filtered at query time); the three indexes.
- `docs/security.md`: four routes for any regular key with Web Demo access; master keys refused; no text stored or
  logged; the provider's answer never echoed.
- `docs/operations.md`: the fill script's first run, its `--check`, and the per-book run after an upload; the
  word collection in the Qdrant snapshot; the embedding check's scripts.
- `backend/README.md` and `backend/python/tests/README.md`: the new scripts and the three test files
  (`test_game_search.py`, `test_word_index.py`, `test_embedding_check.py`), and the rewritten `test_discovery.py`.
- `CONTEXT.md`: "word index" if the glossary keeps such terms.
- Release notes 0.0.19 and the version.

## 7. Tests

`backend/python/tests/test_game_search.py`, `test_word_index.py`, `test_embedding_check.py`,
`test_discovery.py`: 77 tests, no database, no Qdrant, no provider. The whole suite on this PC: 753 pass and 11
fail, all in `test_deployment_package.py`, which needs a `.env` and the release tools (unchanged by this lane).
