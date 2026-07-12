"""Channel-related MCP tools."""

from __future__ import annotations

from discord_mcp_bridge.config import Settings
from discord_mcp_bridge.tools._common import (
    DiscordClientProtocol,
    assert_guild_is_allowed,
    build_client,
    filter_allowed_channels,
    require_bot_token,
    resolve_settings,
)


async def discord_list_channels(guild_id: str | None = None) -> dict[str, object]:
    """List channels visible to the configured bot in a Discord guild."""

    return await _discord_list_channels(guild_id=guild_id)


async def _discord_list_channels(
    *,
    guild_id: str | None,
    settings: Settings | None = None,
    client: DiscordClientProtocol | None = None,
) -> dict[str, object]:
    resolved_settings = resolve_settings(settings)
    normalized_guild_id = _resolve_guild_id(guild_id=guild_id, settings=resolved_settings)
    bot_token = require_bot_token(resolved_settings)
    assert_guild_is_allowed(guild_id=normalized_guild_id, settings=resolved_settings)

    managed_client = client is None
    discord_client = client or build_client(bot_token=bot_token)

    try:
        channels = await discord_client.list_guild_channels(normalized_guild_id)
    finally:
        if managed_client:
            await discord_client.aclose()

    filtered_channels = filter_allowed_channels(channels=channels, settings=resolved_settings)
    sorted_channels = sorted(
        filtered_channels,
        key=lambda channel: (
            channel.position if channel.position is not None else 10**9,
            channel.name or "",
            channel.id,
        ),
    )

    return {
        "status": "ok",
        "guild_id": normalized_guild_id,
        "count": len(sorted_channels),
        "channels": [
            {
                "id": channel.id,
                "name": channel.name,
                "guild_id": channel.guild_id,
                "type": channel.type,
                "position": channel.position,
            }
            for channel in sorted_channels
        ],
    }


def _resolve_guild_id(*, guild_id: str | None, settings: Settings) -> str:
    if guild_id is not None and guild_id.strip():
        return guild_id.strip()

    default_guild_id = settings.default_guild_id
    if default_guild_id is not None:
        return default_guild_id

    raise ValueError(
        "guild_id is required unless DISCORD_DEFAULT_GUILD_ID is configured."
    )
