# Round 25: Text reading order

Open `/demo/?prototype=wisdom&revision=25&arrival=0&book=analysis&view=realms&place=tree&notebook=B&realm=text`.

Back and Continue now use the same ordered traversal. In Text they visit the
previous and next non-exercise. In Questions they visit the previous and next
exercise. Completed objects remain in both sequences. Buttons disable at
their respective ends without wrapping. Atlas selection sets the position
from which both buttons navigate.

The regression came from mixing two navigation rules: Continue used grimoire
order, while Text Back still popped visit history. Selecting item 14 from
item 1 then pressing Back returned to 1 rather than 13. The obsolete history
storage is removed; cross-book Return to original book remains independent.

`node tests/study-reader.mjs` first failed with `1 !== 13`, then passed after
the correction. It mounts the actual composable and exercises the action
guard and parent realm feedback, including Text 14 to 18 and back to 14,
Questions-to-Text selection, both full sequences and pending writing.

Browser mouse checks confirmed 13 to 14 to 18, then Back to 14, with Text
remaining active. The realm navigation/filtering checks and Demo build pass.

Local prototype only. No deployment or release version change.
