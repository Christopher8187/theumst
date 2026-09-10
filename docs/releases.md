# Releases

Theumst uses one coordinated application version. The 0.1.0 delivery combines AFSR/documentation, the accepted Atlas and earlier functional repairs. UI product labels and release records use that version. API compatibility metadata and third-party package versions remain independent.

Future update numbering follows MWF's observed change levels while retaining Theumst's own sequence. MWF 0.6.1 includes features and removed APIs, and its planned 0.6.2 adds workflow management. Last-number increments are therefore not restricted to bug fixes. No fixed first/second-number thresholds have been settled. Compare a future update's scope with MWF; a comparable bounded feature, repair or documentation update may become Theumst 0.1.1.

## Publication identity

Run the [required verification](testing.md), resolve failures, and record exact commands, setup and results. Publish the verified tree on `main`. Create an annotated `v0.1.0` tag on that exact commit and a GitHub release referencing that tag. Preserve legacy branches until their separate migration route decides their disposition.

Record the source commit, clean-tree status, tag object, release URL and SHA-256 of deployment artifacts. Keep configuration/secrets outside public assets. A release built from extra uncommitted source is not identical to its tag.

Deploy the published revision to COM through [operations](operations.md) after verified backup. Record the deployed revision and post-deployment results. CN is outside this delivery. Complete the implementing issue only after implementation, verification, main publication, tag/release and COM deployment are recorded. The [0.1.0 GitHub release](https://github.com/Christopher8187/theumst/releases/tag/v0.1.0) owns the resulting commit, artifact digests and deployment observations.
