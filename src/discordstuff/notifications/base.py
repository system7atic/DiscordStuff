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


class BookableMoviesSendError(Exception):
    """Raised by `send_bookable_movies` after attempting every message, when some
    failed. `unsent_theatres` are those nobody was told about at all, which the
    Job should retry next run. Every other theatre counts as announced - once a
    subscriber has been pinged, re-sending would ping them again every run if
    the failure is permanent."""

    def __init__(self, unsent_theatres: "set[WatchedTheatre]", message: str):
        super().__init__(message)
        self.unsent_theatres = unsent_theatres


class Notifier(Protocol):
    async def send_bookable_movies(
        self, theatre_movies: "dict[WatchedTheatre, list[MovieBookingInfo]]"
    ) -> None:
        """Raises BookableMoviesSendError if only some messages could be sent. Any
        other exception means nothing was sent."""
        ...

    async def send_error(self, notification: Notification) -> None: ...
