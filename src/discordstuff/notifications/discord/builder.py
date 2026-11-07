from discordstuff.config import Config
from discordstuff.jobs.cineplex.client import CineplexClient
from discordstuff.notifications.discord.client import DiscordClient
from discordstuff.notifications.discord.commands import (
    register_commands,
    register_get_bookable_movies_command,
    register_test_command,
)
from discordstuff.repository.cineplex.bookable_movie_subscribers import (
    BookableMovieSubscriberRepository,
)


def build_discord_client(
    config: Config,
    subscribers: BookableMovieSubscriberRepository,
    cineplex_client: CineplexClient,
) -> DiscordClient:
    discord_client = DiscordClient(guild_id=config.discord_guild_id)
    register_commands(discord_client.tree, discord_client.guild, subscribers)
    if "cineplex" in config.enabled_jobs:
        register_get_bookable_movies_command(
            discord_client.tree, discord_client.guild, cineplex_client
        )
    if config.is_dev:
        register_test_command(discord_client.tree, discord_client.guild)
    return discord_client
