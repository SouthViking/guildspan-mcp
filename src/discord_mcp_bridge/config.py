"""Configuration for Discord MCP Bridge."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings for the local MCP server."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_bot_token: str | None = None
    discord_allowed_guilds: str | None = None
    discord_allowed_channels: str | None = None
    discord_actor_name: str | None = None
    discord_actor_discord_id: str | None = None
    discord_append_attribution: bool = True


def load_settings() -> Settings:
    """Load settings from environment variables and an optional local .env file."""

    return Settings()
