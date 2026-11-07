from datetime import date

import httpx
import pytest

from discordstuff.jobs.cineplex.client import (
    BASE_URL,
    CineplexAuthError,
    CineplexBlockedError,
    CineplexClient,
)

# Trimmed samples captured from a real browser session against the live API (2026-10-31).
MOVIES_BOOKABLE_SAMPLE = [
    {
        "id": 34362,
        "name": "Avengers: Doomsday",
        "filmUrl": "avengers-doomsday",
        "isEvent": False,
        "genres": [],
        "mediumPosterImageUrl": "https://mediafiles.cineplex.com/Central/Film/Posters/34362_320_470.jpg",
    },
    {
        "id": 99999,
        "name": "National Theatre Live: Hamlet",
        "filmUrl": "ntl-hamlet",
        "isEvent": True,
        "genres": [],
        "mediumPosterImageUrl": "https://mediafiles.cineplex.com/Central/Film/Posters/99999_320_470.jpg",
    },
    {
        "id": 62291,
        "name": "Ramayana (Hindi w/e.s.t.)",
        "filmUrl": "est-ramayana-hindi-west",
        "isEvent": False,
        "genres": ["International"],
        "mediumPosterImageUrl": "https://mediafiles.cineplex.com/Central/Film/Posters/62291_320_470.jpg",
    },
    {
        "id": 60710,
        "name": "Godzilla Minus Zero (Japanese w/e.s.t.)",
        "filmUrl": "godzilla-minus-zero-japanese-west",
        "isEvent": False,
        "genres": ["Action"],
        "mediumPosterImageUrl": "https://mediafiles.cineplex.com/Central/Film/Posters/60710_320_470.jpg",
    },
    {
        "id": 62163,
        "name": "Once Upon a Time in the Middle East (Mandarin w/Chinese and e.s.t.)",
        "filmUrl": "once-upon-a-time-in-the-middle-east-mandarin-wchinese-and-est",
        "isEvent": False,
        "genres": ["International", "Drama"],
        "mediumPosterImageUrl": "https://mediafiles.cineplex.com/Central/Film/Posters/62163_320_470.jpg",
    },
]

THEATRES_SAMPLE = {
    "favouriteTheatres": [],
    "nearbyTheatres": [
        {"theatreId": 1145, "theatreName": "Cineplex Cinemas Marine Gateway and VIP"},
        {"theatreId": 1409, "theatreName": "SilverCity Riverport Cinemas"},
    ],
    "otherTheatres": [
        {"theatreId": 1151, "theatreName": "Cineplex Cinemas Park Royal and VIP"},
    ],
}

DATES_BOOKABLE_SAMPLE = ["2026-12-17T00:00:00", "2026-12-18T00:00:00", "2026-12-19T00:00:00"]

CHUNK_URL = "https://www.cineplex.com/next-static-files/_next/static/chunks/pages/_app-abc123.js"
HOMEPAGE_HTML = f'<html><script src="{CHUNK_URL}"></script></html>'


def chunk_js_with_key(key: str) -> str:
    return f'let i={{headers:{{"Ocp-Apim-Subscription-Key":"{key}"}}}};'


def json_response(payload) -> httpx.Response:
    return httpx.Response(200, json=payload, headers={"content-type": "application/json"})


@pytest.mark.asyncio
async def test_get_bookable_movies_parses_real_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(MOVIES_BOOKABLE_SAMPLE)

    client = CineplexClient(transport=httpx.MockTransport(handler), api_key="test-key")
    movies = await client.get_bookable_movies()

    assert len(movies) == 5
    assert movies[0].film_id == 34362
    assert movies[0].title == "Avengers: Doomsday"
    assert movies[0].slug == "avengers-doomsday"
    assert movies[0].is_event is False
    assert movies[0].is_international is False
    assert movies[0].poster_url == "https://mediafiles.cineplex.com/Central/Film/Posters/34362_320_470.jpg"
    assert movies[1].is_event is True

    # "International" genre tag, not an exempt language -> excluded
    assert movies[2].is_international is True
    # no "International" genre tag, but the title's subtitle marker still catches it;
    # Japanese is an exempt language though, so it's not excluded
    assert movies[3].is_international is False
    # "International" genre tag, but Mandarin is exempt -> not excluded
    assert movies[4].is_international is False


@pytest.mark.asyncio
async def test_get_theatres_for_film_flattens_all_buckets():
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(THEATRES_SAMPLE)

    client = CineplexClient(transport=httpx.MockTransport(handler), api_key="test-key")
    theatres = await client.get_theatres_for_film(34362)

    assert {t.theatre_id for t in theatres} == {1145, 1409, 1151}
    assert any(t.name == "SilverCity Riverport Cinemas" for t in theatres)


@pytest.mark.asyncio
async def test_get_bookable_dates_parses_iso_dates():
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(DATES_BOOKABLE_SAMPLE)

    client = CineplexClient(transport=httpx.MockTransport(handler), api_key="test-key")
    dates = await client.get_bookable_dates(34362)

    assert dates == [date(2026, 12, 17), date(2026, 12, 18), date(2026, 12, 19)]


@pytest.mark.asyncio
async def test_get_bookable_dates_scopes_to_a_theatre_when_given_one():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(DATES_BOOKABLE_SAMPLE)

    client = CineplexClient(transport=httpx.MockTransport(handler), api_key="test-key")
    await client.get_bookable_dates(34362, theatre_id=1409)

    assert requests[0].url.params["filmId"] == "34362"
    assert requests[0].url.params["locationId"] == "1409"


@pytest.mark.asyncio
async def test_get_bookable_dates_is_film_wide_without_a_theatre():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(DATES_BOOKABLE_SAMPLE)

    client = CineplexClient(transport=httpx.MockTransport(handler), api_key="test-key")
    await client.get_bookable_dates(34362)

    assert "locationId" not in requests[0].url.params


@pytest.mark.asyncio
async def test_discovers_api_key_when_not_provided():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://www.cineplex.com/":
            return httpx.Response(200, text=HOMEPAGE_HTML, headers={"content-type": "text/html"})
        if str(request.url) == CHUNK_URL:
            return httpx.Response(
                200, text=chunk_js_with_key("d15c0ded0000000000000000000001aa"), headers={"content-type": "application/javascript"}
            )
        assert request.headers["ocp-apim-subscription-key"] == "d15c0ded0000000000000000000001aa"
        return json_response(MOVIES_BOOKABLE_SAMPLE)

    client = CineplexClient(transport=httpx.MockTransport(handler))
    movies = await client.get_bookable_movies()

    assert client._api_key == "d15c0ded0000000000000000000001aa"
    assert len(movies) == 5


@pytest.mark.asyncio
async def test_401_rediscovers_key_and_retries_once():
    calls_to_movies_endpoint = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls_to_movies_endpoint
        if str(request.url) == "https://www.cineplex.com/":
            return httpx.Response(200, text=HOMEPAGE_HTML, headers={"content-type": "text/html"})
        if str(request.url) == CHUNK_URL:
            return httpx.Response(
                200, text=chunk_js_with_key("f2e5b0ed0000000000000000000002bb"), headers={"content-type": "application/javascript"}
            )
        calls_to_movies_endpoint += 1
        if calls_to_movies_endpoint == 1:
            return httpx.Response(401, json={"message": "denied"}, headers={"content-type": "application/json"})
        assert request.headers["ocp-apim-subscription-key"] == "f2e5b0ed0000000000000000000002bb"
        return json_response(MOVIES_BOOKABLE_SAMPLE)

    client = CineplexClient(transport=httpx.MockTransport(handler), api_key="stale-key")
    movies = await client.get_bookable_movies()

    assert calls_to_movies_endpoint == 2
    assert len(movies) == 5


@pytest.mark.asyncio
async def test_401_still_failing_after_retry_raises_auth_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://www.cineplex.com/":
            return httpx.Response(200, text=HOMEPAGE_HTML, headers={"content-type": "text/html"})
        if str(request.url) == CHUNK_URL:
            return httpx.Response(
                200, text=chunk_js_with_key("5eed0bad0000000000000000000003cc"), headers={"content-type": "application/javascript"}
            )
        return httpx.Response(401, json={"message": "denied"}, headers={"content-type": "application/json"})

    client = CineplexClient(transport=httpx.MockTransport(handler), api_key="stale-key")
    with pytest.raises(CineplexAuthError, match="even after automatically refreshing"):
        await client.get_bookable_movies()


@pytest.mark.asyncio
async def test_non_json_response_raises_blocked_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>Incapsula challenge</html>", headers={"content-type": "text/html"})

    client = CineplexClient(transport=httpx.MockTransport(handler), api_key="test-key")
    with pytest.raises(CineplexBlockedError, match="Imperva"):
        await client.get_bookable_movies()


@pytest.mark.asyncio
async def test_discovery_raises_when_app_chunk_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>no chunks here</html>", headers={"content-type": "text/html"})

    client = CineplexClient(transport=httpx.MockTransport(handler))
    with pytest.raises(CineplexBlockedError, match="app bundle"):
        await client.get_bookable_movies()


def test_base_url_is_theatrical_api():
    assert BASE_URL == "https://apis.cineplex.com/prod/cpx/theatrical/api"
