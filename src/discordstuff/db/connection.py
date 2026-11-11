import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class MigrationError(Exception):
    """Raised when a migration file fails to apply, naming the file."""


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
            logger.info("Applying migration %s", migration_file.name)
            try:
                async with conn.transaction():
                    await conn.execute(migration_file.read_text())
                    await conn.execute(
                        "INSERT INTO applied_migrations (filename) VALUES ($1)",
                        migration_file.name,
                    )
            except asyncpg.PostgresError as exc:
                raise MigrationError(f"Migration {migration_file.name} failed: {exc}") from exc
