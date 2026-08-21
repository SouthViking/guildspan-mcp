"""Configuration for GuildSpan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_UPLOAD_TOTAL_BYTES = 24 * 1024 * 1024
DEFAULT_ATTRIBUTION_TEXT = "sent using GuildSpan"


@dataclass(frozen=True)
class HostedAuthSettings:
    """Validated settings required by the hosted OAuth runtime."""

    public_base_url: str
    discord_client_id: str
    discord_client_secret: str
    auth_secret: str


class Settings(BaseSettings):
    """Environment-backed settings shared by local and HTTP runtimes."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_bot_token: str | None = None
    discord_default_guild_id: str | None = None
    discord_allowed_guilds: str | None = None
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
    database_url: str | None = Field(
        default=None,
        validation_alias="DATABASE_URL",
    )
    database_echo: bool = Field(
        default=False,
        validation_alias="GUILDSPAN_DATABASE_ECHO",
    )
    database_pool_size: int = Field(
        default=5,
        gt=0,
        validation_alias="GUILDSPAN_DATABASE_POOL_SIZE",
    )
    database_max_overflow: int = Field(
        default=10,
        ge=0,
        validation_alias="GUILDSPAN_DATABASE_MAX_OVERFLOW",
    )
    auth_enabled: bool = Field(
        default=False,
        validation_alias="GUILDSPAN_AUTH_ENABLED",
    )
    public_base_url: str | None = Field(
        default=None,
        validation_alias="GUILDSPAN_PUBLIC_BASE_URL",
    )
    discord_oauth_client_id: str | None = Field(
        default=None,
        validation_alias="DISCORD_OAUTH_CLIENT_ID",
    )
    discord_oauth_client_secret: str | None = Field(
        default=None,
        validation_alias="DISCORD_OAUTH_CLIENT_SECRET",
    )
    auth_secret: str | None = Field(
        default=None,
        validation_alias="GUILDSPAN_AUTH_SECRET",
    )
    http_host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("GUILDSPAN_HTTP_HOST", "HOST"),
    )
    http_port: int = Field(
        default=8000,
        gt=0,
        le=65535,
        validation_alias=AliasChoices("GUILDSPAN_HTTP_PORT", "PORT"),
    )
    http_log_level: Literal[
        "critical", "error", "warning", "info", "debug", "trace"
    ] = Field(
        default="info",
        validation_alias="GUILDSPAN_HTTP_LOG_LEVEL",
    )

    @property
    def default_guild_id(self) -> str | None:
        """Return the normalized configured default guild ID."""

        return _normalized_or_none(self.discord_default_guild_id)

    @property
    def allowed_guild_ids(self) -> set[str]:
        """Return normalized configured guild IDs."""

        return _parse_csv_ids(self.discord_allowed_guilds)

    @property
    def allowed_attachment_mime_patterns(self) -> set[str]:
        """Return optional normalized MIME patterns allowed for downloads."""

        return {
            value.lower()
            for value in _parse_csv_values(self.discord_allowed_attachment_mime_types)
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

    def require_database_url(self) -> str:
        """Return the configured database URL or fail with an actionable error."""

        database_url = _normalized_or_none(self.database_url)
        if database_url is None:
            raise ValueError("DATABASE_URL is required for persistent GuildSpan data")
        return database_url

    def require_hosted_auth_settings(self) -> HostedAuthSettings:
        """Validate and return the hosted OAuth configuration."""

        public_base_url = _required_setting(
            self.public_base_url,
            "GUILDSPAN_PUBLIC_BASE_URL",
        ).rstrip("/")
        parsed_url = urlsplit(public_base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError(
                "GUILDSPAN_PUBLIC_BASE_URL must be an absolute HTTP(S) URL"
            )
        if (
            parsed_url.path not in {"", "/"}
            or parsed_url.query
            or parsed_url.fragment
            or parsed_url.username is not None
        ):
            raise ValueError(
                "GUILDSPAN_PUBLIC_BASE_URL must contain only the public origin"
            )
        if parsed_url.scheme != "https" and parsed_url.hostname not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise ValueError(
                "GUILDSPAN_PUBLIC_BASE_URL must use HTTPS outside local development"
            )

        discord_client_id = _required_setting(
            self.discord_oauth_client_id,
            "DISCORD_OAUTH_CLIENT_ID",
        )
        discord_client_secret = _required_setting(
            self.discord_oauth_client_secret,
            "DISCORD_OAUTH_CLIENT_SECRET",
        )
        auth_secret = _required_setting(
            self.auth_secret,
            "GUILDSPAN_AUTH_SECRET",
        )
        if len(auth_secret) < 32:
            raise ValueError(
                "GUILDSPAN_AUTH_SECRET must contain at least 32 characters"
            )
        if not self.allowed_guild_ids:
            raise ValueError(
                "DISCORD_ALLOWED_GUILDS must contain at least one guild when hosted "
                "authentication is enabled"
            )

        _required_setting(self.discord_bot_token, "DISCORD_BOT_TOKEN")
        self.require_database_url()
        return HostedAuthSettings(
            public_base_url=public_base_url,
            discord_client_id=discord_client_id,
            discord_client_secret=discord_client_secret,
            auth_secret=auth_secret,
        )


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


def _required_setting(raw_value: str | None, variable_name: str) -> str:
    normalized = _normalized_or_none(raw_value)
    if normalized is None:
        raise ValueError(f"{variable_name} is required when hosted auth is enabled")
    return normalized
