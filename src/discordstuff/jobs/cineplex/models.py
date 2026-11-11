from dataclasses import dataclass

MOVIE_URL_TEMPLATE = "https://www.cineplex.com/movie/{slug}"


@dataclass(frozen=True)
class BookableMovie:
    film_id: int
    title: str
    slug: str
    is_event: bool
    is_international: bool
    poster_url: str | None

    @property
    def is_excluded(self) -> bool:
        return self.is_event or self.is_international

    @property
    def url(self) -> str:
        return MOVIE_URL_TEMPLATE.format(slug=self.slug)


@dataclass(frozen=True)
class Theatre:
    theatre_id: int
    name: str
