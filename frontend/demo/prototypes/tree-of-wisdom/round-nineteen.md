# Round 19: notebook ruling and clear Atlas routes

Open `/demo/?prototype=wisdom&revision=19&arrival=0&book=analysis&view=realms&place=tree&notebook=B&realm=text`.

Statement and Workings each occupy a 30-pixel ruled row. The same ruling
continues through prose, displayed mathematics and the empty writing area.
The translucent blue palette remains. Context and the object title share one
line. Local Atlas and the section breadcrumb also share one line. Segoe UI
is used across the Text page's headings, prose, labels, controls and graph;
KaTeX retains its mathematical glyphs and the realm mark retains its character
font. The right page and graph no longer carry notebook or grid ruling.

The Realms spread now begins 16 pixels from the top and ends 16 pixels from
the bottom at the normal desktop size. Return navigation, book title, progress
and language sit inside the book. At narrow widths the return arrow retains
its accessible name while its long label is hidden.

Compact Atlas reading rows use each group's actual width. The 4.1 to 4.2
gutter in the reported Real Analysis view drops from 392 to 56 drawing units.
Matching connection ports keep the short aligned arrows straight, including
the separate gold and dependency arrows between the same objects. Long
same-column dependencies leave from the side. Routing costs discourage
following another arrow or a group border within eight units, while permitting
perpendicular crossings. Selection, relationship meaning and the two layout
methods remain unchanged.

## Verification

- `node tests/atlas-route-clearance.mjs` reproduced the reported jogs,
  crowded routes, border-following arrow and excessive section gutter before
  the fix. It now passes, including the horizontal 1 to 4 dependency.
- `node tests/atlas-compact.mjs` passes both layouts, sparse and dense data,
  and 14 frozen Real Analysis cases. Selection and relationships are retained,
  cards and headings are clear of routes, and omitted ranges retain labels.
- `node tests/atlas.mjs`, `node tests/atlas-api.mjs`, and the Vite build pass.
- Browser checks confirm 30-pixel heading rows and ruling, shared typefaces,
  side-by-side headings, selection updates and Text/Realms return navigation.
  The expanded Realms book also fits at 390 by 844 without page overflow or
  overflowing headers. The temporary viewport override was reset.

Local prototype only. No production deployment or release version change.
