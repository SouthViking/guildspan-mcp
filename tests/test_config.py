from typing import Any, cast

from discord_mcp_bridge.config import Settings, load_settings


def make_settings(**kwargs: object) -> Settings:
    settings_ctor = cast(Any, Settings)
    return cast(Settings, settings_ctor(_env_file=None, **kwargs))


def test_settings_can_be_constructed_without_discord_token() -> None:
    settings = make_settings()

    assert settings.discord_bot_token is None
    assert settings.discord_append_attribution is True
    assert settings.discord_attribution_text == "sent using Discord Bridge"
    assert settings.discord_max_attachment_bytes == 10 * 1024 * 1024
    assert settings.allowed_attachment_mime_patterns == set()
    assert settings.allowed_upload_paths == ()
    assert settings.allowed_upload_url_hosts == set()
    assert settings.discord_max_upload_bytes == 10 * 1024 * 1024
    assert settings.discord_max_upload_total_bytes == 24 * 1024 * 1024
    assert settings.allowed_upload_mime_patterns == set()


def test_load_settings_returns_settings() -> None:
    assert isinstance(load_settings(), Settings)


def test_settings_parse_allowed_ids() -> None:
    settings = make_settings(
        discord_default_guild_id=" guild-123 ",
        discord_allowed_guilds="123, 456 ,,",
        discord_allowed_channels="abc, def",
    )

    assert settings.default_guild_id == "guild-123"
    assert settings.allowed_guild_ids == {"123", "456"}
    assert settings.allowed_channel_ids == {"abc", "def"}


def test_settings_parse_attachment_mime_patterns() -> None:
    settings = make_settings(
        discord_max_attachment_bytes=2048,
        discord_allowed_attachment_mime_types=" image/*, APPLICATION/PDF ,,",
    )

    assert settings.discord_max_attachment_bytes == 2048
    assert settings.allowed_attachment_mime_patterns == {
        "image/*",
        "application/pdf",
    }


def test_settings_parse_upload_controls() -> None:
    settings = make_settings(
        discord_allowed_upload_paths=" /tmp/media, /opt/files ,,",
        discord_allowed_upload_url_hosts=" CDN.EXAMPLE.COM, files.example.com ",
        discord_max_upload_bytes=2048,
        discord_max_upload_total_bytes=4096,
        discord_allowed_upload_mime_types=" image/*, AUDIO/* ,,",
    )

    assert settings.allowed_upload_paths == ("/opt/files", "/tmp/media")
    assert settings.allowed_upload_url_hosts == {
        "cdn.example.com",
        "files.example.com",
    }
    assert settings.discord_max_upload_bytes == 2048
    assert settings.discord_max_upload_total_bytes == 4096
    assert settings.allowed_upload_mime_patterns == {"image/*", "audio/*"}
