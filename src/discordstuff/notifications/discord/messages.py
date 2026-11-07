from datetime import date

import discord

from discordstuff.jobs.cineplex.bookable_movies import (
    BookableListing,
    BookableMoviesBatch,
    MovieBookingInfo,
    TheatreSection,
    format_date,
)
from discordstuff.jobs.cineplex.theatres import WatchedTheatre
from discordstuff.notifications.base import Notification

NORMAL_COLOR = discord.Color.blue()

# Discord caps a message's Components V2 tree at 40 components total (recursively,
# including the container itself). A movie's Section costs 4: the Section, its
# Thumbnail accessory, and its 2 TextDisplay children.
_MAX_COMPONENTS = 40
_MOVIE_SECTION_COST = 4

# Discord's classic embed limits, which the /get-bookable-movies list has to fit.
_MAX_EMBED_DESCRIPTION = 4096
_MAX_MESSAGE_EMBED_CHARS = 6000
_LIST_INTRO = "Bookable movies and their first bookable date"


def build_mention_prefix(subscriber_ids: list[int]) -> str:
    return " ".join(f"<@{user_id}>" for user_id in subscriber_ids)


def build_failure_message(notification: Notification) -> str:
    return f"{notification.title}: {notification.body}"


def theatre_title(theatre: WatchedTheatre) -> str:
    return f"{theatre.key.title()}: {theatre.name}"


def theatre_heading(theatre: WatchedTheatre) -> str:
    return f"**{theatre_title(theatre)}**"


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


def _listing_row(listing: BookableListing, today: date) -> str:
    if listing.first_bookable_date is None:
        when = "unknown"
    elif listing.first_bookable_date == today:
        when = "Today"
    else:
        when = format_date(listing.first_bookable_date)
    return f"- [{listing.title}]({listing.url}) · {when}"


def _list_embed(theatre: WatchedTheatre, rows: list[str], continued: bool) -> discord.Embed:
    title = theatre_title(theatre)
    title, lines = (f"{title} (continued)", rows) if continued else (title, [_LIST_INTRO, *rows])
    return discord.Embed(title=title, description="\n".join(lines), color=NORMAL_COLOR)


def build_bookable_list_messages(
    theatre: WatchedTheatre, listings: list[BookableListing], today: date
) -> list[dict]:
    """One theatre's list as a single embed where it fits. Longer lists continue in
    another embed in the same message, then in further messages once a message
    reaches Discord's total embed limit, always splitting between movies."""
    if not listings:
        return [{"content": f"No bookable movies at {theatre.name} right now."}]

    messages: list[list[discord.Embed]] = [[]]
    rows: list[str] = []
    continued = False

    def current_message_chars() -> int:
        return sum(len(embed) for embed in messages[-1])

    for listing in listings:
        row = _listing_row(listing, today)
        candidate = _list_embed(theatre, [*rows, row], continued)
        fits_embed = len(candidate.description or "") <= _MAX_EMBED_DESCRIPTION
        if fits_embed and current_message_chars() + len(candidate) <= _MAX_MESSAGE_EMBED_CHARS:
            rows.append(row)
            continue
        messages[-1].append(_list_embed(theatre, rows, continued))
        rows = [row]
        continued = True
        next_embed = _list_embed(theatre, rows, continued)
        if current_message_chars() + len(next_embed) > _MAX_MESSAGE_EMBED_CHARS:
            messages.append([])

    messages[-1].append(_list_embed(theatre, rows, continued))
    return [{"embeds": embeds} for embeds in messages]
