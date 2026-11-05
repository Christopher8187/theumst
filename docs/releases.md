# Releases

Theumst 0.0.11 is in progress on the `login-limit` branch and not yet published. It gives the website's login the game sign-in's wrong-password limit, and deletes a character's save with the character, including through its account (migration 014). 0.0.10 is the current release, published as [v0.0.10](https://github.com/Christopher8187/theumst/releases/tag/v0.0.10) and deployed to COM on 5 November 2026. It lets UMST sign in to theumst.com and keep its characters there, gives every account a Default key, and counts API requests per minute, apart for book reads and the game's calls (migration 013). 0.0.9 lets one book image belong to several knowledge objects, as a figure or as a scan of a page. 0.0.8 let Whole-book upload share knowledge crystals and keep dependency cycles. 0.0.7 replaced the previous Web Demo with the accepted Sanctuary, Orbit, realm book and notebook design, connected to persistent books, notes, completion, saved positions and discovery. It also gave knowledge objects an optional name and kept checked-off Mind Palace knowledge when a book leaves the collection. The homepage and dashboard retain their accepted design.

Christopher selected 0.0.7 for that delivery, superseding the previously proposed 0.0.4 and correcting the earlier 0.2.x numbering. 0.0.8 and 0.0.9 continue it. Historical tags remain unchanged. API compatibility metadata and third-party package versions remain independent.

## 0.0.11 release notes

Migration 014 can run while 0.0.10 is still serving. It changes no column. It adds a function and a trigger on `"character"` and removes saves no character points at. 0.0.10's character delete keeps working, because its own delete of the save finds nothing left after the trigger. While the runner replaces the trigger it holds an exclusive lock on `"character"` until its transaction commits, so game calls wait for that moment instead of failing. After 0.0.11 starts, website logins add rows to `sign_in_attempt` and count toward the game's limits. [Game accounts](game-accounts.md#checking-migration-014) lists the checks for a restored copy of COM's database.

## 0.0.10 release notes

The deployment applies migration 013 with the new image while the 0.0.9 backend is still serving, then starts 0.0.10. 0.0.9 reads `api_rate.searches_per_hour`, which 013 renames, so from the migration's commit until the 0.0.10 backend answers, about the time a backend takes to start, every API-key request and the dashboard's API Keys list fail with 500. That short outage is accepted for 0.0.10 and the migration order stays as it is. The reason: COM has two accounts and one publisher key, so a few seconds of failed key requests cost less than carrying both column shapes across two releases. Deploy when no Whole-book upload is running.

## Publication identity

Run the [required verification](testing.md), resolve failures, and record exact commands, setup and results. Publish the verified tree on `main`. Create an annotated `v<version>` tag, such as `v0.0.9`, on that exact commit and a GitHub release referencing that tag. Preserve legacy branches until their separate migration route decides their disposition.

Record the source commit, clean-tree status, tag object, release URL and SHA-256 of deployment artifacts. Keep configuration/secrets outside public assets. A release built from extra uncommitted source is not identical to its tag.

Deploy the published revision to COM through [operations](operations.md) after verified backup. Record the deployed revision and post-deployment results. CN is outside this delivery. Complete the implementing issue only after implementation, verification, main publication, tag/release and COM deployment are recorded. The annotated release and its GitHub release notes own the resulting source commit, artifact digests and COM deployment observations. The earlier [0.1.0 release](https://github.com/Christopher8187/theumst/releases/tag/v0.1.0) records the previous Demo implementation.

See the [0.0.7 verification record](history/release-0.0.7.md) for local checks, browser coverage and backup verification. The [0.0.8](https://github.com/Christopher8187/theumst/releases/tag/v0.0.8) and [0.0.9](https://github.com/Christopher8187/theumst/releases/tag/v0.0.9) release notes record their verification and COM deployment.
