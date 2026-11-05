# Game accounts

UMST signs in to theumst.com with a username and password, then keeps its characters here. `routers/game.py` serves the game under `/api/game`; migration 013 holds the tables. The game sends JSON with `Content-Type: application/json`. Answers are JSON with `Cache-Control: no-store`, and times are UTC, such as `2026-11-05T10:00:00Z`.

## Keys and limits

`POST /api/game/sign-in` checks the password and makes a regular key at the `standard` tier named `UMST · <computer>`, with `api_key.client = 'umst'`. Every other call sends a key in `X-API-Key` or `Authorization: Bearer`. Any active key of the account works, so a key pasted into the game's settings works too. `GET /api/game/me` names the account behind a key. Sign-out revokes the key only when its client is `umst`.

A regular key gets its tier's `requests_per_minute` (600 for `standard`) for each kind of request in a one-minute window. Calls under `/api/game` count as `character`; calls under `/api/v1` count as `book`. Past the limit the answer is 429 with `Retry-After` in seconds. Master keys have no limit. `api_usage_daily` counts every accepted request by key, UTC day and kind, master keys included. A refused request counts nowhere.

Confirming an email address makes a regular `standard` key named `Default` and returns its full text once as `default_key`; the confirmation page shows it with a copy button. Accounts confirmed before 0.0.10 get theirs when the API Keys page first opens: `POST /api/api-keys/default` answers 201 with the key, or `{"created": false}`. Any key named `Default` without a client counts, revoked ones too, so revoking it never brings another.

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

A master key has `tier` and `requests_per_minute` null. A character:

```json
{"character_id": 12, "name": "Aria", "sex": "female", "summary": {"rank": {"key": "...", "args": []}, "day": 3},
 "created_at": "2026-11-03T10:00:00Z", "last_played_at": null,
 "open_elsewhere": false, "open_elsewhere_seconds_left": null}
```

The list carries no saves. `sex` is `female` or `male`. `summary` is a JSON object of at most 2 KiB, stored as the game sends it; a PUT without one keeps the stored summary. `save` is a JSON object of at most 64 KiB, measured as PostgreSQL's text of the `jsonb`, and `save_version` (0 or more) is the game's save format. A name has 1 to 50 characters once spaces are trimmed and collapsed, and need not be unique. An account holds at most six characters.

## Leases and revisions

Opening takes a 120-second lease for the key and returns the save and its `revision`. A heartbeat or save renews the lease; close releases it, as do sign-out and revoking the key. While the lease lives, another key's open, heartbeat, save or delete gets `open_elsewhere`. A key's lapsed lease stays its own until another key opens the character, so a computer that slept carries on. A save must name the current revision, and its answer gives the next one. While idle, the game should heartbeat about every 30 seconds.

## Errors

Errors answer `{"code", "detail"}` and the listed fields.

| Status | Code | When |
| --- | --- | --- |
| 401 | `wrong_credentials` | sign-in: unknown username or wrong password |
| 403 | `email_unverified` | sign-in: right password, email not confirmed |
| 429 | `too_many_attempts` | sign-in slowed; `retry_after` and `Retry-After` |
| 401 | `invalid_key` | key missing, unknown or revoked, or its account unconfirmed |
| 429 | `rate_limited` | key over its minute; `retry_after` and `Retry-After` |
| 404 | `not_found` | no such character on this account |
| 409 | `full` | a seventh character; `limit` |
| 409 | `open_elsewhere` | another key holds a live lease; `seconds_left` |
| 409 | `not_open` | heartbeat or save without this key's lease; open it again |
| 409 | `stale` | save from an older revision; `revision` is the current one |
| 409 | `name_mismatch` | delete: the typed name differs |
| 413 | `save_too_large`, `summary_too_large` | over 64 KiB or 2 KiB; `limit_bytes` |
| 422 | `invalid_name` | name empty, over 50 characters or with control characters |
| 422 | `invalid_request` | malformed body, NaN or Infinity; `errors` lists `{field, message}` |

## Slowing wrong passwords

`sign_in_attempt` keeps each game sign-in for a day: the SHA-256 of the casefolded username, the client's public address, and whether the password was right. A username may fail 10 times in 15 minutes after its last right password, and an address 30 times in 15 minutes. Past either, sign-in answers `too_many_attempts` without checking the password. An unknown username costs the same password check as a known one. Website login at `/auth/login` has no such limit yet.

Uvicorn reads the client from `X-Forwarded-For` only when the connecting proxy is in `FORWARDED_ALLOW_IPS`, which `compose.deploy.yml` sets to Docker's private ranges. The address limit skips private and loopback addresses, so without that setting only the username limit applies, instead of one limit locking everyone out together.

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

The `api_rate_window` primary key is `(api_key_id, kind)`. `"character"` has no unique constraint on `name`, and `class_id` and `sex` accept null. `character_data.data` and `save_version` have no default.
