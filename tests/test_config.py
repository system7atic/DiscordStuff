import pytest

from discordstuff.config import Config


def test_from_env_requires_discord_bot_token(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN"):
        Config.from_env()


def test_from_env_requires_cineplex_api_key_when_job_enabled(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "123")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("ENABLED_JOBS", "cineplex")
    monkeypatch.delenv("CINEPLEX_API_KEY", raising=False)

    with pytest.raises(ValueError, match="CINEPLEX_API_KEY"):
        Config.from_env()
