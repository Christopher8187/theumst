# Theumst 0.0.7 verification

The accepted revision 25 prototype at `43a17d3562b95168e8044f8464f0947252e04d18` is the visual baseline. The release replaces the previous Demo entry with `src/sanctuary/SanctuaryApp.vue`. Production loads book content, notes, completion and positions from authenticated APIs. The frozen prototype remains a development-only reference and sample export source.

## Automated checks

On Windows, using isolated PostgreSQL 16 at `127.0.0.1:55437`, database/user `theumst007`, `SERVER=LOCAL`, disabled schema replay and `THEUMST_DATABASE_INTEGRATION=1`:

- `python -m pytest tests -q -rs`: 164 passed, 14 skipped. The 14 skips are the separately gated News PostgreSQL acceptance cases. Warnings are FastAPI/Starlette Python deprecations.
- `python -m pytest tests/test_demo_007_database.py -q` with `THEUMST_007_ARCHIVES` pointing to the exported books: 2 passed. This checks actual PostgreSQL optional-name fallback, reimport identity, incoming-only Dependencies, collection removal preserving completion, owned notes remaining editable, rejected unauthorized note retargeting, note deletion, source withdrawal, and old/new Real Analysis identity and position retention. Tests roll back their database changes.
- All 13 Demo `.mjs` checks pass. `production-reader.mjs` uses simulated HTTP and the actual production composable. It checks adjacent realm navigation, completion writes, reloading positions, dirty-note departure, empty realms and unavailable saved positions without overwriting the saved ID. Atlas fixtures check both layouts, distinct ports, compact grouping and omitted counts without depending on object IDs or titles.
- All three frontends build successfully. Public and dashboard retain the existing large scene-chunk warning. The production Demo Docker image builds successfully after copying shared artwork into its build context.

## Browser observations

Real local FastAPI, PostgreSQL and filesystem storage were used with isolated review accounts. Qdrant was disabled in this local setup; generated sample books contain no invented embeddings.

Sol review workers checked Orbit pointer/keyboard selection, Brief summaries/counts/chapter expansion, search empty/recovery, collection removal/re-add retaining completion, attached and scribble note persistence, multiple-note selection, all three unsaved-writing choices, language switching and keyboard focus. Desktop 1440 and phone 390 checks covered Orbit, Brief, Realms, Text and discovery. Measured document width equaled scroll width. Accepted artwork, translucency, notebook ruling and Atlas remained recognizable.

Root browser checks verified Text 5 to 7 and back skips exercise 6, Questions 6 to 15 and back, a non-exercise Atlas choice returning to Text, and reload restoring the selected object. Escape from the Notes toolbar was corrected and rechecked. Unfinished realms remain on the realm book with a localized coming-soon notice. Retry was added to failed discovery requests, and object-type labels were localized.

One navigation worker could not attach to its browser; root covered its core navigation objectives. Browser reduced-motion emulation was unavailable; the source retains the accepted media-query handling. After the existing preview services recovered, root verified Descend from the Sanctuary arriving at the rendered homepage on port 5173. Continuous ascent visual inspection was interrupted by browser timeouts and is not reported as passed.

Successful semantic ranking and cross-book discovery were not browser-tested with real embeddings in this run. Existing deterministic retrieval tests passed. The local sample endpoint returned 409 for a missing statement projection, which is an explicit data limitation, not an empty successful result.

The final source review found and corrected two additional gaps. All notes can now open directly from the Sanctuary without any visible grimoire, and the simulated component check verifies retained hidden-source writing, two consecutive saves and unchanged selection. Its new layout was not separately browser-reviewed. An exact allowlist returns successful Demo reauthentication to `/demo/`, retaining the current production host or local Demo port. The return-destination check rejects external or malformed destinations. All affected builds passed after these fixes.

## COM preparation

Read-only inspection found source `74a0b0ca7154c5af8d836191912e428320b5ce23`, healthy application services, one grimoire, 36 knowledge objects, zero notes/completion rows and two saved study positions. A custom PostgreSQL dump was restored into `theumst_restore_007`; all these counts matched. Backup SHA-256 is `08ac87459d3f7f9c105ae1910dbcefdf110bceff69a13f4dc9347d353534a510`. The backup and source/config archive are retained privately under `/home/chris/backups/theumst-007-20260919`.

The generated COM environment was compared with the retained remote environment: no changed or added keys. Existing databases use only reviewed migration 010 for nullable knowledge-object names. The published tag and GitHub release notes record the final source revision, deployment digest and post-deployment observations.

The retained Qdrant collection `knowledge-qwen3-embedding-0-6b` was green with zero points before deployment. Its existing named volume and configuration are retained. Source image recovery information remains in the database backup and retained source/configuration; COM uses its existing Spaces storage.
