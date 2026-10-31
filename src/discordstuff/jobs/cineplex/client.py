import httpx

from discordstuff.config import Config

BASE_URL = "https://apis.cineplex.com/prod/cpx/theatrical/api"


class CineplexClient:
    """Thin wrapper around the unofficial Cineplex API. See README for the
    endpoints this is built from and what's still unverified."""

    def __init__(self, config: Config):
        self._api_key = config.cineplex_api_key
        self._location_params = {
            "city": config.cineplex_city,
            "region": config.cineplex_region,
            "regionCode": config.cineplex_region_code,
            "country": "Canada",
            "postalCode": config.cineplex_postal_code,
            "latitude": config.cineplex_latitude,
            "longitude": config.cineplex_longitude,
            "accuracyKm": 5,
        }

    def _headers(self) -> dict[str, str]:
        return {"Ocp-Apim-Subscription-Key": self._api_key or ""}

    async def get_bookable_movies(self) -> list[dict]:
        # Response shape unverified — make a real request against
        # /v1/movies/bookable and map the actual fields before relying on this.
        raise NotImplementedError("get_bookable_movies: response shape not yet verified")

    async def get_theatres_for_film(self, film_id: int) -> list[dict]:
        # Response shape unverified — same caveat as get_bookable_movies.
        raise NotImplementedError("get_theatres_for_film: response shape not yet verified")

    async def get_bookable_dates(self, film_id: int) -> list[str]:
        raise NotImplementedError("get_bookable_dates: response shape not yet verified")
