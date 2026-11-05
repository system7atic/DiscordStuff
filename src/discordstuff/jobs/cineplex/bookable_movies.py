from dataclasses import dataclass

from discordstuff.jobs.cineplex.theatres import WatchedTheatre


@dataclass(frozen=True)
class MovieBookingInfo:
    title: str
    first_bookable_date: str
    url: str
    poster_url: str


@dataclass(frozen=True)
class TheatreSection:
    theatre: WatchedTheatre
    movies: list[MovieBookingInfo]


@dataclass(frozen=True)
class BookableMoviesBatch:
    subscriber_ids: list[int]
    sections: list[TheatreSection]


def build_batches(
    theatre_movies: dict[WatchedTheatre, list[MovieBookingInfo]],
    subscribers_by_theatre: dict[int, list[int]],
) -> list[BookableMoviesBatch]:
    """Group theatres with new movies by their exact subscriber set, so that
    subscribers watching several theatres get one combined message instead of
    one per theatre. Theatres with no subscribers are dropped entirely."""
    theatre_ids_by_subscriber_set: dict[frozenset[int], list[WatchedTheatre]] = {}
    for theatre in theatre_movies:
        subscriber_set = frozenset(subscribers_by_theatre.get(theatre.theatre_id, []))
        if not subscriber_set:
            continue
        theatre_ids_by_subscriber_set.setdefault(subscriber_set, []).append(theatre)

    return [
        BookableMoviesBatch(
            subscriber_ids=sorted(subscriber_set),
            sections=[
                TheatreSection(theatre=theatre, movies=theatre_movies[theatre])
                for theatre in theatres
            ],
        )
        for subscriber_set, theatres in theatre_ids_by_subscriber_set.items()
    ]
