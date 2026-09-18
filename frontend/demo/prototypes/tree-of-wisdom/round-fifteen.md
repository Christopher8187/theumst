# Round 15: reading space and Atlas settings

Christopher requested changes to the selected Text notebook's controls and
spacing. Open `/demo/?prototype=wisdom&revision=15&arrival=0&book=symmetry&view=realms&place=tree&realm=text&notebook=B`.

The book begins 30 pixels higher on desktop. The visible 書 Text mark now sits
inside its title row beside the grimoire title. The small Knowledge path label
is removed. The blue palette, opacity and notebook ruling are retained.

Workings has Listen beside its heading and Prompt at the bottom of the page.
The image viewer has a Download link with a download attribute. Image captions
and lower reader controls use larger type; Back, Continue, Train and Mark done
use 14px text.

Atlas Settings contains Book distance, Dependency distance, Reading rows,
Hierarchy, Scale and Center current object. The panel overlays the graph without
resizing it. It closes on its button, outside activation, focus leaving the
controls or Escape. Escape restores focus to Settings and keeps the Text realm
open. Settings remain selected while the Atlas is mounted.

## Scope and verification

`TextRealm.vue` supplies the new heading and enables the notebook presentation.
`StudyView.vue` passes that presentation to the reader, image viewer and Atlas;
its default presentation is retained for the normal Demo. `AtlasSettings.vue`
owns the disclosure and focus behavior while `SectionAtlas.vue` retains its
existing control values and layout calculations. No graph algorithm changed.

The production Demo build passed. Browser checks at 1280 by 900 confirmed the
larger book, control positions, image label and download attribute, and larger
footer text. Switching to Hierarchy, closing with Escape and reopening retained
the selected view. Continue dismissed Settings and advanced through objects 201,
202 and 203. At 390 by 844, Settings and its controls fit the Atlas width. The
temporary viewport override was reset after checking.

This remains a local prototype. No release or deployment is part of this round.
