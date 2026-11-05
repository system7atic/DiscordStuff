import logging

import discord

from discordstuff.config import Config
from discordstuff.jobs.cineplex.bookable_movies import MovieBookingInfo, build_batches
from discordstuff.jobs.cineplex.theatres import WatchedTheatre
from discordstuff.notifications.base import Notification
from discordstuff.notifications.discord.builder import build_discord_client
from discordstuff.notifications.discord.messages import build_batch_messages, build_failure_message
from discordstuff.repository.cineplex.bookable_movie_subscribers import (
    BookableMovieSubscriberRepository,
)

logger = logging.getLogger(__name__)


class DiscordNotifier:
    def __init__(self, config: Config, subscribers: BookableMovieSubscriberRepository):
        self._discord = build_discord_client(config, subscribers)
        self._token = config.discord_bot_token
        self._channel_id = config.discord_channel_id
        self._alert_list = config.alert_list
        self._subscribers = subscribers

    async def start(self) -> None:
        await self._discord.start(self._token)

    async def send_bookable_movies(
        self, theatre_movies: dict[WatchedTheatre, list[MovieBookingInfo]]
    ) -> None:
        await self._discord.wait_until_ready()
        client = self._discord.client
        channel = client.get_channel(self._channel_id) or await client.fetch_channel(
            self._channel_id
        )
        if not isinstance(channel, discord.abc.Messageable):
            raise TypeError(
                f"Discord channel {self._channel_id} is a {type(channel).__name__}, which can't "
                "receive messages - configure a text channel ID instead."
            )
        subscribers_by_theatre = await self._subscribers.list_all_grouped_by_theatre()
        for batch in build_batches(theatre_movies, subscribers_by_theatre):
            for message in build_batch_messages(batch):
                await channel.send(**message)

    async def send_error(self, notification: Notification) -> None:
        await self._discord.wait_until_ready()
        message = build_failure_message(notification)
        for user_id in self._alert_list:
            try:
                user = await self._discord.client.fetch_user(user_id)
                await user.send(message)
            except Exception:
                logger.exception("Failed to DM alert recipient %s", user_id)
