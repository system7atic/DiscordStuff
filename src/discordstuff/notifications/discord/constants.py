from discordstuff.jobs.cineplex.bookable_movies import MovieBookingInfo
from discordstuff.jobs.cineplex.theatres import THEATRES_BY_KEY, WatchedTheatre

# A placeholder second subscriber so /test-bookable-movies can demonstrate the
# audience-splitting behaviour (a message shared by several subscribers vs. one
# seen only by the invoker) without touching real subscriber data.
TEST_OTHER_SUBSCRIBER_ID = 1

_SAMPLE_POSTER_URL = "https://mediafiles.cineplex.com/Central/Film/Posters/62206_320_470.jpg"

SAMPLE_THEATRE_MOVIES: dict[WatchedTheatre, list[MovieBookingInfo]] = {
    THEATRES_BY_KEY["richmond"]: [
        MovieBookingInfo(
            title="Avengers: Doomsday",
            first_bookable_date="Dec 17, 2026",
            url="https://www.cineplex.com/movie/avengers-doomsday",
            poster_url=_SAMPLE_POSTER_URL,
        ),
        MovieBookingInfo(
            title="Zootopia 2",
            first_bookable_date="Dec 18, 2026",
            url="https://www.cineplex.com/movie/zootopia-2",
            poster_url=_SAMPLE_POSTER_URL,
        ),
        MovieBookingInfo(
            title="Toy Story 5",
            first_bookable_date="Dec 19, 2026",
            url="https://www.cineplex.com/movie/toy-story-5",
            poster_url=_SAMPLE_POSTER_URL,
        ),
    ],
    THEATRES_BY_KEY["metropolis"]: [
        MovieBookingInfo(
            title="Wicked: For Good",
            first_bookable_date="Dec 20, 2026",
            url="https://www.cineplex.com/movie/wicked-for-good",
            poster_url=_SAMPLE_POSTER_URL,
        ),
        MovieBookingInfo(
            title="Dune: Part Three",
            first_bookable_date="Dec 21, 2026",
            url="https://www.cineplex.com/movie/dune-part-three",
            poster_url=_SAMPLE_POSTER_URL,
        ),
        MovieBookingInfo(
            title="The Hunger Games: Sunrise on the Reaping",
            first_bookable_date="Dec 22, 2026",
            url="https://www.cineplex.com/movie/hunger-games-sunrise-on-the-reaping",
            poster_url=_SAMPLE_POSTER_URL,
        ),
        MovieBookingInfo(
            title="Moana 3",
            first_bookable_date="Dec 23, 2026",
            url="https://www.cineplex.com/movie/moana-3",
            poster_url=_SAMPLE_POSTER_URL,
        ),
        MovieBookingInfo(
            title="Shrek 5",
            first_bookable_date="Dec 24, 2026",
            url="https://www.cineplex.com/movie/shrek-5",
            poster_url=_SAMPLE_POSTER_URL,
        ),
    ],
    THEATRES_BY_KEY["coquitlam"]: [
        MovieBookingInfo(
            title="Spider-Man: Brand New Day",
            first_bookable_date="Dec 25, 2026",
            url="https://www.cineplex.com/movie/spider-man-brand-new-day",
            poster_url=_SAMPLE_POSTER_URL,
        ),
        MovieBookingInfo(
            title="Now You See Me: Now You Don't",
            first_bookable_date="Dec 26, 2026",
            url="https://www.cineplex.com/movie/now-you-see-me-now-you-dont",
            poster_url=_SAMPLE_POSTER_URL,
        ),
        MovieBookingInfo(
            title="The Batman Part II",
            first_bookable_date="Dec 27, 2026",
            url="https://www.cineplex.com/movie/the-batman-part-ii",
            poster_url=_SAMPLE_POSTER_URL,
        ),
    ],
}


def sample_subscribers_by_theatre(invoker_id: int) -> dict[int, list[int]]:
    richmond_id = THEATRES_BY_KEY["richmond"].theatre_id
    metropolis_id = THEATRES_BY_KEY["metropolis"].theatre_id
    coquitlam_id = THEATRES_BY_KEY["coquitlam"].theatre_id
    return {
        richmond_id: [invoker_id, TEST_OTHER_SUBSCRIBER_ID],
        metropolis_id: [invoker_id],
        coquitlam_id: [invoker_id],
    }
