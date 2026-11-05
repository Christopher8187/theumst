-- Theumst 0.0.10: UMST online accounts.
-- Per-minute allowances counted apart for book reads and the game's character
-- calls, daily usage per key, the game's own keys, characters stored on the
-- website, and sign-in attempts for slowing repeated wrong passwords.
-- Safe on tables that already hold rows; every statement can run again.

-- api_rate: requests_per_minute replaces searches_per_hour. The standard tier
-- allows 600 a minute; any other tier keeps its hourly allowance spread over a
-- minute, rounded up. The conversion is the column's USING expression.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'api_rate' AND column_name = 'searches_per_hour'
    ) THEN
        ALTER TABLE api_rate DROP CONSTRAINT IF EXISTS api_rate_searches_per_hour_check;
        ALTER TABLE api_rate RENAME COLUMN searches_per_hour TO requests_per_minute;
        ALTER TABLE api_rate ALTER COLUMN requests_per_minute TYPE int
            USING CASE
                WHEN level_name = 'standard' THEN 600
                ELSE ceil(requests_per_minute / 60.0)::int
            END;
    END IF;
END $$;
ALTER TABLE api_rate DROP CONSTRAINT IF EXISTS api_rate_requests_per_minute_check;
ALTER TABLE api_rate ADD CONSTRAINT api_rate_requests_per_minute_check
    CHECK (requests_per_minute >= 0);

-- api_rate_window holds only live counters, so the hourly table is replaced by
-- one row per key and kind, each a one-minute window.
DO $$
BEGIN
    IF to_regclass('api_rate_window') IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'api_rate_window' AND column_name = 'kind'
    ) THEN
        DROP TABLE api_rate_window;
    END IF;
END $$;
CREATE TABLE IF NOT EXISTS api_rate_window (
    api_key_id int NOT NULL REFERENCES api_key(api_key_id) ON DELETE CASCADE,
    kind text NOT NULL CHECK (kind IN ('book', 'character')),
    window_started_at timestamptz NOT NULL DEFAULT now(),
    request_count int NOT NULL DEFAULT 0 CHECK (request_count >= 0),
    PRIMARY KEY (api_key_id, kind)
);

-- Accepted requests per key, UTC day and kind, master keys included.
CREATE TABLE IF NOT EXISTS api_usage_daily (
    api_key_id int NOT NULL REFERENCES api_key(api_key_id) ON DELETE CASCADE,
    day date NOT NULL,
    kind text NOT NULL CHECK (kind IN ('book', 'character')),
    request_count bigint NOT NULL DEFAULT 0 CHECK (request_count >= 0),
    PRIMARY KEY (api_key_id, day, kind)
);

-- The program a key was made for: null for keys made on the dashboard and the
-- Default key, 'umst' for keys made by the game's sign-in.
ALTER TABLE api_key ADD COLUMN IF NOT EXISTS client text;
ALTER TABLE api_key DROP CONSTRAINT IF EXISTS api_key_client_check;
ALTER TABLE api_key ADD CONSTRAINT api_key_client_check
    CHECK (client ~ '^[a-z][a-z0-9_-]{0,31}$');

-- "character": a player's character. The old site-wide unique alias becomes
-- the name, 1 to 50 characters and not unique; class becomes optional.
DO $$
DECLARE
    unique_name text;
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'character' AND column_name = 'alias'
    ) THEN
        FOR unique_name IN
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_attribute att
              ON att.attrelid = con.conrelid AND att.attnum = ANY (con.conkey)
            WHERE con.conrelid = '"character"'::regclass
              AND con.contype = 'u'
              AND cardinality(con.conkey) = 1
              AND att.attname = 'alias'
        LOOP
            EXECUTE 'ALTER TABLE "character" DROP CONSTRAINT ' || quote_ident(unique_name);
        END LOOP;
        ALTER TABLE "character" RENAME COLUMN alias TO name;
        ALTER TABLE "character" ALTER COLUMN name TYPE text
            USING COALESCE(NULLIF(left(btrim(name), 50), ''), 'Character ' || character_id);
    END IF;
END $$;
ALTER TABLE "character" DROP CONSTRAINT IF EXISTS character_name_check;
ALTER TABLE "character" ADD CONSTRAINT character_name_check
    CHECK (char_length(name) BETWEEN 1 AND 50);
ALTER TABLE "character" ALTER COLUMN class_id DROP NOT NULL;

-- Null sex only on rows made before this migration; the game always sends it.
ALTER TABLE "character" ADD COLUMN IF NOT EXISTS sex text;
ALTER TABLE "character" DROP CONSTRAINT IF EXISTS character_sex_check;
ALTER TABLE "character" ADD CONSTRAINT character_sex_check
    CHECK (sex IN ('female', 'male'));

-- What the game shows in its character list without loading the save, stored
-- as the game sends it.
ALTER TABLE "character" ADD COLUMN IF NOT EXISTS summary jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE "character" DROP CONSTRAINT IF EXISTS character_summary_check;
ALTER TABLE "character" ADD CONSTRAINT character_summary_check
    CHECK (jsonb_typeof(summary) = 'object' AND octet_length(summary::text) <= 2048);

ALTER TABLE "character" ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE "character" ADD COLUMN IF NOT EXISTS last_played_at timestamptz;

-- The lease: the key that has the character open, until lease_expires_at.
ALTER TABLE "character" ADD COLUMN IF NOT EXISTS lease_api_key_id int;
ALTER TABLE "character" DROP CONSTRAINT IF EXISTS character_lease_api_key_id_fkey;
ALTER TABLE "character" ADD CONSTRAINT character_lease_api_key_id_fkey
    FOREIGN KEY (lease_api_key_id) REFERENCES api_key(api_key_id) ON DELETE SET NULL;
ALTER TABLE "character" ADD COLUMN IF NOT EXISTS lease_expires_at timestamptz;

-- One character_data row per character.
DO $$
BEGIN
    IF to_regclass('character_character_data_id_key') IS NULL THEN
        ALTER TABLE "character" ADD CONSTRAINT character_character_data_id_key
            UNIQUE (character_data_id);
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS character_user_idx ON "character" (user_id);
CREATE INDEX IF NOT EXISTS character_lease_key_idx
    ON "character" (lease_api_key_id) WHERE lease_api_key_id IS NOT NULL;

-- character_data: the game's save as a JSON object within 64 KiB, the save
-- format version the game wrote, and a revision raised by every save. Rows
-- made before this migration hold an empty save of version 0.
ALTER TABLE character_data ALTER COLUMN level DROP NOT NULL;
ALTER TABLE character_data ADD COLUMN IF NOT EXISTS data jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE character_data ALTER COLUMN data DROP DEFAULT;
ALTER TABLE character_data ADD COLUMN IF NOT EXISTS save_version int NOT NULL DEFAULT 0;
ALTER TABLE character_data ALTER COLUMN save_version DROP DEFAULT;
ALTER TABLE character_data ADD COLUMN IF NOT EXISTS revision int NOT NULL DEFAULT 1;
ALTER TABLE character_data ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE character_data DROP CONSTRAINT IF EXISTS character_data_data_check;
ALTER TABLE character_data ADD CONSTRAINT character_data_data_check
    CHECK (jsonb_typeof(data) = 'object' AND octet_length(data::text) <= 65536);
ALTER TABLE character_data DROP CONSTRAINT IF EXISTS character_data_save_version_check;
ALTER TABLE character_data ADD CONSTRAINT character_data_save_version_check
    CHECK (save_version >= 0);
ALTER TABLE character_data DROP CONSTRAINT IF EXISTS character_data_revision_check;
ALTER TABLE character_data ADD CONSTRAINT character_data_revision_check
    CHECK (revision >= 1);

-- Game sign-in attempts, kept a day. An attempt on an account names its
-- user_id; one on a username no account has keeps the SHA-256 of the
-- username as the lookup normalises it. Also the client's public address
-- when known, and whether the password was right.
CREATE TABLE IF NOT EXISTS sign_in_attempt (
    sign_in_attempt_id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id int REFERENCES "user"(user_id) ON DELETE CASCADE,
    username_hash text CHECK (username_hash ~ '^[0-9a-f]{64}$'),
    address inet,
    succeeded boolean NOT NULL,
    attempted_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT sign_in_attempt_subject_check CHECK ((user_id IS NULL) <> (username_hash IS NULL))
);
CREATE INDEX IF NOT EXISTS sign_in_attempt_user_idx
    ON sign_in_attempt (user_id, attempted_at) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS sign_in_attempt_username_idx
    ON sign_in_attempt (username_hash, attempted_at) WHERE username_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS sign_in_attempt_address_idx
    ON sign_in_attempt (address, attempted_at) WHERE address IS NOT NULL;
CREATE INDEX IF NOT EXISTS sign_in_attempt_time_idx
    ON sign_in_attempt (attempted_at);
