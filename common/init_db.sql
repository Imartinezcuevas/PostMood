CREATE TABLE IF NOT EXISTS sentiment_corrections (
    id BIGSERIAL PRIMARY KEY,

    post_id TEXT NOT NULL,
    keyword TEXT NOT NULL,

    text TEXT NOT NULL,
    original_sentiment TEXT NOT NULL,
    corrected_sentiment TEXT NOT NULL,

    score FLOAT,

    source TEXT NOT NULL DEFAULT 'manual',
    approved BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dataset_generation_log (
    id BIGSERIAL PRIMARY KEY,
    last_post_id BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);