CREATE TABLE IF NOT EXISTS notified_movies (
    film_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT now()
);
