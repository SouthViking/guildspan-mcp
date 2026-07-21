"""Thread-related MCP tools."""

from __future__ import annotations

from guildspan.config import Settings
from guildspan.tools._common import (
    DiscordClientProtocol,
    assert_channel_is_allowed,
    bounded_int,
    build_client,
    optional_id,
    required_id,
    required_text,
    require_bot_token,
    resolve_settings,
)


async def discord_create_thread(
    channel_id: str,
    name: str,
    message_id: str | None = None,
    auto_archive_duration: int = 1440,
) -> dict[str, object]:
    """Create a public Discord thread in a channel or from a message."""

    return await _discord_create_thread(
        channel_id=channel_id,
        name=name,
        message_id=message_id,
        auto_archive_duration=auto_archive_duration,
    )


async def _discord_create_thread(
    *,
    channel_id: str,
    name: str,
    message_id: str | None = None,
    auto_archive_duration: int = 1440,
    settings: Settings | None = None,
    client: DiscordClientProtocol | None = None,
) -> dict[str, object]:
    normalized_channel_id = required_id(channel_id, "channel_id")
    normalized_name = required_text(name, "name")
    normalized_message_id = optional_id(message_id)
    normalized_auto_archive_duration = bounded_int(
        value=auto_archive_duration,
        name="auto_archive_duration",
        minimum=60,
        maximum=10080,
    )

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
        thread = await discord_client.create_thread(
            channel_id=normalized_channel_id,
            name=normalized_name,
            message_id=normalized_message_id,
            auto_archive_duration=normalized_auto_archive_duration,
        )
    finally:
        if managed_client:
            await discord_client.aclose()

    return {
        "status": "created",
        "thread_id": thread.id,
        "channel_id": thread.id,
        "name": thread.name,
        "parent_channel_id": thread.parent_id or normalized_channel_id,
        "guild_id": thread.guild_id,
        "type": thread.type,
    }
