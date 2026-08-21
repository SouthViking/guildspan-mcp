from typing import Any, cast

import pytest

from guildspan.config import Settings, load_settings


def make_settings(**kwargs: object) -> Settings:
    settings_ctor = cast(Any, Settings)
    return cast(Settings, settings_ctor(_env_file=None, **kwargs))


def test_settings_can_be_constructed_without_discord_token() -> None:
    settings = make_settings()

    assert settings.discord_bot_token is None
    assert settings.discord_append_attribution is True
    assert settings.discord_attribution_text == "sent using GuildSpan"
    assert settings.discord_max_attachment_bytes == 10 * 1024 * 1024
    assert settings.allowed_attachment_mime_patterns == set()
    assert settings.allowed_upload_paths == ()
    assert settings.allowed_upload_url_hosts == set()
    assert settings.discord_max_upload_bytes == 10 * 1024 * 1024
    assert settings.discord_max_upload_total_bytes == 24 * 1024 * 1024
    assert settings.allowed_upload_mime_patterns == set()
    assert settings.database_url is None
    assert settings.database_echo is False
    assert settings.database_pool_size == 5
    assert settings.database_max_overflow == 10


def test_load_settings_returns_settings() -> None:
    assert isinstance(load_settings(), Settings)


def test_settings_parse_allowed_ids() -> None:
    settings = make_settings(
        discord_default_guild_id=" guild-123 ",
        discord_allowed_guilds="123, 456 ,,",
    )

    assert settings.default_guild_id == "guild-123"
    assert settings.allowed_guild_ids == {"123", "456"}


def test_settings_parse_http_runtime_values() -> None:
    settings = make_settings(
        GUILDSPAN_HTTP_HOST="0.0.0.0",
        PORT=9000,
        GUILDSPAN_HTTP_LOG_LEVEL="debug",
    )

    assert settings.http_host == "0.0.0.0"
    assert settings.http_port == 9000
    assert settings.http_log_level == "debug"


def test_settings_parse_database_values() -> None:
    settings = make_settings(
        DATABASE_URL=" postgresql://guildspan:secret@db/guildspan ",
        GUILDSPAN_DATABASE_ECHO=True,
        GUILDSPAN_DATABASE_POOL_SIZE=8,
        GUILDSPAN_DATABASE_MAX_OVERFLOW=4,
    )

    assert (
        settings.require_database_url() == "postgresql://guildspan:secret@db/guildspan"
    )
    assert settings.database_echo is True
    assert settings.database_pool_size == 8
    assert settings.database_max_overflow == 4


def test_database_url_is_optional_until_persistence_is_used() -> None:
    settings = make_settings(DATABASE_URL="   ")

    with pytest.raises(ValueError, match="DATABASE_URL is required"):
        settings.require_database_url()


def test_blank_default_guild_id_is_normalized_to_none() -> None:
    settings = make_settings(discord_default_guild_id="   ")

    assert settings.default_guild_id is None


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
