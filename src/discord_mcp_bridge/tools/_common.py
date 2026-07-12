"""Shared helpers for Discord MCP tools."""

from __future__ import annotations

from typing import Protocol

from discord_mcp_bridge.config import Settings, load_settings
from discord_mcp_bridge.discord_client import DiscordChannel, DiscordClient, DiscordMessage
from discord_mcp_bridge.errors import DiscordConfigurationError, DiscordPermissionError


class DiscordClientProtocol(Protocol):
    """Protocol for Discord client interactions used by tools and tests."""

    async def get_channel(self, channel_id: str) -> DiscordChannel:
        """Fetch one channel by id."""

    async def list_guild_channels(self, guild_id: str) -> list[DiscordChannel]:
        """List channels visible to the bot in a guild."""

    async def send_message(self, *, channel_id: str, content: str) -> DiscordMessage:
        """Send a message."""

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
    client: DiscordClientProtocol,
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
