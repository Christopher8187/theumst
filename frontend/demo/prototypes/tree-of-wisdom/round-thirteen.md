# Round 13: printed notebook pages

Question: how should Text's left leaf combine statement and workings into one
notebook page? Christopher rejected round 12 and supplied six photographs of
physical notebooks as the preferred references. This round replaces all three
left-page treatments on the existing route.

Open `/demo/?prototype=wisdom&revision=13&arrival=0&book=symmetry&view=realms&place=tree&realm=text&notebook=A`.
Use the bottom comparison controls or change `notebook` to `B` or `C`.

## References and treatments

- A, Study sheet: photo 1's compact printed fields and shallow dotted divisions.
  The object type and number occupy the top register, followed by its title.
  The statement and workings share an unruled page with a fine division.
- B, Daily notebook: photo 2's small memo heading, double rule and continuous
  horizontal writing lines. The prose and lines use the same 30px rhythm.
- C, Open frame: photo 3's fine outline and photo 4's section rules. One frame
  encloses the entire entry, with the object type and number set into its top
  edge. Lined statement text leads into an open working area.

All use ivory paper and dark ink. The existing translucent folio, spine and
Atlas remain around the left leaf. Photos 5 and 6 inform restrained type and
rule weights; they do not introduce calendar functionality. No dates, confidence
values or weather marks are fabricated from the stationery photographs.

The photo filenames, in supplied order, are `fc541f7c0cdcec81c2d17df639cbbfcd.jpg`,
`376144d72b467faa014a713bc6bdec09.jpg`, `105a7a6baf6b4b6118f56158167a7379.jpg`,
`cdd3edfc357a48201e12e9b7e95fde38.jpg`, `23dc473920abfec74c5292930542f144.jpg`,
and `e381e955fc99766086e32199f2bbc0dd.jpg`. They were supplied directly in this
task. The prototype recreates page structure in CSS and does not embed the photos.

## Ownership and scope

`notebook-variants.css` owns these presentations. `NotebookComparison.vue` owns
the translated choice labels. `TextRealm.vue` continues to hold the choice and
URL; `useTextStudy` continues to hold the reading state. Shared `StudyView` and
`KnowledgeViewer` source, events and controls are unchanged. Each source section
grows with its content, with one scrolling reading leaf.

GPT-5.6 Sol reviewed the direction and the implemented CSS. Its findings led to
rules on the actual text container, an ivory area behind display mathematics,
quieter tool hover states, corrected frame labels and shorter phone leaf heights.

Desktop inspection at 1280 by 800 covered all three designs. Continue reached
Symmetry object 202 and switching from C to B retained that theorem and formula.
The 390 by 844 phone check confirmed no page-wide horizontal overflow, the
display formula fitting its own area, dark theorem labels and a 52px gap between
the last action row and comparison bar. The reader remains the only source
scroller. Production Demo build passed; its build excludes the prototype.

This remains a throwaway design study on `codex/tree-of-wisdom-prototype`.
No winner is selected and no production release or version change is made.
