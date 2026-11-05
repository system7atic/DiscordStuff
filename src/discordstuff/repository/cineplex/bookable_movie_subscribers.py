import asyncpg


class BookableMovieSubscriberRepository:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def add(self, user_id: int, theatre_id: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO bookable_movie_subscribers (user_id, theatre_id)
                VALUES ($1, $2)
                ON CONFLICT (user_id, theatre_id) DO NOTHING
                """,
                user_id,
                theatre_id,
            )

    async def remove(self, user_id: int, theatre_id: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM bookable_movie_subscribers WHERE user_id = $1 AND theatre_id = $2",
                user_id,
                theatre_id,
            )

    async def remove_all(self, user_id: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM bookable_movie_subscribers WHERE user_id = $1", user_id)

    async def list_theatre_ids_for_user(self, user_id: int) -> list[int]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT theatre_id FROM bookable_movie_subscribers WHERE user_id = $1", user_id
            )
            return [row["theatre_id"] for row in rows]

    async def list_all_grouped_by_theatre(self) -> dict[int, list[int]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT theatre_id, user_id FROM bookable_movie_subscribers ORDER BY theatre_id"
            )
            grouped: dict[int, list[int]] = {}
            for row in rows:
                grouped.setdefault(row["theatre_id"], []).append(row["user_id"])
            return grouped
