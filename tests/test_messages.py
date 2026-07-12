from typing import Any, cast

import pytest

from discord_mcp_bridge.config import Settings
from discord_mcp_bridge.discord_client import DiscordChannel, DiscordMessage
from discord_mcp_bridge.errors import DiscordConfigurationError, DiscordPermissionError
from discord_mcp_bridge.tools import messages as messages_module
from discord_mcp_bridge.tools import _common as common_module
from discord_mcp_bridge.tools.messages import _discord_send_message, discord_send_message


def make_settings(**kwargs: object) -> Settings:
    settings_ctor = cast(Any, Settings)
    return cast(Settings, settings_ctor(_env_file=None, **kwargs))


class FakeDiscordClient:
    def __init__(
        self,
        *,
        channel: DiscordChannel | None = None,
        message: DiscordMessage | None = None,
    ) -> None:
        self.channel = channel or DiscordChannel(
            id="1234567890",
            name="general",
            guild_id=None,
            type=0,
            position=0,
        )
        self.message = message or DiscordMessage(
            id="message-1",
            channel_id="1234567890",
            content="hello",
            author_username="bridge-bot",
        )
        self.sent_payloads: list[tuple[str, str]] = []
        self.closed = False

    async def get_channel(self, channel_id: str) -> DiscordChannel:
        return DiscordChannel(
            id=channel_id,
            name=self.channel.name,
            guild_id=self.channel.guild_id,
            type=self.channel.type,
            position=self.channel.position,
        )

    async def list_guild_channels(self, guild_id: str) -> list[DiscordChannel]:
        raise AssertionError("list_guild_channels should not be called by discord_send_message")

    async def list_channel_messages(
        self,
        *,
        channel_id: str,
        limit: int,
        before: str | None = None,
        after: str | None = None,
        around: str | None = None,
    ) -> list[dict[str, object]]:
        raise AssertionError("list_channel_messages should not be called by discord_send_message")

    async def send_message(self, *, channel_id: str, content: str) -> DiscordMessage:
        self.sent_payloads.append((channel_id, content))
        return DiscordMessage(
            id=self.message.id,
            channel_id=channel_id,
            content=content,
            author_username=self.message.author_username,
        )

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_discord_send_message_rejects_missing_bot_token() -> None:
    with pytest.raises(DiscordConfigurationError, match="DISCORD_BOT_TOKEN is required"):
        await _discord_send_message(
            channel_id="1234567890",
            content="hello",
            settings=make_settings(discord_bot_token=None),
        )


@pytest.mark.asyncio
async def test_discord_send_message_rejects_blank_channel_id() -> None:
    with pytest.raises(ValueError, match="channel_id is required"):
        await discord_send_message(channel_id=" ", content="hello")


@pytest.mark.asyncio
async def test_discord_send_message_rejects_blank_content() -> None:
    with pytest.raises(ValueError, match="content is required"):
        await discord_send_message(channel_id="1234567890", content=" ")


@pytest.mark.asyncio
async def test_discord_send_message_sends_message() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_send_message(
        channel_id="1234567890",
        content="hello",
        settings=make_settings(discord_bot_token="token"),
        client=fake_client,
    )

    assert result == {
        "status": "sent",
        "message_id": "message-1",
        "channel_id": "1234567890",
        "content": "hello",
        "author_username": "bridge-bot",
    }
    assert fake_client.sent_payloads == [("1234567890", "hello")]


@pytest.mark.asyncio
async def test_discord_send_message_appends_actor_attribution() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_send_message(
        channel_id="1234567890",
        content="deploy done",
        settings=make_settings(
            discord_bot_token="token",
            discord_actor_discord_id="4242",
            discord_append_attribution=True,
        ),
        client=fake_client,
    )

    assert result["content"] == "deploy done\n\n-# sent via MCP by <@4242>"
    assert fake_client.sent_payloads == [
        ("1234567890", "deploy done\n\n-# sent via MCP by <@4242>")
    ]


@pytest.mark.asyncio
async def test_discord_send_message_blocks_non_allowed_channel() -> None:
    fake_client = FakeDiscordClient()

    with pytest.raises(DiscordPermissionError, match="not in DISCORD_ALLOWED_CHANNELS"):
        await _discord_send_message(
            channel_id="1234567890",
            content="hello",
            settings=make_settings(
                discord_bot_token="token",
                discord_allowed_channels="9999999999",
            ),
            client=fake_client,
        )


@pytest.mark.asyncio
async def test_discord_send_message_blocks_non_allowed_guild() -> None:
    fake_client = FakeDiscordClient(
        channel=DiscordChannel(
            id="1234567890",
            name="general",
            guild_id="guild-2",
            type=0,
            position=0,
        )
    )

    with pytest.raises(DiscordPermissionError, match="not in DISCORD_ALLOWED_GUILDS"):
        await _discord_send_message(
            channel_id="1234567890",
            content="hello",
            settings=make_settings(
                discord_bot_token="token",
                discord_allowed_guilds="guild-1",
            ),
            client=fake_client,
        )


@pytest.mark.asyncio
async def test_discord_send_message_closes_managed_client() -> None:
    class RecordingDiscordClient(FakeDiscordClient):
        instances: list["RecordingDiscordClient"] = []

        def __init__(self, *, bot_token: str) -> None:
            super().__init__()
            self.bot_token = bot_token
            RecordingDiscordClient.instances.append(self)

    fake_settings = make_settings(discord_bot_token="token")
    original_factory = common_module.build_client
    original_messages_factory = cast(Any, messages_module).build_client

    try:
        common_module.build_client = lambda *, bot_token: RecordingDiscordClient(
            bot_token=bot_token
        )
        cast(Any, messages_module).build_client = common_module.build_client
        result = await _discord_send_message(
            channel_id="1234567890",
            content="hello",
            settings=fake_settings,
        )
    finally:
        common_module.build_client = original_factory
        cast(Any, messages_module).build_client = original_messages_factory

    assert result["status"] == "sent"
    assert RecordingDiscordClient.instances[0].closed is True
