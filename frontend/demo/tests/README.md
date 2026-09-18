# Demo checks

Run the `.mjs` checks with Node from `frontend/demo`: `node tests/graph-contents.mjs`, `node tests/similar.mjs`, `node tests/visual-contract.mjs`, and the Atlas checks present in this directory. Then run `npm ci` and `npm run build` using the checked-in lockfile.

`graph-contents.mjs` covers graph-response normalization and bounded Contents helpers. `similar.mjs` executes the discovery adapter with simulated responses, including duplicate collapse, source exclusion, numeric ordering and k limits. `visual-contract.mjs` checks existing styling/accessibility assumptions; source-pattern checks do not establish rendered behavior. Atlas checks use explicit simulated section/relation fixtures, not inferred dependencies from real books.

Follow the [browser objectives](../../../docs/testing/web-demo.md) after deterministic checks. Preserve distinct results for simulated API display, real PostgreSQL/Qdrant study behavior and the deployed application. All three frontend builds are required for a coordinated release. Screenshots, raw traces and timing samples belong in the Parent Repo Test Area; durable results belong in release evidence.

`atlas-api.mjs` checks the reader's Atlas view request through the real normalizer and both layouts, including separate dependency and reading-order paths sharing endpoints. Its response is simulated; the database and deployed-browser checks establish the stored-data path.

`node tests/atlas-compact.mjs` checks the notebook's compact spacing in both
layouts, comparing visible objects and relationships with regular spacing.
Synthetic cases cover card/heading collisions, gap labels and drawing size at
8, 16 and 24 objects. Fourteen frozen Real Analysis cases cover relationships
and gap labels at seven selected objects in both layouts.

`node tests/atlas-route-clearance.mjs` reproduces the reported Real Analysis
view at object 1. It checks straight aligned arrows, separation of the two
dependencies to object 27, clearance from chapter borders, and the compact
gutter between sections 4.1 and 4.2.
