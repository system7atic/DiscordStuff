from dataclasses import dataclass
from zoneinfo import ZoneInfo

# Every watched Theatre is in Metro Vancouver, so "today" at a Theatre is always
# this zone's date, whatever the clock on the machine running the bot says.
THEATRE_TIMEZONE = ZoneInfo("America/Vancouver")


@dataclass(frozen=True)
class WatchedTheatre:
    key: str
    theatre_id: int
    name: str


WATCHED_THEATRES = (
    WatchedTheatre(key="richmond", theatre_id=1409, name="SilverCity Riverport Cinemas"),
    WatchedTheatre(key="metropolis", theatre_id=1408, name="Cineplex Cinemas Metropolis"),
    WatchedTheatre(key="coquitlam", theatre_id=1412, name="Cineplex Cinemas Coquitlam and VIP"),
)

THEATRES_BY_KEY = {theatre.key: theatre for theatre in WATCHED_THEATRES}
THEATRES_BY_ID = {theatre.theatre_id: theatre for theatre in WATCHED_THEATRES}
