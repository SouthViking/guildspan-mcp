"""Shared helpers for Discord MCP tools."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from guildspan.config import Settings, load_settings
from guildspan.discord_client import (
    DiscordChannel,
    DiscordClient,
    DiscordMessage,
    DiscordThread,
    DiscordUpload,
)
from guildspan.errors import DiscordConfigurationError, DiscordPermissionError


class ChannelAccessClientProtocol(Protocol):
    """Protocol for validating access to one Discord channel."""

    async def get_channel(self, channel_id: str) -> DiscordChannel:
        """Fetch one channel by id."""


class DiscordClientProtocol(ChannelAccessClientProtocol, Protocol):
    """Protocol for Discord client interactions used by tools and tests."""

    async def list_guild_channels(self, guild_id: str) -> list[DiscordChannel]:
        """List channels visible to the bot in a guild."""

    async def list_channel_messages(
        self,
        *,
        channel_id: str,
        limit: int,
        before: str | None = None,
        after: str | None = None,
        around: str | None = None,
    ) -> list[dict[str, object]]:
        """List messages visible to the bot in a channel."""

    async def send_message(
        self,
        *,
        channel_id: str,
        content: str | None,
        attachments: Sequence[DiscordUpload] = (),
        sticker_ids: Sequence[str] = (),
    ) -> DiscordMessage:
        """Send a message."""

    async def edit_message(
        self,
        *,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> DiscordMessage:
        """Edit a message."""

    async def add_reaction(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        """Add a reaction."""

    async def create_thread(
        self,
        *,
        channel_id: str,
        name: str,
        message_id: str | None = None,
        auto_archive_duration: int = 1440,
    ) -> DiscordThread:
        """Create a thread."""

    async def aclose(self) -> None:
        """Close network resources."""


def resolve_settings(settings: Settings | None) -> Settings:
    """Load settings if a caller did not supply them."""

    return settings or load_settings()


def require_bot_token(settings: Settings) -> str:
    """Return the configured bot token or fail with a clear error."""

    bot_token = settings.discord_bot_token
    if bot_token is None or not bot_token.strip():
        raise DiscordConfigurationError("DISCORD_BOT_TOKEN is required.")
    return bot_token.strip()


def build_client(*, bot_token: str) -> DiscordClientProtocol:
    """Construct the default Discord REST client."""

    return DiscordClient(bot_token=bot_token)


async def assert_channel_is_allowed(
    *,
    channel_id: str,
    settings: Settings,
    client: ChannelAccessClientProtocol,
) -> None:
    """Validate that a channel is allowed by the local policy."""

    allowed_channels = settings.allowed_channel_ids
    if allowed_channels and channel_id not in allowed_channels:
        raise DiscordPermissionError(
            f"Channel {channel_id} is not in DISCORD_ALLOWED_CHANNELS."
        )

    allowed_guilds = settings.allowed_guild_ids
    if not allowed_guilds:
        return

    channel = await client.get_channel(channel_id)
    guild_id = channel.guild_id
    if guild_id is None:
        raise DiscordPermissionError(
            f"Channel {channel_id} is not a guild channel and DISCORD_ALLOWED_GUILDS is set."
        )
    if guild_id not in allowed_guilds:
        raise DiscordPermissionError(
            f"Guild {guild_id} for channel {channel_id} is not in DISCORD_ALLOWED_GUILDS."
        )


def assert_guild_is_allowed(*, guild_id: str, settings: Settings) -> None:
    """Validate that a guild is allowed by the local policy."""

    allowed_guilds = settings.allowed_guild_ids
    if allowed_guilds and guild_id not in allowed_guilds:
        raise DiscordPermissionError(
            f"Guild {guild_id} is not in DISCORD_ALLOWED_GUILDS."
        )


def filter_allowed_channels(
    *,
    channels: list[DiscordChannel],
    settings: Settings,
) -> list[DiscordChannel]:
    """Filter listed channels against local channel allowlists."""

    allowed_channels = settings.allowed_channel_ids
    if not allowed_channels:
        return channels
    return [channel for channel in channels if channel.id in allowed_channels]


def required_id(value: str, name: str) -> str:
    """Normalize a required Discord snowflake-like identifier."""

    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def optional_id(value: str | None) -> str | None:
    """Normalize an optional Discord snowflake-like identifier."""

    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def required_text(value: str, name: str) -> str:
    """Normalize required user-facing text."""

    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def bounded_int(*, value: int, name: str, minimum: int, maximum: int) -> int:
    """Validate an integer against inclusive bounds."""

    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value
