"""Configuration for GuildSpan."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_UPLOAD_TOTAL_BYTES = 24 * 1024 * 1024
DEFAULT_ATTRIBUTION_TEXT = "sent using GuildSpan"


class Settings(BaseSettings):
    """Environment-backed settings for the local MCP server."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_bot_token: str | None = None
    discord_default_guild_id: str | None = None
    discord_allowed_guilds: str | None = None
    discord_allowed_channels: str | None = None
    discord_actor_name: str | None = None
    discord_actor_discord_id: str | None = None
    discord_append_attribution: bool = True
    discord_attribution_text: str | None = DEFAULT_ATTRIBUTION_TEXT
    discord_max_attachment_bytes: int = Field(
        default=DEFAULT_MAX_ATTACHMENT_BYTES,
        gt=0,
    )
    discord_allowed_attachment_mime_types: str | None = None
    discord_allowed_upload_paths: str | None = None
    discord_allowed_upload_url_hosts: str | None = None
    discord_max_upload_bytes: int = Field(
        default=DEFAULT_MAX_UPLOAD_BYTES,
        gt=0,
    )
    discord_max_upload_total_bytes: int = Field(
        default=DEFAULT_MAX_UPLOAD_TOTAL_BYTES,
        gt=0,
        le=25 * 1024 * 1024,
    )
    discord_allowed_upload_mime_types: str | None = None

    @property
    def default_guild_id(self) -> str | None:
        """Return the normalized configured default guild ID."""

        return _normalized_or_none(self.discord_default_guild_id)

    @property
    def allowed_guild_ids(self) -> set[str]:
        """Return normalized configured guild IDs."""

        return _parse_csv_ids(self.discord_allowed_guilds)

    @property
    def allowed_channel_ids(self) -> set[str]:
        """Return normalized configured channel IDs."""

        return _parse_csv_ids(self.discord_allowed_channels)

    @property
    def allowed_attachment_mime_patterns(self) -> set[str]:
        """Return optional normalized MIME patterns allowed for downloads."""

        return {
            value.lower()
            for value in _parse_csv_values(
                self.discord_allowed_attachment_mime_types
            )
        }

    @property
    def allowed_upload_paths(self) -> tuple[str, ...]:
        """Return configured filesystem roots allowed for outgoing files."""

        return tuple(sorted(_parse_csv_values(self.discord_allowed_upload_paths)))

    @property
    def allowed_upload_url_hosts(self) -> set[str]:
        """Return optional normalized hosts allowed for outgoing URL downloads."""

        return {
            value.lower()
            for value in _parse_csv_values(self.discord_allowed_upload_url_hosts)
        }

    @property
    def allowed_upload_mime_patterns(self) -> set[str]:
        """Return optional normalized MIME patterns allowed for uploads."""

        return {
            value.lower()
            for value in _parse_csv_values(self.discord_allowed_upload_mime_types)
        }


def load_settings() -> Settings:
    """Load settings from environment variables and an optional local .env file."""

    return Settings()


def _parse_csv_ids(raw_value: str | None) -> set[str]:
    return _parse_csv_values(raw_value)


def _parse_csv_values(raw_value: str | None) -> set[str]:
    if raw_value is None:
        return set()
    return {part.strip() for part in raw_value.split(",") if part.strip()}


def _normalized_or_none(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    normalized = raw_value.strip()
    if not normalized:
        return None
    return normalized
