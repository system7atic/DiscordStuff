from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from discordstuff.jobs.cineplex.bookable_movies import MovieBookingInfo
    from discordstuff.jobs.cineplex.theatres import WatchedTheatre


@dataclass(frozen=True)
class Notification:
    title: str
    body: str
    url: str | None = None


class Notifier(Protocol):
    async def send_bookable_movies(
        self, theatre_movies: "dict[WatchedTheatre, list[MovieBookingInfo]]"
    ) -> None: ...

    async def send_error(self, notification: Notification) -> None: ...
