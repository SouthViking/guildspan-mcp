"""FastMCP server entrypoint."""

from fastmcp import FastMCP

from discord_mcp_bridge.tools.messages import discord_send_message


def create_server() -> FastMCP:
    """Create and configure the Discord MCP Bridge server."""

    mcp = FastMCP("Discord MCP Bridge")
    mcp.tool(discord_send_message)
    return mcp


def main() -> None:
    """Run the local MCP server over stdio."""

    create_server().run()


if __name__ == "__main__":
    main()
