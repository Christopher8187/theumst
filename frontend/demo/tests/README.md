# Demo checks

Run the `.mjs` checks with Node from `frontend/demo`: `node tests/graph-contents.mjs`, `node tests/similar.mjs`, `node tests/visual-contract.mjs`, and the Atlas checks present in this directory. Then run `npm ci` and `npm run build` using the checked-in lockfile.

`graph-contents.mjs` covers graph-response normalization and bounded Contents helpers. `similar.mjs` executes the discovery adapter with simulated responses, including duplicate collapse, source exclusion, numeric ordering and k limits. `visual-contract.mjs` checks existing styling/accessibility assumptions; source-pattern checks do not establish rendered behavior. Atlas checks use explicit simulated section/relation fixtures, not inferred dependencies from real books.

Follow the [browser objectives](../../../docs/testing/web-demo.md) after deterministic checks. Preserve distinct results for simulated API display, real PostgreSQL/Qdrant study behavior and the deployed application. All three frontend builds are required for a coordinated release. Screenshots, raw traces and timing samples belong in the Parent Repo Test Area; durable results belong in release evidence.
