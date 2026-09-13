# Round 9: Orbit, Brief and the world tree

Local visual prototype for issue #70, based on revision 8 at `8cdea06`.
Christopher requested volumetric book motion, contained cover text, a simpler
Brief, visible metadata and completion, and subtle mouse-follow movement in the
background. During this round he also requested a monumental world/wisdom tree,
a library at its base, and a larger altar. He withdrew the proposed repositioning
after seeing the new artwork, so its composition is retained.

Open `/demo/?prototype=wisdom&revision=9&arrival=0&book=symmetry`.
Add `scenario=progress` to inspect the in-memory completion examples. Add
`panel=brief` for Brief, or `view=realms&place=tree` for the realm book.

## Current design

Orbit uses CSS 3D book volumes with distinct front/back covers, spine, top and
bottom, and page edges. Selection moves each volume along a circular path in
depth, easing over 820 ms and turning its cover with its position. Rapid selection
continues from the current angle. Two search results use 120-degree spacing so
one does not disappear directly behind the other. Arrow keys, Home and End move
the selection, while click and Enter retain the ordinary book-selection action.
The cover uses the existing short title; the full title stays below the book and
in the selected-book details. Text occupies bounded rows rather than overflowing
the cover. Book motion starts at the requested book's resting position.

Brief now contains Summary and Contents. The Extract tab and its transition are
removed; the separate Text and Questions arrival readers are retained. Contents
still expands and selects sections. Book details opens by default. Its five
entries are Edition, ISBN, Progress, Objects and Chapters. The repeated ordinal
in the request was interpreted as adding object and chapter counts as the final
two entries. Chapter totals follow the displayed chapter hierarchy, excluding
the book wrapper and nested sections. The smaller emblem leaves room for details.

The native completion bar always appears, including at zero. It shows completed
objects, total objects and a rounded percentage. The same book values feed Brief,
the right leaf's upper margin in the realm chooser, and the grimoire title area
inside a realm. Christopher rejected the initial floating progress box; the
current version uses a thin line integrated into the book and arrival header.

The new panorama preserves ivory bark, subtle gold, pale pink/lavender foliage,
clouds and scholarly/sacred details. The tree extends beyond the frame and its
library galleries establish the scale. The altar is a larger reading sanctuary.
The requested orders-of-magnitude increase is an art direction expressed through
scale cues, not physical dimensions in a modeled world. The continuous tree-to-
altar pan uses the same image with the recorded aspect ratio of 2161/728.

The painted background follows a mouse slightly in the same direction, bounded
by 6 horizontal and 4 vertical pixels and less on small screens. A fixed 1.8%
overscan conceals the image edges. Damped movement settles and stops requesting
frames. The interface stays stationary. Mouse-follow resets during scene travel,
when the pointer leaves or the window loses focus; hidden documents stop it.
Touch and reduced-motion preferences disable mouse-follow. Reduced motion also
snaps Orbit selection to its resting position.

## Components

- `OrbitVariant.vue` renders the book positions and selection controls.
- `ProjectedBook.vue` renders the six faces and contained cover typography.
- `useOrbitMotion.ts` owns the continuous angle and frame cleanup.
- `useSceneParallax.ts` owns mouse-follow and preference/visibility cleanup;
  `ArrivalTransition.vue` applies it to a wrapper around the painted layers.
- `GrimoireReader.vue` and `BriefSummary.vue` own the reduced Brief and metadata.
- `bookStats.ts` derives chapter/object totals and bounded completion values.
- `GrimoireCompletion.vue` renders the shared native progress indicator.
- `RealmBook.vue` and `RealmDestination.vue` place completion inside their headers.
- `sceneArt.ts` selects the new panorama; provenance is in `scene-art-prompts.md`.

GPT-5.6 Sol implemented the Brief changes and independently reviewed the combined
motion/layout source. A separate art agent created the new panorama using the
built-in image tool. The root agent integrated the changes and performed the
browser review. Review corrections included two-result spacing, reducing the
Brief emblem so metadata fits, and mobile header offsets.

## Verification

The 26 prototype Vue components compile and the Demo production build passes.
The new Orbit, panorama, and mouse-follow code are excluded from production output.
Rendered checks covered 1280 × 800 and 390 × 844: all three short cover titles
fit, the document had no horizontal overflow, and both object/chapter metadata
values fit in Brief without scrolling. Contents expansion and section selection
stay inside Contents. Brief exposes only Summary and Contents on the phone.
Two-result search showed separated book positions; selection changes the named
grimoire. Measured CSS transforms include depth, and real pointer input changed
the scenery offset by a few pixels with the same horizontal direction.
The 2/4 sample completion carried from Brief to the realm-page margin and Text
header. The Text sample still exposes its original chapter and passage controls.

This remains on `codex/tree-of-wisdom-prototype`. It does not merge, deploy, or
change production versions. The next implemented Demo release remains 0.0.4.
Completion examples are in memory and neither selecting nor adding a book
checks off knowledge. Full individual learning views remain later design rounds.
