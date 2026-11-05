from discordstuff.config import Config
from discordstuff.notifications.discord.client import DiscordClient
from discordstuff.notifications.discord.commands import register_commands, register_test_command
from discordstuff.repository.cineplex.bookable_movie_subscribers import (
    BookableMovieSubscriberRepository,
)


def build_discord_client(
    config: Config, subscribers: BookableMovieSubscriberRepository
) -> DiscordClient:
    discord_client = DiscordClient(guild_id=config.discord_guild_id)
    register_commands(discord_client.tree, discord_client.guild, subscribers)
    if config.is_dev:
        register_test_command(discord_client.tree, discord_client.guild)
    return discord_client
