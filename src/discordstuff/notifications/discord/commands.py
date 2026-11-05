import discord
from discord import app_commands

from discordstuff.jobs.cineplex.bookable_movies import build_batches
from discordstuff.jobs.cineplex.theatres import THEATRES_BY_ID, THEATRES_BY_KEY, WATCHED_THEATRES
from discordstuff.notifications.discord.constants import (
    SAMPLE_THEATRE_MOVIES,
    sample_subscribers_by_theatre,
)
from discordstuff.notifications.discord.messages import build_batch_messages
from discordstuff.repository.cineplex.bookable_movie_subscribers import (
    BookableMovieSubscriberRepository,
)

ALL_LOCATIONS_CHOICE_VALUE = "all"

THEATRE_CHOICES = [
    app_commands.Choice(name=theatre.key.title(), value=theatre.key) for theatre in WATCHED_THEATRES
]
UNSUBSCRIBE_CHOICES = [
    *THEATRE_CHOICES,
    app_commands.Choice(name="All locations", value=ALL_LOCATIONS_CHOICE_VALUE),
]


def register_commands(
    tree: app_commands.CommandTree,
    guild: discord.Object,
    subscribers: BookableMovieSubscriberRepository,
) -> None:
    @tree.command(
        name="subscribe-bookable-movies",
        description="Get @mentioned when a new movie becomes bookable at a theatre",
        guild=guild,
    )
    @app_commands.choices(theatre=THEATRE_CHOICES)
    async def subscribe(
        interaction: discord.Interaction, theatre: app_commands.Choice[str]
    ) -> None:
        watched = THEATRES_BY_KEY[theatre.value]
        await subscribers.add(interaction.user.id, watched.theatre_id)
        await interaction.response.send_message(
            f"You're subscribed to bookable-movie alerts for {watched.name}.", ephemeral=True
        )

    @tree.command(
        name="unsubscribe-bookable-movies",
        description="Stop getting @mentioned about newly bookable movies",
        guild=guild,
    )
    @app_commands.choices(theatre=UNSUBSCRIBE_CHOICES)
    async def unsubscribe(
        interaction: discord.Interaction, theatre: app_commands.Choice[str]
    ) -> None:
        if theatre.value == ALL_LOCATIONS_CHOICE_VALUE:
            await subscribers.remove_all(interaction.user.id)
            await interaction.response.send_message(
                "You're unsubscribed from bookable-movie alerts for all locations.", ephemeral=True
            )
            return
        watched = THEATRES_BY_KEY[theatre.value]
        await subscribers.remove(interaction.user.id, watched.theatre_id)
        await interaction.response.send_message(
            f"You're unsubscribed from bookable-movie alerts for {watched.name}.", ephemeral=True
        )

    @tree.command(
        name="my-bookable-movie-subscriptions",
        description="List which theatres you're subscribed to for bookable-movie alerts",
        guild=guild,
    )
    async def my_subscriptions(interaction: discord.Interaction) -> None:
        theatre_ids = await subscribers.list_theatre_ids_for_user(interaction.user.id)
        if not theatre_ids:
            await interaction.response.send_message(
                "You're not subscribed to any theatres.", ephemeral=True
            )
            return
        names = [
            THEATRES_BY_ID[theatre_id].name
            for theatre_id in theatre_ids
            if theatre_id in THEATRES_BY_ID
        ]
        lines = "\n".join(f"- {name}" for name in names)
        await interaction.response.send_message(f"You're subscribed to:\n{lines}", ephemeral=True)


def register_test_command(tree: app_commands.CommandTree, guild: discord.Object) -> None:
    @tree.command(
        name="test-bookable-movies",
        description="Preview the bookable-movie alert layout with fabricated sample data",
        guild=guild,
    )
    async def test_bookable_movies(interaction: discord.Interaction) -> None:
        batches = build_batches(
            SAMPLE_THEATRE_MOVIES, sample_subscribers_by_theatre(interaction.user.id)
        )
        messages = [message for batch in batches for message in build_batch_messages(batch)]
        await interaction.response.send_message(**messages[0], ephemeral=True)
        for message in messages[1:]:
            await interaction.followup.send(**message, ephemeral=True)
