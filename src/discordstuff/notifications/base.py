from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from discordstuff.jobs.cineplex.theatres import WatchedTheatre
    from discordstuff.notifications.bookable_movies import MovieBookingInfo


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
