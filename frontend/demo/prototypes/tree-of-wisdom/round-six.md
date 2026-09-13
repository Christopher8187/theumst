# Selected folio and rail, round 6

13 September 2026. Christopher selected A's folio and E's navigation rail,
requested more refinement, vertical icon alignment fixes, and a corrected
language icon. He requested one prototype for this round.

## Chosen presentation

The entrance keeps the sacred pale tree and Orbit grimoire chooser. My grimoires
and the four cross-grimoire realm actions share E's left rail. The rail uses
one outer frame, common icon squares, aligned labels, and an inline collection
count. On phones its five entries become one horizontal ribbon below search.

Brief keeps A's 42/58 two-page composition. Summary and the book emblem occupy
the left page; Contents and Extract share the right. A straight, subdued seam,
a narrow lower page edge, and more consistent margins refine the folio.
On phones one Summary/Contents/Extract row replaces the two stacked tab rows.
The reading body scrolls while tabs and Add/Enter remain available.

The language control has a vector translation mark, a centered dropdown label
and chevron. It stays visible on small screens. Rail glyphs and collection
artwork use explicit square frames, independent of text baselines. Close,
Add/Enter, Descend and Book details use centered vector marks too.

When Brief opens, the underlying rail, header, detail panel and Descend fade.
The tree remains visible around the folio. Closing returns to the existing
browsing state. The open Brief state is stored in the URL as `panel=brief`.

## Single prototype

There is no A-F bar or keyboard cycling in revision 6. Previous comparison
parameters are normalized away. The six alternatives are preserved at
commit `7050c98` on `codex/tree-of-wisdom-prototype`.

The existing components retain separate responsibilities: TreePrototype owns
selection, collection and scene state; AcrossGrimoireActions owns rail display;
LanguageControl owns the language selector; GrimoireReader owns the folio and
reading selection; BriefSummary, BriefContents and BriefExtract render its pages.

## Review and verification

The GPT-5.6 Sol Brief reviewer returned for a focused critique of the selected
combination. Their source review led to a common icon frame, hiding the rail
behind Brief, one mobile tab row, a persistent mobile language icon and removal
of the comparison controls. Their isolated browser was unavailable for the final
rendered pass; the primary agent completed the visual checks directly.

- Rendered at 1440 x 900, 1280 x 720, 390 x 844, and 308 x 760.
- At 308px with Japanese labels, every navigation icon frame starts at the
  same vertical coordinate. Longer labels wrap below the icons. No page-width
  overflow was observed. The language icon and chevron share the control's
  vertical center.
- At 1280 x 720, the folio's Summary body measures 462px with 462px of content,
  with no scrollbar at the seam.
- Checked the single mobile tab row, chapter expansion, selection of a chapter
  exercise, answer reveal, Add changing to Enter, and Escape restoring focus
  to the original Brief button. There are no comparison controls in the DOM.
- All 21 prototype Vue scripts, templates and styles compiled. The existing
  `node tests/graph-contents.mjs` checks and `npm run build` passed.

## Revised scene art

Christopher then requested a pinch more sacred, magical and scholarly detail,
plus restrained color in the pale tree. The built-in image tool first edited
the original tree, adding muted pink and sage foliage, books at its roots,
small hanging ornament and gold details. This intermediate 1672 x 941 image is
saved as `assets/sacred-tree-scholar.png`.

A second sequential generation extended the scene about 67% to the right,
placing a stone altar, open book, candles and a ruined pointed arch there.
The final 2159 x 728 panorama is `assets/sanctuary-panorama.png`.
The generated image has a wider field but a lower pixel height than the first
image. Both outputs are retained, alongside [the complete prompts](scene-art-prompts.md).

The prototype uses the panorama. `sceneArt.ts` records its dimensions and the
original 1672:941 frame aspect. ArrivalTransition scales the image uniformly
and clips the original tree frame, preserving the existing desktop and phone
focal positions. The added altar remains beyond the visible right edge.
The same crop is used during ascent/descent. No altar control or destination
is introduced yet.

The local descent/ascent round trip returned to the same selected, added book.
At 1280 x 720 the visible right edge is 59.91% of the panorama, before the altar.
The rendered image retains the source aspect ratio. The phone crop retains its
previous left focal position and also excludes the altar.

## Boundary

This is a local prototype checkpoint, with no backend or account mutations.
The four future realm actions and the next-scene destination remain placeholders.
Christopher's selection narrows the visual direction; this turn does not merge
or deploy it. The next implemented Web Demo release remains 0.0.4.
