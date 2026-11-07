import asyncio
from datetime import date

import pytest

from discordstuff.jobs.cineplex.bookable_movies import BookableListing, list_bookable_at
from discordstuff.jobs.cineplex.models import BookableMovie
from discordstuff.jobs.cineplex.theatres import WatchedTheatre

RICHMOND = WatchedTheatre(key="richmond", theatre_id=1409, name="SilverCity Riverport Cinemas")
METROPOLIS_ID = 1408


def _movie(film_id, title, slug, is_event=False, is_international=False) -> BookableMovie:
    return BookableMovie(
        film_id=film_id,
        title=title,
        slug=slug,
        is_event=is_event,
        is_international=is_international,
        poster_url=f"https://example.com/{slug}.jpg",
    )


class FakeTheatre:
    def __init__(self, theatre_id):
        self.theatre_id = theatre_id


class FakeClient:
    def __init__(self, movies, theatre_ids_by_film=None, dates_by_film_and_theatre=None):
        self._movies = movies
        self._theatre_ids_by_film = theatre_ids_by_film or {}
        self._dates = dates_by_film_and_theatre or {}

    async def get_bookable_movies(self):
        return self._movies

    async def get_theatres_for_film(self, film_id):
        return [FakeTheatre(theatre_id) for theatre_id in self._theatre_ids_by_film.get(film_id, [])]

    async def get_bookable_dates(self, film_id, theatre_id=None):
        return self._dates.get((film_id, theatre_id), [])


@pytest.mark.asyncio
async def test_lists_a_movie_at_the_theatre_with_its_link_and_that_theatres_first_date():
    client = FakeClient(
        [_movie(1, "Zootopia 2", "zootopia-2")],
        {1: [RICHMOND.theatre_id]},
        {
            (1, None): [date(2026, 11, 1)],
            (1, RICHMOND.theatre_id): [date(2026, 11, 20), date(2026, 11, 14)],
        },
    )

    assert await list_bookable_at(client, RICHMOND) == [
        BookableListing(
            title="Zootopia 2",
            url="https://www.cineplex.com/movie/zootopia-2",
            first_bookable_date=date(2026, 11, 14),
        )
    ]


@pytest.mark.asyncio
async def test_leaves_out_movies_not_playing_at_the_theatre():
    client = FakeClient(
        [_movie(1, "Elsewhere", "elsewhere")],
        {1: [METROPOLIS_ID]},
    )

    assert await list_bookable_at(client, RICHMOND) == []


@pytest.mark.asyncio
async def test_leaves_out_excluded_movies():
    client = FakeClient(
        [
            _movie(1, "NTL: Hamlet", "ntl-hamlet", is_event=True),
            _movie(2, "Ramayana (Hindi w/e.s.t.)", "ramayana", is_international=True),
        ],
        {1: [RICHMOND.theatre_id], 2: [RICHMOND.theatre_id]},
    )

    assert await list_bookable_at(client, RICHMOND) == []


@pytest.mark.asyncio
async def test_sorts_soonest_first_then_by_title_with_undated_movies_last():
    client = FakeClient(
        [
            _movie(1, "No Date", "no-date"),
            _movie(2, "later", "later"),
            _movie(3, "Zebra", "zebra"),
            _movie(4, "Apple", "apple"),
        ],
        {film_id: [RICHMOND.theatre_id] for film_id in (1, 2, 3, 4)},
        {
            (2, RICHMOND.theatre_id): [date(2026, 12, 1)],
            (3, RICHMOND.theatre_id): [date(2026, 11, 7)],
            (4, RICHMOND.theatre_id): [date(2026, 11, 7)],
        },
    )

    listings = await list_bookable_at(client, RICHMOND)

    assert [listing.title for listing in listings] == ["Apple", "Zebra", "later", "No Date"]
    assert listings[-1].first_bookable_date is None


@pytest.mark.asyncio
async def test_never_makes_more_than_five_cineplex_requests_at_once():
    class ConcurrencyTrackingClient(FakeClient):
        in_flight = 0
        peak = 0

        async def _track(self):
            type(self).in_flight += 1
            type(self).peak = max(type(self).peak, type(self).in_flight)
            await asyncio.sleep(0)
            type(self).in_flight -= 1

        async def get_theatres_for_film(self, film_id):
            await self._track()
            return await super().get_theatres_for_film(film_id)

        async def get_bookable_dates(self, film_id, theatre_id=None):
            await self._track()
            return await super().get_bookable_dates(film_id, theatre_id)

    movies = [_movie(film_id, f"Movie {film_id}", f"movie-{film_id}") for film_id in range(20)]
    client = ConcurrencyTrackingClient(
        movies, {movie.film_id: [RICHMOND.theatre_id] for movie in movies}
    )

    listings = await list_bookable_at(client, RICHMOND)

    assert len(listings) == 20
    assert ConcurrencyTrackingClient.peak == 5


@pytest.mark.asyncio
async def test_a_failed_cineplex_request_fails_the_whole_listing():
    class FailingDatesClient(FakeClient):
        async def get_bookable_dates(self, film_id, theatre_id=None):
            raise RuntimeError("Cineplex is down")

    client = FailingDatesClient([_movie(1, "Zootopia 2", "zootopia-2")], {1: [RICHMOND.theatre_id]})

    with pytest.raises(RuntimeError, match="Cineplex is down"):
        await list_bookable_at(client, RICHMOND)
