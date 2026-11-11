import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
from discord import app_commands

from discordstuff.notifications.discord.client import COMMAND_FAILED_MESSAGE, DiscordClient


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


async def test_ready_is_still_set_when_command_sync_fails():
    discord_client = DiscordClient(guild_id=123)
    discord_client.tree.sync = AsyncMock(side_effect=discord.HTTPException(Mock(status=500), "boom"))
    discord_client.client.loop = asyncio.get_running_loop()

    discord_client.client.dispatch("ready")
    await asyncio.sleep(0)

    assert discord_client.ready.is_set()


def _fake_interaction(response_done: bool) -> SimpleNamespace:
    return SimpleNamespace(
        command=SimpleNamespace(qualified_name="subscribe-bookable-movies"),
        user=SimpleNamespace(id=111),
        response=SimpleNamespace(is_done=lambda: response_done, send_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )


async def test_command_error_replies_to_the_user_when_nothing_was_sent_yet():
    discord_client = DiscordClient(guild_id=123)
    interaction = _fake_interaction(response_done=False)
    error = app_commands.CommandInvokeError(Mock(), RuntimeError("database down"))

    await discord_client.tree.on_error(interaction, error)

    interaction.response.send_message.assert_awaited_once_with(
        COMMAND_FAILED_MESSAGE, ephemeral=True
    )


async def test_command_error_follows_up_when_the_command_already_responded():
    discord_client = DiscordClient(guild_id=123)
    interaction = _fake_interaction(response_done=True)
    error = app_commands.CommandInvokeError(Mock(), RuntimeError("database down"))

    await discord_client.tree.on_error(interaction, error)

    interaction.followup.send.assert_awaited_once_with(COMMAND_FAILED_MESSAGE, ephemeral=True)
