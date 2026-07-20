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
        "discord_health_check",
        "discord_list_channels",
        "discord_get_channel",
        "discord_get_current_bot_user",
        "discord_get_user",
        "discord_get_member",
        "discord_search_members",
        "discord_list_roles",
        "discord_read_messages",
        "discord_download_attachment",
        "discord_search_messages",
        "discord_send_message",
        "discord_edit_own_message",
        "discord_create_thread",
        "discord_add_reaction",
    ]
