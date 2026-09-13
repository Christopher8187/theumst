# Round 10: more space around the tree

Local art adjustment for issue #70, based on revision 9 at `ec9d181`.
Christopher found the tree's closeness and interwoven roots intimidating and
asked for it to sit slightly farther away. He also requested a little more of
the upper branches, while keeping the full crown beyond the image.

Two sequential built-in image edits preserve the pale braided trunk, warm root
library, soft colors and right-hand reading altar. More cloud foreground
separates the viewer from the roots. The main upper boughs spread visibly across
the left side and continue beyond the frame.

`sceneArt.ts` uses `assets/sanctuary-world-tree-distance.png`, 2160 x 728.
Both earlier panoramas remain available. The frame proportions and continuous
tree-to-altar travel are unchanged. The prompts are in `scene-art-prompts.md`.

Open `/demo/?prototype=wisdom&revision=10&arrival=0&book=symmetry`.
This changes only the prototype artwork and checkpoint URL. Production remains
unchanged; the next implemented Demo release remains 0.0.4.

## Verification

Rendered checks covered the tree at 1280 x 800 and 390 x 844 and the altar endpoint
after entering Real Analysis. The new branches, root library and cloud foreground
remain visible in the desktop crop; the phone crop retains the library and trunk.
An independent art review checked the distance, branch framing and altar placement.
The final panorama has no visible join or abrupt horizon change.

The Demo production build passes and excludes the new image and prototype motion
code. The image dimensions match `sceneArt.ts`. No interaction or rendering
logic changed in this round.
