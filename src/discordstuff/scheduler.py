import asyncio
import logging
import time

from discordstuff.errors import describe_exception
from discordstuff.jobs.base import Job
from discordstuff.notifications.base import Notification, Notifier

logger = logging.getLogger(__name__)


class JobScheduler:
    def __init__(self, jobs: list[Job], notifier: Notifier, interval_seconds: int):
        self._jobs = jobs
        self._notifier = notifier
        self._interval_seconds = interval_seconds

    async def run_forever(self) -> None:
        if not self._jobs:
            logger.warning("No jobs enabled - set ENABLED_JOBS to run any")
        while True:
            for job in self._jobs:
                await self._run_job_safely(job)
            await asyncio.sleep(self._interval_seconds)

    async def _run_job_safely(self, job: Job) -> None:
        started = time.monotonic()
        logger.info("Job '%s' starting", job.name)
        try:
            await job.run(self._notifier)
        except Exception as exc:
            logger.exception(
                "Job '%s' failed after %.1fs", job.name, time.monotonic() - started
            )
            await self._alert(
                Notification(title=f"Job '{job.name}' failed", body=describe_exception(exc))
            )
            return
        logger.info("Job '%s' finished in %.1fs", job.name, time.monotonic() - started)

    async def _alert(self, notification: Notification) -> None:
        # An alert that can't be sent must not take the scheduler loop down with
        # it - the failure is already in the logs, and the next run still happens.
        try:
            await self._notifier.send_error(notification)
        except Exception:
            logger.exception("Failed to send failure alert %r", notification.title)
