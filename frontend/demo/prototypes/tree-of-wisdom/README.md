# Sanctuary grimoire interface prototype

This throwaway prototype supports
[Settle improvements to the Theumst Web Demo](https://github.com/Christopher8187/product/issues/70).
It explores selecting and adding grimoires in an interface intended eventually
to work inside the game.

## Run and compare

From `frontend/demo`, run `npm run dev -- --host 127.0.0.1`.
Open `http://127.0.0.1:5175/demo/?prototype=wisdom&revision=2&variant=A`.
Use the port reported by Vite if 5175 is occupied.

All three variants keep the approved pale Sanctuary tree:

- A, Projection: a projected inventory with selected-book details alongside it.
- B, Orbit: floating book selections above a separate reading and action area.
- C, Signals: compact book rows with an expanding detail area.

The bottom comparison controls and left/right arrow keys switch variants.
`arrival=0` skips the initial ascent. `book=symmetry` or `book=light`
selects a short sample. Search matches titles and subjects. The slash key focuses
search. My grimoires filters the personal collection. Add grimoire adds the
selection for this visit; Enter grimoire reaches a next-scene placeholder.

Return home plays the descending transition and then navigates to
`https://theumst.com/`. Replay ascent repeats the arrival. Both offer Skip.
Reduced motion skips automatic arrival and shortens return to a still handoff.

## Decisions and open questions

Christopher selected the pale tree above clouds from the first art pair.
The Sanctuary is sacred and separate from the ordinary study area. The
earlier domestic tree setting was discarded.

The next correction replaces the homepage's retro window style in the Demo.
Christopher wants a techy, sleek, neon, Lo-Fi grimoire interface, with Subnautica 2
as a reference, because this Demo should eventually be in the game. The new
proposals use blue translucent surfaces, fine luminous edges, cyan, pink and
violet accents, and projected book shapes. No interface variant is approved yet.

The observed [Subnautica 2 inventory screenshot](https://img.gamewith.net/img/original_be6467b40e96fc1de8c4901fccb32338.png)
is reproduced in [GameWith's guide](https://gamewith.net/subnautica-2/75851).
It informed the visual study; no game artwork or interface assets were copied
into the prototype.

Mind Palace remains the collection of knowledge objects a user has checked off,
as defined in the repository glossary. Opening or adding a book does not check
off its contents.

Christopher wants to plan a journey of expanding knowledge: choose grimoires
and decide where future study will lead. The proposed personal space's name must
express this function. The original reference to “Domain Expansion” concerned
mental growth through reading, not merely a place with a magical name.
Mind Atlas and Horizon Map are candidate names for the planner, not settled
terms. The relationship to the existing Outer grimoire view, journey editing,
and how growth appears still need discussion. The current collection filter is
only a simple step toward that future planner.

Design one scene at a time. Realms is likely next when Christopher is satisfied
with this entrance. Do not treat this checkpoint as permission to implement
the planner, redesign Realms, merge or deploy.

## Verification and limits

The original ascent moved the image down 80% while it remained visible.
A browser measurement reproduced the edge inside the frame at approximately
12 pixels, with opacity 1. The corrected movement scales the image enough to
cover the viewport throughout its small translation; a cloud layer covers the
handoff. The overlay is fixed to the viewport, including on scrolled phones.
The same browser check passed for ascent and descent. Descent reached the actual
homepage.

Browser checks covered three layouts, search, collection filtering, adding,
sample equations, disclosure expansion/collapse, entry and return. Desktop
1440 × 900, phone 390 × 844 and narrow 308 × 760 layouts were checked. Narrow
layouts scroll vertically without horizontal overflow. No console errors or
warnings were observed.

The Demo production build passed. Its output excludes these components and
the generated tree assets. All sample interaction state is in memory; there
are no account, backend, publication or saved-progress mutations. This is CSS,
SVG and raster scene exploration, not modeled 3D or a working learning planner.

## Source checkpoints

Keep this work on `codex/tree-of-wisdom-prototype`, outside main.
Commit `194e42b` preserves the earlier sacred-tree comparisons and retro
preview. Their old components remain as reference material and are no longer
mounted by the current prototype.

The built-in image tool generated the retained [pale tree](assets/sacred-tree-dawn.png)
and [night alternative](assets/sacred-tree-night.png).
See [the art prompt brief](art-prompts.md). Revision 2 uses the existing pale art.
