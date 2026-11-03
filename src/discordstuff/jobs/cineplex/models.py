from dataclasses import dataclass


@dataclass(frozen=True)
class BookableMovie:
    film_id: int
    title: str
    slug: str
    is_event: bool
    is_international: bool
    poster_url: str


@dataclass(frozen=True)
class Theatre:
    theatre_id: int
    name: str
