# Altar and realm book

Local design exploration for issue #70. One prototype, retaining the selected
revision 6 entrance. No comparison bar, production integration, merge, deployment,
or release change. The next implemented Web Demo version remains 0.0.4.

## Question and direction

How should entering a grimoire move through the Sanctuary and reveal the eight
realms? Christopher requested a continuous move to the existing altar, followed
by a translucent hi-tech book rising into view. Ruled lines, a central fold,
background blur, and drawings that illuminate on selection establish the book.

Christopher then rejected a grid and simple cartoon doodles. The current spread
uses unequal positions, sizes, and angles. Its pen-and-ink illustrations have
separate contour, structural, construction, and hatching strokes: a perspective
folio, faceted solid, asymmetric quill, chambered shell, celestial aperture,
reading lamp, botanical sprig, and spiral stair. Cyan, violet, and dusty pink
remain the selection colors. The two larger illustrations anchor the pages.
The final artwork and motion are proposals awaiting Christopher's judgment.

## Try it

Run `npm run dev -- --host 127.0.0.1` in `frontend/demo`.

- Start at `http://127.0.0.1:5175/demo/?prototype=wisdom&revision=7&arrival=0&book=symmetry`.
- Add the grimoire, then choose Enter grimoire. Brief's Enter and My grimoires'
  Open action lead to the same altar.
- Add `&view=realms` to open the book directly. `&realm=questions` opens that
  local arrival. `from=collection` restores the collection as the return origin.
- First click, tap, Space, or Enter selects a drawing. The next activation of
  that drawing enters it; the shared Enter button does the same. Repeated
  keydown events from holding Enter do not count as another activation. Two
  quick pointer presses intentionally follow the two-press behavior.
- Realms or Escape from a destination returns to the book. Back to grimoires
  reverses the journey, returning to the entry location. Skip movement finishes
  the current journey. Reduced motion changes directly to the destination.
- My grimoires now has Remove on every book. `scenario=progress` supplies 12/36
  completed for Real Analysis and 2/4 for Symmetry for a removal/re-add check.

## State and scope

Collection membership is independent of checked-off knowledge. Removing a book
changes the in-memory membership array only. It leaves the sample completion
values and source material unchanged; re-adding exposes the same progress.
This prototype does not call an API or persist collection changes. The accepted
future behavior is also that removal must not affect the Mind Palace.

Text and Questions arrivals reuse the local extract component. Questions filters
to exercises and supplies a short original sequence exercise for Real Analysis,
whose entrance passages describe chapters. That fallback belongs to this arrival
sample and does not change the book's count or entrance contents. Notes offers a
local text area. Its text survives switching realms while this book is mounted,
but leaving the book or reloading discards it. Review, Preview, Advice, Expand,
and Progress show their destination and purpose, with the study view explicitly
left for a later design round. These samples do not replace the existing Demo's
reading, notes, completion, discovery, or graph functions.

URL parameters record the current grimoire, book/destination view, and return
origin. The prototype still uses replacement history, so the browser Back button
does not traverse every local interaction. Use the visible return controls.

## Components and motion

- `TreePrototype.vue` owns grimoire selection, collection membership, scene, and
  the return origin. It passes the chosen book and animation state to the view.
- `useAltarTravel.ts` owns one reversible 0–1 timeline, lasting 3.6 seconds.
  Entrance opacity, horizontal image travel, and book reveal derive from it.
- `ArrivalTransition.vue` keeps the same panorama image, scale, and vertical
  framing during horizontal travel. The end position is clamped to the image
  boundaries. It retains the existing home/tree ascent and descent.
- `RealmBook.vue` owns selection and local realm entry. Props provide the book,
  reveal amount, and readiness; events return realm changes and the request to
  leave. It animates both entry and return. Visible ink rotates within stable
  hit areas instead of rotating adjacent interactive rectangles.
- `RealmDiagram.vue` draws the eight illustrations. `realms.ts` owns their marks,
  limited palette, and translated purpose text using the current glossary.
- `RealmDestination.vue` presents the small local arrivals. `BriefExtract.vue`
  retains the shared excerpt behavior and bounds empty paging.

Short landscape screens scroll a spread with a usable minimum height. Portrait
phones retain two leaves, with the sketches staggered vertically. The caption
space stays fixed when a realm is selected so the page geometry does not jump.

## Review and verification

GPT-5.6 Sol performed two source-only adversarial reviews of the interaction and
taste. It identified empty Questions paging, a missing reverse realm fade,
excessive color variety, collection return origin, removal focus, short landscape
space, and an animation fill-mode conflict. Those findings were addressed.
Its second drawing review found that the new silhouettes and internal structures
read as scientific illustrations; the root agent performed rendered checks.

Verification is local and uses in-memory examples, not backend acceptance:

- All eight selections set their selected state, enter the correctly named
  local destination, and return to the realm book.
- Keyboard Enter first selects, then enters. Real Analysis Questions displays
  the original sequence exercise and disables Next at its single passage.
- Removing the sole Real Analysis book reaches the empty collection; adding it
  again retains 12/36 completed. No completion mutation is made.
- During the measured desktop return, the image remained the same resource at
  2136.406 × 720.375 CSS pixels. Intermediate positions moved continuously from
  x≈−856.41 toward zero and covered the 1280-pixel viewport throughout.
- Collection entry records `from=collection`. Return and direct view parameters
  use the same selected book. Destination return preserves the selected drawing.
- Desktop and narrow portrait layouts were inspected, including Japanese labels
  at 308 × 760. The document had no horizontal overflow. Hit area geometry was
  checked again after moving rotation from the buttons to their ink.
- Vue script/template/style compilation and the Demo production build pass.
  The production build continues to exclude the prototype route and artwork.

The full backend and release acceptance procedure is outside this local visual
round. Individual study designs, real collection persistence, and Mind Palace
integration remain for implementation after the scene designs are accepted.
