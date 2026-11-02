-- Publisher keys for knowledge crystals, so one upload can place several objects in one crystal and a reimport finds it again.
ALTER TABLE knowledge_crystal ADD COLUMN IF NOT EXISTS source_key text;
CREATE UNIQUE INDEX IF NOT EXISTS knowledge_crystal_source_key_unique
    ON knowledge_crystal (source_key) WHERE source_key IS NOT NULL;
