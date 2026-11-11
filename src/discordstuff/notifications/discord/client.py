import asyncio
import logging

import discord
from discord import app_commands

logger = logging.getLogger(__name__)

COMMAND_FAILED_MESSAGE = "Something went wrong running that command, try again shortly."


class DiscordClient:
    """Thin wrapper around discord.Client and its command tree: owns the ready
    signal so callers can await startup before sending anything, and syncs
    slash commands to the configured guild once connected. Commands are
    registered onto `.tree` separately, by the builder."""

    def __init__(self, guild_id: int):
        intents = discord.Intents.default()
        self.client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.client)
        self.tree.error(self._handle_command_error)
        self.guild = discord.Object(id=guild_id)
        self.ready = asyncio.Event()
        # Assigned explicitly (not via `.event()`) so the required name on
        # discord.Client - `on_ready` - is a literal here, not inferred from
        # this method's own name. `.event()` relies on `coro.__name__`
        # matching a known event name with no validation; a rename of this
        # method alone silently broke that twice.
        self.client.on_ready = self._handle_ready

    async def _handle_ready(self) -> None:
        # A failed sync only leaves slash commands stale - it mustn't stop
        # `ready` being set, or every notification would wait on it forever.
        try:
            synced = await self.tree.sync(guild=self.guild)
            logger.info("Synced %d slash commands to guild %s", len(synced), self.guild.id)
        except discord.DiscordException:
            logger.exception("Failed to sync slash commands to guild %s", self.guild.id)
        logger.info("Discord notifier ready as %s", self.client.user)
        self.ready.set()

    async def _handle_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Catch-all for any slash command that raises, so the user gets a reply
        instead of Discord's generic "The application did not respond"."""
        command = interaction.command.qualified_name if interaction.command else "unknown"
        original = error.original if isinstance(error, app_commands.CommandInvokeError) else error
        logger.error(
            "Slash command /%s failed for user %s", command, interaction.user.id, exc_info=original
        )
        try:
            if interaction.response.is_done():
                await interaction.followup.send(COMMAND_FAILED_MESSAGE, ephemeral=True)
            else:
                await interaction.response.send_message(COMMAND_FAILED_MESSAGE, ephemeral=True)
        except discord.HTTPException:
            logger.exception("Couldn't tell user %s that /%s failed", interaction.user.id, command)

    async def start(self, token: str) -> None:
        await self.client.start(token)

    async def wait_until_ready(self) -> None:
        await self.ready.wait()
