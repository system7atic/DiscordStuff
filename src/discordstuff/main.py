import asyncio
import logging

import asyncpg
from dotenv import load_dotenv

from discordstuff.config import Config
from discordstuff.db.connection import create_pool, run_migrations
from discordstuff.jobs.base import Job
from discordstuff.jobs.cineplex.client import CineplexClient
from discordstuff.jobs.cineplex.job import CineplexJob
from discordstuff.notifications.discord.notifier import DiscordNotifier
from discordstuff.repository.cineplex.bookable_movie_subscribers import (
    BookableMovieSubscriberRepository,
)
from discordstuff.repository.cineplex.notified_movies import NotifiedMovieRepository
from discordstuff.scheduler import JobScheduler

logging.basicConfig(level=logging.INFO)


def build_jobs(config: Config, pool: asyncpg.Pool, cineplex_client: CineplexClient) -> list[Job]:
    jobs: list[Job] = []
    if "cineplex" in config.enabled_jobs:
        repository = NotifiedMovieRepository(pool)
        jobs.append(CineplexJob(cineplex_client, repository))
    return jobs


async def main() -> None:
    load_dotenv()
    config = Config.from_env()
    pool = await create_pool(config.database_url)
    await run_migrations(pool)

    subscribers = BookableMovieSubscriberRepository(pool)
    # Shared so the job and /get-bookable-movies reuse one discovered API key.
    cineplex_client = CineplexClient()
    notifier = DiscordNotifier(config, subscribers, cineplex_client)
    jobs = build_jobs(config, pool, cineplex_client)
    scheduler = JobScheduler(
        jobs=jobs, notifier=notifier, interval_seconds=config.job_interval_seconds
    )

    await asyncio.gather(
        notifier.start(),
        scheduler.run_forever(),
    )


if __name__ == "__main__":
    asyncio.run(main())
