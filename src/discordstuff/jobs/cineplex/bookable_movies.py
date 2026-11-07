import asyncio
from dataclasses import dataclass
from datetime import date

from discordstuff.jobs.cineplex.client import CineplexClient
from discordstuff.jobs.cineplex.models import BookableMovie
from discordstuff.jobs.cineplex.theatres import WatchedTheatre

# Cineplex has no "movies at this theatre" endpoint, so listing a theatre takes
# one or two requests per movie. Capped so a command doesn't hammer the API,
# which sits behind Imperva and is also what the scheduled job depends on.
MAX_CONCURRENT_REQUESTS = 5


@dataclass(frozen=True)
class MovieBookingInfo:
    title: str
    first_bookable_date: str
    url: str
    poster_url: str


@dataclass(frozen=True)
class BookableListing:
    title: str
    url: str
    first_bookable_date: date | None


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


async def list_bookable_at(
    client: CineplexClient, theatre: WatchedTheatre
) -> list[BookableListing]:
    """Every non-excluded movie currently bookable at one theatre, soonest first.
    Read-only: this doesn't touch Notified movies, so it has no effect on alerts."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def listing_if_at_theatre(movie: BookableMovie) -> BookableListing | None:
        async with semaphore:
            theatres = await client.get_theatres_for_film(movie.film_id)
            if not any(candidate.theatre_id == theatre.theatre_id for candidate in theatres):
                return None
        async with semaphore:
            dates = await client.get_bookable_dates(movie.film_id, theatre_id=theatre.theatre_id)
        return BookableListing(
            title=movie.title,
            url=movie.url,
            first_bookable_date=min(dates) if dates else None,
        )

    movies = await client.get_bookable_movies()
    results = await asyncio.gather(
        *(listing_if_at_theatre(movie) for movie in movies if not movie.is_excluded)
    )
    return sorted(
        (listing for listing in results if listing is not None),
        key=lambda listing: (
            listing.first_bookable_date or date.max,
            listing.title.casefold(),
        ),
    )


def format_date(value: date) -> str:
    return f"{value:%b} {value.day}, {value.year}"
