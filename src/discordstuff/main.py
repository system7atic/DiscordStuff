import asyncio
import logging

import asyncpg
from dotenv import load_dotenv

from discordstuff.config import Config
from discordstuff.db.connection import create_pool, run_migrations
from discordstuff.jobs.base import Job
from discordstuff.jobs.cineplex.client import CineplexClient
from discordstuff.jobs.cineplex.job import CineplexJob
from discordstuff.jobs.cineplex.repository import NotifiedMovieRepository
from discordstuff.notifications.discord_notifier import DiscordNotifier
from discordstuff.scheduler import JobScheduler

logging.basicConfig(level=logging.INFO)


def build_jobs(config: Config, pool: asyncpg.Pool) -> list[Job]:
    jobs: list[Job] = []
    if "cineplex" in config.enabled_jobs:
        client = CineplexClient(config)
        repository = NotifiedMovieRepository(pool)
        jobs.append(CineplexJob(client, repository, config.cineplex_theatre_id))
    return jobs


async def main() -> None:
    load_dotenv()
    config = Config.from_env()
    pool = await create_pool(config.database_url)
    await run_migrations(pool)

    notifier = DiscordNotifier(config)
    jobs = build_jobs(config, pool)
    scheduler = JobScheduler(jobs=jobs, notifier=notifier, interval_seconds=config.job_interval_seconds)

    await asyncio.gather(
        notifier.start(),
        scheduler.run_forever(),
    )


if __name__ == "__main__":
    asyncio.run(main())
