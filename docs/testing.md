# Testing

Select tests by changed behavior. Documentation-only work uses link/ownership checks and an adversarial comparison with current source, not pytest solely for Markdown. Executable changes run relevant deterministic backend/frontend tests, affected database checks and local acceptance. A coordinated release builds all three frontends.

Backend tests run from `backend/python` with `python -m pytest tests`. Install `requirements-dev.txt` into an isolated environment. Explicitly select LOCAL settings and a disposable database before any integration test. [Backend test modules](../backend/python/tests/README.md) distinguish mocked cursors/import fallbacks from PostgreSQL behavior. Count skips and state their reasons.

Frontend builds run `npm ci` and `npm run build` in each application. [Demo checks](../frontend/demo/tests/README.md) cover helper behavior and source/UI assumptions. A compile success does not establish user behavior or persistence.

After deterministic checks, use six Sol agents at medium reasoning: five workers split approximately twenty distinct [browser objectives](testing/web-demo.md), and one coordinator/reviewer manages setup, coverage and findings. Use waves when concurrency is limited. Each objective has an initial state and observable outcome. Preserve isolated user/fixture state across workers.

Distinguish simulated-service frontend checks, real local backend/database checks and COM-derived examples in every result. Simulations cannot establish production authorization, storage or deployment. The replacement COM server starts with a fresh database at Christopher’s request. Record its empty-library state and new test-account checks separately from old COM data, which is unavailable. A timeout establishes no fact about available book or relation data.

Measure representative retrieval latency, synchronous layout and browser paint separately. Record object/section/edge counts, graph shape, viewport, revision and repetitions before selecting Atlas production limits. Include sparse and dense neighborhoods and both views. The prototype's 18-object/48-arrow limits are historical examples.

Keep source tests in the repository. Raw output, screenshots, local extracts, runtime copies and temporary archives live in the existing Parent Repo Test Area. Record lasting release setup, commands, outcomes and remaining failures in release evidence. The coordinator adversarially checks documentation against current source and resolves stale claims before publication.
