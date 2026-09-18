# Round 22: equation spacing and shared arrow routing

Open `/demo/?prototype=wisdom&revision=22&arrival=0&book=analysis&view=realms&place=tree&notebook=B&realm=text` and select item 13, Continuous implies integrable.

Display equations have 12 pixels above and below, four more than revision 21.
The existing notebook lines and centered mathematics remain.

All graph changes live in the shared Atlas model. No grimoire name, object ID
or precomputed path selects a routing exception.

- Crowded cards no longer reuse an occupied connection point when the preferred
  spacing runs out. The allocator finds space between existing points.
- The compact heading gap grows by eight drawing units to fit separate arrow
  lanes above the card while retaining full arrowhead stems.
- A bend costs the distance of one card width. This prevents a tiny reduction
  in parallel-lane cost from winning over a simpler route.
- The search prefers an approach without reversals near the destination. It
  can relax that preference if surrounding obstacles require a reversal. It
  retains the same collision rules rather than dropping an otherwise valid
  arrow.

## Verification

The item 13 regression initially reproduced reversed approaches and the
shared departure point. It checks the complete arrival-direction progression
for 4 to 31, 8 to 15 and 13 to 15, plus separate tails for 29 to 31 and 29 to 32.
Renaming all object IDs and titles and every section name must produce
identical geometry.

The compact suite covers 12 synthetic sparse/dense graph cases at 8, 16 and
24 objects, and 14 Real Analysis views. Both layouts and both density modes
check distinct connection points and retention of relationships. Existing
card/heading collision, gap label, chapter spacing and arrow-lane checks remain.

The endpoint, compact, route-clearance, ordinary Atlas, Atlas API and notebook
math checks pass, as does the Demo build. Browser verification selected item
13 at 1280 by 720, inspected the graph at 50% and restored its 110% zoom.
Computed display-math padding is 12 pixels above and below. The rendered
4 to 31 route matches the model output, and the browser reports no errors.

Local prototype only. No deployment or release version change.
