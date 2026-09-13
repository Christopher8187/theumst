# Round 12: three notebook pages for Text

Christopher asked to redesign the left side of Text as a notebook, replacing
the appearance of two separate interfaces stacked above each other. This round
compares three left-page compositions within the existing study spread.

Open `/demo/?prototype=wisdom&revision=12&arrival=0&book=symmetry&view=realms&place=tree&realm=text&notebook=A`.
Change `notebook` to `B` or `C`, or use the bottom comparison bar. The parameter
is scoped to the reader so it does not revive the retired entrance comparisons.
The bar supports its buttons and Left/Right keys while it has focus. It is
development-only and appears only during the connected Text/Questions study view.

## The alternatives

- A, Ruled notebook: one translucent ruled leaf with a pink margin, a prominent
  passage title, and small italic section headings in the writing column.
- B, Margin notes: a dotted notebook with Statement, Workings and their tools in
  a separate annotation margin. The source prose flows in the adjacent column.
- C, Field journal: pale squared paper, dark ink, a punched margin and numbered
  passage headings. The left page explores a more physical notebook treatment
  while the Atlas keeps its existing appearance.

All three have one scrollable reading page. Statement and Workings follow the
length of their content, have no independent scrolling, and no longer split
the available height into two fixed regions. Reading actions remain below the
page. The comparison bar has its own space below the desktop spread.

## Scope

`text/notebook-variants.css` changes the layout of the existing `KnowledgeViewer`.
`text/NotebookComparison.vue` owns the comparison controls and translated labels.
`TextRealm.vue` holds the selected design and updates its URL. Switching changes
the presentation without remounting the reader, losing the selected passage,
or resetting the local notes/completion state. The three layouts can therefore
be compared using the same passage and Atlas.

The reader, Atlas, side tools, data, action handlers and sample source content
are reused. The prototype keeps the earlier in-memory limits. No production
component or version changes in this round. No design has been selected yet.

## Checks

The three changed Vue components compiled. Desktop inspection covered A, B and
C with Symmetry's definition and rotation formula. Continue reached object 202;
switching from C to B preserved that object and its equation. Browser inspection
confirmed the shared reading scroller and visible overflow on both source
sections. The comparison bar sits below the desktop folio rather than over its
reading controls. Phone checks at 390 by 844 CSS pixels covered all three designs
with object 202's formula, without horizontal overflow. Enter and Left/Right
keys switched the comparison while retaining the passage. The production Demo
build passed and excludes the notebook styles and comparison controls.
