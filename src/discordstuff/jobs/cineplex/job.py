import logging

from discordstuff.jobs.cineplex.client import CineplexClient
from discordstuff.jobs.cineplex.repository import NotifiedMovieRepository
from discordstuff.notifications.base import Notifier

logger = logging.getLogger(__name__)


class CineplexJob:
    name = "cineplex"

    def __init__(self, client: CineplexClient, repository: NotifiedMovieRepository, theatre_id: str | None):
        self._client = client
        self._repository = repository
        self._theatre_id = theatre_id

    async def run(self, notifier: Notifier) -> None:
        # Polling/detection logic is pending API verification (see README):
        # confirm response field names, confirm requests aren't blocked by
        # Imperva from the server's IP, and confirm the user's theatre_id.
        raise NotImplementedError("CineplexJob.run: pending API verification, see README")
