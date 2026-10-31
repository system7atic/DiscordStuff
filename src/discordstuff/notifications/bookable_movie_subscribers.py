import asyncpg


class BookableMovieSubscriberRepository:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def add(self, user_id: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO bookable_movie_subscribers (user_id)
                VALUES ($1)
                ON CONFLICT (user_id) DO NOTHING
                """,
                user_id,
            )

    async def remove(self, user_id: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM bookable_movie_subscribers WHERE user_id = $1", user_id)

    async def list_all(self) -> list[int]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id FROM bookable_movie_subscribers")
            return [row["user_id"] for row in rows]
