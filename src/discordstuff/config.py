import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    discord_bot_token: str
    discord_channel_id: int
    discord_guild_id: int
    database_url: str
    enabled_jobs: frozenset[str]
    job_interval_seconds: int
    alert_list: frozenset[int]
    is_dev: bool

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            discord_bot_token=_require_env("DISCORD_BOT_TOKEN"),
            discord_channel_id=int(_require_env("DISCORD_CHANNEL_ID")),
            discord_guild_id=int(_require_env("DISCORD_GUILD_ID")),
            database_url=_require_env("DATABASE_URL"),
            enabled_jobs=_parse_enabled_jobs(os.environ.get("ENABLED_JOBS", "")),
            job_interval_seconds=int(os.environ.get("JOB_INTERVAL_SECONDS", "3600")),
            alert_list=_parse_alert_list(os.environ.get("ALERT_LIST", "")),
            # Defaults to prod so a missing APP_ENV never accidentally exposes
            # dev-only commands (like /test-bookable-movies) on the real bot.
            is_dev=os.environ.get("APP_ENV", "prod").strip().lower() == "dev",
        )


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _parse_enabled_jobs(raw: str) -> frozenset[str]:
    return frozenset(name.strip() for name in raw.split(",") if name.strip())


def _parse_alert_list(raw: str) -> frozenset[int]:
    return frozenset(int(user_id.strip()) for user_id in raw.split(",") if user_id.strip())
