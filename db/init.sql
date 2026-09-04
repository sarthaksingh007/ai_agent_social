-- Runs automatically the first time the Postgres container starts.
-- Defines the content table that holds generated posts + their approval state.
-- This table is the "Content Conveyor Belt" from the PRD (replaces Airtable).

CREATE TABLE IF NOT EXISTS posts (
    id              SERIAL PRIMARY KEY,
    post_id         TEXT        UNIQUE NOT NULL,
    client_name     TEXT        NOT NULL,
    scheduled_date  TEXT,
    target_platforms TEXT[]     DEFAULT '{}',
    pillar          TEXT,
    hook_text       TEXT,
    body_caption    TEXT,
    hashtags        TEXT[]      DEFAULT '{}',
    visual_prompt   TEXT,
    image_path      TEXT,
    -- Human-in-the-loop gate: nothing publishes until this becomes 'Approved'
    status          TEXT        NOT NULL DEFAULT 'Pending Human Review',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_posts_status ON posts (status);

-- Optional: keep updated_at fresh on any row change
CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_posts_updated_at ON posts;
CREATE TRIGGER trg_posts_updated_at
    BEFORE UPDATE ON posts
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
