CREATE TABLE IF NOT EXISTS sentiment_corrections (
    id SERIAL PRIMARY KEY,
    post_id TEXT NOT NULL,
    original_sentiment TEXT NOT NULL,
    corrected_sentiment TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);