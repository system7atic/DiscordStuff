import asyncpg


class NotifiedMovieRepository:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def is_notified(self, film_id: int) -> bool:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM notified_movies WHERE film_id = $1", film_id
            )
            return row is not None

    async def mark_notified(self, film_id: int, title: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO notified_movies (film_id, title)
                VALUES ($1, $2)
                ON CONFLICT (film_id) DO NOTHING
                """,
                film_id,
                title,
            )
