from typing import Protocol


class Notifier(Protocol):
    async def send(self, message: str) -> None: ...

    async def send_error(self, message: str) -> None: ...
