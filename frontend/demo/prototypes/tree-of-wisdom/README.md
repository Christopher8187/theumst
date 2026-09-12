# Sanctuary grimoire interface prototype

This throwaway prototype supports
[Settle improvements to the Theumst Web Demo](https://github.com/Christopher8187/product/issues/70).
It explores selecting and adding grimoires in an interface intended eventually
to work inside the game.

## Run and compare

From `frontend/demo`, run `npm run dev -- --host 127.0.0.1`.
Open `http://127.0.0.1:5175/demo/?prototype=wisdom&revision=3&variant=B`.
Use the port reported by Vite if 5175 is occupied.

All three variants keep the approved pale Sanctuary tree:

- A, Projection: a projected inventory with selected-book details alongside it.
- B, Orbit: the leading direction, with floating book selections and a compact description/action area. It is the default when no variant is specified.
- C, Signals: compact book rows with an expanding detail area.

The bottom comparison controls and left/right arrow keys switch variants.
`arrival=0` skips the initial ascent. `book=symmetry` or `book=light`
selects a short sample. Search matches titles and subjects. The slash key focuses
search. My grimoires filters the personal collection. Add grimoire adds the
selection for this visit; Enter grimoire reaches a next-scene placeholder.

Read a sample opens a separate projected reading surface. Its passage choices,
Previous/Next controls, Close, and Add/Enter actions stay in place. The arrow keys
turn sample pages while it is open; Escape closes it. Closing restores the
selection underneath. Samples do not expand the selection panel.

Descend is fixed at bottom left on desktop and top right on phones. It retraces
the ascent to a local home-scene landing. Ascend to the tree travels back without
losing the selected book or this visit's added grimoires. Both directions offer
Skip. `place=home` opens the home-scene landing directly. Open homepage navigates
to `https://theumst.com/`; the landing is a journey study, not the production
homepage shell. Integration with production routing/browser history is deferred.
Reduced motion skips automatic arrival and replaces travel with a brief still
crossfade. All journey layers remain mounted at both endpoints.

## Decisions and open questions

Christopher selected the pale tree above clouds from the first art pair.
The Sanctuary is sacred and separate from the ordinary study area. The
earlier domestic tree setting was discarded.

The next correction replaces the homepage's retro window style in the Demo.
Christopher wants a techy, sleek, neon, Lo-Fi grimoire interface, with Subnautica 2
as a reference, because this Demo should eventually be in the game. The new
proposals use blue translucent surfaces, fine luminous edges, cyan, pink and
violet accents, and projected book shapes. Christopher is leaning toward B, but has not approved a final entrance design.

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

Revision 2 fixed exposed image edges, but Christopher still found ascent
uneven and descent absent. Its separately timed fades and final overlay removal
did not establish continuous movement. Its small return control could be missed.

Revision 3 uses one 6.8-second progress timeline for the images, clouds, stars and
interface visibility. Descent traverses the same transforms and opacity curves
in reverse. Both image layers cover the frame throughout their translation and
share their exact resting positions and shading with the idle scenes. There is
no replacement image or route reload at the tree endpoint.

The old expanded Symmetry sample had 940px of content in a 308px-high detail area.
The revised B details fit without overflow at 1440 × 900, 390 × 844 and 308 × 760.
The separate reader was checked with page selection, keyboard page turns, answer
reveal, Escape, adding and entering. The physics calculation is broken across
lines, and both the reading area and equation fit without scrolling at 308 × 760.
A and C also open the shared reader. The local descent/ascent round trip preserves
selection and added books. Animation smoothness remains a visual decision for
Christopher; this is an image-based journey, not a 3D environment.

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
See [the art prompt brief](art-prompts.md). Revisions 2 and 3 use the existing pale art.

## EVE Online reference

Christopher added EVE Online as another inspiration during revision 3.
The particular screens and features to borrow are still open. Relevant primary
sources for the next discussion:

- [Skill Plans and How They Work](https://support.eveonline.com/hc/en-us/articles/4406388028178-Skill-Plans-and-How-They-Work): goal-oriented skill lists, filters, milestones, and tracking. A candidate reference for planning a knowledge-growth journey, distinct from checked-off knowledge in the Mind Palace.
- [Updates to Skill Training](https://www.eveonline.com/news/view/updates-to-skill-training): visual examples of planned growth before acquiring the required skills.
- [Photon UI tips](https://support.eveonline.com/hc/en-us/articles/7264100568220-User-Interface-Tips-and-Tricks): transparency and compact controls over the world. A possible reference for managing complexity while keeping the scenery visible.

These are references for discussion. They do not settle a planner model or
replace the approved sacred tree and Lo-Fi atmosphere.