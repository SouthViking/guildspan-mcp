import pytest

from discord_mcp_bridge.server import create_server


def test_create_server_returns_fastmcp_instance() -> None:
    server = create_server()

    assert server.name == "Discord MCP Bridge"


@pytest.mark.asyncio
async def test_create_server_registers_discord_send_message_tool() -> None:
    server = create_server()

    tools = await server.list_tools()

    assert [tool.name for tool in tools] == [
        "discord_list_channels",
        "discord_send_message",
    ]
