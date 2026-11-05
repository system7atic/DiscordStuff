import discord

from discordstuff.jobs.cineplex.bookable_movies import (
    BookableMoviesBatch,
    MovieBookingInfo,
    TheatreSection,
)
from discordstuff.jobs.cineplex.theatres import WatchedTheatre
from discordstuff.notifications.base import Notification

NORMAL_COLOR = discord.Color.blue()

# Discord caps a message's Components V2 tree at 40 components total (recursively,
# including the container itself). A movie's Section costs 4: the Section, its
# Thumbnail accessory, and its 2 TextDisplay children.
_MAX_COMPONENTS = 40
_MOVIE_SECTION_COST = 4


def build_mention_prefix(subscriber_ids: list[int]) -> str:
    return " ".join(f"<@{user_id}>" for user_id in subscriber_ids)


def build_failure_message(notification: Notification) -> str:
    return f"{notification.title}: {notification.body}"


def theatre_heading(theatre: WatchedTheatre) -> str:
    return f"**{theatre.key.title()}: {theatre.name}**"


def build_movie_section(movie: MovieBookingInfo) -> discord.ui.Section:
    return discord.ui.Section(
        discord.ui.TextDisplay(f"[{movie.title}]({movie.url})"),
        discord.ui.TextDisplay(f"Bookable from {movie.first_bookable_date}"),
        accessory=discord.ui.Thumbnail(media=movie.poster_url),
    )


def combined_cost(batch: BookableMoviesBatch) -> int:
    cost = 1  # the container itself
    for index, section in enumerate(batch.sections):
        if index > 0:
            cost += 1  # separator
        cost += 1  # theatre heading
        cost += len(section.movies) * _MOVIE_SECTION_COST
    return cost


def build_combined_layout(batch: BookableMoviesBatch) -> discord.ui.LayoutView:
    container = discord.ui.Container(accent_colour=NORMAL_COLOR)
    for index, section in enumerate(batch.sections):
        if index > 0:
            container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(theatre_heading(section.theatre)))
        for movie in section.movies:
            container.add_item(build_movie_section(movie))
    view = discord.ui.LayoutView()
    view.add_item(container)
    return view


def build_single_theatre_layouts(section: TheatreSection) -> list[discord.ui.LayoutView]:
    """One theatre's movies as their own card(s), never sharing a container with
    another theatre. A theatre with enough movies to exceed Discord's 40-component
    cap on its own spills into additional continuation cards, repeating the theatre
    heading rather than splitting a movie's Section in half."""
    views: list[discord.ui.LayoutView] = []
    heading = theatre_heading(section.theatre)
    container = discord.ui.Container(accent_colour=NORMAL_COLOR)
    container.add_item(discord.ui.TextDisplay(heading))
    count = 2  # container + heading

    def finish_container() -> None:
        view = discord.ui.LayoutView()
        view.add_item(container)
        views.append(view)

    for movie in section.movies:
        if count + _MOVIE_SECTION_COST > _MAX_COMPONENTS:
            finish_container()
            container = discord.ui.Container(accent_colour=NORMAL_COLOR)
            container.add_item(discord.ui.TextDisplay(f"{heading} (continued)"))
            count = 2  # container + heading
        container.add_item(build_movie_section(movie))
        count += _MOVIE_SECTION_COST

    finish_container()
    return views


def build_theatre_layouts(batch: BookableMoviesBatch) -> list[discord.ui.LayoutView]:
    """Components V2 layout: one Container ("big card") holding one Section
    ("inner card") per movie, each with its own poster thumbnail, grouped under a
    theatre heading - instead of several stacked embeds or one image-less card.
    If every theatre's movies together fit in one card, they share it. Otherwise,
    each theatre gets its own card (and continuation cards, if needed) rather than
    splitting a mixed bag of theatres awkwardly across cards."""
    if combined_cost(batch) <= _MAX_COMPONENTS:
        return [build_combined_layout(batch)]
    return [view for section in batch.sections for view in build_single_theatre_layouts(section)]


def build_message_content(subscriber_ids: list[int]) -> str:
    mention_prefix = build_mention_prefix(subscriber_ids)
    header = "**New movies now bookable**"
    return f"{mention_prefix} {header}" if mention_prefix else header


def build_batch_messages(batch: BookableMoviesBatch) -> list[dict]:
    """The mentions and header are sent as their own plain-content message ahead
    of the card(s) - Discord doesn't allow combining `content` with a Components
    V2 `view` in the same message."""
    messages: list[dict] = [{"content": build_message_content(batch.subscriber_ids)}]
    messages.extend({"view": view} for view in build_theatre_layouts(batch))
    return messages
