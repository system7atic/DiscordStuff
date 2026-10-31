import asyncio
import logging

import discord

from discordstuff.config import Config

logger = logging.getLogger(__name__)


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

    async def send(self, message: str) -> None:
        await self._send_to_channel(self._channel_id, message)

    async def send_error(self, message: str) -> None:
        await self._send_to_channel(self._error_channel_id, f":warning: {message}")

    async def _send_to_channel(self, channel_id: int, message: str) -> None:
        await self._ready.wait()
        channel = self._client.get_channel(channel_id) or await self._client.fetch_channel(channel_id)
        await channel.send(message)
