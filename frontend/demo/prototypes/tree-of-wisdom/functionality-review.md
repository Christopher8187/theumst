# Entrance and Brief functionality review

Revision 4, 12 September 2026. Supports
[Settle improvements to the Theumst Web Demo](https://github.com/Christopher8187/product/issues/70).

Christopher identified missing expandable contents and missing chapter divisions
in the short books. He requested the label Brief and GPT-5.6 Sol adversarial checks.
Two independent, read-only Sol reviewers compared the entrance against the
existing Demo components and examined navigation and state changes. Both completed
their final passes with no material entrance omission remaining.

## Comparison

| Previous Demo function | Revision 4 |
| --- | --- |
| Library search and book selection | Search title/subject, preserve selection, repair an invalid initial book value. Searching from the Realms placeholder returns to the Tree. |
| Tile publisher and completion | Supplied publisher and non-zero completed/total on all three selector variants. |
| Separate personal collection | My grimoires has its own query, count, summaries, progress, Brief and Open; add/open updates recent activity. |
| Book metadata and summary | Overview supplies title fallback, edition/version fallback, ISBN fallback and publisher. Unknown metadata is marked unavailable. |
| Expandable contents | Reuses the existing ContentsTree component, including keyboard navigation and bounded rendering. |
| Short sample reading | Brief separates Overview, Contents and Extract. Chapter choices and four passage buttons remain visible. |
| Summon and opening existing books | Add updates membership immediately; Enter/Open uses the chosen book. The agreed Add-then-Enter interaction replaces the old timed jump. |
| Language preference | English, Chinese and Japanese share the existing persisted preference; document language and title update. |
| Review, Advice, Expand, Generate | Available under More with the previous coming-soon feedback. |
| Empty cases | Separate no-matches, empty-collection and unavailable-library views. |

## Chapter structure

Real Analysis retains four root chapters and twenty section rows from the
existing Section Atlas example. Its four extracts correspond to those chapters.

Symmetry has Symmetries and Examples and practice. Light has Light in a vacuum
and Examples and practice. Each has two sections per chapter. The numbered
section names match the four extract titles. These are four passages, rather
than a claim that four production knowledge objects have been created.

## Defects caught and corrected

- Extract arrow keys stopped working when a navigation button retained focus.
- The selected book could disagree with an invalid initial URL value.
- Short samples were labeled as objects in the entrance and passages in Brief.
- The short-book edition was hidden behind an unavailable version marker.
- Publisher/progress disappeared from the Tree selectors.
- The visible search did nothing while the Realms placeholder stayed open.
- Journey accessibility text and the document title did not follow language changes.

## Verification

The root agent exercised both short-book chapter trees and Real Analysis's
Integration > Integrability > Continuous case path in the browser. Pointer and
keyboard expansion, collapse, chapter jumps, direct passage choices, arrow turns,
answer reveal, Escape and Add-then-Enter were checked. Separate Tree/collection
queries and the collection no-match state were exercised.

The reader was visually checked at 1440 x 900, 390 x 844 and 308 x 760. The
physics calculation, body and fixed actions had no overflow at 308 x 760.
Chinese and Japanese controls were checked at the narrow width. A fresh page
retained the chosen language and displayed the explicit 12/36 progress sample.
The empty-library and empty-collection scenarios showed their distinct messages.
Brief opened from A, B and C; the final browser log had no warnings or errors.

Both reviewers checked source behavior. One directly compiled all fifteen
prototype Vue components and compared chapter/section/extract counts. The root
also loaded the changed prototype through Vite, since the production build
deliberately excludes this development-only path. Existing graph/contents
assertions and the production build pass.

## Boundary and release decision

Collection and completion sample state remain in memory. No account writes,
saved study progress or backend requests were added. Enter still reaches the
explicit next-scene placeholder. The production Demo's downstream functions must
survive the later integration; this review does not certify full application parity.

The next implemented Web Demo release is **0.0.4**. Its earlier **0.1.0** label
is erroneous. Prototype revision 4 is a separate checkpoint and is not a release.
Christopher is still evaluating the entrance, with B as the leading direction.
