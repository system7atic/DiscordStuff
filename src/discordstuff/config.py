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

    @classmethod
    def from_env(cls) -> "Config":
        discord_bot_token = _require_env("DISCORD_BOT_TOKEN")
        discord_channel_id = int(_require_env("DISCORD_CHANNEL_ID"))
        return cls(
            discord_bot_token=discord_bot_token,
            discord_channel_id=discord_channel_id,
            discord_error_channel_id=int(
                os.environ.get("DISCORD_ERROR_CHANNEL_ID") or discord_channel_id
            ),
            database_url=_require_env("DATABASE_URL"),
            enabled_jobs=_parse_enabled_jobs(os.environ.get("ENABLED_JOBS", "")),
            job_interval_seconds=int(os.environ.get("JOB_INTERVAL_SECONDS", "3600")),
        )


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _parse_enabled_jobs(raw: str) -> frozenset[str]:
    return frozenset(name.strip() for name in raw.split(",") if name.strip())
