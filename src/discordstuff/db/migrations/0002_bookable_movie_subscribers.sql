CREATE TABLE IF NOT EXISTS bookable_movie_subscribers (
    user_id BIGINT PRIMARY KEY,
    subscribed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
