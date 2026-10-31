import pytest

from discordstuff.jobs.cineplex.job import CineplexJob
from discordstuff.jobs.cineplex.models import BookableMovie
from discordstuff.notifications.base import Notification

THEATRE_ID = 1409
OTHER_THEATRE_ID = 1145

AVENGERS = BookableMovie(
    film_id=34362, title="Avengers: Doomsday", slug="avengers-doomsday", is_event=False, is_international=False
)
HAMLET_EVENT = BookableMovie(
    film_id=99999, title="NTL: Hamlet", slug="ntl-hamlet", is_event=True, is_international=False
)
RAMAYANA_INTERNATIONAL = BookableMovie(
    film_id=62291,
    title="Ramayana (Hindi w/e.s.t.)",
    slug="est-ramayana-hindi-west",
    is_event=False,
    is_international=True,
)


class FakeClient:
    def __init__(self, movies, theatres_by_film_id, dates_by_film_id=None):
        self._movies = movies
        self._theatres_by_film_id = theatres_by_film_id
        self._dates_by_film_id = dates_by_film_id or {}

    async def get_bookable_movies(self):
        return self._movies

    async def get_theatres_for_film(self, film_id):
        return self._theatres_by_film_id.get(film_id, [])

    async def get_bookable_dates(self, film_id):
        return self._dates_by_film_id.get(film_id, [])


class FakeTheatre:
    def __init__(self, theatre_id):
        self.theatre_id = theatre_id


class FakeRepository:
    def __init__(self, seeded_film_ids=()):
        self._notified = set(seeded_film_ids)

    async def has_any(self):
        return bool(self._notified)

    async def is_notified(self, film_id):
        return film_id in self._notified

    async def mark_notified(self, film_id, title):
        self._notified.add(film_id)


class FakeNotifier:
    def __init__(self):
        self.sent: list[Notification] = []

    async def send(self, notification):
        self.sent.append(notification)

    async def send_error(self, notification):
        raise AssertionError("send_error should not be called directly by the job")


@pytest.mark.asyncio
async def test_first_run_seeds_silently_without_notifying():
    client = FakeClient(
        movies=[AVENGERS],
        theatres_by_film_id={34362: [FakeTheatre(THEATRE_ID)]},
    )
    repository = FakeRepository()
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatre_id=THEATRE_ID)

    await job.run(notifier)

    assert notifier.sent == []
    assert await repository.is_notified(34362)


@pytest.mark.asyncio
async def test_notifies_new_movie_bookable_at_my_theatre():
    client = FakeClient(
        movies=[AVENGERS],
        theatres_by_film_id={34362: [FakeTheatre(THEATRE_ID)]},
        dates_by_film_id={34362: []},
    )
    repository = FakeRepository(seeded_film_ids={1})  # non-empty, so this isn't a first run
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatre_id=THEATRE_ID)

    await job.run(notifier)

    assert len(notifier.sent) == 1
    assert "Avengers: Doomsday" in notifier.sent[0].title
    assert notifier.sent[0].url == "https://www.cineplex.com/movie/avengers-doomsday"
    assert await repository.is_notified(34362)


@pytest.mark.asyncio
async def test_does_not_notify_when_bookable_elsewhere_but_not_my_theatre():
    client = FakeClient(
        movies=[AVENGERS],
        theatres_by_film_id={34362: [FakeTheatre(OTHER_THEATRE_ID)]},
    )
    repository = FakeRepository(seeded_film_ids={1})
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatre_id=THEATRE_ID)

    await job.run(notifier)

    assert notifier.sent == []
    assert not await repository.is_notified(34362)


@pytest.mark.asyncio
async def test_does_not_renotify_already_notified_movie():
    client = FakeClient(
        movies=[AVENGERS],
        theatres_by_film_id={34362: [FakeTheatre(THEATRE_ID)]},
    )
    repository = FakeRepository(seeded_film_ids={34362})
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatre_id=THEATRE_ID)

    await job.run(notifier)

    assert notifier.sent == []


@pytest.mark.asyncio
async def test_skips_special_events():
    client = FakeClient(
        movies=[HAMLET_EVENT],
        theatres_by_film_id={99999: [FakeTheatre(THEATRE_ID)]},
    )
    repository = FakeRepository(seeded_film_ids={1})
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatre_id=THEATRE_ID)

    await job.run(notifier)

    assert notifier.sent == []
    assert not await repository.is_notified(99999)


@pytest.mark.asyncio
async def test_skips_international_releases():
    client = FakeClient(
        movies=[RAMAYANA_INTERNATIONAL],
        theatres_by_film_id={62291: [FakeTheatre(THEATRE_ID)]},
    )
    repository = FakeRepository(seeded_film_ids={1})
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatre_id=THEATRE_ID)

    await job.run(notifier)

    assert notifier.sent == []
    assert not await repository.is_notified(62291)


@pytest.mark.asyncio
async def test_empty_movie_list_raises_instead_of_silently_passing():
    client = FakeClient(movies=[], theatres_by_film_id={})
    repository = FakeRepository(seeded_film_ids={1})
    notifier = FakeNotifier()
    job = CineplexJob(client, repository, theatre_id=THEATRE_ID)

    with pytest.raises(RuntimeError):
        await job.run(notifier)
