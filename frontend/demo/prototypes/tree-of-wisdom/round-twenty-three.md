# Round 23: reading flow and inline counts

Open `/demo/?prototype=wisdom&revision=23&arrival=0&book=analysis&view=realms&place=tree&notebook=B&realm=text`.

Gold omitted-range counts sit in breaks in their own dotted lines. The text
retains its hover explanation and pointer/keyboard action. Placement searches
along the line instead of trying detached positions beside it. Regular Demo
labels retain their existing presentation.

The shared compact Atlas model changes chapter packing and routing:

- Short chapters may stack below earlier chapters beside a taller one, when
  this improves the drawing without increasing its height.
- Heading obstacles leave unused space to the right available for routing.
- Reading-order departures follow chapter placement, preventing a last card
  from directing an arrow back around its own chapter.
- Incoming arrows have full stems. Approach bends leave room beside straight
  crossing routes; only the arrowhead itself blocks perpendicular crossings.

Notebook image links flow after the final prose in Workings, or Statement
when no Workings exists. They wrap as ordinary inline text and still open the
image panel. Display mathematics retains its own expanding notebook row.

## Verification

The reading-flow regression first reproduced the item 1 loop, item 15 stem
and chapter arrangement, and item 29 bump with parallel crowding. Shared
rules resolve these cases without grimoire or object-specific branches.

The compact suite passes 12 synthetic sparse/dense cases and 14 frozen Real
Analysis cases across both layouts. It checks relationship retention,
card/heading clearance, distinct connection points, and inline counts with
no missing labels. Endpoint, route-clearance, ordinary Atlas, Atlas API and
notebook-math checks pass, as does the Demo build.

Browser checks confirm the rendered item 29 path is straight and the nearby
4 to 31 approach is 12 drawing units away. Chapter 4 starts directly below
chapter 1 in the item 15 view. The image link begins on the final Workings
line, wraps naturally, and opens the image panel with its Download action.
Activating +8 reports positions 5 through 12 without navigating. The browser
reported no JavaScript errors. The Atlas returns to its 110% zoom.

Local prototype only. No deployment or release version change.
