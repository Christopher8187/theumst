# Round 17: one book heading and an integrated Atlas

Open `/demo/?prototype=wisdom&revision=17&arrival=0&book=analysis&view=realms&place=tree&notebook=B&realm=text`.

Realms now sits beside Real Analysis in one 64px header, replacing the previous
50px navigation row and 76px heading row. Text remains at the right of the left
leaf. The right leaf holds Local Atlas, its chapter path, completion and language.
The desktop book has equal 16px top and bottom margins. Narrow screens retain
the stacked leaves, with the Atlas heading and controls above its graph.

The overview is an inset at the lower right of the graph. It no longer occupies
a separate strip below it. Zoom out, a scale selector and Zoom in remain visible
at the graph's lower left. Settings retains distance, layout, centering, Fit map
and qualifying-object count. Node placement and arrow routing are unchanged.

## Verification

- Real Analysis inspected at the normal 1280×720 viewport and at 390×844.
- Browser measurements confirmed a 64px header, equal 16px desktop margins,
  and the overview entirely inside the graph bounds.
- Zoom out changed 110% to 100%; Zoom in restored 110% while Settings stayed
  closed. Settings opened with its remaining controls. Narrow-screen labels,
  lower tools, graph, zoom and overview were inspected.
- `node tests/atlas.mjs` and `node tests/atlas-api.mjs` passed.
- `node node_modules/vite/bin/vite.js build` passed.

This is a local prototype update, with no production deployment or release change.
