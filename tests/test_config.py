import pytest

from discordstuff.config import Config


def test_from_env_requires_discord_bot_token(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN"):
        Config.from_env()


def test_from_env_requires_database_url(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "123")
    monkeypatch.setenv("DISCORD_GUILD_ID", "456")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValueError, match="DATABASE_URL"):
        Config.from_env()


def test_from_env_requires_discord_guild_id(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "123")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")
    monkeypatch.delenv("DISCORD_GUILD_ID", raising=False)

    with pytest.raises(ValueError, match="DISCORD_GUILD_ID"):
        Config.from_env()


def test_from_env_parses_alert_list(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "123")
    monkeypatch.setenv("DISCORD_GUILD_ID", "456")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")
    monkeypatch.setenv("ALERT_LIST", "111, 222,333")

    config = Config.from_env()

    assert config.alert_list == frozenset({111, 222, 333})


def test_from_env_defaults_alert_list_to_empty(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "123")
    monkeypatch.setenv("DISCORD_GUILD_ID", "456")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")
    monkeypatch.delenv("ALERT_LIST", raising=False)

    config = Config.from_env()

    assert config.alert_list == frozenset()


def _set_required_env(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "123")
    monkeypatch.setenv("DISCORD_GUILD_ID", "456")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")


def test_from_env_defaults_is_dev_to_false(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.delenv("APP_ENV", raising=False)

    assert Config.from_env().is_dev is False


def test_from_env_is_dev_true_when_app_env_is_dev(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "DEV")

    assert Config.from_env().is_dev is True


def test_from_env_is_dev_false_for_prod(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "prod")

    assert Config.from_env().is_dev is False


def test_from_env_names_the_variable_when_an_integer_is_malformed(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("JOB_INTERVAL_SECONDS", "30m")

    with pytest.raises(ValueError, match="JOB_INTERVAL_SECONDS.*'30m'"):
        Config.from_env()


def test_from_env_names_alert_list_when_a_user_id_is_malformed(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("ALERT_LIST", "111,@daniel")

    with pytest.raises(ValueError, match="ALERT_LIST"):
        Config.from_env()
