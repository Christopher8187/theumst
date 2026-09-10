# Web Demo browser objectives

Use five Sol/medium browser workers and one Sol/medium coordinator after deterministic verification. Each worker owns four objectives below, a separate browser context and its own fixture/user state. Record initial state, actions, observed outcome, response failures, screenshots, tested revision and pass/fail.

Evidence labels: S means built frontend with simulated services; L means real FastAPI, PostgreSQL, Qdrant and storage (record actual service hosts and any SSH tunnel); C means the deployed COM application. Simulations cannot pass requirements marked L. On 10 September 2026 Christopher selected a fresh database for the replacement COM server after the old Droplet was destroyed. Old COM book examples are consequently unavailable; record C empty-library/health/auth observations honestly and use labeled local fixtures for reading checks.

## Worker 1: visibility, unavailable material, and retained user state

### 1. Reader visibility follows book availability

- Evidence: `L` required. Repeat read-only on `C` if suitable hidden and visible books already exist. An `S` preflight may exercise the UI but cannot pass this objective.
- Initial state: the signed-in reader has one summoned visible book and a second book that an authorized manager can hide. Each contains identifiable knowledge objects and images. Find-neighbor and Crystallization fixtures include objects from both books.
- Steps: open the visible book and its reader content; hide the second book through the real management operation; refresh the library, personal grimoire list, direct reader route, image route, Find neighbors, and Crystallization; try known direct object and image URLs.
- Observable outcome: no reader-facing route exposes the hidden book's source content, objects, or images. Find neighbors and Crystallization omit every hidden-book instance, including a hidden preferred instance. Authorized management access can still inspect and unhide it. Record each backend response rather than relying only on absent UI cards.

### 2. Personal writing survives a hidden source

- Evidence: `L` required; `S` may confirm the message and disabled-link presentation.
- Initial state: the reader owns two attached notes on one object and a scribble associated with a book. The book is then hidden by an authorized manager.
- Steps: open All notes after the hide; open each attached note and the scribble; edit and save personal text; attempt the source link; sign out and back in, then reopen the notes.
- Observable outcome: the user's writing remains readable and editable after reload. The source link is unavailable and reveals no source content. The UI explains the unavailable attachment without deleting or silently retargeting the note.

### 3. Unavailable progress is retained and restored

- Evidence: `L` required.
- Initial state: a reader has a saved position and completion records in a visible book. Capture their object IDs. Hide the book without deleting those records.
- Steps: reload the reader and personal collection; inspect the user state through the supported API or a read-only database query; unhide the same book; reopen Text and Questions.
- Observable outcome: hiding withholds content but preserves the saved IDs and completion state. Unhiding restores the exact position and completion. No fallback object overwrites the unavailable position while access is absent.

### 4. Base and original grimoire availability choices

- Evidence: `S` for exhaustive state combinations and `L` for persistence and real hide behavior.
- Initial state: scenario A begins in original grimoire A. Scenario B begins in A, visits B, and keeps B as the current base grimoire. Saved positions, completion, and notes exist in both.
- Steps: in A, make A unavailable while it is the base; in the excursion, make original A unavailable while B remains visible; exercise `Confirm and exit` in both states and `Stay in this base grimoire` in the second state.
- Observable outcome: source content disappears immediately. A clear notice appears. Both exit actions go to My grimoires. The Stay action keeps readable B open. Retained positions, completion, and personal writing remain unchanged.

## Worker 2: ordered study, completion, and realm state

### 5. Train advances only to an unfinished exercise ahead

- Evidence: `S` and `L`.
- Initial state: one ordered book has completed and unfinished exercises before and after the selected object, plus a final state with no unfinished exercise ahead.
- Steps: select a non-exercise item; choose Train repeatedly; mark intervening exercises complete; invoke Train at the final unfinished or exhausted position.
- Observable outcome: Train chooses the next unfinished exercise ahead in source order. It never wraps backward. When none remains ahead, it stays put and explains why. The selected exercise replaces reader content while the graph remains alongside it.

### 6. Completion is shared and immediately visible

- Evidence: `L` required; `S` checks immediate display only.
- Initial state: the same exercise is visible from Text and Questions and appears in the current Atlas. It starts incomplete.
- Steps: mark it done in Text; inspect the selected item and Atlas without reloading; switch to Questions; reload and sign in again; toggle it back if the fixture allows cleanup.
- Observable outcome: the item stays selected. Reader and Atlas completion feedback update immediately. Questions shows the same completion value, and the value survives reload because completion belongs to the knowledge object rather than the realm.

### 7. Text and Questions keep separate positions

- Evidence: `L` required.
- Initial state: the reader's Text position is object T and Questions position is exercise Q in the same book.
- Steps: move Text to T2; move Questions to Q2; alternate realms several times; reload the page and start a new signed-in session.
- Observable outcome: each realm returns to its own last object. Switching realms does not replace the other realm's saved position. Completion remains shared even though positions differ.

### 8. Continue follows the complete book order

- Evidence: `S` against a deliberately gapped view, then `L` against the backend's ordered reader response. Use `C` read-only if a suitable ordered book exists.
- Initial state: the visible Atlas omits several intervening objects and includes completed objects and a section boundary. The full ordered list is known independently of graph edges.
- Steps: choose Continue from the selected object until crossing the hidden gap and section boundary; use Back; compare visited IDs with the backend order and completion values.
- Observable outcome: Continue visits exactly one next object each time, including omitted, completed, and next-section objects. It does not mark items done. Back returns through navigation without expanding the entire book. Generated source order is not described as an authored dependency.

## Worker 3: notes, language, book detail, and contents

### 9. Multiple attached notes can be selected and created

- Evidence: `S` and `L`.
- Initial state: the selected object has two saved attached notes with distinct text.
- Steps: open Notes from the reader action row; switch between both notes; edit and save each independently; choose New note, save a third note, close with Escape, reopen Notes, and open All notes.
- Observable outcome: a selector and New note control appear above the editor. Each note retains its own text after reload. Escape closes the panel and restores focus to the Notes trigger. All notes contains all three without turning them into scribbles.

### 10. Unfinished note switching protects edits and destination

- Evidence: `S` for every branch, plus one `L` save branch.
- Initial state: note A has saved text; note B and another navigation destination are available.
- Steps: edit A without saving, then attempt to select B, create a note, close the panel, select a knowledge object, and leave the realm. Across runs choose Save and continue, Discard and continue, and Keep editing.
- Observable outcome: every departure offers all three choices. Save persists A and reaches the intended destination. Discard restores A's prior saved text and reaches it. Keep editing cancels navigation and leaves the draft in place. The pending destination does not change while the choice is open.

### 11. Supported interface languages are complete

- Evidence: `S`; repeat core navigation on `L`.
- Initial state: a clean profile begins in English with source content supplied in Chinese or Japanese for at least one object.
- Steps: inspect the language selector; traverse library, detail, realms, Text, Questions, Notes, Atlas, Find neighbors, empty/error notices, unavailable-source notice, and exit flow in English, Chinese, and Japanese; reload after each choice.
- Observable outcome: the selector offers exactly English, Chinese, and Japanese. Interface strings on every listed surface follow the choice, the document language updates and the setting survives reload. Source content stays in its supplied language. Old English-only labels such as `Cluster`, `Graph`, and version `0.0.1` do not leak into Chinese or Japanese.

### 12. Book metadata and nested contents use honest fallbacks

- Evidence: `S` and `L`.
- Initial state: one book has supplied summary and ISBN; one lacks each field. A large contents tree has at least three levels, long titles, an orphan, and enough children to require internal scrolling.
- Steps: open both book details at 1440, 768, and 390 CSS px; expand and collapse chapters by pointer and keyboard; select a deep item; inspect the DOM count before and after expansion.
- Observable outcome: supplied summary and ISBN display unchanged. Missing values use the documented fallback and never invent metadata. The initial tree shows top-level entries only; expansion reveals actual descendants from parent metadata. The list remains bounded, long text stays inside the page, and accessible expanded/current state changes correctly.

## Worker 4: Find neighbors, scoring, and excursions

### 13. Find neighbors can discover across visible books

- Evidence: `L` with real PostgreSQL and Qdrant required. Repeat read-only on `C` when suitable embeddings exist.
- Initial state: compatible statement and statement/workings projections exist across at least two visible books. A third candidate book is hidden. Record embedding model, dimensions, projection types, and source IDs.
- Steps: run Find neighbors from the source item; capture Qdrant and API results; compare the result set with read-only database rows; hide the third book in local testing and repeat.
- Observable outcome: visible cross-book candidates may appear and hidden-book candidates never appear. The result count is the final top k after combining the distinct candidate sample. The selected item is excluded. Record whether native combination or application-side top-k union was used.

### 14. Two-projection ranking follows all workings cases

- Evidence: `S` with exact scores and `L` with seeded embeddings.
- Initial state: candidates cover both objects having workings, exactly one lacking workings, both lacking workings, and a processing fault where workings exist but an embedding is missing. Include a signed-score case.
- Steps: request enough neighbors to retain every candidate; calculate expected ranks from captured component scores; compare UI and API order.
- Observable outcome: complete pairs use equal averaging. A one-sided workings mismatch uses `0.8 × statement score`, with a method that always lowers rank for signed similarities. Two objects without workings use the statement score without penalty. A missing embedding despite existing workings is reported as a fault, not treated as the expected no-workings case.

### 15. Find-neighbor panel distinguishes all response states

- Evidence: `S`, with `L` for success and at least one service failure.
- Initial state: deterministic responses exist for loading delay, results with duplicates and self-result, empty success, 404/501/503 unavailable, 500, malformed payload, and network failure.
- Steps: open and close the panel for each response at 1440 and 390 CSS px; retry where offered; navigate rapidly so an older response arrives after a newer request.
- Observable outcome: loading, results, empty, unavailable, and failure look distinct. Results sort descending, collapse duplicate knowledge IDs to the best score, exclude the selected item, respect the requested bound, wrap without page overflow, ignore stale responses, and restore focus when closed.

### 16. Cross-book return restores the whole origin

- Evidence: `S` for A to B to C and `L` with real cross-book results.
- Initial state: start in Questions on object A-Q, with original book A and saved Text position A-T. Find-neighbor results lead from A to B and then C.
- Steps: open B, then C; use the existing Return to original book control; repeat with Text as the starting realm; compare the Questions Book action with Return.
- Observable outcome: A remains the origin throughout the excursion. Return restores A, the exact starting object, and the starting realm. It does not choose A-T when the excursion began at A-Q. The Questions Book action keeps its own documented destination and does not replace Return.

## Worker 5: Section Atlas display and bounded navigation

### 17. The two views and two distances remain independent

- Evidence: `S` with the full fixture range, then `L` with representative real data.
- Initial state: focus item 13 has near-by-book candidates, dependency-near but book-distant candidates, and objects failing both limits.
- Steps: switch between Reading rows and Hierarchy; move book distance alone, dependency distance alone, both extremes, and intermediate values; switch views after each change.
- Observable outcome: there are exactly two view choices and no blend/layout slider. Each distance control changes only its own threshold and preserves the chosen view. Either qualification includes an object that passes either measure. Objects failing both are absent.

### 18. Section groups and rows match the hierarchy

- Evidence: `S` and `L`.
- Initial state: a book has direct subsections with nested smaller sections, uneven object counts, long headings, and qualifying objects in only part of one section.
- Steps: inspect both views at 1440, 768, and 390 CSS px; compare displayed group membership with section ancestry; resize and change distances.
- Observable outcome: smallest sections have filled groups. Direct subsections below the book root have curved borders and labels. Deeper membership follows ancestry without fixing node coordinates. Reading rows restart inside each larger subsection. Partial sections contain qualifying objects only. Borders and headings do not cover cards.

### 19. Gold order, dependencies, ports, and gap labels stay distinct

- Evidence: `S` with adversarial routing fixtures and `L` against returned relations.
- Initial state: the graph has at least one pair sharing source order and an authored dependency, converging dependencies, multiple omitted order runs, and routes near headings and borders.
- Steps: inspect both views and distance extremes; trace the complete visible gold path and every dependency; select each `+N outside view` marker; compare counts with omitted positions.
- Observable outcome: shared pairs retain separate gold and dependency arrows. Gold forms the complete source-order path across visible runs; dependencies remain separately styled and directed. Routes use distinct ports and do not merge, vanish, or cross cards, headings, markers, or borders. Every count-only label sits beside its own dotted gold arrow, reports exact omitted positions, and does not bulk-expand them.

### 20. Bounded rendering, selection, math, and measured limits

- Evidence: `S` for deterministic load series, `L` for representative retrieval and paint, and read-only `C` measurements when suitable data exists.
- Initial state: datasets span small, ordinary, dense, and beyond-bound cases. Selected objects contain valid and invalid LaTeX. The production candidate limits are configuration values derived from measurements, not the prototype's 18-object or 48-arrow numbers.
- Steps: record retrieval, layout, and paint timing and DOM counts; select nodes near each boundary; use Continue and Back across a cropped area; resize to 390 CSS px; inspect console and routing counters.
- Observable outcome: rendering stays within the selected measured limits and reports additional qualifying-object counts without loading the whole book. Selection updates reader and focus without losing surrounding context. Continue and Back work one object at a time. Valid math renders through KaTeX, unsafe or invalid input does not become trusted HTML, controls remain reachable, the page has no horizontal overflow, every candidate arrow is either routed or visibly reported, and browser errors are empty.
