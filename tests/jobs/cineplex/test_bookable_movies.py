from discordstuff.jobs.cineplex.theatres import WatchedTheatre
from discordstuff.jobs.cineplex.bookable_movies import MovieBookingInfo, build_batches

RICHMOND = WatchedTheatre(key="richmond", theatre_id=1409, name="SilverCity Riverport Cinemas")
METROPOLIS = WatchedTheatre(key="metropolis", theatre_id=1408, name="Cineplex Cinemas Metropolis")
COQUITLAM = WatchedTheatre(
    key="coquitlam", theatre_id=1412, name="Cineplex Cinemas Coquitlam and VIP"
)

AVENGERS = MovieBookingInfo(
    title="Avengers: Doomsday",
    first_bookable_date="2026-12-17",
    url="https://www.cineplex.com/movie/avengers",
    poster_url="https://example.com/avengers.jpg",
)
TOY_STORY = MovieBookingInfo(
    title="Toy Story 5",
    first_bookable_date="2026-12-18",
    url="https://www.cineplex.com/movie/toy-story-5",
    poster_url="https://example.com/toy-story-5.jpg",
)
WICKED = MovieBookingInfo(
    title="Wicked: For Good",
    first_bookable_date="2026-12-19",
    url="https://www.cineplex.com/movie/wicked",
    poster_url="https://example.com/wicked.jpg",
)


def test_single_theatre_produces_a_single_batch():
    batches = build_batches(
        theatre_movies={RICHMOND: [AVENGERS]},
        subscribers_by_theatre={RICHMOND.theatre_id: [111, 222]},
    )

    assert len(batches) == 1
    assert batches[0].subscriber_ids == [111, 222]
    assert batches[0].sections[0].theatre == RICHMOND
    assert batches[0].sections[0].movies == [AVENGERS]


def test_theatres_with_the_same_subscribers_share_one_batch():
    batches = build_batches(
        theatre_movies={METROPOLIS: [TOY_STORY], COQUITLAM: [WICKED]},
        subscribers_by_theatre={METROPOLIS.theatre_id: [111], COQUITLAM.theatre_id: [111]},
    )

    assert len(batches) == 1
    assert batches[0].subscriber_ids == [111]
    assert {section.theatre for section in batches[0].sections} == {METROPOLIS, COQUITLAM}


def test_theatres_with_different_subscribers_split_into_separate_batches():
    # One person subscribed to all 3 theatres, another subscribed only to Richmond:
    # Richmond's shared audience gets its own batch, the other two theatres (seen
    # only by the first person) share a second batch.
    batches = build_batches(
        theatre_movies={RICHMOND: [AVENGERS], METROPOLIS: [TOY_STORY], COQUITLAM: [WICKED]},
        subscribers_by_theatre={
            RICHMOND.theatre_id: [111, 222],
            METROPOLIS.theatre_id: [111],
            COQUITLAM.theatre_id: [111],
        },
    )

    assert len(batches) == 2
    richmond_batch = next(batch for batch in batches if batch.subscriber_ids == [111, 222])
    solo_batch = next(batch for batch in batches if batch.subscriber_ids == [111])
    assert [section.theatre for section in richmond_batch.sections] == [RICHMOND]
    assert {section.theatre for section in solo_batch.sections} == {METROPOLIS, COQUITLAM}


def test_theatre_with_no_subscribers_produces_no_batch():
    batches = build_batches(theatre_movies={RICHMOND: [AVENGERS]}, subscribers_by_theatre={})

    assert batches == []


def test_theatre_with_no_subscribers_is_dropped_even_alongside_subscribed_theatres():
    batches = build_batches(
        theatre_movies={RICHMOND: [AVENGERS], COQUITLAM: [WICKED]},
        subscribers_by_theatre={RICHMOND.theatre_id: [111]},
    )

    assert len(batches) == 1
    assert [section.theatre for section in batches[0].sections] == [RICHMOND]
