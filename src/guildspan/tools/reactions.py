"""Reaction-related MCP tools."""

from __future__ import annotations

from guildspan.config import Settings
from guildspan.tools._common import (
    DiscordClientProtocol,
    assert_channel_is_allowed,
    build_client,
    require_bot_token,
    required_id,
    required_text,
    resolve_settings,
)


async def discord_add_reaction(
    channel_id: str,
    message_id: str,
    emoji: str,
) -> dict[str, str]:
    """Add a reaction to a Discord message using the configured bot."""

    return await _discord_add_reaction(
        channel_id=channel_id,
        message_id=message_id,
        emoji=emoji,
    )


async def _discord_add_reaction(
    *,
    channel_id: str,
    message_id: str,
    emoji: str,
    settings: Settings | None = None,
    client: DiscordClientProtocol | None = None,
) -> dict[str, str]:
    normalized_channel_id = required_id(channel_id, "channel_id")
    normalized_message_id = required_id(message_id, "message_id")
    normalized_emoji = required_text(emoji, "emoji")

    resolved_settings = resolve_settings(settings)
    bot_token = require_bot_token(resolved_settings)

    managed_client = client is None
    discord_client = client or build_client(bot_token=bot_token)

    try:
        await assert_channel_is_allowed(
            channel_id=normalized_channel_id,
            settings=resolved_settings,
            client=discord_client,
        )
        await discord_client.add_reaction(
            channel_id=normalized_channel_id,
            message_id=normalized_message_id,
            emoji=normalized_emoji,
        )
    finally:
        if managed_client:
            await discord_client.aclose()

    return {
        "status": "reacted",
        "channel_id": normalized_channel_id,
        "message_id": normalized_message_id,
        "emoji": normalized_emoji,
    }
