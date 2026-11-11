from datetime import date

import pytest

from discordstuff.jobs.cineplex.job import CineplexJob
from discordstuff.jobs.cineplex.models import BookableMovie
from discordstuff.jobs.cineplex.theatres import WatchedTheatre
from discordstuff.notifications.base import BookableMoviesSendError

RICHMOND = WatchedTheatre(key="richmond", theatre_id=1409, name="SilverCity Riverport Cinemas")
METROPOLIS = WatchedTheatre(key="metropolis", theatre_id=1408, name="Cineplex Cinemas Metropolis")
OTHER_THEATRE_ID = 1145

AVENGERS = BookableMovie(
    film_id=34362,
    title="Avengers: Doomsday",
    slug="avengers-doomsday",
    is_event=False,
    is_international=False,
    poster_url="https://mediafiles.cineplex.com/Central/Film/Posters/34362_320_470.jpg",
)
HAMLET_EVENT = BookableMovie(
    film_id=99999,
    title="NTL: Hamlet",
    slug="ntl-hamlet",
    is_event=True,
    is_international=False,
    poster_url="https://mediafiles.cineplex.com/Central/Film/Posters/99999_320_470.jpg",
)
RAMAYANA_INTERNATIONAL = BookableMovie(
    film_id=62291,
    title="Ramayana (Hindi w/e.s.t.)",
    slug="est-ramayana-hindi-west",
    is_event=False,
    is_international=True,
    poster_url="https://mediafiles.cineplex.com/Central/Film/Posters/62291_320_470.jpg",
)


TOY_STORY = BookableMovie(
    film_id=40001,
    title="Toy Story 5",
    slug="toy-story-5",
    is_event=False,
    is_international=False,
    poster_url=None,
)


class FakeClient:
    def __init__(self, movies, theatres_by_film_id, dates_by_film_id=None, failing_film_ids=()):
        self._movies = movies
        self._theatres_by_film_id = theatres_by_film_id
        self._dates_by_film_id = dates_by_film_id or {}
        self._failing_film_ids = set(failing_film_ids)

    async def get_bookable_movies(self):
        return self._movies

    async def get_theatres_for_film(self, film_id):
        if film_id in self._failing_film_ids:
            raise ConnectionError("simulated dropped Cineplex request")
        return self._theatres_by_film_id.get(film_id, [])

    async def get_bookable_dates(self, film_id):
        return self._dates_by_film_id.get(film_id, [])


class FakeTheatre:
    def __init__(self, theatre_id):
        self.theatre_id = theatre_id


class FakeRepository:
    def __init__(self, seeded_theatre_ids=()):
        self._seeded_theatre_ids = set(seeded_theatre_ids)
        self._notified: set[tuple[int, int]] = set()

    async def has_any(self, theatre_id):
        return theatre_id in self._seeded_theatre_ids

    async def is_notified(self, film_id, theatre_id):
        return (film_id, theatre_id) in self._notified

    async def mark_notified(self, film_id, title, theatre_id):
        self._notified.add((film_id, theatre_id))
        self._seeded_theatre_ids.add(theatre_id)


class FakeNotifier:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_bookable_movies(self, theatre_movies):
        self.sent.append(theatre_movies)

    async def send_error(self, notification):
        raise AssertionError("send_error should not be called directly by the job")


class FailingNotifier(FakeNotifier):
    async def send_bookable_movies(self, theatre_movies):
        raise RuntimeError("simulated Discord send failure")


@pytest.mark.asyncio
async def test_first_run_seeds_silently_without_notifying():
    client = FakeClient(
        movies=[AVENGERS],
        theatres_by_film_id={34362: [FakeTheatre(RICHMOND.theatre_id)]},
    )
    repository = FakeRepository()
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatres=[RICHMOND])

    await job.run(notifier)

    assert notifier.sent == []
    assert await repository.is_notified(34362, RICHMOND.theatre_id)


@pytest.mark.asyncio
async def test_notifies_new_movie_bookable_at_watched_theatre():
    client = FakeClient(
        movies=[AVENGERS],
        theatres_by_film_id={34362: [FakeTheatre(RICHMOND.theatre_id)]},
        dates_by_film_id={34362: []},
    )
    repository = FakeRepository(seeded_theatre_ids={RICHMOND.theatre_id})
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatres=[RICHMOND])

    await job.run(notifier)

    assert len(notifier.sent) == 1
    [theatre_movies] = notifier.sent
    assert [movie.title for movie in theatre_movies[RICHMOND]] == ["Avengers: Doomsday"]
    assert theatre_movies[RICHMOND][0].url == "https://www.cineplex.com/movie/avengers-doomsday"
    assert theatre_movies[RICHMOND][0].poster_url == AVENGERS.poster_url
    assert await repository.is_notified(34362, RICHMOND.theatre_id)


@pytest.mark.asyncio
async def test_formats_first_bookable_date_as_month_day_year():
    client = FakeClient(
        movies=[AVENGERS],
        theatres_by_film_id={34362: [FakeTheatre(RICHMOND.theatre_id)]},
        dates_by_film_id={34362: [date(2026, 12, 25), date(2026, 12, 17)]},
    )
    repository = FakeRepository(seeded_theatre_ids={RICHMOND.theatre_id})
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatres=[RICHMOND])

    await job.run(notifier)

    [theatre_movies] = notifier.sent
    assert theatre_movies[RICHMOND][0].first_bookable_date == "Dec 17, 2026"


@pytest.mark.asyncio
async def test_does_not_notify_when_bookable_elsewhere_but_not_a_watched_theatre():
    client = FakeClient(
        movies=[AVENGERS],
        theatres_by_film_id={34362: [FakeTheatre(OTHER_THEATRE_ID)]},
    )
    repository = FakeRepository(seeded_theatre_ids={RICHMOND.theatre_id})
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatres=[RICHMOND])

    await job.run(notifier)

    assert notifier.sent == []
    assert not await repository.is_notified(34362, RICHMOND.theatre_id)


@pytest.mark.asyncio
async def test_does_not_renotify_already_notified_movie():
    client = FakeClient(
        movies=[AVENGERS],
        theatres_by_film_id={34362: [FakeTheatre(RICHMOND.theatre_id)]},
    )
    repository = FakeRepository(seeded_theatre_ids={RICHMOND.theatre_id})
    await repository.mark_notified(34362, AVENGERS.title, RICHMOND.theatre_id)
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatres=[RICHMOND])

    await job.run(notifier)

    assert notifier.sent == []


@pytest.mark.asyncio
async def test_skips_special_events():
    client = FakeClient(
        movies=[HAMLET_EVENT],
        theatres_by_film_id={99999: [FakeTheatre(RICHMOND.theatre_id)]},
    )
    repository = FakeRepository(seeded_theatre_ids={RICHMOND.theatre_id})
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatres=[RICHMOND])

    await job.run(notifier)

    assert notifier.sent == []
    assert not await repository.is_notified(99999, RICHMOND.theatre_id)


@pytest.mark.asyncio
async def test_skips_international_releases():
    client = FakeClient(
        movies=[RAMAYANA_INTERNATIONAL],
        theatres_by_film_id={62291: [FakeTheatre(RICHMOND.theatre_id)]},
    )
    repository = FakeRepository(seeded_theatre_ids={RICHMOND.theatre_id})
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatres=[RICHMOND])

    await job.run(notifier)

    assert notifier.sent == []
    assert not await repository.is_notified(62291, RICHMOND.theatre_id)


@pytest.mark.asyncio
async def test_empty_movie_list_raises_instead_of_silently_passing():
    client = FakeClient(movies=[], theatres_by_film_id={})
    repository = FakeRepository(seeded_theatre_ids={RICHMOND.theatre_id})
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatres=[RICHMOND])

    with pytest.raises(RuntimeError):
        await job.run(notifier)


@pytest.mark.asyncio
async def test_seeds_a_newly_added_theatre_independently_of_already_seeded_ones():
    """Adding a theatre to WATCHED_THEATRES shouldn't flood its subscribers with
    every movie already bookable there - it gets its own silent first-run seed,
    even though other watched theatres are long past seeding."""
    client = FakeClient(
        movies=[AVENGERS],
        theatres_by_film_id={34362: [FakeTheatre(RICHMOND.theatre_id), FakeTheatre(METROPOLIS.theatre_id)]},
    )
    repository = FakeRepository(seeded_theatre_ids={RICHMOND.theatre_id})
    await repository.mark_notified(34362, AVENGERS.title, RICHMOND.theatre_id)  # already notified at Richmond
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatres=[RICHMOND, METROPOLIS])

    await job.run(notifier)

    assert notifier.sent == []
    assert await repository.is_notified(34362, RICHMOND.theatre_id)
    assert await repository.is_notified(34362, METROPOLIS.theatre_id)


@pytest.mark.asyncio
async def test_groups_movie_bookable_at_multiple_watched_theatres_into_one_batch():
    client = FakeClient(
        movies=[AVENGERS],
        theatres_by_film_id={34362: [FakeTheatre(RICHMOND.theatre_id), FakeTheatre(METROPOLIS.theatre_id)]},
        dates_by_film_id={34362: []},
    )
    repository = FakeRepository(seeded_theatre_ids={RICHMOND.theatre_id, METROPOLIS.theatre_id})
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatres=[RICHMOND, METROPOLIS])

    await job.run(notifier)

    assert len(notifier.sent) == 1
    [theatre_movies] = notifier.sent
    assert set(theatre_movies.keys()) == {RICHMOND, METROPOLIS}


@pytest.mark.asyncio
async def test_failed_send_leaves_movies_unmarked_so_the_next_run_retries():
    client = FakeClient(
        movies=[AVENGERS],
        theatres_by_film_id={34362: [FakeTheatre(RICHMOND.theatre_id)]},
    )
    repository = FakeRepository(seeded_theatre_ids={RICHMOND.theatre_id})
    job = CineplexJob(client, repository, theatres=[RICHMOND])

    with pytest.raises(RuntimeError):
        await job.run(FailingNotifier())
    assert not await repository.is_notified(34362, RICHMOND.theatre_id)

    notifier = FakeNotifier()
    await job.run(notifier)
    [theatre_movies] = notifier.sent
    assert [movie.title for movie in theatre_movies[RICHMOND]] == ["Avengers: Doomsday"]
    assert await repository.is_notified(34362, RICHMOND.theatre_id)


@pytest.mark.asyncio
async def test_cineplex_failure_partway_through_leaves_earlier_movies_unmarked():
    client = FakeClient(
        movies=[AVENGERS, TOY_STORY],
        theatres_by_film_id={34362: [FakeTheatre(RICHMOND.theatre_id)]},
        failing_film_ids={TOY_STORY.film_id},
    )
    repository = FakeRepository(seeded_theatre_ids={RICHMOND.theatre_id})
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatres=[RICHMOND])

    with pytest.raises(ConnectionError):
        await job.run(notifier)

    assert notifier.sent == []
    assert not await repository.is_notified(34362, RICHMOND.theatre_id)


@pytest.mark.asyncio
async def test_cineplex_failure_during_seeding_leaves_the_theatre_unseeded():
    """A half-finished seed must not leave the theatre with some rows, or the next
    run would treat it as seeded and announce every remaining movie as new."""
    client = FakeClient(
        movies=[AVENGERS, TOY_STORY],
        theatres_by_film_id={34362: [FakeTheatre(RICHMOND.theatre_id)]},
        failing_film_ids={TOY_STORY.film_id},
    )
    repository = FakeRepository()
    job = CineplexJob(client, repository, theatres=[RICHMOND])

    with pytest.raises(ConnectionError):
        await job.run(FakeNotifier())

    assert not await repository.has_any(RICHMOND.theatre_id)


class PartlyFailingNotifier(FakeNotifier):
    def __init__(self, unsent_theatres):
        super().__init__()
        self._unsent_theatres = unsent_theatres

    async def send_bookable_movies(self, theatre_movies):
        self.sent.append(theatre_movies)
        raise BookableMoviesSendError(self._unsent_theatres, "simulated partial failure")


@pytest.mark.asyncio
async def test_partial_send_failure_only_leaves_unsent_theatres_to_retry():
    client = FakeClient(
        movies=[AVENGERS],
        theatres_by_film_id={34362: [FakeTheatre(RICHMOND.theatre_id), FakeTheatre(METROPOLIS.theatre_id)]},
    )
    repository = FakeRepository(seeded_theatre_ids={RICHMOND.theatre_id, METROPOLIS.theatre_id})
    job = CineplexJob(client, repository, theatres=[RICHMOND, METROPOLIS])

    with pytest.raises(BookableMoviesSendError):
        await job.run(PartlyFailingNotifier(unsent_theatres={METROPOLIS}))

    assert await repository.is_notified(34362, RICHMOND.theatre_id)
    assert not await repository.is_notified(34362, METROPOLIS.theatre_id)


@pytest.mark.asyncio
async def test_partial_send_failure_does_not_block_seeding_another_theatre():
    client = FakeClient(
        movies=[AVENGERS],
        theatres_by_film_id={34362: [FakeTheatre(RICHMOND.theatre_id), FakeTheatre(METROPOLIS.theatre_id)]},
    )
    # Richmond is established; Metropolis is newly added and should seed silently.
    repository = FakeRepository(seeded_theatre_ids={RICHMOND.theatre_id})
    job = CineplexJob(client, repository, theatres=[RICHMOND, METROPOLIS])

    with pytest.raises(BookableMoviesSendError):
        await job.run(PartlyFailingNotifier(unsent_theatres={RICHMOND}))

    assert not await repository.is_notified(34362, RICHMOND.theatre_id)
    assert await repository.is_notified(34362, METROPOLIS.theatre_id)


@pytest.mark.asyncio
async def test_film_listed_twice_is_only_announced_once():
    client = FakeClient(
        movies=[AVENGERS, AVENGERS],
        theatres_by_film_id={34362: [FakeTheatre(RICHMOND.theatre_id)]},
    )
    repository = FakeRepository(seeded_theatre_ids={RICHMOND.theatre_id})
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatres=[RICHMOND])

    await job.run(notifier)

    [theatre_movies] = notifier.sent
    assert [movie.title for movie in theatre_movies[RICHMOND]] == ["Avengers: Doomsday"]
