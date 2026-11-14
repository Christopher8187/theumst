# Game accounts

UMST signs in to theumst.com with a username and password, then keeps its characters here. Since 0.0.16 it also downloads whole books here and keeps the account's Web Demo notes. `routers/game.py` serves the game under `/api/game`; migration 013 holds the tables, 014 deletes a character's save with it, 015 keeps the install that has a character open, and 017 holds the books the game reads. The game sends JSON with `Content-Type: application/json`. Answers are JSON with `Cache-Control: no-store`, apart from a book's 200 and 304, and times are UTC, such as `2026-11-05T10:00:00Z`. A note's times also give microseconds.

## Keys and limits

`POST /api/game/sign-in` checks the password and makes a regular key at the `standard` tier named `UMST · <computer>`, with `api_key.client = 'umst'`. Signing in again on the same computer revokes that computer's earlier game key first. Every other call sends a key in `X-API-Key` or `Authorization: Bearer`. Any active regular key of the account works, so a key pasted into the game's settings works too; master keys are refused. The account and character calls and the list of grimoires need no Web Demo access, so every confirmed account plays. A book and its notes need it, as reading books under `/api/v1` has since 0.0.13 ([security](security.md)). Another account's key gets 403 `demo_access_required` there, and the call counts nowhere. `GET /api/game/me` names the account behind a key. Sign-out revokes the key only when its client is `umst`. A password reset revokes all the account's game keys.

A call may name its game install in `X-Install-Id`, the short id the game keeps per install and puts in its key names, `UMST · <computer> · <install id>`. The value is 1 to 64 ASCII letters, digits, hyphens or underscores, such as `k7m2qx`. A malformed or repeated header gets 422 `invalid_request` naming `X-Install-Id`, before the key is looked up or the call counted. Only the leases read it, and the game in players' hands sends none yet.

A regular key gets its tier's `requests_per_minute` (600 for `standard`) for each kind of request in a one-minute window. Account and character calls count as `character`. The list of grimoires, books and notes under `/api/game`, and calls under `/api/v1`, count as `book` and share one window. Past the limit the answer is 429 with `Retry-After` in seconds; a tier without allowance answers 429 with `Retry-After: 60`. Master keys have no limit on `/api/v1`. `api_usage_daily` counts every accepted request by key, UTC day and kind, master keys included. A refused request counts nowhere.

The Default key comes only from the signed-in API Keys page. When an account without one opens it, `POST /api/api-keys/default` makes a regular `standard` key named `Default` and answers 201 with its full text, once; otherwise it answers 200 `{"created": false}`. Confirming an email makes no key, because its link works without a session and could reach a mail scanner or anyone the email is forwarded to. Any key named `Default` without a client counts, revoked ones too, so revoking it never brings another.

## Endpoints

Paths are under `/api/game`.

| Call | Body | Answer |
| --- | --- | --- |
| `POST /sign-in` | `username`, `password`, `computer` | 200 `{user_id, username, key}` |
| `GET /me` | | 200 `{user_id, username, key}`, the key without its text |
| `POST /sign-out` | | 200 `{revoked, released_characters}` |
| `GET /characters` | | 200 `{characters: [character], limit: 6}` |
| `POST /characters` | `name`, `sex`, `save`, `save_version`, optional `summary` | 201 `{character, revision}` |
| `POST /characters/{id}/open` | | 200 `{character, save, save_version, revision, updated_at, lease_seconds, lease_expires_at}` |
| `POST /characters/{id}/heartbeat` | | 200 `{lease_seconds, lease_expires_at}` |
| `POST /characters/{id}/close` | | 200 `{released}` |
| `PUT /characters/{id}/data` | `save`, `save_version`, `revision`, optional `summary` | 200 `{revision, updated_at, last_played_at, lease_seconds, lease_expires_at}` |
| `DELETE /characters/{id}` | `name` | 200 `{deleted: true, character_id}` |
| `GET /grimoires` | | 200 `{may_read, grimoires: [grimoire]}` |
| `GET /grimoires/{id}/book` | | 200 the book, or 304 |
| `GET /grimoires/{id}/notes` | | 200 `{notes: [note]}` |
| `POST /grimoires/{id}/notes` | `note_type`, `knowledge_id` when attached, optional `tag`, `content` | 201 `{note}` |
| `PUT /grimoires/{id}/notes/{note_id}` | `tag`, `content`, `if_updated_at` | 200 `{note}` |
| `DELETE /grimoires/{id}/notes/{note_id}` | `if_updated_at` | 200 `{deleted: true, demo_note_id}` |

The sign-in `key`, and `/me`'s without `key`:

```json
{"api_key_id": 41, "name": "UMST · DESKTOP-1", "key": "umst_read_...", "key_prefix": "umst_read_AbCdEf",
 "key_type": "regular", "client": "umst", "tier": "standard", "requests_per_minute": 600}
```

A key made on the dashboard has `client` null. A character:

```json
{"character_id": 12, "name": "Aria", "sex": "female", "summary": {"rank": {"key": "...", "args": []}, "day": 3},
 "created_at": "2026-11-03T10:00:00Z", "last_played_at": null,
 "open_elsewhere": false, "open_elsewhere_seconds_left": null}
```

The list carries no saves. `sex` is `female` or `male`. `summary` is a JSON object of at most 2 KiB, stored as the game sends it; a PUT without one keeps the stored summary. `save` is a JSON object of at most 64 KiB, measured as PostgreSQL's text of the `jsonb`, and `save_version` (0 or more) is the game's save format. A name has 1 to 50 characters once spaces are trimmed and collapsed, and need not be unique. An account holds at most six characters. Deleting a character deletes its save, and so does deleting its account.

## Leases and revisions

Opening takes a 120-second lease for the key and returns the save and its `revision`. A heartbeat or save renews the lease. Close releases it, and so does anything that revokes the key: sign-out, the dashboard, a new sign-in on the same computer and a password reset. While the lease lives, another key's open, heartbeat, save or delete gets `open_elsewhere`. A key's lapsed lease stays its own until another key opens the character, so a computer that slept carries on. A save must name the current revision, and its answer gives the next one. While idle, the game should heartbeat about every 30 seconds.

Since 0.0.13 the lease also keeps the install that took it, so one key pasted on two computers no longer shares a lease. While the lease lives, the same key from another install counts as another key. Its open, heartbeat, save or delete gets `open_elsewhere`, the list shows the character `open_elsewhere`, and its close releases nothing. Once the lease lapses, that install may open the character and take the lease. Until it does, its heartbeat or save gets `not_open`. The key alone decides a call without the header, as before 0.0.13. Such a call keeps the install already beside its key's lease, and a call that names an install puts it on a lease that has none. Sign-out, and anything else that frees a key's leases, still frees every one of them, whichever install took it.

Each character call checks inside its own transaction that the key is still active, and holds it until the transaction ends.

## Books and notes

Since 0.0.16 the game downloads a whole book once per version and lays it out itself, so turning a page asks theumst.com nothing. `GET /grimoires` lists the grimoires the Web Demo shows, by id; hidden ones are absent. A grimoire:

```json
{"grimoire_id": 18, "title": "Topological Spaces, Part IB lecture notes (Randal-Williams, 2026)",
 "author": "Randal-Williams", "version": "<64 hex>", "objects": 468, "bytes": 70604, "may_read": true}
```

`title` is the language-1 title. `author` is the book's `source_metadata.author` when that is a non-empty string, else the title's last parenthesis less its `, YYYY`, else null. `version`, `objects` and `bytes`, the stored gzip's size, are those of the book's stored game answer, and null while it has none. `may_read` says whether the account has Web Demo access. Every row's value equals the top-level one today.

`GET /grimoires/{id}/book` sends that answer: the Web Demo's whole-book read of format 1 with each object's statement, working, summary, figures and page scans, as [data architecture](architecture/data.md) explains. It is served as the [Web Demo's](web-demo.md#whole-book-read) is. A 200 or 304 carries `ETag: "<version>"`, `Cache-Control: private, max-age=1209600` and `Vary: X-API-Key, Authorization, Accept-Encoding`, never `no-store`. `If-None-Match` matches when any listed tag equals the ETag, with or without `W/`, or is `*`, and the answer is then 304 with no body. A client whose `Accept-Encoding` allows gzip gets the stored gzip bytes with `Content-Encoding: gzip`, and any other the JSON. No request builds the answer: until ingestion or the [manual run](operations.md#whole-book-reads) has stored one, the book gets 409 `book_read_not_computed`.

Figures and page scans come from `GET /api/v1/storage/{storage_key}`, the `url` each one names. That route serves any active image of a visible book to a key whose account has Web Demo access, counts as `book` and answers `Cache-Control: private, no-store`. Its refusals are `/api/v1`'s: 401 and 404 as `{"detail"}`, 403 `demo_access_required`, and 429 with `Retry-After`.

The notes are the Web Demo's own `demo_note` rows, so a note made in the game shows in the Web Demo's notebook and one made there shows in the game. A note:

```json
{"demo_note_id": 7, "grimoire_id": 18, "knowledge_id": 18190, "note_type": "attached", "tag": "IVT",
 "content": "Compare $f(a) < 0 < f(b)$.", "created_at": "2026-11-13T10:00:00.123456Z",
 "updated_at": "2026-11-13T10:05:00.654321Z"}
```

The list gives the account's notes in one book, attached and scribbles, most recently changed first. Only the account's own notes are ever read or changed, and another account's note answers as a missing one. An `attached` note names an active object of the book in `knowledge_id`, and a `scribble` names none. `tag` holds at most 120 characters, stored without surrounding whitespace, and `content` at most 50,000, as in the Web Demo; neither may hold NUL or a lone surrogate. Unlike the Web Demo's, making a note needs no book in My grimoires and adds none. A PUT gives both `tag` and `content` and changes nothing else. A PUT or DELETE sends the `updated_at` it read as `if_updated_at`, with any UTC offset. When the note has changed since, the answer is 409 `note_changed` with the current `note`, so the game never overwrites an edit made on the website. The Web Demo's own edits have no such check. Notes carry no ETag.

## Errors

Errors answer `{"code", "detail"}` and the listed fields.

| Status | Code | Calls | When |
| --- | --- | --- | --- |
| 401 | `wrong_credentials` | sign-in | unknown username or wrong password |
| 403 | `email_unverified` | sign-in | right password, email not confirmed |
| 429 | `too_many_attempts` | sign-in | too many wrong passwords; `retry_after` and `Retry-After` |
| 401 | `invalid_key` | all others | key missing, unknown or revoked, revoked during the call, or its account unconfirmed |
| 403 | `master_key_not_allowed` | all others | a master key |
| 403 | `demo_access_required` | book, notes | the account has no Web Demo access; nothing counted |
| 429 | `rate_limited` | all others | key over its minute, or a tier without allowance; `retry_after` and `Retry-After` |
| 404 | `book_not_found` | book, notes | unknown or hidden grimoire |
| 404 | `object_not_found` | make note | `knowledge_id` is no active object of the book |
| 404 | `note_not_found` | change or delete note | no such note of this account in this book |
| 409 | `book_read_not_computed` | book | no stored answer in format 1 |
| 409 | `note_changed` | change or delete note | `if_updated_at` is not the note's `updated_at`; `note` is the current one |
| 404 | `not_found` | open, heartbeat, close, save, delete | no such character on this account |
| 409 | `full` | make | a seventh character; `limit` |
| 409 | `open_elsewhere` | open, heartbeat, save, delete | another key, or this key from another install, holds a live lease; `seconds_left` |
| 409 | `not_open` | heartbeat, save | this key has no lease, or another install of it took the lapsed one; open the character again |
| 409 | `stale` | save | made from an older revision; `revision` is the current one |
| 409 | `name_mismatch` | delete | the typed name differs |
| 413 | `save_too_large`, `summary_too_large` | make, save | over 64 KiB or 2 KiB; `limit_bytes` |
| 422 | `invalid_name` | make | name empty, over 50 characters or with control characters |
| 422 | `invalid_request` | any | malformed body or path, NaN or Infinity, a blank computer name, a malformed or repeated `X-Install-Id`, a note over its limits, holding NUL or with the wrong target; `errors` lists `{field, message}`, empty when no field is to blame |

A call checks its path, `X-Install-Id` and the shape of its body first, then the key in the table's order: 401, a master key, Web Demo access where needed, the minute. The call's own checks come after those.

Other answers come from outside the game API. In deployment the internal proxy (`config/nginx.docker.conf`) refuses a body over 128 KiB with 413 and an HTML page, or over 1 MiB on the notes paths, so any note the Web Demo stores fits. An unknown path answers 404 `{"detail": "API route not found"}`, a wrong method 405 `{"detail": "Method Not Allowed"}`, and a server failure 500.

## Slowing wrong passwords

The game's sign-in and the website's login at `/auth/login` check passwords through the same `sign_in_attempts.attempt()`, so they share these limits and records. A wrong password at either counts toward both. An attempt first looks the account up as `lower(username) = lower(btrim(typed))` in PostgreSQL; the website trims surrounding whitespace from the typed username first, as it always has. `sign_in_attempt` keeps each attempt for a day: the account's `user_id` when one matches, otherwise the SHA-256 of `lower(btrim(typed))`, computed by the same query; the client's public address; and whether the password was right. An account may fail 10 times in 15 minutes after its own last right password, so a look-alike account cannot clear another's count. A successful password reset counts as the account's right password: in the reset's own transaction, `sign_in_attempts.clear_account()` records one for the account with no address, so a locked-out player who resets can sign in at once at either. The wrong passwords stay recorded, so each address keeps its count. An unknown username may fail 10 times in 15 minutes, and an address 30 times. Past either limit, both refuse the attempt without checking the password and record nothing. A right password on an unconfirmed email counts as right. An unknown username costs the same password check as a known one. Advisory locks on the account or username, then on the address, are held from counting to recording, so parallel attempts cannot all pass.

Past a limit the game gets `too_many_attempts`. The website's login answers a JSON request with 429, its usual `ok` and `detail`, `code: "too_many_attempts"` and `retry_after`, and sets `Retry-After`, both in seconds. A form post goes back to `/login?error=too-many-attempts&retry_after=<seconds>`. The login page says how long to wait, in seconds under a minute and otherwise in minutes rounded up. The login's other answers are unchanged: an unknown username or a wrong password gets 401, a right password on an unconfirmed email gets 403 `email_unverified`, and any other right password starts a session. Form posts get the same redirects as before.

Uvicorn reads the client from `X-Forwarded-For` only when the connecting proxy is in `FORWARDED_ALLOW_IPS`, which `compose.deploy.yml` sets to Docker's private ranges. The address limit skips private and loopback addresses, so without that setting only the account limit applies, instead of one limit locking everyone out together.

## Checking migration 013

Read-only queries for a database after the migration:

```sql
SELECT api_rate_id, level_name, requests_per_minute FROM api_rate ORDER BY api_rate_id;  -- standard: 600
SELECT table_name, column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('api_rate', 'api_rate_window', 'api_usage_daily', 'api_key', 'character', 'character_data', 'sign_in_attempt')
ORDER BY table_name, ordinal_position;
SELECT conrelid::regclass, conname, pg_get_constraintdef(oid) FROM pg_constraint
WHERE conrelid IN ('api_rate'::regclass, 'api_rate_window'::regclass, 'api_usage_daily'::regclass, 'api_key'::regclass,
                   '"character"'::regclass, 'character_data'::regclass, 'sign_in_attempt'::regclass)
ORDER BY 1, 2;
SELECT indexrelid::regclass, pg_get_indexdef(indexrelid) FROM pg_index
WHERE indrelid IN ('"character"'::regclass, 'sign_in_attempt'::regclass, 'api_rate_window'::regclass, 'api_usage_daily'::regclass);
SELECT count(*) FILTER (WHERE key_type = 'master') AS master_keys, count(*) AS keys, count(client) AS game_keys FROM api_key;
SELECT (SELECT count(*) FROM "user") AS users, (SELECT count(*) FROM "character") AS characters,
       (SELECT count(*) FROM character_data) AS saves;
```

The `api_rate_window` primary key is `(api_key_id, kind)`. `"character"` has no unique constraint on `name`, and `class_id` and `sex` accept null. `character_data.data` and `save_version` have no default. `sign_in_attempt` has `sign_in_attempt_subject_check`, which requires exactly one of `user_id` and `username_hash`.

## Checking migration 014

`"character".character_data_id` references `character_data` with `ON DELETE CASCADE`, so deleting a save deletes its character, but deleting a character left its save behind. Migration 014 adds the function `delete_character_data()` and the `AFTER DELETE` row trigger `character_delete_character_data` on `"character"`. The trigger deletes the save a deleted character pointed at, whether the game deleted the character or its account's deletion cascaded to it. 014 also removes saves no character points at. The game's own delete of the save then finds nothing left to delete.

Run the `saves_without_character` query before applying 014 to see how many saves it will remove. Read-only queries for a database after the migration:

```sql
BEGIN TRANSACTION READ ONLY;
SELECT tgname, tgenabled, pg_get_triggerdef(oid) FROM pg_trigger
WHERE tgrelid = '"character"'::regclass AND NOT tgisinternal;
SELECT pg_get_functiondef('public.delete_character_data()'::regprocedure);
SELECT count(*) AS saves_without_character FROM character_data d
WHERE NOT EXISTS (SELECT 1 FROM "character" c WHERE c.character_data_id = d.character_data_id);
SELECT (SELECT count(*) FROM "user") AS users, (SELECT count(*) FROM "character") AS characters,
       (SELECT count(*) FROM character_data) AS saves;
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
WHERE conrelid = '"character"'::regclass AND contype IN ('f', 'u') ORDER BY conname;
COMMIT;
```

`character_delete_character_data` is the table's only trigger. It is enabled (`O`) and reads `AFTER DELETE ... FOR EACH ROW EXECUTE FUNCTION delete_character_data()`. The function deletes the row `WHERE character_data_id = OLD.character_data_id`. `saves_without_character` is 0 and `characters` equals `saves`. `character_character_data_id_fkey` still reads `REFERENCES character_data(character_data_id) ON DELETE CASCADE`, beside `character_character_data_id_key`.

## Checking migration 015

Migration 015 adds the nullable column `"character".lease_install_id` and its check `character_lease_install_id_check`, with the pattern the API takes for `X-Install-Id`. It changes no row, so every lease keeps its key and expiry and has no install until a call that names one takes or renews it. The runner marks 015 by the column. Run the last three queries before applying 015 too, and compare. Read-only queries for a database after the migration:

```sql
BEGIN TRANSACTION READ ONLY;
SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'character' ORDER BY ordinal_position;
SELECT count(lease_install_id) AS install_ids FROM "character";
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
WHERE conrelid = '"character"'::regclass ORDER BY conname;
SELECT count(*) AS characters, count(lease_api_key_id) AS leases,
       count(*) FILTER (WHERE lease_expires_at > now()) AS live_leases FROM "character";
SELECT (SELECT count(*) FROM "user") AS users, (SELECT count(*) FROM "character") AS characters,
       (SELECT count(*) FROM character_data) AS saves, (SELECT count(*) FROM api_key) AS keys;
COMMIT;
```

`lease_install_id` is the last column, after `lease_expires_at`. It is `text`, nullable, with no default. The constraints are those from before plus `character_lease_install_id_check`, which reads `CHECK ((lease_install_id ~ '^[A-Za-z0-9_-]{1,64}$'::text))`. `install_ids` is 0, and the other counts equal those from before, apart from leases that lapsed in between.
