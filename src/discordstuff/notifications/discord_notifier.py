import asyncio
import logging

import discord
from discord import app_commands

from discordstuff.config import Config
from discordstuff.jobs.cineplex.theatres import (
    THEATRES_BY_ID,
    THEATRES_BY_KEY,
    WATCHED_THEATRES,
    WatchedTheatre,
)
from discordstuff.notifications.base import Notification
from discordstuff.notifications.bookable_movie_subscribers import (
    BookableMovieSubscriberRepository,
)
from discordstuff.notifications.bookable_movies import (
    BookableMoviesBatch,
    MovieBookingInfo,
    TheatreSection,
    build_batches,
)

logger = logging.getLogger(__name__)

NORMAL_COLOR = discord.Color.blue()

ALL_LOCATIONS_CHOICE_VALUE = "all"

THEATRE_CHOICES = [
    app_commands.Choice(name=theatre.key.title(), value=theatre.key) for theatre in WATCHED_THEATRES
]
UNSUBSCRIBE_CHOICES = [
    *THEATRE_CHOICES,
    app_commands.Choice(name="All locations", value=ALL_LOCATIONS_CHOICE_VALUE),
]

# A placeholder second subscriber so /test-bookable-movies can demonstrate the
# audience-splitting behaviour (a message shared by several subscribers vs. one
# seen only by the invoker) without touching real subscriber data.
TEST_OTHER_SUBSCRIBER_ID = 1


def _build_mention_prefix(subscriber_ids: list[int]) -> str:
    return " ".join(f"<@{user_id}>" for user_id in subscriber_ids)


def _build_failure_message(notification: Notification) -> str:
    return f"{notification.title}: {notification.body}"


# Discord caps a message's Components V2 tree at 40 components total (recursively,
# including the container itself). A movie's Section costs 4: the Section, its
# Thumbnail accessory, and its 2 TextDisplay children.
_MAX_COMPONENTS = 40
_MOVIE_SECTION_COST = 4


def _theatre_heading(theatre: WatchedTheatre) -> str:
    return f"**{theatre.key.title()}: {theatre.name}**"


def _build_movie_section(movie: MovieBookingInfo) -> discord.ui.Section:
    return discord.ui.Section(
        discord.ui.TextDisplay(f"[{movie.title}]({movie.url})"),
        discord.ui.TextDisplay(f"Bookable from {movie.first_bookable_date}"),
        accessory=discord.ui.Thumbnail(media=movie.poster_url),
    )


def _combined_cost(batch: BookableMoviesBatch) -> int:
    cost = 1  # the container itself
    for index, section in enumerate(batch.sections):
        if index > 0:
            cost += 1  # separator
        cost += 1  # theatre heading
        cost += len(section.movies) * _MOVIE_SECTION_COST
    return cost


def _build_combined_layout(batch: BookableMoviesBatch) -> discord.ui.LayoutView:
    container = discord.ui.Container(accent_colour=NORMAL_COLOR)
    for index, section in enumerate(batch.sections):
        if index > 0:
            container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(_theatre_heading(section.theatre)))
        for movie in section.movies:
            container.add_item(_build_movie_section(movie))
    view = discord.ui.LayoutView()
    view.add_item(container)
    return view


def _build_single_theatre_layouts(section: TheatreSection) -> list[discord.ui.LayoutView]:
    """One theatre's movies as their own card(s), never sharing a container with
    another theatre. A theatre with enough movies to exceed Discord's 40-component
    cap on its own spills into additional continuation cards, repeating the theatre
    heading rather than splitting a movie's Section in half."""
    views: list[discord.ui.LayoutView] = []
    heading = _theatre_heading(section.theatre)
    container = discord.ui.Container(accent_colour=NORMAL_COLOR)
    container.add_item(discord.ui.TextDisplay(heading))
    count = 2  # container + heading

    def finish_container() -> None:
        view = discord.ui.LayoutView()
        view.add_item(container)
        views.append(view)

    for movie in section.movies:
        if count + _MOVIE_SECTION_COST > _MAX_COMPONENTS:
            finish_container()
            container = discord.ui.Container(accent_colour=NORMAL_COLOR)
            container.add_item(discord.ui.TextDisplay(f"{heading} (continued)"))
            count = 2  # container + heading
        container.add_item(_build_movie_section(movie))
        count += _MOVIE_SECTION_COST

    finish_container()
    return views


def _build_theatre_layouts(batch: BookableMoviesBatch) -> list[discord.ui.LayoutView]:
    """Components V2 layout: one Container ("big card") holding one Section
    ("inner card") per movie, each with its own poster thumbnail, grouped under a
    theatre heading - instead of several stacked embeds or one image-less card.
    If every theatre's movies together fit in one card, they share it. Otherwise,
    each theatre gets its own card (and continuation cards, if needed) rather than
    splitting a mixed bag of theatres awkwardly across cards."""
    if _combined_cost(batch) <= _MAX_COMPONENTS:
        return [_build_combined_layout(batch)]
    return [view for section in batch.sections for view in _build_single_theatre_layouts(section)]


def _build_message_content(subscriber_ids: list[int]) -> str:
    mention_prefix = _build_mention_prefix(subscriber_ids)
    header = "**New movies now bookable**"
    return f"{mention_prefix} {header}" if mention_prefix else header


def _build_batch_messages(batch: BookableMoviesBatch) -> list[dict]:
    """The mentions and header are sent as their own plain-content message ahead
    of the card(s) - Discord doesn't allow combining `content` with a Components
    V2 `view` in the same message."""
    messages: list[dict] = [{"content": _build_message_content(batch.subscriber_ids)}]
    messages.extend({"view": view} for view in _build_theatre_layouts(batch))
    return messages


class DiscordNotifier:
    def __init__(self, config: Config, subscribers: BookableMovieSubscriberRepository):
        intents = discord.Intents.default()
        self._client = discord.Client(intents=intents)
        self._tree = app_commands.CommandTree(self._client)
        self._token = config.discord_bot_token
        self._channel_id = config.discord_channel_id
        self._guild = discord.Object(id=config.discord_guild_id)
        self._alert_list = config.alert_list
        self._is_dev = config.is_dev
        self._subscribers = subscribers
        self._ready = asyncio.Event()
        self._client.event(self.on_ready)
        self._register_commands()

    def _register_commands(self) -> None:
        @self._tree.command(
            name="subscribe-bookable-movies",
            description="Get @mentioned when a new movie becomes bookable at a theatre",
            guild=self._guild,
        )
        @app_commands.choices(theatre=THEATRE_CHOICES)
        async def subscribe(interaction: discord.Interaction, theatre: app_commands.Choice[str]) -> None:
            watched = THEATRES_BY_KEY[theatre.value]
            await self._subscribers.add(interaction.user.id, watched.theatre_id)
            await interaction.response.send_message(
                f"You're subscribed to bookable-movie alerts for {watched.name}.", ephemeral=True
            )

        @self._tree.command(
            name="unsubscribe-bookable-movies",
            description="Stop getting @mentioned about newly bookable movies",
            guild=self._guild,
        )
        @app_commands.choices(theatre=UNSUBSCRIBE_CHOICES)
        async def unsubscribe(interaction: discord.Interaction, theatre: app_commands.Choice[str]) -> None:
            if theatre.value == ALL_LOCATIONS_CHOICE_VALUE:
                await self._subscribers.remove_all(interaction.user.id)
                await interaction.response.send_message(
                    "You're unsubscribed from bookable-movie alerts for all locations.", ephemeral=True
                )
                return
            watched = THEATRES_BY_KEY[theatre.value]
            await self._subscribers.remove(interaction.user.id, watched.theatre_id)
            await interaction.response.send_message(
                f"You're unsubscribed from bookable-movie alerts for {watched.name}.", ephemeral=True
            )

        @self._tree.command(
            name="my-bookable-movie-subscriptions",
            description="List which theatres you're subscribed to for bookable-movie alerts",
            guild=self._guild,
        )
        async def my_subscriptions(interaction: discord.Interaction) -> None:
            theatre_ids = await self._subscribers.list_theatre_ids_for_user(interaction.user.id)
            if not theatre_ids:
                await interaction.response.send_message(
                    "You're not subscribed to any theatres.", ephemeral=True
                )
                return
            names = [THEATRES_BY_ID[theatre_id].name for theatre_id in theatre_ids if theatre_id in THEATRES_BY_ID]
            lines = "\n".join(f"- {name}" for name in names)
            await interaction.response.send_message(
                f"You're subscribed to:\n{lines}", ephemeral=True
            )

        if self._is_dev:
            self._register_test_command()

    def _register_test_command(self) -> None:
        @self._tree.command(
            name="test-bookable-movies",
            description="Preview the bookable-movie alert layout with fabricated sample data",
            guild=self._guild,
        )
        async def test_bookable_movies(interaction: discord.Interaction) -> None:
            batches = build_batches(_SAMPLE_THEATRE_MOVIES, _sample_subscribers_by_theatre(interaction.user.id))
            messages = [message for batch in batches for message in _build_batch_messages(batch)]
            await interaction.response.send_message(**messages[0], ephemeral=True)
            for message in messages[1:]:
                await interaction.followup.send(**message, ephemeral=True)

    async def on_ready(self) -> None:
        await self._tree.sync(guild=self._guild)
        logger.info("Discord notifier ready as %s", self._client.user)
        self._ready.set()

    async def start(self) -> None:
        await self._client.start(self._token)

    async def send_bookable_movies(self, theatre_movies: dict[WatchedTheatre, list[MovieBookingInfo]]) -> None:
        await self._ready.wait()
        channel = self._client.get_channel(self._channel_id) or await self._client.fetch_channel(
            self._channel_id
        )
        if not isinstance(channel, discord.abc.Messageable):
            raise TypeError(
                f"Discord channel {self._channel_id} is a {type(channel).__name__}, which can't "
                "receive messages - configure a text channel ID instead."
            )
        subscribers_by_theatre = await self._subscribers.list_all_grouped_by_theatre()
        for batch in build_batches(theatre_movies, subscribers_by_theatre):
            for message in _build_batch_messages(batch):
                await channel.send(**message)

    async def send_error(self, notification: Notification) -> None:
        await self._ready.wait()
        message = _build_failure_message(notification)
        for user_id in self._alert_list:
            try:
                user = await self._client.fetch_user(user_id)
                await user.send(message)
            except Exception:
                logger.exception("Failed to DM alert recipient %s", user_id)


_SAMPLE_POSTER_URL = "https://mediafiles.cineplex.com/Central/Film/Posters/62206_320_470.jpg"

_SAMPLE_THEATRE_MOVIES: dict[WatchedTheatre, list[MovieBookingInfo]] = {
    THEATRES_BY_KEY["richmond"]: [
        MovieBookingInfo(
            title="Avengers: Doomsday",
            first_bookable_date="Dec 17, 2026",
            url="https://www.cineplex.com/movie/avengers-doomsday",
            poster_url=_SAMPLE_POSTER_URL,
        ),
        MovieBookingInfo(
            title="Zootopia 2",
            first_bookable_date="Dec 18, 2026",
            url="https://www.cineplex.com/movie/zootopia-2",
            poster_url=_SAMPLE_POSTER_URL,
        ),
        MovieBookingInfo(
            title="Toy Story 5",
            first_bookable_date="Dec 19, 2026",
            url="https://www.cineplex.com/movie/toy-story-5",
            poster_url=_SAMPLE_POSTER_URL,
        ),
    ],
    THEATRES_BY_KEY["metropolis"]: [
        MovieBookingInfo(
            title="Wicked: For Good",
            first_bookable_date="Dec 20, 2026",
            url="https://www.cineplex.com/movie/wicked-for-good",
            poster_url=_SAMPLE_POSTER_URL,
        ),
        MovieBookingInfo(
            title="Dune: Part Three",
            first_bookable_date="Dec 21, 2026",
            url="https://www.cineplex.com/movie/dune-part-three",
            poster_url=_SAMPLE_POSTER_URL,
        ),
        MovieBookingInfo(
            title="The Hunger Games: Sunrise on the Reaping",
            first_bookable_date="Dec 22, 2026",
            url="https://www.cineplex.com/movie/hunger-games-sunrise-on-the-reaping",
            poster_url=_SAMPLE_POSTER_URL,
        ),
        MovieBookingInfo(
            title="Moana 3",
            first_bookable_date="Dec 23, 2026",
            url="https://www.cineplex.com/movie/moana-3",
            poster_url=_SAMPLE_POSTER_URL,
        ),
        MovieBookingInfo(
            title="Shrek 5",
            first_bookable_date="Dec 24, 2026",
            url="https://www.cineplex.com/movie/shrek-5",
            poster_url=_SAMPLE_POSTER_URL,
        ),
    ],
    THEATRES_BY_KEY["coquitlam"]: [
        MovieBookingInfo(
            title="Spider-Man: Brand New Day",
            first_bookable_date="Dec 25, 2026",
            url="https://www.cineplex.com/movie/spider-man-brand-new-day",
            poster_url=_SAMPLE_POSTER_URL,
        ),
        MovieBookingInfo(
            title="Now You See Me: Now You Don't",
            first_bookable_date="Dec 26, 2026",
            url="https://www.cineplex.com/movie/now-you-see-me-now-you-dont",
            poster_url=_SAMPLE_POSTER_URL,
        ),
        MovieBookingInfo(
            title="The Batman Part II",
            first_bookable_date="Dec 27, 2026",
            url="https://www.cineplex.com/movie/the-batman-part-ii",
            poster_url=_SAMPLE_POSTER_URL,
        ),
    ],
}


def _sample_subscribers_by_theatre(invoker_id: int) -> dict[int, list[int]]:
    richmond_id = THEATRES_BY_KEY["richmond"].theatre_id
    metropolis_id = THEATRES_BY_KEY["metropolis"].theatre_id
    coquitlam_id = THEATRES_BY_KEY["coquitlam"].theatre_id
    return {
        richmond_id: [invoker_id, TEST_OTHER_SUBSCRIBER_ID],
        metropolis_id: [invoker_id],
        coquitlam_id: [invoker_id],
    }
