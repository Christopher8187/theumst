# Tree of Wisdom scene prototype

Three entrance designs on the existing local `/demo/` route. This throwaway
prototype supports the live discussion in
[Settle improvements to the Theumst Web Demo](https://github.com/Christopher8187/product/issues/70).
The question is how a sacred tree can introduce book discovery and selection.

## Open it

From `frontend/demo`, run `npm run dev -- --host 127.0.0.1`.
Open `http://127.0.0.1:5175/demo/?prototype=wisdom&variant=C`.
The development server may report a different port if 5175 is occupied.

- `variant=A`: The sacred grove. Select illuminated symbols around a painted tree.
- `variant=B`: The celestial tree. Pan and zoom a drawn tree among stars.
- `variant=C`: The sanctuary. A pale tree above clouds, with books listed beside it.
- `arrival=0`: Skip the initial ascent. Replay arrival remains available.
- `book=analysis`, `book=symmetry`, or `book=light`: Open a book preview directly.

Use the bottom bar or left/right arrow keys to compare variants. Escape closes
the book preview. Search and My grimoires filter the books. Summon adds a book
to the collection for this visit. Enter grimoire reaches a next-scene placeholder.

## Christopher's decisions, 2026-09-12

- Design one scene at a time, beginning with the Tree of Wisdom, replacing the
  Arcane Library name. Realms is likely next. Christopher decides when a scene
  is satisfactory and ready to move on.
- This tree is a sacred, holy place, separate from the ordinary study area.
  The earlier cozy tree with study furniture was discarded.
- The second generated image, the pale luminous tree above clouds, is preferred.
  It appears in variant C and is the default. This selects an art direction;
  it does not approve the complete variant C interface.
- Explore an animated ascent from the homepage into space and up to the tree.
  This prototype takes about 5.7 seconds and offers Skip and Replay. Reduced
  motion skips the automatic arrival.
- Use mathematics and science sample books. Symmetry & Transformations and
  Light, Distance & Time each contain four short passages, including an exercise
  and an answer. Real Analysis retains a longer-book presence, with four chapter
  summaries previewing the existing 36-object illustrative sample.
- Mind Palace means the collection of knowledge objects a user has checked off.
  The definition is recorded in the repository glossary. Summoning or opening
  a grimoire does not add its objects to the Mind Palace. Its visual form and
  place in navigation remain open.

## Boundaries

All interaction state lives in memory and resets on reload. The prototype does
not mount the real Demo App, read account data, call the backend, or publish its
sample books. Decorative branches do not express authored dependencies or
prerequisites. This is an image and CSS arrival experiment, not a modeled 3D
space. The B tree is drawn in SVG.

The development-only boot condition is removed by the production build. The
prototype, comparison controls and generated tree images stay out of release
output. No release version, live Demo, or deployment has changed.

## Checks

Browser checks covered all three variants, arrow-key switching, search and
personal collection filtering, preview dismissal, equation and answer
disclosures, summoning, entry and return, B panning and zooming, and arrival
completion. Desktop 1440 × 900, phone 390 × 844, and narrow 308 × 760 layouts
were inspected. The narrow page had no horizontal overflow. No browser console
warnings or errors were reported during these checks.

`npm run build` passed. A search of `dist` found no prototype component names,
tree assets, sample-book titles or prototype URL condition. These checks do not
constitute acceptance of the real Demo or an implemented realms scene.

## Art

The built-in image-generation tool produced both raster tree illustrations.
Their retained prompt brief is in [art-prompts.md](art-prompts.md).

- [Night sacred tree](assets/sacred-tree-night.png)
- [Preferred pale sanctuary](assets/sacred-tree-dawn.png)

Keep this source on `codex/tree-of-wisdom-prototype`, outside `main`, as a record
of the alternatives. The owning discussion stays open until Christopher
confirms shared understanding. Later implementation must preserve the accepted
functional Demo decisions and follow the existing Wayfinder successors.
