from typing import Protocol

from discordstuff.notifications.base import Notifier


class Job(Protocol):
    name: str

    async def run(self, notifier: Notifier) -> None: ...
