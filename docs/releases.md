# Releases

Theumst 0.2.2 updates the scene shortcuts, repairs scene-control contrast and open-window dock colors in Cool blue, and adds a language symbol in Settings. It retains the single-address desktop and HTML revalidation from 0.2.1. The protected Web Demo remains at 0.1.0 with unchanged source and UI. API compatibility metadata and third-party package versions remain independent.

Future update numbering follows MWF's observed change levels while retaining Theumst's own sequence. MWF 0.6.1 includes features and removed APIs, and its planned 0.6.2 adds workflow management. Last-number increments are therefore not restricted to bug fixes. No fixed first/second-number thresholds have been settled. Compare a future update's scope with MWF; a comparable bounded feature, repair or documentation update may become Theumst 0.2.3.

## Publication identity

Run the [required verification](testing.md), resolve failures, and record exact commands, setup and results. Publish the verified tree on `main`. Create an annotated `v0.2.2` tag on that exact commit and a GitHub release referencing that tag. Preserve legacy branches until their separate migration route decides their disposition.

Record the source commit, clean-tree status, tag object, release URL and SHA-256 of deployment artifacts. Keep configuration/secrets outside public assets. A release built from extra uncommitted source is not identical to its tag.

Deploy the published revision to COM through [operations](operations.md) after verified backup. Record the deployed revision and post-deployment results. CN is outside this delivery. Complete the implementing issue only after implementation, verification, main publication, tag/release and COM deployment are recorded. The annotated release and its GitHub release notes own the resulting source commit, artifact digests and COM deployment observations. The earlier [0.1.0 release](https://github.com/Christopher8187/theumst/releases/tag/v0.1.0) remains the reference for the unchanged Demo.
