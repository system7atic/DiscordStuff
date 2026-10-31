from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Notification:
    title: str
    body: str
    url: str | None = None


class Notifier(Protocol):
    async def send(self, notification: Notification) -> None: ...

    async def send_error(self, notification: Notification) -> None: ...
