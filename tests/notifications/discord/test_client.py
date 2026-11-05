import asyncio
from unittest.mock import AsyncMock

from discordstuff.notifications.discord.client import DiscordClient


async def test_ready_dispatch_syncs_commands_and_sets_ready():
    discord_client = DiscordClient(guild_id=123)
    discord_client.tree.sync = AsyncMock(return_value=[])
    # dispatch() schedules the handler via `self.loop.create_task(...)`; outside
    # a real `.start()`/`.connect()` call, `Client.loop` is still the
    # `_LoopSentinel` placeholder, so point it at this test's running loop.
    discord_client.client.loop = asyncio.get_running_loop()

    discord_client.client.dispatch("ready")
    await asyncio.sleep(0)  # let the scheduled task run

    assert discord_client.ready.is_set()
    discord_client.tree.sync.assert_awaited_once_with(guild=discord_client.guild)
