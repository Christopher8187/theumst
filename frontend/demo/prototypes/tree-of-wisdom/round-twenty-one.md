# Round 21: aligned pages and shorter graph cards

Open `/demo/?prototype=wisdom&revision=21&arrival=0&book=analysis&view=realms&place=tree&notebook=B&realm=text`.

Realms page ruling now uses the drawing area's bounds. Its left margin and
horizontal lines align with the header rule on both pages. The illustrations
and book material retain their existing design.

`FolioNavigation.vue` owns the return arrow and grimoire title.
`FolioStatus.vue` owns completion and language controls. Realms and the Text
and Questions notebooks reuse these components. Local Atlas moves 16 pixels
right to clear the bookmark. Text keeps narrower progress spacing to make room
for the section breadcrumb.

Display math is centered and has eight pixels of space above and below.
Empty Workings headings and their Listen buttons are hidden in the notebook;
the unused writing lines and any book-image actions remain available.

Compact Atlas cards place the number beside the title and shrink from 64 to
52 drawing units high. Rendering, camera centering, overview and routing use
the dimensions returned by the layout. Ordinary Demo cards stay 160 by 64.
Long dependency departures stop eight units outside their source card, while
approaches to arrowheads retain their longer clearance. This removes the
down-and-up detours in 1 to 27, 2 to 27 and 4 to 25.

## Verification

The endpoint regression first reproduced all three detours and now passes.
The compact, route-clearance, ordinary Atlas, Atlas API and notebook math
checks pass, as does the Demo build. Compact checks cover both layouts and
14 frozen Real Analysis cases. Browser checks confirmed centered math,
hidden empty Workings, 52-unit cards, matching page-rule widths and shared
headers at desktop and 390-pixel phone widths. The temporary viewport was reset.

Local prototype only. No deployment or release version change.
