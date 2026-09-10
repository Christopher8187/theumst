Historical input. Read current docs from the repository README.

# Protected Web Demo acceptance matrix

This document records the Demo Team's focused acceptance surface. It is not a release declaration and does not cover shared authentication, storage, migrations, ingestion, Nginx, infrastructure, or deployment.

## CEO visual checkpoint draft

**Status:** checkpoint candidate only. It is not integration-ready, production-ready, deployed, or released. Product must attach matched before/after screenshots and complete integrated acceptance.

**Lane credit:** the protected Demo Team visual/performance QA lane owns the calm navy comfort layer, typography and spacing judgments, responsive CSS, focus/reduced-motion behavior, bounded Contents and relationship-map styling, image-panel usability styling, the static visual contract, and this evidence matrix. Graph/Contents behavior and the Cluster interaction remain credited to their respective implementation lanes; Product owns consolidation and final judgment.

Checkpoint judgments for Product review:

1. Retain the warm off-white on calm dark navy, with cyan/teal reserved for focus and action, and muted gold for mathematical provenance or secondary emphasis.
2. Retain a 16px document base, 8px-derived spacing, 12–16px surface radii, 44px close targets, and restrained label tracking. Metadata may be smaller but should not recreate the former 6–10px density.
3. Retain the two-pane reader at 1440 and 1024 CSS px; use the bounded stacked reader at 768 and the single-column/bottom-rail layout at 390.
4. Retain a bounded, internally scrolling Contents root and relationship-map viewport. Neither may determine document height from total book size.
5. Retain an in-flow right-side image panel on wide screens and a bounded stacked panel on narrow screens. If Product changes it into a modal or drawer, focus trapping, Escape, and trigger-focus restoration become mandatory.
6. Retain the learner language guard. Mathematical content and types remain precise; implementation vocabulary remains behind the interface.
7. Do not accept the checkpoint while the static contract reports a failure, the graph invents edges in the client, the server-supplied `book_order_v1` projection is unlabeled or invalid, any missing state is ambiguous, or matched viewport evidence is absent.

## Reproducible checks

From `frontend/demo`:

```powershell
node tests/visual-contract.mjs
npm run build
```

The first command is a dependency-free source contract. It does not replace browser, accessibility, API-contract, or performance testing. The second is the existing Vite production build; this repository does not currently define a frontend unit-test script.

## Evidence baseline

The Product-verified pre-task state is the comparison baseline:

| Measure | Before | Acceptance target |
| --- | ---: | ---: |
| Contents visible rows on initial book detail | 802 | Top-level rows only; child rows absent until expanded |
| Contents elements | 1,662 | Proportional to visible branches, not all 802 sections |
| Contents document height | 34,362 px | Bounded internal scroller, no page-height wall |
| Study-entry request | Still pending after 20 s | Static reader index cached once per book/session; focused graph loads independently |
| Focused graph nodes | Whole-book behavior | At most 150 returned; at most the client render bound in the DOM |

Live before/after request sizes and timings depend on a Product-provided running service and authenticated demo data. Record them in the final handoff rather than inferring them from source.

## Browser and interaction matrix

Use a fresh session at each CSS viewport. Browser zoom must be 100%; record the browser version, device-pixel ratio, service revision, `graph_revision`, and focus knowledge ID beside captures.

| Surface | 1440 px | 1024 px | 768 px | 390 px | Keyboard / state acceptance |
| --- | --- | --- | --- | --- | --- |
| Library and book detail | Four-column breathing room | Three/four-column without clipping | Three/two-column transition | One-column books | Logical tab order; visible focus; long title wraps |
| Contents | Bounded nested tree | Bounded nested tree | Bounded nested tree | No horizontal page scroll | Enter/Space expands; `aria-expanded` changes; current item remains visible |
| Reader | Balanced reader/side pane | Two-pane reader remains usable | Panes stack within bounded heights | Actions become two columns | Math scrolls locally; no focus loss after selection |
| Focused graph | Relation-only DAG | Relation-only DAG | Bounded stacked panel | Labels do not force page width | Loading, edge-empty, unavailable, and failure states are distinguishable |
| Cluster | Top-k side panel | Top-k side panel | Bounded stacked panel | Long labels/scores wrap | Loading, results, empty, unavailable, failure; result order descending |
| Image panel | Image contained in right pane | Image contained in right pane | Stacked image pane | Close target remains visible | Named close button; Escape/close behavior verified; focus returns to trigger |
| Notes and progress | Preserved | Preserved | Stacked panes | Controls remain reachable above bottom rail | Inputs named; save/delete focus predictable; completion state visible |

## Required semantic proofs

- Crystallize has no live control and no legacy API call. The replacement action and panel are labelled exactly **Cluster**.
- Cluster returns top-k embedding neighbours, excludes the selected item, and sorts by descending `similarity_score`. This discovery overlay is never a graph edge and does not imply a separate clustering algorithm.
- The graph requests only the frozen focused endpoint with ancestor/descendant depth and the 150-node server limit.
- Exercise has `graph_role=assessment`; JAS / “just a statement” has `graph_role=fragment`. Neither may appear on the semantic backbone.
- Graph edges come only from the bounded server-supplied projection (`source_knowledge_id`, `target_knowledge_id`, and `relation_type=book_order_v1`). The client does not recreate book order. The main-item spine and non-main fan are distinct; Exercise and JAS never become anchors. Edge-empty input remains edge-empty and is explained honestly.
- Contents derives nesting from actual parent/section metadata. Collapsed descendants do not exist in the initial DOM.
- The permitted static reader index is cached once per grimoire in the demo session and is not repeatedly loaded as part of per-user progress, note, selection, return-to-origin, or book-switch overlays.

## Learner-facing language

The Web Demo is written first for an advanced mathematics learner and remains extensible to other semantic/STEM material. Implementation vocabulary stays behind the interface.

| Internal concept | Learner-facing wording |
| --- | --- |
| Embedding/vector lookup | **Cluster**, “nearby knowledge” |
| Node | **Knowledge item**, **item**, or the item's mathematical type |
| Edge / DAG | **Relationship**, **connection**, or **knowledge map** |
| API, storage, graph revision | No learner-facing label; explain only the available action or current state |

Translated strings and literal template text must not expose **embedding**, **vector**, **API**, **node**, **edge**, **DAG**, or **graph revision** (including obvious translated equivalents). Developer-only variable names, canonical contract fields, tests, and diagnostics may retain precise technical terminology.

## Manual accessibility and resilience checks

1. Complete every demo route using only Tab, Shift+Tab, Enter, Space, arrow keys where supported, and Escape for an open dismissible panel. Confirm no keyboard trap and a visible cyan focus ring on every control.
2. Enable reduced motion in the operating system. Confirm summoning, loading indicators, cards, graph nodes, and toasts do not translate, scale, or loop visibly.
3. Force long book, section, node, image, and note labels. Confirm wrapping or ellipsis is local and the page never gains horizontal scrolling.
4. Exercise loading, empty, HTTP 404/501 unavailable, HTTP 500/network failure, and successful states for graph and Cluster. Unavailable must not look like an empty successful result.
5. Open and close an inline image repeatedly at each viewport. Confirm the image is contained, its description and original link remain reachable, and the close target stays at least 44 by 44 CSS pixels.
6. Scroll beyond the start/end of the document and every internal panel. Confirm no white canvas appears and scroll chaining is contained where appropriate.

## Evidence to attach to Product handoff

- DevTools Network export or screenshots for initial book detail and study entry, with request count, transferred bytes, payload bytes, and duration.
- DOM counters for initial Contents rows/elements and focused graph nodes/edges.
- Screenshots at 1440, 1024, 768, and 390 CSS px for book detail, reader + graph, reader + Cluster, and reader + image.
- Keyboard-focus screenshots for Contents expansion, Cluster result, image close, note save, and progress action.
- Reduced-motion media-query capture and the exact outputs of the static contract and Vite build.

Any missing live-service evidence is a blocker to integrated acceptance, not evidence of a pass.
