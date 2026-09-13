# Round 8: a connected realm spread

Local visual exploration for issue #70, on `codex/tree-of-wisdom-prototype`.
This is the current realm-book treatment, following the revision 7 checkpoint
at `b6c3061`. Christopher asked for a larger drawing area, illustrations that
can grow into scenes, shared strokes between them, hover illumination, and
direct entry with one click.

Open `/demo/?prototype=wisdom&revision=8&arrival=0&book=symmetry&view=realms&place=tree`.
Omit `view=realms` to try the continuous travel from tree to altar first.

## Current treatment

The confirmation footer is removed. The book occupies more of the viewport,
with its fold, translucent leaves, ruled lines, and altar background retained.
At 1280 × 800, the spread measures approximately 1211 × 666 CSS pixels.

The eight scientific pen drawings now have surrounding scenery. Folded paper
becomes a distant ridge; a measured arch surrounds the solid; loose paper sits
beneath the quill; shorelines surround the shell. The facing page combines an
orbital study, reading recess, rooted garden, and architectural landings.
Page-edge contours, orbital arcs, ink trails, desk planes, and terrain strokes
join the scenes. One ink trail continues through the fold. The shared drawing
layer cannot receive pointer input.

Hover lights the subject and its nearest strokes. Shared bridges stay quiet.
Keyboard focus gives the same ink response and a separate visible label outline.
The latest pointer or focus interaction controls illumination. Touch activation
does not require an earlier hover or selection.

One click, Enter, or Space opens the matching local arrival after a short
320 ms response. The realm buttons are navigation actions, without a pressed
state or second Enter button. Repeated activation is ignored during travel.
Escape or Realms returns to the spread and restores the last realm's focus.
The navigation controls are inert during that short return, so focus cannot
be pulled away from a language selection made mid-transition.

## Files

- `RealmBook.vue` owns layout, illumination, native button activation, and return.
- `RealmDiagram.vue` owns the eight subjects and their immediate environments.
- `RealmContinuity.vue` owns the shared, non-interactive drawing between them.
- `RealmDestination.vue` retains revision 7's local arrival samples.
- `TreePrototype.vue` writes revision 8 in the prototype URL.

## Review and scope

GPT-5.6 Sol reviewed the composition and interaction independently, expanded the
eight immediate environments, and reviewed the assembled source. The root agent
built the larger layout and continuous scenery and checked the rendered result.
Review corrections covered stale mouse hover overriding keyboard focus,
over-bright connecting strokes, focus during return, and an arrow extending
outside its button.

Browser checks confirmed all eight direct-entry and return paths, native Enter
and Space activation, Escape return, and restored realm focus. The tree/altar
round trip ended at the existing 0.000 and 1.000 positions with the same book.
Desktop, narrow portrait, and short landscape layouts were inspected. The
measured narrow and short layouts had no overlapping realm targets or document
width overflow; Japanese labels also fit. Keyboard illumination was inspected
visually; pointer illumination uses the same state with mouse enter/leave.
All 25 prototype Vue components compile, and the Demo production build passes.
Its output excludes the prototype components and panorama.

Text and Questions still use local excerpts and exercises; Notes is in memory.
The other five arrival views remain samples for later design rounds. This
iteration changes the chooser, not those full learning experiences. Collection
removal and Mind Palace completion remain independent. The panorama movement
and image framing are unchanged.

This prototype does not authorize a merge or deployment. The next implemented
Demo release remains 0.0.4; revision 8 is only a prototype checkpoint.
