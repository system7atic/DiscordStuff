import asyncio
import logging

import discord
from discord import app_commands

logger = logging.getLogger(__name__)


class DiscordClient:
    """Thin wrapper around discord.Client and its command tree: owns the ready
    signal so callers can await startup before sending anything, and syncs
    slash commands to the configured guild once connected. Commands are
    registered onto `.tree` separately, by the builder."""

    def __init__(self, guild_id: int):
        intents = discord.Intents.default()
        self.client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.client)
        self.guild = discord.Object(id=guild_id)
        self.ready = asyncio.Event()
        # Assigned explicitly (not via `.event()`) so the required name on
        # discord.Client - `on_ready` - is a literal here, not inferred from
        # this method's own name. `.event()` relies on `coro.__name__`
        # matching a known event name with no validation; a rename of this
        # method alone silently broke that twice.
        self.client.on_ready = self._handle_ready

    async def _handle_ready(self) -> None:
        await self.tree.sync(guild=self.guild)
        logger.info("Discord notifier ready as %s", self.client.user)
        self.ready.set()

    async def start(self, token: str) -> None:
        await self.client.start(token)

    async def wait_until_ready(self) -> None:
        await self.ready.wait()
