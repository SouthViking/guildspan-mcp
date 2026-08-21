import pytest

from guildspan import __version__
from guildspan import local as local_module
from guildspan import server as server_module
from guildspan.server import GUILDSPAN_INSTRUCTIONS, create_server

READ_ONLY_TOOLS = {
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
}
WRITE_TOOL_ANNOTATIONS = {
    "discord_send_message": {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    "discord_edit_own_message": {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    "discord_create_thread": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    "discord_add_reaction": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
}


def test_create_server_returns_fastmcp_instance() -> None:
    server = create_server()

    assert server.name == "GuildSpan"
    assert server.version == __version__
    assert server.instructions == GUILDSPAN_INSTRUCTIONS


def test_local_main_runs_stdio_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str | None] = []

    class RecordingServer:
        def run(self, transport: str | None = None) -> None:
            calls.append(transport)

    monkeypatch.setattr(local_module, "create_server", RecordingServer)

    local_module.main()

    assert calls == ["stdio"]


def test_legacy_server_main_delegates_to_local_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str | None] = []

    class RecordingServer:
        def run(self, transport: str | None = None) -> None:
            calls.append(transport)

    monkeypatch.setattr(local_module, "create_server", RecordingServer)

    server_module.main()

    assert calls == ["stdio"]


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


@pytest.mark.asyncio
async def test_every_tool_exposes_user_facing_metadata_and_safety_hints() -> None:
    server = create_server()

    registered_tools = await server.list_tools()
    tools = {tool.name: tool.to_mcp_tool() for tool in registered_tools}

    assert set(tools) == READ_ONLY_TOOLS | set(WRITE_TOOL_ANNOTATIONS)
    for tool in tools.values():
        assert tool.title
        assert tool.description is not None
        assert tool.description.startswith("Use this")
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is not None
        assert tool.annotations.destructiveHint is not None
        assert tool.annotations.idempotentHint is not None
        assert tool.annotations.openWorldHint is not None

    expected_read_only = {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
    for name in READ_ONLY_TOOLS:
        annotations = tools[name].annotations
        assert annotations is not None
        assert annotations.model_dump(exclude_none=True) == expected_read_only

    for name, expected in WRITE_TOOL_ANNOTATIONS.items():
        annotations = tools[name].annotations
        assert annotations is not None
        assert annotations.model_dump(exclude_none=True) == expected


def test_server_instructions_put_write_safety_guidance_first() -> None:
    first_512_characters = GUILDSPAN_INSTRUCTIONS[:512]

    assert "never guess IDs" in first_512_characters
    assert "external side effects" in first_512_characters
    assert "Do not automatically retry a write" in first_512_characters
