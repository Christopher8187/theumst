# Round 20: shared realm book and adaptive Atlas

Open `/demo/?prototype=wisdom&revision=20&arrival=0&book=analysis&view=realms&place=tree&notebook=B&realm=text`.

Realms, Text and Questions use `RealmFolio.vue` for the translucent blue pages,
blur, spine, page edges and lavender bookmark. The reading view has equal-width
pages and a centered spine, with 16-pixel top and bottom margins on desktop.
The entrance animation no longer retains a layer that blocks background blur.
The narrow reading layout stacks the pages with equal side margins.

Context and other object types regain their rectangular outline. Inline math
stays within prose. Display math starts on the next ruled row, and that row
grows to contain tall notation. Ordinary prose and empty writing space retain
30-pixel ruling. `NotebookMath.vue` uses the existing escaped KaTeX renderer.

The Atlas regains its subtle square grid and shares the book's lighter glass
colors and hover illumination. Compact reading layout chooses chapter rows
from their measured widths and heights. In the Bounded sequences sample,
chapters 1, 2 and 3 share a row and the wider chapter 4 sits below.

Incoming and outgoing aligned arrows reserve distinct ports. Long horizontal
dependencies bypass intervening cards below the row. Arrowheads reserve room
for a straight final segment, and other routes avoid that room. In the reported
sample, 4 to 25 passes lower, the +5 label sits above its gold 19 to 25 arrow,
and the 19 to 25, 25 to 27 and 27 to 34 arrows have separate tips and tails.

## Verification

- `atlas-endpoints.mjs` covers the reported chapter arrangement, arrow ports,
  4 to 31 final segment and +5 placement.
- The route-clearance, compact Atlas, ordinary Atlas and Atlas API checks pass.
  Compact checks include 14 frozen Real Analysis cases and both layouts.
- `notebook-math.mjs` checks inline/display separation, surrounding line breaks
  and escaping. Browser verification also covered a tall matrix and arrow,
  which expanded its row without intersecting the next line or adding a
  needless horizontal scrollbar.
- The Demo Vite build passes. Browser checks cover desktop alignment and blur,
  return navigation, and the book at 390 by 844. Temporary viewport overrides
  and the temporary math verification page were removed.

Local prototype only. No production deployment or release version change.
