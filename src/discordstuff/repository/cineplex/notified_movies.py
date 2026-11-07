import asyncpg


class NotifiedMovieRepository:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def has_any(self, theatre_id: int) -> bool:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM notified_movies WHERE theatre_id = $1 LIMIT 1", theatre_id
            )
            return row is not None

    async def is_notified(self, film_id: int, theatre_id: int) -> bool:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM notified_movies WHERE film_id = $1 AND theatre_id = $2",
                film_id,
                theatre_id,
            )
            return row is not None

    async def mark_notified(self, film_id: int, title: str, theatre_id: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO notified_movies (film_id, title, theatre_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (film_id, theatre_id) DO NOTHING
                """,
                film_id,
                title,
                theatre_id,
            )
