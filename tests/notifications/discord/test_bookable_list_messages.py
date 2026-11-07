from datetime import date

from discordstuff.jobs.cineplex.bookable_movies import BookableListing
from discordstuff.jobs.cineplex.theatres import WatchedTheatre
from discordstuff.notifications.discord.messages import build_bookable_list_messages

RICHMOND = WatchedTheatre(key="richmond", theatre_id=1409, name="SilverCity Riverport Cinemas")
TODAY = date(2026, 11, 6)
TITLE = "Richmond: SilverCity Riverport Cinemas"
INTRO = "Bookable movies and their first bookable date"


def _listing(title, first_bookable_date=TODAY) -> BookableListing:
    return BookableListing(
        title=title,
        url=f"https://www.cineplex.com/movie/{title.lower().replace(' ', '-')}",
        first_bookable_date=first_bookable_date,
    )


def _many_listings(count: int) -> list[BookableListing]:
    # Roughly the same line length as real Cineplex rows (about 95 characters).
    return [_listing(f"A Reasonable Movie Title {n:03}") for n in range(count)]


def _rows_of(messages: list[dict]) -> list[str]:
    return [
        line
        for message in messages
        for embed in message["embeds"]
        for line in embed.description.split("\n")
        if line.startswith("- ")
    ]


def test_row_links_the_title_and_says_today_when_first_bookable_today():
    [message] = build_bookable_list_messages(RICHMOND, [_listing("Zootopia 2")], TODAY)
    [embed] = message["embeds"]

    assert embed.title == TITLE
    assert embed.description == (
        f"{INTRO}\n- [Zootopia 2](https://www.cineplex.com/movie/zootopia-2) · Today"
    )


def test_row_shows_the_date_when_first_bookable_on_another_day():
    [message] = build_bookable_list_messages(
        RICHMOND, [_listing("Zootopia 2", date(2026, 11, 14))], TODAY
    )

    assert _rows_of([message]) == [
        "- [Zootopia 2](https://www.cineplex.com/movie/zootopia-2) · Nov 14, 2026"
    ]


def test_row_says_unknown_when_there_is_no_date():
    [message] = build_bookable_list_messages(RICHMOND, [_listing("Zootopia 2", None)], TODAY)

    assert _rows_of([message]) == [
        "- [Zootopia 2](https://www.cineplex.com/movie/zootopia-2) · unknown"
    ]


def test_rows_keep_the_order_they_were_given():
    messages = build_bookable_list_messages(
        RICHMOND, [_listing("Zebra"), _listing("Apple")], TODAY
    )

    assert [row.split("]")[0] for row in _rows_of(messages)] == ["- [Zebra", "- [Apple"]


def test_empty_theatre_gets_a_plain_message():
    assert build_bookable_list_messages(RICHMOND, [], TODAY) == [
        {"content": "No bookable movies at SilverCity Riverport Cinemas right now."}
    ]


def test_a_full_real_world_list_fits_in_one_embed():
    # Richmond had 35 eligible movies when this was written.
    messages = build_bookable_list_messages(RICHMOND, _many_listings(35), TODAY)

    assert len(messages) == 1
    assert len(messages[0]["embeds"]) == 1
    assert len(_rows_of(messages)) == 35


def test_list_past_the_description_limit_continues_in_a_second_embed_of_the_same_message():
    messages = build_bookable_list_messages(RICHMOND, _many_listings(55), TODAY)

    assert len(messages) == 1
    first, second = messages[0]["embeds"]
    assert first.title == TITLE
    assert second.title == f"{TITLE} (continued)"
    assert first.description.startswith(INTRO)
    assert not second.description.startswith(INTRO)
    assert len(_rows_of(messages)) == 55


def test_list_past_the_message_limit_continues_in_another_message():
    listings = _many_listings(150)

    messages = build_bookable_list_messages(RICHMOND, listings, TODAY)

    assert len(messages) > 1
    expected_titles = [f"- [{listing.title}]" for listing in listings]
    assert [row.split("(")[0] for row in _rows_of(messages)] == expected_titles


def test_no_embed_or_message_exceeds_discords_limits():
    for count in (43, 44, 62, 63, 64, 90, 150, 400):
        for message in build_bookable_list_messages(RICHMOND, _many_listings(count), TODAY):
            assert sum(len(embed) for embed in message["embeds"]) <= 6000
            assert len(message["embeds"]) <= 10
            for embed in message["embeds"]:
                assert len(embed.description) <= 4096
                assert len(embed.title) <= 256
