import httpx

from discordstuff.errors import describe_exception
from discordstuff.scheduler import JobScheduler


class FailingJob:
    name = "cineplex"

    def __init__(self, exc: Exception):
        self._exc = exc

    async def run(self, notifier):
        raise self._exc


class RecordingNotifier:
    def __init__(self):
        self.errors = []

    async def send_bookable_movies(self, theatre_movies):
        pass

    async def send_error(self, notification):
        self.errors.append(notification)


class BrokenAlertNotifier(RecordingNotifier):
    async def send_error(self, notification):
        raise RuntimeError("Discord is down too")


def test_describe_exception_includes_type_and_message():
    assert describe_exception(ValueError("bad value")) == "ValueError: bad value"


def test_describe_exception_falls_back_to_type_for_an_empty_message():
    assert describe_exception(httpx.ConnectError("")) == "ConnectError"


async def test_failed_job_sends_an_alert_naming_the_exception():
    notifier = RecordingNotifier()
    scheduler = JobScheduler(jobs=[], notifier=notifier, interval_seconds=60)

    await scheduler._run_job_safely(FailingJob(httpx.ConnectError("")))

    [alert] = notifier.errors
    assert alert.title == "Job 'cineplex' failed"
    assert alert.body == "ConnectError"


async def test_failure_to_send_an_alert_does_not_propagate():
    scheduler = JobScheduler(jobs=[], notifier=BrokenAlertNotifier(), interval_seconds=60)

    await scheduler._run_job_safely(FailingJob(RuntimeError("boom")))
