import logging
from datetime import date

from discordstuff.jobs.cineplex.client import CineplexClient
from discordstuff.jobs.cineplex.models import BookableMovie
from discordstuff.jobs.cineplex.repository import NotifiedMovieRepository
from discordstuff.jobs.cineplex.theatres import WATCHED_THEATRES, WatchedTheatre
from discordstuff.notifications.base import Notifier
from discordstuff.notifications.bookable_movies import MovieBookingInfo

logger = logging.getLogger(__name__)

MOVIE_URL_TEMPLATE = "https://www.cineplex.com/movie/{slug}"


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
        for movie in movies:
            if self._is_excluded(movie):
                continue
            for theatre_id in await self._bookable_watched_theatre_ids(movie.film_id, watched_theatres_by_id):
                if await self._repository.is_notified(movie.film_id, theatre_id):
                    continue
                await self._repository.mark_notified(movie.film_id, movie.title, theatre_id)
                if theatre_id in seeding_theatre_ids:
                    continue
                if movie.film_id not in booking_info_by_film_id:
                    booking_info_by_film_id[movie.film_id] = await self._build_booking_info(movie)
                theatre = watched_theatres_by_id[theatre_id]
                new_movies_by_theatre.setdefault(theatre, []).append(booking_info_by_film_id[movie.film_id])

        if new_movies_by_theatre:
            await notifier.send_bookable_movies(new_movies_by_theatre)

    async def _bookable_watched_theatre_ids(
        self, film_id: int, watched_theatres_by_id: dict[int, WatchedTheatre]
    ) -> list[int]:
        theatres = await self._client.get_theatres_for_film(film_id)
        return [theatre.theatre_id for theatre in theatres if theatre.theatre_id in watched_theatres_by_id]

    def _is_excluded(self, movie: BookableMovie) -> bool:
        return movie.is_event or movie.is_international

    async def _build_booking_info(self, movie: BookableMovie) -> MovieBookingInfo:
        dates = await self._client.get_bookable_dates(movie.film_id)
        first_date = _format_date(min(dates)) if dates else "unknown"
        return MovieBookingInfo(
            title=movie.title,
            first_bookable_date=first_date,
            url=MOVIE_URL_TEMPLATE.format(slug=movie.slug),
            poster_url=movie.poster_url,
        )


def _format_date(value: date) -> str:
    return f"{value:%b} {value.day}, {value.year}"
