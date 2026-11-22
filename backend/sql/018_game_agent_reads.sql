-- Theumst 0.0.19: the reads UMST's agents make over every book.
-- The game's search (/api/game/search) and graph reads (/api/game/graph) count
-- each call in a key's per-minute allowance and its daily usage under kinds of
-- their own, 'search' and 'graph', beside 'book' and 'character'. The checks
-- keep the names PostgreSQL gave schema.sql's inline checks.
-- Three partial indexes keep the agents' reads in proportion to what they
-- return as books are added: a crystal's active members (every answer's
-- crystal size, a crystal's members), an active object by its source key
-- (neighbours, ?source_key= and match), and the books the Web Demo hides (the
-- search's Qdrant filter).
-- Changes no row. 0.0.18 writes only 'book' and 'character', so this can run
-- while it serves. Every statement can run again.

ALTER TABLE api_rate_window DROP CONSTRAINT IF EXISTS api_rate_window_kind_check;
ALTER TABLE api_rate_window ADD CONSTRAINT api_rate_window_kind_check
    CHECK (kind IN ('book', 'character', 'search', 'graph'));
ALTER TABLE api_usage_daily DROP CONSTRAINT IF EXISTS api_usage_daily_kind_check;
ALTER TABLE api_usage_daily ADD CONSTRAINT api_usage_daily_kind_check
    CHECK (kind IN ('book', 'character', 'search', 'graph'));

CREATE INDEX IF NOT EXISTS knowledge_active_crystal_idx
    ON knowledge (knowledge_crystal_id) WHERE is_active;
CREATE INDEX IF NOT EXISTS knowledge_active_source_key_idx
    ON knowledge (source_key) WHERE is_active;
CREATE INDEX IF NOT EXISTS grimoire_hidden_idx
    ON grimoire (grimoire_id) WHERE (source_metadata->>'demo') IS DISTINCT FROM 'true';
