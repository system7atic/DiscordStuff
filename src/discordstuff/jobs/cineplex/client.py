import re
from datetime import date
from typing import Any

import httpx

from discordstuff.jobs.cineplex.location import LOCATION_PARAMS
from discordstuff.jobs.cineplex.models import BookableMovie, Theatre

BASE_URL = "https://apis.cineplex.com/prod/cpx/theatrical/api"
REQUEST_TIMEOUT_SECONDS = 15

# The subscription key is a public front-end key, hardcoded by Cineplex into
# their own Next.js app bundle - not a per-user secret. We pull it from there
# instead of asking the user to copy it out of DevTools, and re-pull it
# automatically if it's ever rotated.
HOMEPAGE_URL = "https://www.cineplex.com/"
APP_CHUNK_PATTERN = re.compile(
    r'src="(https://www\.cineplex\.com/next-static-files/_next/static/chunks/pages/_app-[^"]+\.js)"'
)
API_KEY_PATTERN = re.compile(r'"Ocp-Apim-Subscription-Key":"([a-f0-9]{32})"')

# Cineplex marks subtitled/dubbed foreign-language releases with a trailing
# parenthetical like "(Hindi w/e.s.t.)" or "(English Dubbed)" and/or an
# "International" genre tag - but not consistently (e.g. "Godzilla Minus
# Zero (Japanese w/e.s.t.)" has no "International" genre). Verified against
# the live bookable-movies list on 2026-10-31: this combined check correctly
# separated all 19 international titles from the other 87 bookable movies.
INTERNATIONAL_TITLE_PATTERN = re.compile(r"\((?:[^)]*\be\.?\s*s\.?\s*t\.?\b[^)]*|[^)]*dubbed[^)]*)\)", re.IGNORECASE)

# Languages the user wants to see despite the "international" flagging above -
# the API exposes no structured language field, so this matches against the
# title's parenthetical language marker (e.g. "(Japanese w/e.s.t.)").
EXEMPT_INTERNATIONAL_LANGUAGES = ("japanese", "mandarin", "korean")


def _is_international(movie: dict) -> bool:
    is_flagged = "International" in movie.get("genres", []) or bool(
        INTERNATIONAL_TITLE_PATTERN.search(movie["name"])
    )
    if not is_flagged:
        return False
    title_lower = movie["name"].lower()
    return not any(language in title_lower for language in EXEMPT_INTERNATIONAL_LANGUAGES)


class CineplexAuthError(Exception):
    """Raised when the API still rejects requests after refreshing the subscription key."""


class CineplexBlockedError(Exception):
    """Raised when Cineplex returns something other than the expected JSON/JS (e.g. an
    Imperva challenge page, or the site's internals changed enough that key discovery broke)."""


class CineplexClient:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, api_key: str | None = None):
        self._transport = transport
        self._api_key = api_key

    async def get_bookable_movies(self) -> list[BookableMovie]:
        data = await self._get_json("/v1/movies/bookable", {"language": "en"})
        return [
            BookableMovie(
                film_id=movie["id"],
                title=movie["name"],
                slug=movie["filmUrl"],
                is_event=movie["isEvent"],
                is_international=_is_international(movie),
                poster_url=movie["mediumPosterImageUrl"],
            )
            for movie in data
        ]

    async def get_theatres_for_film(self, film_id: int) -> list[Theatre]:
        params = {"language": "en", "filmId": film_id, **LOCATION_PARAMS}
        data = await self._get_json("/v1/theatres", params)
        all_theatres = [
            *data["favouriteTheatres"],
            *data["nearbyTheatres"],
            *data["otherTheatres"],
        ]
        return [
            Theatre(theatre_id=theatre["theatreId"], name=theatre["theatreName"])
            for theatre in all_theatres
        ]

    async def get_bookable_dates(self, film_id: int) -> list[date]:
        data = await self._get_json("/v1/dates/bookable", {"filmId": film_id})
        return [date.fromisoformat(raw.split("T")[0]) for raw in data]

    async def _get_json(self, path: str, params: dict) -> Any:
        if self._api_key is None:
            self._api_key = await self._discover_api_key()

        response = await self._request(path, params)
        if response.status_code in (401, 403):
            self._api_key = await self._discover_api_key()
            response = await self._request(path, params)

        self._raise_for_cineplex_errors(response)
        return response.json()

    async def _request(self, path: str, params: dict) -> httpx.Response:
        headers = {"Ocp-Apim-Subscription-Key": self._api_key or ""}
        async with httpx.AsyncClient(
            base_url=BASE_URL,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
            transport=self._transport,
        ) as http_client:
            return await http_client.get(path, params=params)

    async def _discover_api_key(self) -> str:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_SECONDS, transport=self._transport
        ) as http_client:
            home_response = await http_client.get(HOMEPAGE_URL)
            home_response.raise_for_status()

            chunk_match = APP_CHUNK_PATTERN.search(home_response.text)
            if chunk_match is None:
                raise CineplexBlockedError(
                    "Could not find Cineplex's app bundle on the homepage - the site's layout "
                    "likely changed."
                )

            chunk_response = await http_client.get(chunk_match.group(1))
            chunk_response.raise_for_status()

            key_match = API_KEY_PATTERN.search(chunk_response.text)
            if key_match is None:
                raise CineplexBlockedError(
                    "Could not find a subscription key in Cineplex's app bundle - the site's "
                    "internals likely changed."
                )
            return key_match.group(1)

    def _raise_for_cineplex_errors(self, response: httpx.Response) -> None:
        if response.status_code in (401, 403):
            raise CineplexAuthError(
                f"Cineplex API returned {response.status_code} on {response.url} even after "
                "automatically refreshing the subscription key - something deeper changed."
            )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            raise CineplexBlockedError(
                f"Cineplex returned a non-JSON response ({content_type!r}) on {response.url} - "
                "likely an Imperva challenge page rather than real data."
            )
