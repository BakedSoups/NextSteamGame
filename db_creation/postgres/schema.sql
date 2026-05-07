CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    processed_rows INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS canonical_tag_groups (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    source_family TEXT NOT NULL,
    context TEXT NOT NULL,
    representative_tag TEXT NOT NULL,
    parent_tag TEXT NOT NULL DEFAULT '',
    specificity_level INTEGER NOT NULL DEFAULT 1,
    member_count INTEGER NOT NULL,
    total_occurrences INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS canonical_tag_members (
    group_id BIGINT NOT NULL REFERENCES canonical_tag_groups(id) ON DELETE CASCADE,
    member_tag TEXT NOT NULL,
    PRIMARY KEY (group_id, member_tag)
);

CREATE TABLE IF NOT EXISTS games (
    appid BIGINT PRIMARY KEY,
    name TEXT,
    normalized_name TEXT NOT NULL,
    canonical_vectors JSONB NOT NULL,
    canonical_metadata JSONB NOT NULL,
    source_review_samples JSONB NOT NULL,
    source_vectors JSONB NOT NULL,
    source_metadata JSONB NOT NULL,
    metacritic_score INTEGER,
    recommendations_total INTEGER,
    steamspy_owner_estimate BIGINT,
    steamspy_ccu INTEGER,
    positive INTEGER,
    negative INTEGER,
    estimated_review_count INTEGER,
    release_date_parsed TEXT,
    short_description TEXT NOT NULL DEFAULT '',
    header_image TEXT NOT NULL DEFAULT '',
    capsule_image TEXT NOT NULL DEFAULT '',
    capsule_imagev5 TEXT NOT NULL DEFAULT '',
    background_image TEXT NOT NULL DEFAULT '',
    background_image_raw TEXT NOT NULL DEFAULT '',
    logo_image TEXT NOT NULL DEFAULT '',
    library_hero_image TEXT NOT NULL DEFAULT '',
    library_capsule_image TEXT NOT NULL DEFAULT '',
    developers JSONB NOT NULL DEFAULT '[]'::jsonb,
    publishers JSONB NOT NULL DEFAULT '[]'::jsonb,
    release_date_text TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    search_name TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', coalesce(name, '')), 'A')
    ) STORED
);

CREATE INDEX IF NOT EXISTS games_normalized_name_idx
    ON games (normalized_name);

CREATE INDEX IF NOT EXISTS games_name_trgm_idx
    ON games USING GIN (normalized_name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS games_search_name_idx
    ON games USING GIN (search_name);

CREATE TABLE IF NOT EXISTS game_screenshots (
    appid BIGINT NOT NULL REFERENCES games(appid) ON DELETE CASCADE,
    screenshot_id INTEGER NOT NULL,
    path_thumbnail TEXT NOT NULL DEFAULT '',
    path_full TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (appid, screenshot_id)
);

CREATE INDEX IF NOT EXISTS game_screenshots_appid_idx
    ON game_screenshots (appid);

CREATE TABLE IF NOT EXISTS precomputed_candidates (
    source_appid BIGINT NOT NULL REFERENCES games(appid) ON DELETE CASCADE,
    candidate_appid BIGINT NOT NULL REFERENCES games(appid) ON DELETE CASCADE,
    rank INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'chroma',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_appid, candidate_appid)
);

CREATE INDEX IF NOT EXISTS precomputed_candidates_source_rank_idx
    ON precomputed_candidates (source_appid, rank);
