"""Message-related MCP tool facades."""

from discord_mcp_bridge.errors import DiscordToolNotImplementedError


async def discord_send_message(channel_id: str, content: str) -> dict[str, str]:
    """Send a message to a Discord channel.

    This facade defines the public MCP contract for the first milestone. Discord
    REST integration will be implemented in a later milestone.
    """

    if not channel_id.strip():
        raise ValueError("channel_id is required")

    if not content.strip():
        raise ValueError("content is required")

    raise DiscordToolNotImplementedError(
        "discord_send_message is registered, but Discord REST support is not implemented yet."
    )
