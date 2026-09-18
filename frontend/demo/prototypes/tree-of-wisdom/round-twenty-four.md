# Round 24: realm navigation and shared progress

Open `/demo/?prototype=wisdom&revision=24&arrival=0&book=analysis&view=realms&place=tree&notebook=B&realm=text`.

Only the smallest containing subsection appears beside Local Atlas. The
progress count, percentage and bar use the same shared component and sizing
as the Realms spread, with no notebook-specific compression. The subsection
can shorten with an ellipsis in a narrow header; its full name remains in
the hover title. Realm drawings and connecting strokes brighten in 70 ms.

Text's Continue skips exercises. Its Atlas excludes exercise cards before
applying the visible-object limit, while retaining the original grimoire
numbers, authored dependency distances and omitted-position counts.

Questions has one navigation row. Back and Continue visit the previous and
next exercise, including completed exercises, without wrapping. The buttons
disable at the ends. Its Atlas includes every working type within the local
view. Selecting a non-exercise opens it in Text and updates the realm URL.
Each realm retains its own saved position; completion remains shared.

The prototype keeps the existing note guard around navigation. A realm
change updates the parent without resetting the selected object or history.
All type rules use the object's working type, not a grimoire or object ID.

## Verification

The realm test checks deliberately nonsequential IDs, exercise-only input,
completed exercises and boundaries. Every non-exercise Real Analysis position
has a filtered Atlas without omitted routes or missing counts in both layouts. Filtering
exposed an overlong arrow approach beside a neighboring card; extensions now
require clear space and do not alter already aligned direct routes.

Browser checks confirmed Text 14 to 18, Questions 6 to 15 and Back to 6,
and selecting theorem 4 from Questions switching to Text at theorem 4.
The extra Previous/Next row is absent. At 1280 CSS pixels, both realm headers
have identical progress width, count/percentage fonts and spacing, and
two-pixel bars. The active realm drawing uses a 70 ms transition.
The browser reported no JavaScript errors. Realm navigation, compact Atlas,
route-clearance, reading-flow, endpoint and Atlas API checks pass, as does
the Demo production build.

Local prototype only. No deployment or release version change.
