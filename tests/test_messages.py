from typing import Any, cast

import pytest

from discord_mcp_bridge.config import Settings
from discord_mcp_bridge.discord_client import DiscordChannel, DiscordMessage, DiscordThread
from discord_mcp_bridge.errors import DiscordConfigurationError, DiscordPermissionError
from discord_mcp_bridge.tools import messages as messages_module
from discord_mcp_bridge.tools import _common as common_module
from discord_mcp_bridge.tools.messages import (
    _discord_edit_own_message,
    _discord_send_message,
    discord_send_message,
)


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

    async def edit_message(
        self,
        *,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> DiscordMessage:
        raise AssertionError("edit_message should not be called by discord_send_message")

    async def add_reaction(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        raise AssertionError("add_reaction should not be called by discord_send_message")

    async def create_thread(
        self,
        *,
        channel_id: str,
        name: str,
        message_id: str | None = None,
        auto_archive_duration: int = 1440,
    ) -> DiscordThread:
        raise AssertionError("create_thread should not be called by discord_send_message")

    async def aclose(self) -> None:
        self.closed = True


class EditingDiscordClient(FakeDiscordClient):
    def __init__(self) -> None:
        super().__init__()
        self.edited_payloads: list[tuple[str, str, str]] = []

    async def edit_message(
        self,
        *,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> DiscordMessage:
        self.edited_payloads.append((channel_id, message_id, content))
        return DiscordMessage(
            id=message_id,
            channel_id=channel_id,
            content=content,
            author_username="bridge-bot",
        )


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
        "content": "hello\n\n-# sent using Discord Bridge",
        "author_username": "bridge-bot",
    }
    assert fake_client.sent_payloads == [
        ("1234567890", "hello\n\n-# sent using Discord Bridge")
    ]


@pytest.mark.asyncio
async def test_discord_send_message_appends_branded_attribution() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_send_message(
        channel_id="1234567890",
        content="deploy done",
        settings=make_settings(
            discord_bot_token="token",
            discord_actor_discord_id="4242",
            discord_append_attribution=True,
            discord_attribution_text="sent using My Bridge",
        ),
        client=fake_client,
    )

    assert result["content"] == "<@4242>\ndeploy done\n\n-# sent using My Bridge"
    assert fake_client.sent_payloads == [
        ("1234567890", "<@4242>\ndeploy done\n\n-# sent using My Bridge")
    ]


@pytest.mark.asyncio
async def test_discord_send_message_can_fall_back_to_actor_attribution() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_send_message(
        channel_id="1234567890",
        content="deploy done",
        settings=make_settings(
            discord_bot_token="token",
            discord_actor_discord_id="4242",
            discord_append_attribution=True,
            discord_attribution_text=" ",
        ),
        client=fake_client,
    )

    assert result["content"] == "deploy done\n\n-# sent via MCP by <@4242>"


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


@pytest.mark.asyncio
async def test_discord_edit_own_message_applies_actor_attribution() -> None:
    fake_client = EditingDiscordClient()

    result = await _discord_edit_own_message(
        channel_id="1234567890",
        message_id="message-1",
        content="updated",
        settings=make_settings(
            discord_bot_token="token",
            discord_actor_name="SouthViking",
            discord_actor_discord_id="4242",
            discord_append_attribution=True,
            discord_attribution_text="sent using Discord Bridge",
        ),
        client=fake_client,
    )

    assert result == {
        "status": "edited",
        "message_id": "message-1",
        "channel_id": "1234567890",
        "content": "**SouthViking**\nupdated\n\n-# sent using Discord Bridge",
        "author_username": "bridge-bot",
    }
    assert fake_client.edited_payloads == [
        (
            "1234567890",
            "message-1",
            "**SouthViking**\nupdated\n\n-# sent using Discord Bridge",
        )
    ]


@pytest.mark.asyncio
async def test_discord_send_message_can_disable_attribution() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_send_message(
        channel_id="1234567890",
        content="plain message",
        settings=make_settings(
            discord_bot_token="token",
            discord_append_attribution=False,
        ),
        client=fake_client,
    )

    assert result["content"] == "plain message"
