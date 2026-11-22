# Lane 2: theumst-graph

Branch `agents-graph-0.0.19` in `C:\Business\product\worktrees\theumst-agents-graph`, cut from `origin/main` (2e8250f).
Brief: `C:\Business\product\docs\plans\umst-agentic-build-brief-20261122.md`, part "2. theumst-graph".

## Existing files I will change

None. Every shared change (router registration in `app/main.py` or wherever routers are included, the rate-limit
kind, documents, the version, `routers/game.py`) goes into `MERGE.md`.

## Files and folders I create

- `backend/python/app/routers/game_graph.py`: the routes under `/api/game/graph/...` for the game's key.
- `backend/python/app/services/game_graph.py`: the queries (object with its load, crystal members, uses and used by,
  closures over crystals, section in book order, before and after, source pages). All filtering by what the reader
  may see is inside the SQL.
- `backend/python/tests/.../test_game_graph*.py`: unit tests with a fake cursor, no database.
- `LANE.md`, `ROUTES-graph.md`, `STATUS.md`, `MERGE.md` at this folder's root.

## What I offer other lanes

`ROUTES-graph.md`: each route's method, path, parameters, answer shape with an example, and errors. The door lane
(3) builds its book tools from it.

## What I need from other lanes

Nothing to build. The search lane (1) owns search, neighbours, latcher candidates and which-crystal; I do not touch
`find_neighbors` or any search code. If both lanes need the same helper (the key check for the game's reader, a
visible-book filter), each keeps its own copy and `MERGE.md` says so.
