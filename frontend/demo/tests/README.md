# Demo checks

Run the `.mjs` checks with Node from `frontend/demo`: `node tests/graph-contents.mjs`, `node tests/similar.mjs`, `node tests/visual-contract.mjs`, and the Atlas checks present in this directory. Then run `npm ci` and `npm run build` using the checked-in lockfile.

`graph-contents.mjs` covers graph-response normalization and bounded Contents helpers. `similar.mjs` executes the discovery adapter with simulated responses, including duplicate collapse, source exclusion, numeric ordering and k limits. `visual-contract.mjs` checks existing styling/accessibility assumptions; source-pattern checks do not establish rendered behavior. Atlas checks use explicit simulated section/relation fixtures, not inferred dependencies from real books.

Follow the [browser objectives](../../../docs/testing/web-demo.md) after deterministic checks. Preserve distinct results for simulated API display, real PostgreSQL/Qdrant study behavior and the deployed application. All three frontend builds are required for a coordinated release. Screenshots, raw traces and timing samples belong in the Parent Repo Test Area; durable results belong in release evidence.

`atlas-api.mjs` checks the reader's Atlas view request through the real normalizer and both layouts, including separate dependency and reading-order paths sharing endpoints. Its response is simulated; the database and deployed-browser checks establish the stored-data path.

`node tests/atlas-compact.mjs` checks the notebook's compact spacing in both
layouts, comparing visible objects and relationships with regular spacing.
Synthetic cases cover card/heading collisions, gap labels and drawing size at
8, 16 and 24 objects. Fourteen frozen Real Analysis cases cover relationships
and gap labels at seven selected objects in both layouts. Every case also
checks that arrows have distinct connection points on each card, including
incoming versus outgoing arrows and regular versus compact spacing.
Compact omitted counts must lie on their own dotted stroke, with no missing
labels across the cases.

`node tests/atlas-route-clearance.mjs` reproduces the reported Real Analysis
view at object 1. It checks straight aligned arrows, separation of the two
dependencies to object 27, clearance from chapter borders, and the compact
gutter between sections 4.1 and 4.2.

`node tests/atlas-endpoints.mjs` checks content-sized chapter rows, distinct
incoming and outgoing ports, arrowhead clearance, and the reported 4 to 25
route and +5 label placement in the Bounded sequences sample. It also checks
that 1 to 27, 2 to 27 and 4 to 25 turn right without a short departure detour.
The object 13 view checks the full approaches of 4 to 31, 8 to 15 and 13 to 15,
so moving a reversed hook earlier does not count as a fix. It checks separate
tails for 29 to 31 and 29 to 32. Renaming all object IDs, object titles and
section names must leave node positions and routed geometry unchanged.
Compact checks use the layout's returned card dimensions, including the
52-unit height of cards with numbers beside their titles.

`node tests/atlas-reading-flow.mjs` covers reading-row transitions around item
1, full arrowhead stems and balanced chapter placement around item 15, and
the straight 27 to 34 route beside the 4 to 31 approach around item 29.

`node tests/notebook-math.mjs` checks that inline mathematics stays within prose,
display mathematics occupies separate notebook rows, and source text remains
escaped. Tall formula sizing also requires a browser check.

`node tests/study-realms.mjs` checks the notebook's separate Text and Questions
sequences, completed exercises, end boundaries, type-based realm selection,
and Atlas filtering without renumbering. It covers every non-exercise position
in both layouts of the frozen Real Analysis sample and checks that filtering loses no routes
or omitted-position labels. Browser checks cover the actual realm switch,
URL, shared progress appearance, and the Back/Continue controls.
