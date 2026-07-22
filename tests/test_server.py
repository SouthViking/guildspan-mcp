import pytest

from guildspan import server as server_module
from guildspan.server import create_server


def test_create_server_returns_fastmcp_instance() -> None:
    server = create_server()

    assert server.name == "GuildSpan"


def test_main_runs_the_configured_server(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class RecordingServer:
        def run(self) -> None:
            calls.append("run")

    monkeypatch.setattr(server_module, "create_server", RecordingServer)

    server_module.main()

    assert calls == ["run"]


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

    send_tool = next(tool for tool in tools if tool.name == "discord_send_message")
    properties = send_tool.parameters["properties"]
    assert set(properties) == {
        "channel_id",
        "content",
        "attachments",
        "sticker_ids",
        "locale",
    }
    assert "language of the outgoing message" in properties["locale"]["description"]
    assert "fall back to English" in properties["locale"]["description"]
    attachment_array = properties["attachments"]["anyOf"][0]
    source_variants = attachment_array["items"]["oneOf"]
    assert {
        variant["properties"]["source_type"]["const"] for variant in source_variants
    } == {"path", "url", "base64"}
