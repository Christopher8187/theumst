# Round 14: selected daily notebook

Christopher selected B's daily notebook. The ruling now continues through the
unused space below the workings. The left leaf uses the original realm folio's
translucent blue palette and opacity. Statement and workings remain on one
scrolling page. The notebook comparison controls are removed.

Open `/demo/?prototype=wisdom&revision=14&arrival=0&book=symmetry&view=realms&place=tree&realm=text&notebook=B`.

## Notebook tools

Four square symbols borrow the scale and placement of the weather marks in
Christopher's notebook photographs: Crystallization, Dependencies, Notes and
Find neighbors. Labels appear beside the row after a 350ms pointer pause, then
change immediately when moving between symbols. Keyboard focus shows the label
immediately. Escape and activation dismiss it, and pending timers are cancelled.
The label has a fixed starting position, stays inside the leaf and does not
intercept pointer input. Each button retains its accessible name.

Dependencies has a dedicated directed-node symbol. It replaces the former
Project placeholder in this prototype and finds the objects the selected object
directly uses. For an authored dependency A → B, selecting B returns A.
It excludes downstream dependents, indirect ancestors and containment relations.
Results use the supplied sample relations without similarity scores. An empty
result says that no dependencies are recorded. This meaning is recorded in
Theumst's shared vocabulary in `CONTEXT.md`.

## Implementation and verification

`NotebookTools.vue` owns the symbols and label timing. Optional slots in
`StudyView.vue` let this prototype place its tools above the entry while keeping
Back, Continue and Train below. The normal Demo retains its default controls.
`SearchPanel.vue` presents the new dependency result kind. `useTextStudy.ts` and
`studyFixtures.ts` own its action and lookup. `notebook-selected.css` contains
the selected page treatment; the earlier variants remain for reference.

GPT-5.6 Sol reviewed tooltip timing, focus, accessible names and dismissal.
In-memory Vite checks covered incoming relation direction, empty results,
duplicate and malformed relations, selection, Back, and the existing discovery
actions. In-browser inspection confirmed that Symmetry object 202 returns 201
without a similarity score. Desktop inspection also checked the extended ruling,
blue transparency and keyboard label placement. Production Demo build passed;
the prototype remains excluded from that build.

This is a local prototype on `codex/tree-of-wisdom-prototype`. There is no release
or deployment in this round; the next real Demo release remains 0.0.4.
