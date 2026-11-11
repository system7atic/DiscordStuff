import asyncio
import logging
import os
import sys

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

logger = logging.getLogger(__name__)

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_logging() -> None:
    # Read straight from the environment rather than Config, so logging is
    # already set up to report a Config that fails to load.
    raw_level = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
    level = logging.getLevelNamesMapping().get(raw_level)
    logging.basicConfig(level=level or logging.INFO, format=LOG_FORMAT)
    if level is None:
        logger.warning("Unknown LOG_LEVEL %r, using INFO", raw_level)
    # httpx logs every request at INFO, which is hundreds of lines per Cineplex
    # run. Its failures still surface as exceptions in our own logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def build_jobs(config: Config, pool: asyncpg.Pool, cineplex_client: CineplexClient) -> list[Job]:
    jobs: list[Job] = []
    if "cineplex" in config.enabled_jobs:
        repository = NotifiedMovieRepository(pool)
        jobs.append(CineplexJob(cineplex_client, repository))
    return jobs


async def main() -> None:
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
    logger.info(
        "Starting with jobs %s every %ss (%s)",
        sorted(config.enabled_jobs) or "none",
        config.job_interval_seconds,
        "dev" if config.is_dev else "prod",
    )

    await asyncio.gather(
        notifier.start(),
        scheduler.run_forever(),
    )


if __name__ == "__main__":
    load_dotenv()
    configure_logging()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted, shutting down")
    except Exception:
        # Startup failures (bad config, unreachable database, rejected Discord
        # token) land here. Exiting non-zero lets Docker's restart policy retry.
        logger.critical("Fatal error, shutting down", exc_info=True)
        sys.exit(1)
