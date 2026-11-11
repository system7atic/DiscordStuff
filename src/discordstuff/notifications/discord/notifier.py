import logging

import discord

from discordstuff.config import Config
from discordstuff.errors import describe_exception
from discordstuff.jobs.cineplex.bookable_movies import (
    BookableMoviesBatch,
    MovieBookingInfo,
    build_batches,
)
from discordstuff.jobs.cineplex.client import CineplexClient
from discordstuff.jobs.cineplex.theatres import WatchedTheatre
from discordstuff.notifications.base import BookableMoviesSendError, Notification
from discordstuff.notifications.discord.builder import build_discord_client
from discordstuff.notifications.discord.messages import build_batch_messages, build_failure_message
from discordstuff.repository.cineplex.bookable_movie_subscribers import (
    BookableMovieSubscriberRepository,
)

logger = logging.getLogger(__name__)


async def send_batches(channel: discord.abc.Messageable, batches: list[BookableMoviesBatch]) -> None:
    """Sends every batch, carrying on past one that fails so it can't hold up the
    others, then raises BookableMoviesSendError naming the theatres in batches
    that failed before any of their messages went out."""
    unsent: set[WatchedTheatre] = set()
    failures: list[str] = []
    for batch in batches:
        names = ", ".join(section.theatre.name for section in batch.sections)
        sent_any = False
        try:
            for message in build_batch_messages(batch):
                await channel.send(**message)
                sent_any = True
        except Exception as exc:
            failures.append(f"{names}: {describe_exception(exc)}")
            if sent_any:
                logger.exception(
                    "Failed partway through announcing new movies at %s - not retrying, "
                    "since subscribers were already pinged",
                    names,
                )
            else:
                logger.exception("Failed to announce new movies at %s, will retry next run", names)
                unsent.update(section.theatre for section in batch.sections)
            continue
        logger.info(
            "Announced %d new movies at %s to %d subscribers",
            sum(len(section.movies) for section in batch.sections),
            names,
            len(batch.subscriber_ids),
        )
    if failures:
        raise BookableMoviesSendError(unsent, "; ".join(failures))


class DiscordNotifier:
    def __init__(
        self,
        config: Config,
        subscribers: BookableMovieSubscriberRepository,
        cineplex_client: CineplexClient,
    ):
        self._discord = build_discord_client(config, subscribers, cineplex_client)
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
        batches = build_batches(theatre_movies, subscribers_by_theatre)
        batched = {section.theatre for batch in batches for section in batch.sections}
        unsubscribed = [theatre.name for theatre in theatre_movies if theatre not in batched]
        if unsubscribed:
            logger.info("No subscribers at %s, not announcing their new movies", ", ".join(unsubscribed))
        await send_batches(channel, batches)

    async def send_error(self, notification: Notification) -> None:
        if not self._alert_list:
            logger.warning("ALERT_LIST is empty, so nobody was DMed about: %s", notification.title)
            return
        await self._discord.wait_until_ready()
        message = build_failure_message(notification)
        for user_id in self._alert_list:
            try:
                user = await self._discord.client.fetch_user(user_id)
                await user.send(message)
            except Exception:
                logger.exception("Failed to DM alert recipient %s", user_id)
