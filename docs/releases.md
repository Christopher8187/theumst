# Releases

Theumst 0.0.14 is the current release, published as [v0.0.14](https://github.com/Christopher8187/theumst/releases/tag/v0.0.14) and deployed to COM on 11 November 2026. The Web Demo's knowledge list and object view give each object's `difficulty` and `estimated_minutes`. It needs no migration. 0.0.13 was published as [v0.0.13](https://github.com/Christopher8187/theumst/releases/tag/v0.0.13) and deployed to COM on 6 November 2026. Only accounts the Web Demo admits read books through their API keys, and one key cannot open a character on two installs of the game, which migration 015 records. 0.0.12 was published as [v0.0.12](https://github.com/Christopher8187/theumst/releases/tag/v0.0.12) and deployed to COM on 5 November 2026. A successful password reset clears the account's wrong-password count, so a locked-out player who resets can sign in at once, at the website's login and in the game. It needs no migration. 0.0.11 was published as [v0.0.11](https://github.com/Christopher8187/theumst/releases/tag/v0.0.11) and deployed to COM on 5 November 2026. It gives the website's login the game sign-in's wrong-password limit, and deletes a character's save with the character, including through its account (migration 014). 0.0.10 was published as [v0.0.10](https://github.com/Christopher8187/theumst/releases/tag/v0.0.10) and deployed to COM on 5 November 2026. It lets UMST sign in to theumst.com and keep its characters there, gives every account a Default key, and counts API requests per minute, apart for book reads and the game's calls (migration 013). 0.0.9 lets one book image belong to several knowledge objects, as a figure or as a scan of a page. 0.0.8 let Whole-book upload share knowledge crystals and keep dependency cycles. 0.0.7 replaced the previous Web Demo with the accepted Sanctuary, Orbit, realm book and notebook design, connected to persistent books, notes, completion, saved positions and discovery. It also gave knowledge objects an optional name and kept checked-off Mind Palace knowledge when a book leaves the collection. The homepage and dashboard retain their accepted design.

Christopher selected 0.0.7 for that delivery, superseding the previously proposed 0.0.4 and correcting the earlier 0.2.x numbering. 0.0.8 and 0.0.9 continue it. Historical tags remain unchanged. API compatibility metadata and third-party package versions remain independent.

## 0.0.14 release notes

0.0.14 changes no schema and needs no migration. It changes no frontend, so the Web Demo build stays 0.0.7 and shows nothing new. Two backend answers gain the fields `difficulty` and `estimated_minutes`, after `completed`: each row of `knowledge` from `GET /api/demo/grimoires/{grimoire_id}/knowledge`, and the `knowledge` object from `GET /api/demo/grimoires/{grimoire_id}/knowledge/{knowledge_id}`. Each is the number the object's `source_metadata` gives under that name, as stored, such as `40` or `0.05`. It is null when the key is missing or holds anything but a number, as it is for objects uploaded without these values, so a client must accept null. Both routes still need a session with Web Demo access. Every other field and the row order are as in 0.0.13, and the `/api/v1` book reads do not change. Going back to 0.0.13 removes the two fields and changes no data. [Data architecture](architecture/data.md) states the rule; `test_difficulty_postgres.py` checks it against PostgreSQL with `THEUMST_DIFFICULTY_DB_TESTS=1`.

## 0.0.13 release notes

Migration 015 can run while 0.0.12 is still serving. It adds the nullable column `"character".lease_install_id` and its check, and changes no row. 0.0.12 names the columns it reads, so it never meets the new one. While the runner alters `"character"` it holds an exclusive lock on the table until its transaction commits, so game calls wait for that moment instead of failing. 0.0.13 does not start until the runner has applied 015. [Game accounts](game-accounts.md#checking-migration-015) lists the checks for a restored copy of COM's database, and `test_key_access_postgres.py` runs 015 against PostgreSQL with `THEUMST_KEY_ACCESS_DB_TESTS=1`.

The book boundary changes for live accounts as soon as 0.0.13 starts. A regular key whose account lacks Web Demo access gets 403 `demo_access_required` on the knowledge list, an object and its images. On COM that is any confirmed account still at the `user` authority, never approved for the Demo. Book image URLs, which needed neither key nor session before, answer 401 without one, so an API client must send its key with them. The Web Demo keeps working, because its readers have the access and its pages send their session. The game's calls keep working too. `christopher` is a superadmin and Kaicenat's publisher key is a master key, so neither loses a read. This read-only query lists the confirmed accounts whose keys 0.0.13 refuses, with their regular keys and the book reads those keys made since 0.0.10:

```sql
BEGIN TRANSACTION READ ONLY;
SELECT u.user_id, u.username, a.name AS authority,
       (SELECT count(*) FROM api_key k
        WHERE k.user_id = u.user_id AND k.key_type = 'regular' AND k.revoked_at IS NULL) AS active_regular_keys,
       (SELECT COALESCE(sum(d.request_count), 0) FROM api_usage_daily d
        JOIN api_key k ON k.api_key_id = d.api_key_id
        WHERE k.user_id = u.user_id AND k.key_type = 'regular' AND d.kind = 'book') AS book_reads
FROM "user" u
JOIN authority a ON a.authority_id = u.authority_id
WHERE u.email_verified_at IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM authority_access_map aam JOIN access ac ON ac.access_id = aam.access_id
      WHERE aam.authority_id = u.authority_id AND ac.access_point = 'demo')
ORDER BY u.user_id;
COMMIT;
```

The game in players' hands sends no `X-Install-Id`, so its leases work as in 0.0.12 until an update of the game sends one. Going back to 0.0.12 leaves the column in place and unread. 0.0.12 also leaves it as it is when it takes a lease, so after coming forward again an install can find its own key's live lease refused as open elsewhere until that lease lapses, at most two minutes.

## 0.0.12 release notes

0.0.12 changes no schema and needs no migration. A successful reset adds one `sign_in_attempt` row: the account's `user_id`, no username hash or address, and `succeeded` true. 0.0.11 reads such a row as the account's right password too, so going back to 0.0.11 keeps the counts already cleared and only stops clearing new ones. No address's count changes. [Account recovery](account-recovery.md) explains the behavior; `test_sign_in_postgres.py` checks it against PostgreSQL with `THEUMST_SIGN_IN_DB_TESTS=1`.

## 0.0.11 release notes

Migration 014 can run while 0.0.10 is still serving. It changes no column. It adds a function and a trigger on `"character"` and removes saves no character points at. 0.0.10's character delete keeps working, because its own delete of the save finds nothing left after the trigger. While the runner replaces the trigger it holds an exclusive lock on `"character"` until its transaction commits, so game calls wait for that moment instead of failing. After 0.0.11 starts, website logins add rows to `sign_in_attempt` and count toward the game's limits. [Game accounts](game-accounts.md#checking-migration-014) lists the checks for a restored copy of COM's database.

## 0.0.10 release notes

The deployment applies migration 013 with the new image while the 0.0.9 backend is still serving, then starts 0.0.10. 0.0.9 reads `api_rate.searches_per_hour`, which 013 renames, so from the migration's commit until the 0.0.10 backend answers, about the time a backend takes to start, every API-key request and the dashboard's API Keys list fail with 500. That short outage is accepted for 0.0.10 and the migration order stays as it is. The reason: COM has two accounts and one publisher key, so a few seconds of failed key requests cost less than carrying both column shapes across two releases. Deploy when no Whole-book upload is running.

## Publication identity

Run the [required verification](testing.md), resolve failures, and record exact commands, setup and results. Publish the verified tree on `main`. Create an annotated `v<version>` tag, such as `v0.0.9`, on that exact commit and a GitHub release referencing that tag. Preserve legacy branches until their separate migration route decides their disposition.

Record the source commit, clean-tree status, tag object, release URL and SHA-256 of deployment artifacts. Keep configuration/secrets outside public assets. A release built from extra uncommitted source is not identical to its tag.

Deploy the published revision to COM through [operations](operations.md) after verified backup. Record the deployed revision and post-deployment results. CN is outside this delivery. Complete the implementing issue only after implementation, verification, main publication, tag/release and COM deployment are recorded. The annotated release and its GitHub release notes own the resulting source commit, artifact digests and COM deployment observations. The earlier [0.1.0 release](https://github.com/Christopher8187/theumst/releases/tag/v0.1.0) records the previous Demo implementation.

See the [0.0.7 verification record](history/release-0.0.7.md) for local checks, browser coverage and backup verification. The [0.0.8](https://github.com/Christopher8187/theumst/releases/tag/v0.0.8) and [0.0.9](https://github.com/Christopher8187/theumst/releases/tag/v0.0.9) release notes record their verification and COM deployment.
