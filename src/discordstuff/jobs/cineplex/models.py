from dataclasses import dataclass


@dataclass(frozen=True)
class BookableMovie:
    film_id: int
    title: str
    slug: str
    is_event: bool


@dataclass(frozen=True)
class Theatre:
    theatre_id: int
    name: str
