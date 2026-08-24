"""Hosted Discord guild discovery tools."""

from __future__ import annotations

from fastmcp.server.dependencies import get_access_token

from guildspan.errors import DiscordConfigurationError
from guildspan.tools._common import _hosted_authorization


async def discord_list_guilds() -> dict[str, object]:
    """List guilds authorized or eligible for the current OAuth user."""

    token = get_access_token()
    if token is None:
        raise DiscordConfigurationError(
            "discord_list_guilds requires the hosted MCP runtime with OAuth."
        )

    guilds = await _hosted_authorization().list_available_guilds(token=token)
    return {
        "status": "ok",
        "count": len(guilds),
        "guilds": [
            {
                "id": guild.id,
                "name": guild.name,
                "icon_url": guild.icon_url,
                "owner": guild.owner,
                "authorization_status": guild.status,
                "bot_accessible": True,
            }
            for guild in guilds
        ],
    }
