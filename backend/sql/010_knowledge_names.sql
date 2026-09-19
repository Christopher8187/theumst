-- Optional object headings; existing language labels remain the fallback.
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS name text;
