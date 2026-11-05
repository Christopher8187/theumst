# Game accounts

UMST signs in to theumst.com with a username and password, then keeps its characters here. `routers/game.py` serves the game under `/api/game`; migration 013 holds the tables, and 014 deletes a character's save with it. The game sends JSON with `Content-Type: application/json`. Answers are JSON with `Cache-Control: no-store`, and times are UTC, such as `2026-11-05T10:00:00Z`.

## Keys and limits

`POST /api/game/sign-in` checks the password and makes a regular key at the `standard` tier named `UMST · <computer>`, with `api_key.client = 'umst'`. Signing in again on the same computer revokes that computer's earlier game key first. Every other call sends a key in `X-API-Key` or `Authorization: Bearer`. Any active regular key of the account works, so a key pasted into the game's settings works too; master keys are refused. `GET /api/game/me` names the account behind a key. Sign-out revokes the key only when its client is `umst`. A password reset revokes all the account's game keys.

A regular key gets its tier's `requests_per_minute` (600 for `standard`) for each kind of request in a one-minute window. Calls under `/api/game` count as `character`; calls under `/api/v1` count as `book`. Past the limit the answer is 429 with `Retry-After` in seconds; a tier without allowance answers 429 with `Retry-After: 60`. Master keys have no limit on `/api/v1`. `api_usage_daily` counts every accepted request by key, UTC day and kind, master keys included. A refused request counts nowhere.

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

Each character call checks inside its own transaction that the key is still active, and holds it until the transaction ends.

## Errors

Errors answer `{"code", "detail"}` and the listed fields.

| Status | Code | Calls | When |
| --- | --- | --- | --- |
| 401 | `wrong_credentials` | sign-in | unknown username or wrong password |
| 403 | `email_unverified` | sign-in | right password, email not confirmed |
| 429 | `too_many_attempts` | sign-in | too many wrong passwords; `retry_after` and `Retry-After` |
| 401 | `invalid_key` | all others | key missing, unknown or revoked, revoked during the call, or its account unconfirmed |
| 403 | `master_key_not_allowed` | all others | a master key |
| 429 | `rate_limited` | all others | key over its minute, or a tier without allowance; `retry_after` and `Retry-After` |
| 404 | `not_found` | open, heartbeat, close, save, delete | no such character on this account |
| 409 | `full` | make | a seventh character; `limit` |
| 409 | `open_elsewhere` | open, heartbeat, save, delete | another key holds a live lease; `seconds_left` |
| 409 | `not_open` | heartbeat, save | this key has no lease; open the character again |
| 409 | `stale` | save | made from an older revision; `revision` is the current one |
| 409 | `name_mismatch` | delete | the typed name differs |
| 413 | `save_too_large`, `summary_too_large` | make, save | over 64 KiB or 2 KiB; `limit_bytes` |
| 422 | `invalid_name` | make | name empty, over 50 characters or with control characters |
| 422 | `invalid_request` | any | malformed body or path, NaN or Infinity, a blank computer name; `errors` lists `{field, message}`, empty when no field is to blame |

Other answers come from outside the game API. In deployment the internal proxy (`config/nginx.docker.conf`) refuses a body over 128 KiB with 413 and an HTML page. An unknown path answers 404 `{"detail": "API route not found"}`, a wrong method 405 `{"detail": "Method Not Allowed"}`, and a server failure 500.

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
