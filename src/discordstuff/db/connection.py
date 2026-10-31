from pathlib import Path

import asyncpg

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def create_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(database_url)


async def run_migrations(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS applied_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        applied_rows = await conn.fetch("SELECT filename FROM applied_migrations")
        applied = {row["filename"] for row in applied_rows}

        for migration_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if migration_file.name in applied:
                continue
            async with conn.transaction():
                await conn.execute(migration_file.read_text())
                await conn.execute(
                    "INSERT INTO applied_migrations (filename) VALUES ($1)",
                    migration_file.name,
                )
