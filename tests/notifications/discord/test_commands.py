from dataclasses import replace
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from discord import app_commands

from discordstuff.config import Config
from discordstuff.jobs.cineplex.models import BookableMovie
from discordstuff.notifications.discord import commands
from discordstuff.notifications.discord.builder import build_discord_client

RICHMOND_ID = 1409
RICHMOND_CHOICE = app_commands.Choice(name="Richmond", value="richmond")

CONFIG = Config(
    discord_bot_token="token",
    discord_channel_id=1,
    discord_guild_id=2,
    database_url="postgres://unused",
    enabled_jobs=frozenset({"cineplex"}),
    job_interval_seconds=3600,
    alert_list=frozenset(),
    is_dev=False,
)

ZOOTOPIA = BookableMovie(
    film_id=1,
    title="Zootopia 2",
    slug="zootopia-2",
    is_event=False,
    is_international=False,
    poster_url="https://example.com/zootopia-2.jpg",
)


class FakeCineplexClient:
    def __init__(self, movies=(ZOOTOPIA,), dates=(date(2026, 11, 14),), fail_on_dates=False):
        self._movies = list(movies)
        self._dates = list(dates)
        self._fail_on_dates = fail_on_dates

    async def get_bookable_movies(self):
        return self._movies

    async def get_theatres_for_film(self, film_id):
        return [SimpleNamespace(theatre_id=RICHMOND_ID)]

    async def get_bookable_dates(self, film_id, theatre_id=None):
        if self._fail_on_dates:
            raise RuntimeError("Cineplex is down")
        return self._dates


def _fake_interaction() -> SimpleNamespace:
    return SimpleNamespace(
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )


def _command(config: Config, cineplex_client):
    discord_client = build_discord_client(config, AsyncMock(), cineplex_client)
    return discord_client.tree.get_command("get-bookable-movies", guild=discord_client.guild)


async def _invoke(cineplex_client) -> SimpleNamespace:
    interaction = _fake_interaction()
    await _command(CONFIG, cineplex_client).callback(interaction, RICHMOND_CHOICE)
    return interaction


async def test_command_exists_when_the_cineplex_job_is_enabled():
    assert _command(CONFIG, FakeCineplexClient()) is not None


async def test_command_does_not_exist_when_the_cineplex_job_is_disabled():
    config = replace(CONFIG, enabled_jobs=frozenset())

    assert _command(config, FakeCineplexClient()) is None


async def test_defers_publicly_then_posts_the_theatres_list():
    interaction = await _invoke(FakeCineplexClient())

    interaction.response.defer.assert_awaited_once_with()
    interaction.followup.send.assert_awaited_once()
    [embed] = interaction.followup.send.await_args.kwargs["embeds"]
    assert embed.title == "Richmond: SilverCity Riverport Cinemas"
    assert "[Zootopia 2](https://www.cineplex.com/movie/zootopia-2) · Nov 14, 2026" in (
        embed.description
    )


async def test_today_means_today_in_vancouver_not_utc(monkeypatch):
    class EveningInVancouver(datetime):
        @classmethod
        def now(cls, tz=None):
            # 8:34pm on Nov 6 in Vancouver, already Nov 7 in UTC.
            return datetime(2026, 11, 7, 4, 34, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(commands, "datetime", EveningInVancouver)

    interaction = await _invoke(FakeCineplexClient(dates=(date(2026, 11, 6),)))

    [embed] = interaction.followup.send.await_args.kwargs["embeds"]
    assert embed.description.endswith("· Today")


async def test_theatre_with_no_movies_gets_the_empty_message():
    interaction = await _invoke(FakeCineplexClient(movies=[]))

    interaction.followup.send.assert_awaited_once_with(
        content="No bookable movies at SilverCity Riverport Cinemas right now."
    )


async def test_cineplex_failure_posts_one_short_message_and_no_partial_list():
    interaction = await _invoke(FakeCineplexClient(fail_on_dates=True))

    interaction.followup.send.assert_awaited_once_with(
        content="Couldn't reach Cineplex, try again shortly."
    )
