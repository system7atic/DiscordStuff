import logging

from discordstuff.jobs.cineplex.client import CineplexClient
from discordstuff.jobs.cineplex.location import THEATRE_ID
from discordstuff.jobs.cineplex.models import BookableMovie
from discordstuff.jobs.cineplex.repository import NotifiedMovieRepository
from discordstuff.notifications.base import Notification, Notifier

logger = logging.getLogger(__name__)

MOVIE_URL_TEMPLATE = "https://www.cineplex.com/movie/{slug}"


class CineplexJob:
    name = "cineplex"

    def __init__(
        self,
        client: CineplexClient,
        repository: NotifiedMovieRepository,
        theatre_id: int = THEATRE_ID,
    ):
        self._client = client
        self._repository = repository
        self._theatre_id = theatre_id

    async def run(self, notifier: Notifier) -> None:
        movies = await self._client.get_bookable_movies()
        if not movies:
            raise RuntimeError(
                "Cineplex returned zero bookable movies - that's never actually true, "
                "something's wrong with the request or response."
            )

        if not await self._repository.has_any():
            await self._seed(movies)
            return

        for movie in movies:
            if self._is_excluded(movie) or await self._repository.is_notified(movie.film_id):
                continue
            if await self._is_bookable_at_my_theatre(movie.film_id):
                await self._notify_new_movie(notifier, movie)

    async def _seed(self, movies: list[BookableMovie]) -> None:
        for movie in movies:
            if self._is_excluded(movie):
                continue
            if await self._is_bookable_at_my_theatre(movie.film_id):
                await self._repository.mark_notified(movie.film_id, movie.title)

    def _is_excluded(self, movie: BookableMovie) -> bool:
        return movie.is_event or movie.is_international

    async def _is_bookable_at_my_theatre(self, film_id: int) -> bool:
        theatres = await self._client.get_theatres_for_film(film_id)
        return any(theatre.theatre_id == self._theatre_id for theatre in theatres)

    async def _notify_new_movie(self, notifier: Notifier, movie: BookableMovie) -> None:
        dates = await self._client.get_bookable_dates(movie.film_id)
        first_date = min(dates).isoformat() if dates else "unknown"
        await notifier.send(
            Notification(
                title=f"{movie.title} is now bookable at your theatre",
                body=f"First bookable date: {first_date}",
                url=MOVIE_URL_TEMPLATE.format(slug=movie.slug),
            )
        )
        await self._repository.mark_notified(movie.film_id, movie.title)
