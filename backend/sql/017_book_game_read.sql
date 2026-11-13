-- Theumst 0.0.16: the game's whole-book read. One row per book, written by
-- ingestion and by scripts.build_book_reads, with book_read's columns. A new
-- table: safe while 0.0.15 serves, which never reads it. body_gzip holds the
-- served JSON answer gzipped; version is the SHA-256 of the answer without its
-- version key. The migration writes no rows; deleting a book deletes its row.
CREATE TABLE IF NOT EXISTS book_game_read (
    grimoire_id int PRIMARY KEY REFERENCES grimoire(grimoire_id) ON DELETE CASCADE,
    format int NOT NULL CHECK (format > 0),
    version text NOT NULL CHECK (version ~ '^[0-9a-f]{64}$'),
    body_gzip bytea NOT NULL,
    raw_bytes int NOT NULL CHECK (raw_bytes > 0),
    object_count int NOT NULL CHECK (object_count >= 0),
    built_at timestamptz NOT NULL DEFAULT now()
);
