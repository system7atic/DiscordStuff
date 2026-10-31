import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    discord_bot_token: str
    discord_channel_id: int
    discord_error_channel_id: int
    database_url: str
    enabled_jobs: frozenset[str]
    job_interval_seconds: int
    cineplex_api_key: str | None = None
    cineplex_theatre_id: str | None = None
    cineplex_city: str | None = None
    cineplex_region: str | None = None
    cineplex_region_code: str | None = None
    cineplex_postal_code: str | None = None
    cineplex_latitude: float | None = None
    cineplex_longitude: float | None = None

    @classmethod
    def from_env(cls) -> "Config":
        discord_bot_token = _require_env("DISCORD_BOT_TOKEN")
        discord_channel_id = int(_require_env("DISCORD_CHANNEL_ID"))
        config = cls(
            discord_bot_token=discord_bot_token,
            discord_channel_id=discord_channel_id,
            discord_error_channel_id=int(
                os.environ.get("DISCORD_ERROR_CHANNEL_ID") or discord_channel_id
            ),
            database_url=_require_env("DATABASE_URL"),
            enabled_jobs=_parse_enabled_jobs(os.environ.get("ENABLED_JOBS", "")),
            job_interval_seconds=int(os.environ.get("JOB_INTERVAL_SECONDS", "3600")),
            cineplex_api_key=os.environ.get("CINEPLEX_API_KEY"),
            cineplex_theatre_id=os.environ.get("CINEPLEX_THEATRE_ID"),
            cineplex_city=os.environ.get("CINEPLEX_CITY"),
            cineplex_region=os.environ.get("CINEPLEX_REGION"),
            cineplex_region_code=os.environ.get("CINEPLEX_REGION_CODE"),
            cineplex_postal_code=os.environ.get("CINEPLEX_POSTAL_CODE"),
            cineplex_latitude=_optional_float(os.environ.get("CINEPLEX_LATITUDE")),
            cineplex_longitude=_optional_float(os.environ.get("CINEPLEX_LONGITUDE")),
        )
        config._validate_job_requirements()
        return config

    def _validate_job_requirements(self) -> None:
        if "cineplex" in self.enabled_jobs and not self.cineplex_api_key:
            raise ValueError("CINEPLEX_API_KEY is required when 'cineplex' is in ENABLED_JOBS")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _parse_enabled_jobs(raw: str) -> frozenset[str]:
    return frozenset(name.strip() for name in raw.split(",") if name.strip())


def _optional_float(value: str | None) -> float | None:
    return float(value) if value else None
