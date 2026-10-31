import asyncio
import logging

from discordstuff.jobs.base import Job
from discordstuff.notifications.base import Notification, Notifier

logger = logging.getLogger(__name__)


class JobScheduler:
    def __init__(self, jobs: list[Job], notifier: Notifier, interval_seconds: int):
        self._jobs = jobs
        self._notifier = notifier
        self._interval_seconds = interval_seconds

    async def run_forever(self) -> None:
        while True:
            for job in self._jobs:
                await self._run_job_safely(job)
            await asyncio.sleep(self._interval_seconds)

    async def _run_job_safely(self, job: Job) -> None:
        try:
            await job.run(self._notifier)
        except Exception as exc:
            logger.exception("Job '%s' failed", job.name)
            await self._notifier.send_error(
                Notification(title=f"Job '{job.name}' failed", body=str(exc))
            )
