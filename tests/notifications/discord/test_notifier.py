from unittest.mock import Mock

import discord
import pytest

from discordstuff.jobs.cineplex.bookable_movies import (
    BookableMoviesBatch,
    MovieBookingInfo,
    TheatreSection,
)
from discordstuff.jobs.cineplex.theatres import WatchedTheatre
from discordstuff.notifications.base import BookableMoviesSendError
from discordstuff.notifications.discord.notifier import send_batches

RICHMOND = WatchedTheatre(key="richmond", theatre_id=1409, name="SilverCity Riverport Cinemas")
METROPOLIS = WatchedTheatre(key="metropolis", theatre_id=1408, name="Cineplex Cinemas Metropolis")
COQUITLAM = WatchedTheatre(key="coquitlam", theatre_id=1412, name="Cineplex Cinemas Coquitlam and VIP")

MOVIE = MovieBookingInfo(
    title="Avengers: Doomsday",
    first_bookable_date="Dec 17, 2026",
    url="https://www.cineplex.com/movie/avengers",
    poster_url="https://example.com/avengers.jpg",
)


def _batch(theatre: WatchedTheatre, subscriber_id: int) -> BookableMoviesBatch:
    return BookableMoviesBatch(
        subscriber_ids=[subscriber_id], sections=[TheatreSection(theatre=theatre, movies=[MOVIE])]
    )


def _http_error() -> discord.HTTPException:
    return discord.HTTPException(Mock(status=400), "rejected")


class FakeChannel:
    """Fails the sends at the given 0-based indexes, and records the rest."""

    def __init__(self, failing_sends=()):
        self._failing_sends = set(failing_sends)
        self._count = 0
        self.sent: list[dict] = []

    async def send(self, **message):
        index = self._count
        self._count += 1
        if index in self._failing_sends:
            raise _http_error()
        self.sent.append(message)


async def test_sends_every_batch_when_nothing_fails():
    channel = FakeChannel()

    await send_batches(channel, [_batch(RICHMOND, 111), _batch(METROPOLIS, 222)])

    assert len(channel.sent) == 4  # mention + card per batch


async def test_batch_failing_on_its_first_message_is_reported_unsent_and_others_still_go_out():
    # Send 0 is Richmond's mention; its failure skips the rest of Richmond's batch.
    channel = FakeChannel(failing_sends={0})

    with pytest.raises(BookableMoviesSendError) as raised:
        await send_batches(channel, [_batch(RICHMOND, 111), _batch(METROPOLIS, 222)])

    assert raised.value.unsent_theatres == {RICHMOND}
    assert "SilverCity Riverport Cinemas" in str(raised.value)
    assert channel.sent[0]["content"].startswith("<@222>")  # Metropolis still went out
    assert len(channel.sent) == 2


async def test_batch_failing_after_its_mention_went_out_is_not_reported_unsent():
    # Send 1 is Richmond's card, after its mention already pinged subscribers.
    channel = FakeChannel(failing_sends={1})

    with pytest.raises(BookableMoviesSendError) as raised:
        await send_batches(channel, [_batch(RICHMOND, 111), _batch(COQUITLAM, 333)])

    assert raised.value.unsent_theatres == set()
