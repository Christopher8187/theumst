# MERGE.md: lane 2 (theumst-graph), what the merge must do

The lane's own files are committed on `agents-graph-0.0.19`: `backend/python/app/routers/game_graph.py`,
`backend/python/app/services/game_graph.py`, `backend/python/tests/test_game_graph.py`, and `ROUTES-graph.md`,
`LANE.md`, `STATUS.md`, this file at the root. Nothing below is done on the branch: each is a shared file.

The four root files (`LANE.md`, `ROUTES-graph.md`, `STATUS.md`, `MERGE.md`) are the lane's working notes. Do not
carry them into `main`; `ROUTES-graph.md`'s content goes into the documents (item 5).

## 1. Register the router (`backend/python/app/main.py`)

Import beside `game`, and include it after `game.router`, before `frontend.router`:

```python
from .routers import game_graph
...
application.include_router(game.router)
application.include_router(game_graph.router)
game.install_error_handlers(application)
```

`game.install_error_handlers` already answers every `/api/game/...` path in the game's error shape, so nothing else is
needed for the errors. Optionally add the nine paths to `tests/test_application_structure.py`'s list:
`/api/game/graph/object`, `/crystal`, `/uses`, `/used-by`, `/closure`, `/section`, `/around`, `/pages`, `/match`.

## 2. The rate-limit kind `graph`

The routes count each call once as kind `graph` (`routers/game_graph.py`, `GRAPH_KIND`), with the tier's
`requests_per_minute` as `book` and `character` have. No tighter limit. Lane 1 asks for `search` the same way; one
migration can add both.

- `backend/python/app/dependencies.py` line 122: `API_REQUEST_KINDS = ("book", "character", "search", "graph")`.
  Until this lands every graph route answers 500 (`ValueError: Unknown API request kind`).
- `backend/sql/schema.sql` lines 205 and 214: both `CHECK (kind IN (...))` take `'search', 'graph'`.
- A reviewed migration (number after lane 1's, if lane 1 takes 018), the constraint names read from COM on
  22 November:

```sql
ALTER TABLE api_rate_window DROP CONSTRAINT IF EXISTS api_rate_window_kind_check;
ALTER TABLE api_rate_window ADD CONSTRAINT api_rate_window_kind_check
    CHECK (kind IN ('book', 'character', 'search', 'graph'));
ALTER TABLE api_usage_daily DROP CONSTRAINT IF EXISTS api_usage_daily_kind_check;
ALTER TABLE api_usage_daily ADD CONSTRAINT api_usage_daily_kind_check
    CHECK (kind IN ('book', 'character', 'search', 'graph'));
```

- Anything that lists kinds for an account's usage (the website's key page, `docs/security.md`,
  `docs/game-accounts.md`) names the two new kinds.

## 3. Two indexes (migration and `schema.sql`)

COM has no index on `knowledge.knowledge_crystal_id` (read on 22 November). Without it a crystal's members, and the
crystal size every answer carries, scan the whole `knowledge` table: about 50 to 100 ms a query today, growing with
every book. The match and `?source_key=` scan it too. Lane 1's MERGE.md item 3 already asks for both indexes,
under these names; keep its definitions, once, in the migration and in `schema.sql` after `knowledge_section_idx`
(line 656):

```sql
CREATE INDEX IF NOT EXISTS knowledge_active_crystal_idx ON knowledge (knowledge_crystal_id) WHERE is_active;
CREATE INDEX IF NOT EXISTS knowledge_active_source_key_idx ON knowledge (source_key) WHERE is_active;
```

Markers for `reviewed_migrations.py`: the two relations.

Measured on COM through `EXPLAIN ANALYZE` (read only) before the index: 25 objects with their crystal sizes 104 ms,
a crystal's members 63 ms, 25 objects' arrows 1 ms, one book's reader order (Boyce, 9,307 objects) 147 ms.

## 4. Tests to run after the merge

`pytest backend/python/tests/test_game_graph.py` (45 tests, no database), and the whole suite. A check against
PostgreSQL is not written: the routes were run read only against COM's database instead (STATUS.md says which).

## 5. Documents and version (0.0.19)

- `docs/game-accounts.md`: a section "Graph reads for UMST's agents (0.0.19)" from `ROUTES-graph.md`: the nine
  routes, the object fields, the errors, the kind `graph`, Web Demo access, nothing stored.
- `docs/architecture/data.md`: the two indexes; the closure and the component read `knowledge_graph_edge` only
  (`dependency` and `supports`), never the legacy `relation` table; a detached proof's theorem is worked out as the
  game does (the last theorem, semantic theorem or supporting lemma before it in book order among what it uses).
- `docs/architecture/backend.md`: the new router and service.
- `docs/security.md`: the new kind in the allowance; these routes read only visible books for a key with Web Demo
  access, as `/api/game/grimoires` does.
- Release notes for 0.0.19 and the version, with lane 1's.

## 6. The first release

- Run the migration(s) after the backup, as `docs/operations.md` says.
- Check each route once with the test account (brief, "The checks on theumst.com"). Good first objects: `44630`
  (a book-18 theorem; its down closure is 18 crystals, 603 words), `44464` (two supporting lemmas), `44867` (a
  detached proof; it finds "Classification of surfaces").
