-- Protected-research corpus authorization. This migration intentionally seeds
-- no corpus markers and no real user IDs. Security/Legal-approved rollout data
-- must be inserted through a protected operational process.

CREATE SEQUENCE IF NOT EXISTS research_corpus_policy_revision_seq;
CREATE SEQUENCE IF NOT EXISTS research_corpus_access_revision_seq;

CREATE TABLE IF NOT EXISTS research_corpus_policy (
    grimoire_id BIGINT PRIMARY KEY REFERENCES grimoire(grimoire_id) ON DELETE RESTRICT,
    is_protected BOOLEAN NOT NULL DEFAULT TRUE,
    object_key_prefix TEXT NOT NULL UNIQUE,
    required_active_user_count SMALLINT NOT NULL DEFAULT 2
        CHECK (required_active_user_count BETWEEN 1 AND 20),
    policy_revision BIGINT NOT NULL
        DEFAULT nextval('research_corpus_policy_revision_seq')
        CHECK (policy_revision > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (object_key_prefix <> ''),
    CHECK (object_key_prefix = btrim(object_key_prefix, '/')),
    CHECK (object_key_prefix !~ '(^|/)\.\.(/|$)')
);

CREATE TABLE IF NOT EXISTS research_corpus_user_access (
    grimoire_id BIGINT NOT NULL REFERENCES research_corpus_policy(grimoire_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
    access_revision BIGINT NOT NULL
        DEFAULT nextval('research_corpus_access_revision_seq')
        CHECK (access_revision > 0),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ,
    PRIMARY KEY (grimoire_id, user_id)
);

CREATE INDEX IF NOT EXISTS research_corpus_user_access_active_idx
    ON research_corpus_user_access (user_id, grimoire_id)
    WHERE revoked_at IS NULL;

COMMENT ON TABLE research_corpus_policy IS
    'Marks protected research corpora independently from public/demo visibility.';
COMMENT ON TABLE research_corpus_user_access IS
    'Per-corpus allowlist keyed only by stable internal user IDs; roles do not grant access.';

CREATE OR REPLACE FUNCTION bump_research_corpus_policy_revision()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.policy_revision := nextval('research_corpus_policy_revision_seq');
        NEW.updated_at := now();
    ELSIF ROW(NEW.is_protected, NEW.object_key_prefix, NEW.required_active_user_count)
       IS DISTINCT FROM
       ROW(OLD.is_protected, OLD.object_key_prefix, OLD.required_active_user_count) THEN
        NEW.policy_revision := nextval('research_corpus_policy_revision_seq');
        NEW.updated_at := now();
    ELSIF NEW.policy_revision <> OLD.policy_revision THEN
        RAISE EXCEPTION 'policy_revision is maintained automatically';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS research_corpus_policy_revision_guard ON research_corpus_policy;
CREATE TRIGGER research_corpus_policy_revision_guard
BEFORE INSERT OR UPDATE ON research_corpus_policy
FOR EACH ROW EXECUTE FUNCTION bump_research_corpus_policy_revision();

CREATE OR REPLACE FUNCTION bump_research_corpus_access_revision()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.access_revision := nextval('research_corpus_access_revision_seq');
    ELSIF NEW.revoked_at IS DISTINCT FROM OLD.revoked_at THEN
        NEW.access_revision := nextval('research_corpus_access_revision_seq');
    ELSIF NEW.access_revision <> OLD.access_revision THEN
        RAISE EXCEPTION 'access_revision is maintained automatically';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS research_corpus_access_revision_guard ON research_corpus_user_access;
CREATE TRIGGER research_corpus_access_revision_guard
BEFORE INSERT OR UPDATE ON research_corpus_user_access
FOR EACH ROW EXECUTE FUNCTION bump_research_corpus_access_revision();

ALTER TABLE media_post
    ADD COLUMN IF NOT EXISTS grimoire_id BIGINT REFERENCES grimoire(grimoire_id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS media_post_grimoire_idx
    ON media_post (grimoire_id)
    WHERE grimoire_id IS NOT NULL;
