# Sanctuary grimoire interface prototype

This throwaway prototype supports
[Settle improvements to the Theumst Web Demo](https://github.com/Christopher8187/product/issues/70).
It explores selecting and adding grimoires in an interface intended eventually
to work inside the game.

## Run and compare

From `frontend/demo`, run `npm run dev -- --host 127.0.0.1`.
Open `http://127.0.0.1:5175/demo/?prototype=wisdom&revision=4&variant=B`.
Use the port reported by Vite if 5175 is occupied.

All three variants keep the approved pale Sanctuary tree:

- A, Projection: a projected inventory with selected-book details alongside it.
- B, Orbit: the leading direction, with floating book selections and a compact description/action area. It is the default when no variant is specified.
- C, Signals: compact book rows with an expanding detail area.

The bottom comparison controls and left/right arrow keys switch variants.
`arrival=0` skips the initial ascent. `book=symmetry` or `book=light`
selects a short sample. Search matches titles and subjects. The slash key focuses
search. My grimoires opens a separate personal collection with its own search,
summary, publisher, progress, Brief and Open actions. Its search and the Tree
search keep independent values. Add grimoire adds the selection for this visit;
Enter grimoire reaches a next-scene placeholder.

Brief opens a separate reading view with Overview, Contents and Extract.
Overview shows the supplied summary and metadata, contents count and progress.
Contents uses the existing Demo's expandable chapter tree and keyboard controls.
Real Analysis has four chapters and twenty section rows. Each short book has
two chapters with two sections each, matching its four extract passages.
Extract has chapter choices, numbered passage buttons and Previous/Next controls.
The arrow keys turn passages only while Extract is selected; Escape closes Brief.
Close and Add/Enter stay visible while the body scrolls. Closing restores the
selection and focus underneath.

The language selector uses the existing persisted Demo preference for English,
Chinese and Japanese. Source book text stays in its supplied language.
More contains the previous Review, Advice, Expand and Generate actions with
their existing coming-soon behavior. Publisher and non-zero progress appear
on the Tree's book choices. Collection order follows this visit's add/open activity.

Optional URL scenarios make additional states inspectable:

- `view=collection&scenario=empty-collection` opens an empty personal collection.
- `scenario=empty-library` opens the unavailable-library state.
- `scenario=progress` supplies 12/36 completed for Real Analysis and 2/4 for Symmetry.

These progress values are explicitly labeled sample state. Adding or opening
a grimoire never completes its contents.

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
and how growth appears still need discussion. The current personal collection
does not implement that future planner.

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

## Revision 4 and next implementation

Revision 4 restores entrance and Brief functions identified by two independent
GPT-5.6 Sol adversarial reviewers. Their findings, fixes and the browser checks
are recorded in [the functionality review](functionality-review.md).
The original Demo remains available at `/demo/` without the prototype parameter.
The prototype's Enter action does not hand a selected book to that application.

Christopher specified **0.0.4** for the next implemented Web Demo release.
The previous Demo label **0.1.0** is erroneous. Update all production language
labels and release documentation to 0.0.4 during that implementation cycle.
The prototype's language values already carry that correction; revision `4`
in its URL is only a prototype checkpoint. This work does not publish a release
or change the website's separate version.

Keep the working downstream Demo functions when integrating this entrance:
Realms, Text, Questions, Notes, completion, discovery, Atlas, related knowledge,
cross-book return, saved study positions and availability handling. This
checkpoint does not replace them with the prototype's placeholder.

## EVE Online reference

Christopher added EVE Online as another inspiration during revision 3.
The particular screens and features to borrow are still open. Relevant primary
sources for the next discussion:

- [Skill Plans and How They Work](https://support.eveonline.com/hc/en-us/articles/4406388028178-Skill-Plans-and-How-They-Work): goal-oriented skill lists, filters, milestones, and tracking. A candidate reference for planning a knowledge-growth journey, distinct from checked-off knowledge in the Mind Palace.
- [Updates to Skill Training](https://www.eveonline.com/news/view/updates-to-skill-training): visual examples of planned growth before acquiring the required skills.
- [Photon UI tips](https://support.eveonline.com/hc/en-us/articles/7264100568220-User-Interface-Tips-and-Tricks): transparency and compact controls over the world. A possible reference for managing complexity while keeping the scenery visible.

These are references for discussion. They do not settle a planner model or
replace the approved sacred tree and Lo-Fi atmosphere.
