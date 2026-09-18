# Round 16: controls inside the book

Open `/demo/?prototype=wisdom&revision=16&arrival=0&book=symmetry&view=realms&place=tree&realm=text&notebook=B`.

Realms, language and grimoire completion now occupy a row inside the book.
The grimoire title stays on the left leaf; 書 Text sits at that leaf's upper
right. Local Atlas sits beside the chapter path in the right leaf's heading.
The left leaf's five square tools are Crystallization, Dependencies, Notes,
Find neighbors and Train. They sit beside Prompt, above Back, Continue and
Mark done. Train becomes Book while in Questions so the existing return to
reading remains available. The lower tools stay available while source text
scrolls. The hover label stays anchored above the five symbols.

## Atlas presentation

The visible Grimoire order and Dependency legend is removed. The qualifying
object count moves into Settings. The map has dark translucent glass, subtle
cyan grid lines, brighter selected nodes, larger text and a small overview that
shows the current viewport and selected object. Settings retains the two distance
controls, both layouts, scale and centering, and adds Fit map.

The visual references were the [Subnautica PDA study](https://www.behance.net/gallery/94024343/Subnautica-game-ui-design)
and [EVE's Photon UI](https://www.eveonline.com/news/view/improving-photon-ui).
The PDA reference informed the blue glass and illuminated selection. EVE's
compact controls and consistent typography informed the settings and map frame.
The notebook's original paper ruling, blue transparency and serif prose remain.

`atlas-instrument.css` owns the prototype map treatment. `useAtlasCamera.js`
handles display bounds, zoom and centering. It removes padding around the
finished drawing and defaults the prototype to 110% instead of 65%. It includes
nodes, groups, routes and gap badges in the visible bounds. The existing
`domain/atlas.js` is unchanged: node positions, grouping, arrow routing,
qualification and limits still come from the same algorithms.

## Verification

- `node tests/atlas.mjs` passed the supplied Reading rows and Hierarchy cases.
- `node tests/atlas-api.mjs` passed selection, normalization and both arrow layouts.
- `node node_modules/vite/bin/vite.js build` passed.
- Browser checks covered the five-tool layout; Train to object 204; Book back
  to reading; Mark done changing progress to 1/4 and 25%, then restoration to
  0/4; Continue to objects 202 and 203; Fit map; restoration to 110%; and the
  count appearing only inside Settings.

An old tab stalled during hot reload while camera work was in progress. A fresh
revision-16 tab loaded and passed those checks. The tab recovery limited the
viewport checks for this round; the fresh desktop render was inspected.

This remains a local prototype on `codex/tree-of-wisdom-prototype`, with no
release or production deployment.
