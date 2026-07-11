from discord_mcp_bridge.config import Settings, load_settings


def test_settings_can_be_constructed_without_discord_token() -> None:
    settings = Settings()

    assert settings.discord_bot_token is None
    assert settings.discord_append_attribution is True


def test_load_settings_returns_settings() -> None:
    assert isinstance(load_settings(), Settings)
