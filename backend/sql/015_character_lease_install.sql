-- Theumst 0.0.13: the game install that has a character open.
-- A character's lease names the key that opened it, so one key pasted on two
-- computers shared one lease. The game names its install in the X-Install-Id
-- header, and the lease keeps the install that took it, so another install
-- under the same key is refused while the lease lives. Null when the call that
-- took the lease named no install, as the game before this sends none.
-- Safe on tables that already hold rows; every statement can run again.

ALTER TABLE "character" ADD COLUMN IF NOT EXISTS lease_install_id text;
ALTER TABLE "character" DROP CONSTRAINT IF EXISTS character_lease_install_id_check;
ALTER TABLE "character" ADD CONSTRAINT character_lease_install_id_check
    CHECK (lease_install_id ~ '^[A-Za-z0-9_-]{1,64}$');
