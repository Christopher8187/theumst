# Round 11: Text in the realm folio

Local prototype for issue #70, based on revision 10 at `172583f`.
Christopher requested a Text interface whose functions and arrangement stay
close to the existing Web Demo. The realm book is the primary visual reference;
Subnautica and EVE provide supporting control ideas. The selected single-prototype
format remains, with no comparison bar.

Open `/demo/?prototype=wisdom&revision=11&arrival=0&book=symmetry&view=realms&place=tree&realm=text`.
Use `book=analysis` for the original, larger Atlas example or `book=light` for
the second short book. Entering Text from the realm drawing reaches this same view.

## Arrangement and appearance

The spread retains the existing arrangement: book and chapter ancestry above,
Statement and Workings on the left, Atlas on the right, reader actions below
the left page, and completion below the right page. Notes, discovery results and
images temporarily replace Atlas. On narrow screens the reader precedes Atlas
vertically, preserving the previous Demo's reading order and full-width graphs.

The realm chooser supplies the thin ruled pages, central divider and bookmark,
serif headings, soft teal ink and translucent setting. The reader has a more
opaque backing for prose and equations. Supporting controls use compact strips,
small borders and restrained selected states. There is no animated visual noise.

Reference choices:

- [Subnautica's PDA overhaul](https://unknownworlds.com/en/news/voice-deep-update-released)
  shows information and controls within one display. This informed keeping
  the reader and its instruments inside the folio.
- [Photon's iteration](https://www.eveonline.com/news/view/photon-ui-iterating-and-improving)
  describes more compact headers, calmer inactive windows and balanced tab
  highlights. This informed the map controls and active states.
- [EVE's transparency guidance](https://support.eveonline.com/hc/en-us/articles/7264100568220-User-Interface-Tips-and-Tricks)
  distinguishes environmental visibility from content focus. The two pages use
  different opacity to keep the reading area dominant.

Brief now anchors its completion bar to the bottom of the summary page, below
Edition, ISBN, Objects and Chapters and above the main action. It remains visible
when Book details is collapsed. Book details still opens by default.
Realm-book progress retains its placement.

## Components and retained behavior

`text/TextRealm.vue` composes the existing `StudyView`, `KnowledgeViewer`,
`SectionAtlas`, `NotePanel`, `SearchPanel`, `ImagePanel`, `NotesDesk` and
`NoteDecision`, with styles scoped to this prototype. These production components
remain unchanged. `RealmBook.vue` hosts Text and its connected exercise mode.

`text/useTextStudy.ts` owns the in-memory counterpart of the existing reader
actions. `TreePrototype.vue` provides the session once. Book/object completion,
notes and separate Text/Questions positions survive leaving a realm during the
visit. A new realm entrance resets visit history and the original-book marker.
Completion events update Brief, the realm chooser and the personal collection.
Removing a grimoire still changes membership only.

The retained functions include complete-order Continue, visit-history Back,
Atlas selection, next-unfinished-exercise Train without wrapping, completion
without navigation, images, attached notes, multiple note selection, All notes,
scribbles, and the Save/Discard/Keep editing decision before leaving a draft.
Listen, Prompt and Project retain their coming-soon messages.

Find neighbors and Crystallization use finite local examples. Scores are explicitly
illustrative. The latter uses two deliberately repeated definitions in a companion
book to demonstrate equal statements across sources. One three-book route is
Symmetry definition, Crystallization, Companion definition, Continue, Crystallization,
Light definition. Return restores the first original book, object and mode.

Atlas still calls the unchanged `buildAtlas` through the original `SectionAtlas`.
It retains Reading rows and Hierarchy, independent book/dependency distances,
either-distance inclusion, the 24-object/72-arrow limits, authored dependencies,
solid and dotted reading-order paths, gap labels, centering and scale choices.

## Data and scope

`text/study-fixtures-analysis.json` freezes the original sample declarations used
by `backend/examples/real-analysis-demo/build_archive.py`: 36 objects, 42 authored
relations and 24 sections including the whole-book root. Text uses this full
hierarchy. The older entrance's abbreviated contents remain unchanged in this
round. `text/studyFixtures.ts` adapts the original sample and the two four-object
miniatures, adds short explanatory workings and authored diagrams, and defines
the finite discovery examples.

Optional `studyCase` values exercise `no-dependencies`, `discovery-empty`,
`discovery-error`, `discovery-unavailable`, `discovery-loading`, and
`notes-save-error`. Discovery cases apply when opening Find neighbors or
Crystallization; the note case applies when saving an edited note.

This is an in-memory design prototype. It makes no API calls, saves no account
data and cannot establish backend persistence, semantic retrieval quality or
live source-availability detection. Those operational checks belong to later
integration. The Notes and exercise views support Text's connected actions;
other study destinations retain their earlier placeholder scope.

Production versions and deployment remain unchanged. The next implemented
Demo release remains 0.0.4; revision 11 is a prototype checkpoint only.

## Verification

GPT-5.6 Sol mapped the existing Demo and adversarially reviewed the implementation.
Executable Vue state checks covered reading order, Back, Train, independent realm
positions, completion, note creation/editing/deletion, all dirty-draft decisions,
save failure, three-book return, and Return followed by Back and Return again.
The review caught and resolved stale entrance state, missing action feedback and
the original-book marker's lifetime. Book mode switching now preserves the old
Demo's exact visit-history behavior.

The root agent inspected the rendered interface at 1440 x 900 and 390 x 844.
Browser interactions verified Continue, completion without navigation, Hierarchy
selection, Keep editing, Save and continue, Train, restoring the saved Text
position, opening an authored diagram, closing it and restoring trigger focus.
Chinese and Japanese controls fit the phone width. Phone checks caught and fixed
a fixed ancestor that prevented scrolling to Atlas; the document now includes
the lower graph pane and has no horizontal overflow. Brief's progress is below
the statistics at the bottom of its page, with no Summary scrolling at 390 x 844.

All 27 prototype Vue components compile. Existing Atlas, graph, discovery and
static interface checks pass, as does the production Demo build. Its output
excludes the new Text prototype. The three authored diagrams load as local SVG
files. Source and rendered checks establish local prototype behavior, not live
backend persistence or retrieval.

A second Sol agent researched the official visual references and made the first
Brief edit. Its separate rendered taste pass was interrupted before navigation;
the visual observations above are the root agent's checks.
