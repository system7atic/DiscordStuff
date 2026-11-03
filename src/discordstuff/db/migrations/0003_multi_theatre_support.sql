ALTER TABLE notified_movies ADD COLUMN IF NOT EXISTS theatre_id BIGINT;
UPDATE notified_movies SET theatre_id = 1409 WHERE theatre_id IS NULL;
ALTER TABLE notified_movies ALTER COLUMN theatre_id SET NOT NULL;
ALTER TABLE notified_movies DROP CONSTRAINT IF EXISTS notified_movies_pkey;
ALTER TABLE notified_movies ADD PRIMARY KEY (film_id, theatre_id);

ALTER TABLE bookable_movie_subscribers ADD COLUMN IF NOT EXISTS theatre_id BIGINT;
UPDATE bookable_movie_subscribers SET theatre_id = 1409 WHERE theatre_id IS NULL;
ALTER TABLE bookable_movie_subscribers ALTER COLUMN theatre_id SET NOT NULL;
ALTER TABLE bookable_movie_subscribers DROP CONSTRAINT IF EXISTS bookable_movie_subscribers_pkey;
ALTER TABLE bookable_movie_subscribers ADD PRIMARY KEY (user_id, theatre_id);
