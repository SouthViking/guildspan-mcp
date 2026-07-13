"""FastMCP server entrypoint."""

from fastmcp import FastMCP

from discord_mcp_bridge.tools.channels import discord_get_channel, discord_list_channels
from discord_mcp_bridge.tools.diagnostics import discord_health_check
from discord_mcp_bridge.tools.history import discord_read_messages
from discord_mcp_bridge.tools.messages import discord_edit_own_message, discord_send_message
from discord_mcp_bridge.tools.reactions import discord_add_reaction
from discord_mcp_bridge.tools.search import discord_search_messages
from discord_mcp_bridge.tools.threads import discord_create_thread


def create_server() -> FastMCP:
    """Create and configure the Discord MCP Bridge server."""

    mcp = FastMCP("Discord MCP Bridge")
    mcp.tool(discord_health_check)
    mcp.tool(discord_list_channels)
    mcp.tool(discord_get_channel)
    mcp.tool(discord_read_messages)
    mcp.tool(discord_search_messages)
    mcp.tool(discord_send_message)
    mcp.tool(discord_edit_own_message)
    mcp.tool(discord_create_thread)
    mcp.tool(discord_add_reaction)
    return mcp


def main() -> None:
    """Run the local MCP server over stdio."""

    create_server().run()


if __name__ == "__main__":
    main()
