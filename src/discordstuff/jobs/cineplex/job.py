import logging

from discordstuff.jobs.cineplex.bookable_movies import MovieBookingInfo, format_date
from discordstuff.jobs.cineplex.client import CineplexClient
from discordstuff.jobs.cineplex.models import BookableMovie
from discordstuff.jobs.cineplex.theatres import WATCHED_THEATRES, WatchedTheatre
from discordstuff.notifications.base import BookableMoviesSendError, Notifier
from discordstuff.repository.cineplex.notified_movies import NotifiedMovieRepository

logger = logging.getLogger(__name__)


class CineplexJob:
    name = "cineplex"

    def __init__(
        self,
        client: CineplexClient,
        repository: NotifiedMovieRepository,
        theatres: tuple[WatchedTheatre, ...] = WATCHED_THEATRES,
    ):
        self._client = client
        self._repository = repository
        self._theatres = theatres

    async def run(self, notifier: Notifier) -> None:
        movies = await self._client.get_bookable_movies()
        if not movies:
            raise RuntimeError(
                "Cineplex returned zero bookable movies - that's never actually true, "
                "something's wrong with the request or response."
            )

        # A theatre with no notified_movies rows yet (e.g. one just added to
        # WATCHED_THEATRES) is seeded silently so it doesn't flood everyone
        # already bookable there with a backlog of "new" movies.
        seeding_theatre_ids = {
            theatre.theatre_id
            for theatre in self._theatres
            if not await self._repository.has_any(theatre.theatre_id)
        }
        watched_theatres_by_id = {theatre.theatre_id: theatre for theatre in self._theatres}

        new_movies_by_theatre: dict[WatchedTheatre, list[MovieBookingInfo]] = {}
        booking_info_by_film_id: dict[int, MovieBookingInfo] = {}
        # (movie, theatre) pairs to record as Notified movies once the run is done.
        newly_bookable: list[tuple[BookableMovie, WatchedTheatre]] = []
        seeded_count_by_theatre: dict[WatchedTheatre, int] = {}
        checked_film_ids: set[int] = set()
        for movie in movies:
            # Marking is deferred, so is_notified can't catch a film listed twice.
            if movie.is_excluded or movie.film_id in checked_film_ids:
                continue
            checked_film_ids.add(movie.film_id)
            for theatre_id in await self._bookable_watched_theatre_ids(movie.film_id, watched_theatres_by_id):
                if await self._repository.is_notified(movie.film_id, theatre_id):
                    continue
                theatre = watched_theatres_by_id[theatre_id]
                newly_bookable.append((movie, theatre))
                if theatre_id in seeding_theatre_ids:
                    seeded_count_by_theatre[theatre] = seeded_count_by_theatre.get(theatre, 0) + 1
                    continue
                if movie.film_id not in booking_info_by_film_id:
                    booking_info_by_film_id[movie.film_id] = await self._build_booking_info(movie)
                new_movies_by_theatre.setdefault(theatre, []).append(booking_info_by_film_id[movie.film_id])

        # Nothing is marked until the send has been attempted, so a failure before
        # anything reaches Discord - a dropped Cineplex request, an unreachable
        # channel - leaves every movie to be retried next run instead of silently
        # dropped. It also keeps a half-finished seed from leaving a theatre with
        # some rows, which would make the next run announce the rest as new.
        send_error: BookableMoviesSendError | None = None
        if new_movies_by_theatre:
            try:
                await notifier.send_bookable_movies(new_movies_by_theatre)
            except BookableMoviesSendError as exc:
                send_error = exc
        unsent = send_error.unsent_theatres if send_error else set()
        for movie, theatre in newly_bookable:
            if theatre not in unsent:
                await self._repository.mark_notified(movie.film_id, movie.title, theatre.theatre_id)

        for theatre, count in seeded_count_by_theatre.items():
            logger.info("Silently seeded %d movies for first run at %s", count, theatre.name)
        new_counts = ", ".join(
            f"{theatre.name}: {len(theatre_movies)}"
            for theatre, theatre_movies in new_movies_by_theatre.items()
        )
        logger.info(
            "Checked %d bookable movies; newly bookable at watched theatres: %s",
            len(checked_film_ids),
            new_counts or "none",
        )
        if send_error:
            raise send_error

    async def _bookable_watched_theatre_ids(
        self, film_id: int, watched_theatres_by_id: dict[int, WatchedTheatre]
    ) -> list[int]:
        theatres = await self._client.get_theatres_for_film(film_id)
        return [theatre.theatre_id for theatre in theatres if theatre.theatre_id in watched_theatres_by_id]

    async def _build_booking_info(self, movie: BookableMovie) -> MovieBookingInfo:
        dates = await self._client.get_bookable_dates(movie.film_id)
        first_date = format_date(min(dates)) if dates else "unknown"
        return MovieBookingInfo(
            title=movie.title,
            first_bookable_date=first_date,
            url=movie.url,
            poster_url=movie.poster_url,
        )
