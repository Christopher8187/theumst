# Round 18: compact Atlas groups

Open `/demo/?prototype=wisdom&revision=18&arrival=0&book=analysis&view=realms&place=tree&notebook=B&realm=text`.

The notebook uses compact layout spacing instead of scaling down its text.
Cards remain 160×64. Horizontal group gutters shrink from 140 to 80 drawing
units, vertical group gaps from 76 to 48, and gaps between cards from 42 to 28.
Leaf heading space shrinks from 88 to 52; enclosing-group heading space from
92 to 44. Side and bottom padding are also reduced. Routing clearances follow
the smaller gaps so arrows still have usable paths around cards and headings.

The enclosing groups use 4-unit corners and inner groups use 3-unit corners.
Cards also use small uniform corners. The repeated "n objects shown" line is
removed. Omitted-position badges show `+N`, retaining "outside view" in their
accessible name and hover title, and retaining the click/keyboard range report.
This allows the counts to fit safely within the more compact groups.

The two existing layout methods, object qualification and relationship meanings
remain. Ordinary Demo presentation does not opt into compact density.

## Verification

- `node tests/atlas-compact.mjs` passed both layouts at 8, 16 and 24 objects,
  checking preserved selection and relationships, no card/heading crossings,
  no overlapping cards, all gap labels and smaller overall drawing dimensions.
- Fourteen frozen Real Analysis cases passed relationship and gap-label checks
  for objects 1, 2, 4, 13, 25, 29 and 36 in both layouts.
- `node tests/atlas.mjs` and `node tests/atlas-api.mjs` passed.
- `node node_modules/vite/bin/vite.js build` passed.
- The browser showed tighter groups without object-count lines. Selecting
  Subsequences updated the reading page and centered the graph. Hierarchy
  was opened and visually inspected at the normal desktop viewport.

This is a local prototype update, with no production deployment or release change.
