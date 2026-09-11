-- A create request and its result commit with the post and announcement.
-- Keep 008 unchanged for environments that already applied it.
CREATE TABLE IF NOT EXISTS media_create_request (
    user_id int NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
    request_id uuid NOT NULL,
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    response jsonb NOT NULL CHECK (jsonb_typeof(response) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, request_id)
);
