import discord
import pytest

from discordstuff.jobs.cineplex.bookable_movies import (
    BookableMoviesBatch,
    MovieBookingInfo,
    TheatreSection,
)
from discordstuff.jobs.cineplex.theatres import WatchedTheatre
from discordstuff.notifications.base import Notification
from discordstuff.notifications.discord.messages import (
    build_batch_messages,
    build_failure_message,
    build_mention_prefix,
    build_message_content,
    build_theatre_layouts,
)

RICHMOND = WatchedTheatre(key="richmond", theatre_id=1409, name="SilverCity Riverport Cinemas")
METROPOLIS = WatchedTheatre(key="metropolis", theatre_id=1408, name="Cineplex Cinemas Metropolis")

HEADER_TEXT = "**New movies now bookable**"


def _make_movies(count: int, prefix: str) -> list[MovieBookingInfo]:
    return [
        MovieBookingInfo(
            title=f"{prefix} {n}",
            first_bookable_date="Dec 17, 2026",
            url=f"https://www.cineplex.com/movie/{prefix}-{n}",
            poster_url=f"https://example.com/{prefix}-{n}.jpg",
        )
        for n in range(count)
    ]


def test_build_mention_prefix_joins_subscriber_mentions():
    assert build_mention_prefix([111, 222, 333]) == "<@111> <@222> <@333>"


def test_build_mention_prefix_empty_when_no_subscribers():
    assert build_mention_prefix([]) == ""


def test_build_message_content_combines_mentions_and_header():
    assert build_message_content([111, 222]) == f"<@111> <@222> {HEADER_TEXT}"


def test_build_message_content_is_just_the_header_without_subscribers():
    assert build_message_content([]) == HEADER_TEXT


def test_build_failure_message_combines_title_and_body():
    notification = Notification(title="Job 'cineplex' failed", body="boom")

    assert build_failure_message(notification) == "Job 'cineplex' failed: boom"


def test_build_failure_message_truncates_to_discords_message_limit():
    notification = Notification(title="Job 'cineplex' failed", body="x" * 5000)

    message = build_failure_message(notification)

    assert len(message) == 2000
    assert message.endswith("…")


def test_theatre_layout_combines_theatres_into_one_card_when_everything_fits():
    batch = BookableMoviesBatch(
        subscriber_ids=[111],
        sections=[
            TheatreSection(
                theatre=RICHMOND,
                movies=[
                    MovieBookingInfo(
                        title="Avengers: Doomsday",
                        first_bookable_date="Dec 17, 2026",
                        url="https://www.cineplex.com/movie/avengers",
                        poster_url="https://example.com/avengers.jpg",
                    ),
                    MovieBookingInfo(
                        title="Zootopia 2",
                        first_bookable_date="Dec 20, 2026",
                        url="https://www.cineplex.com/movie/zootopia-2",
                        poster_url="https://example.com/zootopia.jpg",
                    ),
                ],
            ),
            TheatreSection(
                theatre=METROPOLIS,
                movies=[
                    MovieBookingInfo(
                        title="Toy Story 5",
                        first_bookable_date="Dec 18, 2026",
                        url="https://www.cineplex.com/movie/toy-story-5",
                        poster_url="https://example.com/toy-story-5.jpg",
                    )
                ],
            ),
        ],
    )

    [view] = build_theatre_layouts(batch)

    [container] = view.children
    assert isinstance(container, discord.ui.Container)

    (
        richmond_heading,
        avengers,
        zootopia,
        separator,
        metropolis_heading,
        toy_story,
    ) = container.children

    assert richmond_heading.content == "**Richmond: SilverCity Riverport Cinemas**"
    assert isinstance(separator, discord.ui.Separator)
    assert metropolis_heading.content == "**Metropolis: Cineplex Cinemas Metropolis**"

    assert (
        avengers.children[0].content
        == "[Avengers: Doomsday](https://www.cineplex.com/movie/avengers)"
    )
    assert avengers.children[1].content == "Bookable from Dec 17, 2026"
    assert avengers.accessory.media.url == "https://example.com/avengers.jpg"
    assert zootopia.accessory.media.url == "https://example.com/zootopia.jpg"
    assert toy_story.accessory.media.url == "https://example.com/toy-story-5.jpg"


@pytest.mark.parametrize("poster_url", [None, ""])
def test_theatre_layout_falls_back_to_plain_text_for_a_movie_without_a_poster(poster_url):
    batch = BookableMoviesBatch(
        subscriber_ids=[],
        sections=[
            TheatreSection(
                theatre=RICHMOND,
                movies=[
                    MovieBookingInfo(
                        title="Mystery Film",
                        first_bookable_date="Dec 17, 2026",
                        url="https://www.cineplex.com/movie/mystery-film",
                        poster_url=poster_url,
                    )
                ],
            )
        ],
    )

    [view] = build_theatre_layouts(batch)

    [container] = view.children
    _heading, movie = container.children
    assert isinstance(movie, discord.ui.TextDisplay)
    assert movie.content == (
        "[Mystery Film](https://www.cineplex.com/movie/mystery-film)\nBookable from Dec 17, 2026"
    )
    # The original crash only surfaced when discord.py serialized the view to send it.
    view.to_components()


def test_theatre_layout_splits_into_one_card_per_theatre_when_combined_would_overflow():
    # Each theatre's 5 movies fits comfortably alone (2 + 5*4 = 22 <= 40), but
    # combined into one card they don't (1 + 21 + 1 + 21 = 44 > 40) - so each
    # theatre must get its own card instead of an awkward mixed split.
    batch = BookableMoviesBatch(
        subscriber_ids=[],
        sections=[
            TheatreSection(theatre=RICHMOND, movies=_make_movies(5, "richmond")),
            TheatreSection(theatre=METROPOLIS, movies=_make_movies(5, "metropolis")),
        ],
    )

    views = build_theatre_layouts(batch)

    assert len(views) == 2
    [richmond_container] = views[0].children
    [metropolis_container] = views[1].children

    richmond_heading, *richmond_movies = richmond_container.children
    assert richmond_heading.content == "**Richmond: SilverCity Riverport Cinemas**"
    assert len(richmond_movies) == 5

    metropolis_heading, *metropolis_movies = metropolis_container.children
    assert metropolis_heading.content == "**Metropolis: Cineplex Cinemas Metropolis**"
    assert len(metropolis_movies) == 5


def test_theatre_layout_splits_into_multiple_messages_past_the_40_component_cap():
    # Container(1) + heading(1) + 9 movies*4 = 38, so a 10th movie would push
    # the first card to 42 - past Discord's 40-component cap - and must spill
    # into a continuation card instead.
    batch = BookableMoviesBatch(
        subscriber_ids=[],
        sections=[TheatreSection(theatre=RICHMOND, movies=_make_movies(10, "movie"))],
    )

    views = build_theatre_layouts(batch)

    assert len(views) == 2
    [first_container] = views[0].children
    [second_container] = views[1].children

    assert len(first_container.children) == 1 + 9  # heading + 9 movie sections
    continued_heading, *second_movies = second_container.children
    assert continued_heading.content == "**Richmond: SilverCity Riverport Cinemas** (continued)"
    assert len(second_movies) == 1


def test_build_batch_messages_combines_mentions_and_header_in_one_content_message():
    batch = BookableMoviesBatch(subscriber_ids=[111, 222], sections=[])

    messages = build_batch_messages(batch)

    assert len(messages) == 2
    assert messages[0] == {"content": f"<@111> <@222> {HEADER_TEXT}"}
    assert "view" in messages[1]


def test_build_batch_messages_content_is_just_the_header_when_no_subscribers():
    batch = BookableMoviesBatch(subscriber_ids=[], sections=[])

    messages = build_batch_messages(batch)

    assert len(messages) == 2
    assert messages[0] == {"content": HEADER_TEXT}
    assert "view" in messages[1]
