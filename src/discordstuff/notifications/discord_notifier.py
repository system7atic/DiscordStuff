import asyncio
import logging

import discord

from discordstuff.config import Config
from discordstuff.notifications.base import Notification

logger = logging.getLogger(__name__)

NORMAL_COLOR = discord.Color.blue()
ERROR_COLOR = discord.Color.red()


class DiscordNotifier:
    def __init__(self, config: Config):
        intents = discord.Intents.default()
        self._client = discord.Client(intents=intents)
        self._token = config.discord_bot_token
        self._channel_id = config.discord_channel_id
        self._error_channel_id = config.discord_error_channel_id
        self._ready = asyncio.Event()
        self._client.event(self._on_ready)

    async def _on_ready(self) -> None:
        logger.info("Discord notifier ready as %s", self._client.user)
        self._ready.set()

    async def start(self) -> None:
        await self._client.start(self._token)

    async def send(self, notification: Notification) -> None:
        await self._send_to_channel(self._channel_id, notification, NORMAL_COLOR)

    async def send_error(self, notification: Notification) -> None:
        await self._send_to_channel(self._error_channel_id, notification, ERROR_COLOR)

    async def _send_to_channel(
        self, channel_id: int, notification: Notification, color: discord.Color
    ) -> None:
        await self._ready.wait()
        channel = self._client.get_channel(channel_id) or await self._client.fetch_channel(channel_id)
        embed = discord.Embed(
            title=notification.title,
            description=notification.body,
            url=notification.url,
            color=color,
        )
        await channel.send(embed=embed)
