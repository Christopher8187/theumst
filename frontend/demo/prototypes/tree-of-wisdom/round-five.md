# Brief and navigation placement, round 5

13 September 2026. Christopher requested six local design studies and
GPT-5.6 Sol adversarial review of their taste. The entrance itself uses the
previous Orbit layout. No final Brief or navigation choice has been approved.

## Vocabulary mapping

Checked the shared knowledge model in the Parent Repo's CONTEXT-MAP.md,
[Theumst's vocabulary](../../../../CONTEXT.md), and the existing
[realm choices](../../src/components/RealmRouter.vue).

| Existing Demo label | Current vocabulary | Meaning |
| --- | --- | --- |
| Review | Review realm, 覺 | Spaced repetition. Name unchanged. |
| Advice | Advice realm, 意 | Collected advice for reflective, meditative learning. Name unchanged. |
| Expand | Expand realm, 道 | Discover knowledge outside the current grimoire, considering additional prerequisite learning. Name unchanged. |
| Generate, using 境 | Progress realm, 境 | Study statistics and longer-term planning through the Outer grimoire view. Generate was an error, corrected explicitly by Christopher. |
| Arcane library | Tree of Wisdom | The sacred grimoire entrance. The visible heading is omitted in this round at Christopher's request. |

The entrance exposes Review, Advice, Expand and Progress across grimoires,
as Christopher clarified. These are the same learning activities with broader
scope. Their ranking, scheduling and selection rules are not implemented here.
The per-grimoire Expand definition assumes all knowledge in the base grimoire
has been studied; how to supply that starting assumption across grimoires
remains a later functional question.

Mind Palace still means checked-off knowledge objects. It is not a replacement
name for Progress, My grimoires, or the future learning planner. Brief is the
book introduction used here. It is distinct from the Preview realm, which
shows motivating results in this and further grimoires.

My grimoires belongs in the same navigation group as the four actions. It
remains a collection destination, separated by a quiet rule inside the shared
frame. It no longer has a separate top-bar button.

## Comparison design

A-C change Brief's structure. A is a translucent two-page folio; B keeps the
contents beside the main pane; C uses a right-side drawer with a localized
backdrop. All retain chapters, extracts, formulas, answer reveal and Add/Enter.
D-F change the placement of the whole five-entry navigation group. D is a top
menu, E a persistent rail, F a persistent dock. Their scope is across grimoires.
Brief and navigation choices are retained independently in the URL.

Removed visible copy: publisher provenance, Selected grimoire, the subject/count
strapline, The Sanctuary and Tree of Wisdom headings, Back inside Brief,
membership status, the source-language note and repeated Overview headings.
The close icon and accessible names remain. Summary is the single label;
edition, ISBN and progress move into a closed Book details disclosure.
The underlying book data still retains publisher metadata.

## Taste review

Two independent GPT-5.6 Sol reviewers cover Brief and navigation respectively.
Their initial challenges led to distinct silhouettes, a quieter folio seam,
contents without nested cards, a localized drawer backdrop, removal of redundant
More toggles on the rail/dock, a consistent treatment of the five navigation
marks, and reserved space for the bottom dock.

Both reviewers then inspected the rendered alternatives at 1280 x 720 in
separate temporary browser tabs, without changing the shared viewport.

The Brief reviewer ranked C, A, B for the requested visual direction. C keeps
the sacred tree most visible. A resembles a magical folio. B is the most useful
reading arrangement but risks looking like a conventional document manager.
Changes following that review:

- B opens on Extract, including on phones.
- The first chapter of each short book opens initially. Small contents lists
  omit the section-count telemetry.
- A's emblem shrank to 96px, allowing Summary and closed Book details to fit
  at 720px high without a scrollbar along the folio seam.
- C hides the underlying Orbit detail panel and navigation while Brief is
  open. The tree stays clear and projected books dim.
- C has less header and passage padding, a quieter Close focus treatment,
  and a faint decorative orbital line in Summary. The short physics
  calculation now fits at 720px high without scrolling.

The navigation reviewer ranked F, E, D for the game direction. D was their
preference for infrequent utility access. Changes following that review:

- F reserves room above the dock and places action feedback above its controls.
  Its scope label is attached to the dock border.
- E has a narrower, more transparent rail. On phones it becomes a horizontal
  strip below search, with room reserved beneath it.
- D has a smaller dropdown and reserved header space. Escape closes the menu
  and returns focus to its trigger.

These are reviewer preferences, not Christopher's selection.

## Revision 5 verification

Local in-memory prototype only, using the existing installed dependencies.
No backend, database, account or deployment verification is claimed.

- All 20 prototype Vue files passed direct script, template and style compilation
  with `@vue/compiler-sfc`.
- `node tests/graph-contents.mjs` passed from `frontend/demo`.
- `npm run build` passed from `frontend/demo`. Its production output excludes
  the development-only prototype components and tree art.
- Rendered A-F at 1280 x 720 and 390 x 844. Also checked the collection, E/F
  navigation, and B reader at 308 x 760 with Japanese interface labels.
- A's desktop Summary body measured 413px with 413px of content. C's longest
  Light calculation measured 327px with 327px of content at 1280 x 720.
  The formula had no horizontal overflow. At narrow phone sizes the reading
  body can scroll while page controls, Add/Enter and comparison controls stay
  visible.
- Expanded the short book's second chapter, selected its worked example,
  switched Brief layouts while retaining the passage, revealed an answer,
  and added the book. The footer changed to Enter and the collection count
  increased from one to two.
- Checked Escape from Brief, the shared My grimoires destination, independent
  Brief/navigation choices, English/Japanese switching, and Progress feedback
  clear of F's dock.

The six choices remain open. Realms and later learning scenes are still the
next design work after Christopher accepts this entrance.

## Release boundary

This is prototype revision 5 on the throwaway branch. It does not release or
deploy the Demo. The next implemented Web Demo release remains 0.0.4, correcting
the erroneous earlier 0.1.0 label. Realms and the working downstream study
functions remain for the later scene and integration work.
