import asyncio
import logging

import discord
from discord import app_commands

from discordstuff.config import Config
from discordstuff.notifications.base import Notification
from discordstuff.notifications.bookable_movie_subscribers import (
    BookableMovieSubscriberRepository,
)

logger = logging.getLogger(__name__)

NORMAL_COLOR = discord.Color.blue()

TEST_NOTIFICATION = Notification(
    title="Test Movie is now bookable at your theatre",
    body="First bookable date: 2026-11-01",
    url="https://www.cineplex.com/movie/test-movie",
)


def _build_mention_prefix(subscriber_ids: list[int]) -> str:
    return " ".join(f"<@{user_id}>" for user_id in subscriber_ids)


def _build_failure_message(notification: Notification) -> str:
    return f"{notification.title}: {notification.body}"


class DiscordNotifier:
    def __init__(self, config: Config, subscribers: BookableMovieSubscriberRepository):
        intents = discord.Intents.default()
        self._client = discord.Client(intents=intents)
        self._tree = app_commands.CommandTree(self._client)
        self._token = config.discord_bot_token
        self._channel_id = config.discord_channel_id
        self._guild = discord.Object(id=config.discord_guild_id)
        self._alert_list = config.alert_list
        self._subscribers = subscribers
        self._ready = asyncio.Event()
        self._client.event(self.on_ready)
        self._register_commands()

    def _register_commands(self) -> None:
        @self._tree.command(
            name="subscribe-bookable-movies",
            description="Get @mentioned when a new movie becomes bookable at the theatre",
            guild=self._guild,
        )
        async def subscribe(interaction: discord.Interaction) -> None:
            await self._subscribers.add(interaction.user.id)
            await interaction.response.send_message(
                "You're subscribed to bookable-movie alerts.", ephemeral=True
            )

        @self._tree.command(
            name="unsubscribe-bookable-movies",
            description="Stop getting @mentioned about newly bookable movies",
            guild=self._guild,
        )
        async def unsubscribe(interaction: discord.Interaction) -> None:
            await self._subscribers.remove(interaction.user.id)
            await interaction.response.send_message(
                "You're unsubscribed from bookable-movie alerts.", ephemeral=True
            )

        @self._tree.command(
            name="test-bookable-movies",
            description="Send a demo bookable-movie notification, pinging all current subscribers",
            guild=self._guild,
        )
        async def test_bookable_movies(interaction: discord.Interaction) -> None:
            await self.send(TEST_NOTIFICATION)
            await interaction.response.send_message("Sent a test notification.", ephemeral=True)

    async def on_ready(self) -> None:
        await self._tree.sync(guild=self._guild)
        logger.info("Discord notifier ready as %s", self._client.user)
        self._ready.set()

    async def start(self) -> None:
        await self._client.start(self._token)

    async def send(self, notification: Notification) -> None:
        await self._ready.wait()
        channel = self._client.get_channel(self._channel_id) or await self._client.fetch_channel(
            self._channel_id
        )
        if not isinstance(channel, discord.abc.Messageable):
            raise TypeError(
                f"Discord channel {self._channel_id} is a {type(channel).__name__}, which can't "
                "receive messages - configure a text channel ID instead."
            )
        subscriber_ids = await self._subscribers.list_all()
        embed = discord.Embed(
            title=notification.title,
            description=notification.body,
            url=notification.url,
            color=NORMAL_COLOR,
        )
        await channel.send(content=_build_mention_prefix(subscriber_ids) or None, embed=embed)

    async def send_error(self, notification: Notification) -> None:
        await self._ready.wait()
        message = _build_failure_message(notification)
        for user_id in self._alert_list:
            try:
                user = await self._client.fetch_user(user_id)
                await user.send(message)
            except Exception:
                logger.exception("Failed to DM alert recipient %s", user_id)
