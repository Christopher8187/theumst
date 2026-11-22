# Lane 1: theumst-search

Branch `agents-search-0.0.19` in `C:\Business\product\worktrees\theumst-agents-search`, cut from `origin/main`
(2e8250f, v0.0.18 plus its release record). Brief: `C:\Business\product\docs\plans\umst-agentic-build-brief-20261122.md`,
part "1. theumst-search".

## Existing files I will change

- `backend/python/app/services/discovery.py`: `find_neighbors`' reach (it reads every eligible row of every visible
  book for each request). Only the neighbour code; nothing the graph lane uses. Its test,
  `backend/python/tests/test_similar_retrieval.py`, follows it.
- `backend/python/app/services/qdrant.py`: helpers for a sparse (word) store and a query by sparse vector, added
  beside the existing dense helpers. Existing functions keep their behaviour.

Nothing shared: router registration, the rate-limit kind, documents, the version and `routers/game.py` go into
`MERGE.md`.

## Files and folders I create

- `backend/python/app/routers/game_search.py`: the routes under `/api/game/search/...` for the game's key.
- `backend/python/app/services/game_search.py`: search (dense + BM25 fused by rank, grouped by crystal with
  max(1, floor(log3 m)) members shown), neighbours, the latcher's candidates, which crystal.
- `backend/python/app/services/word_index.py`: the BM25 word index (tokenising label, name and statement into
  Qdrant sparse vectors with the IDF modifier, in a store of its own keyed by object).
- `backend/python/scripts/fill_word_index.py`: fills the word index for the books already loaded; safe to run twice.
- `backend/python/tests/test_game_search*.py`, `test_word_index.py`: unit tests with fakes, no database.
- `LANE.md`, `ROUTES-search.md`, `STATUS.md`, `MERGE.md` at this folder's root.

## What I offer other lanes

`ROUTES-search.md`: each route's method, path, parameters, answer shape with an example, and errors. The door lane
(3) builds its book tools (search, neighbours, latcher candidates, which crystal) from it.

## What I need from other lanes

Nothing to build. The graph lane (2) owns objects with their load, crystal members, dependencies, closures,
sections and pages; I do not touch its files. If both lanes need the same helper (the game key's reader, the
visible-book filter), each keeps its own copy and `MERGE.md` says so.
