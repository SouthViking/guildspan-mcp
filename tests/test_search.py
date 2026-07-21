from collections.abc import Sequence
from typing import Any, cast

import pytest

from discord_mcp_bridge.config import Settings
from discord_mcp_bridge.discord_client import (
    DiscordChannel,
    DiscordMessage,
    DiscordThread,
    DiscordUpload,
)
from discord_mcp_bridge.errors import DiscordConfigurationError
from discord_mcp_bridge.tools.search import _discord_search_messages


def make_settings(**kwargs: object) -> Settings:
    settings_ctor = cast(Any, Settings)
    return cast(Settings, settings_ctor(_env_file=None, **kwargs))


def make_message(
    *,
    message_id: str,
    channel_id: str,
    content: str,
    author_id: str = "user-1",
    attachments: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "id": message_id,
        "channel_id": channel_id,
        "guild_id": "guild-1",
        "type": 0,
        "content": content,
        "timestamp": "2026-07-12T12:00:00.000000+00:00",
        "edited_timestamp": None,
        "pinned": False,
        "mention_everyone": False,
        "author": {
            "id": author_id,
            "username": "alice",
            "global_name": "Alice",
            "bot": False,
        },
        "attachments": attachments or [],
        "embeds": [],
        "mentions": [],
        "mention_roles": [],
    }


class FakeDiscordClient:
    def __init__(self) -> None:
        self.channels = [
            DiscordChannel(
                id="channel-1",
                name="general",
                guild_id="guild-1",
                type=0,
                position=1,
            ),
            DiscordChannel(
                id="channel-2",
                name="dev",
                guild_id="guild-1",
                type=0,
                position=2,
            ),
        ]
        self.messages = [
            make_message(message_id="104", channel_id="channel-2", content="deploy done"),
            make_message(
                message_id="103",
                channel_id="channel-2",
                content="deploy screenshot",
                attachments=[{"id": "attachment-1", "filename": "shot.png"}],
            ),
            make_message(message_id="102", channel_id="channel-1", content="standup notes"),
            make_message(message_id="101", channel_id="channel-1", content="deploy failed"),
        ]
        self.closed = False

    async def get_channel(self, channel_id: str) -> DiscordChannel:
        for channel in self.channels:
            if channel.id == channel_id:
                return channel
        return DiscordChannel(
            id=channel_id,
            name=None,
            guild_id="guild-1",
            type=0,
            position=None,
        )

    async def list_guild_channels(self, guild_id: str) -> list[DiscordChannel]:
        return [channel for channel in self.channels if channel.guild_id == guild_id]

    async def list_channel_messages(
        self,
        *,
        channel_id: str,
        limit: int,
        before: str | None = None,
        after: str | None = None,
        around: str | None = None,
    ) -> list[dict[str, object]]:
        messages = [
            message
            for message in self.messages
            if cast(str, message["channel_id"]) == channel_id
        ]
        messages = sorted(messages, key=lambda message: int(cast(str, message["id"])), reverse=True)
        return messages[:limit]

    async def send_message(
        self,
        *,
        channel_id: str,
        content: str | None,
        attachments: Sequence[DiscordUpload] = (),
        sticker_ids: Sequence[str] = (),
    ) -> DiscordMessage:
        raise AssertionError("send_message should not be called by discord_search_messages")

    async def edit_message(
        self,
        *,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> DiscordMessage:
        raise AssertionError("edit_message should not be called by discord_search_messages")

    async def add_reaction(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        raise AssertionError("add_reaction should not be called by discord_search_messages")

    async def create_thread(
        self,
        *,
        channel_id: str,
        name: str,
        message_id: str | None = None,
        auto_archive_duration: int = 1440,
    ) -> DiscordThread:
        raise AssertionError("create_thread should not be called by discord_search_messages")

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_discord_search_messages_requires_bot_token() -> None:
    with pytest.raises(DiscordConfigurationError, match="DISCORD_BOT_TOKEN is required"):
        await _discord_search_messages(
            contains="deploy",
            channel_ids=["channel-1"],
            settings=make_settings(discord_bot_token=None),
        )


@pytest.mark.asyncio
async def test_discord_search_messages_searches_visible_guild_channels() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_search_messages(
        contains="DEPLOY",
        guild_id="guild-1",
        settings=make_settings(
            discord_bot_token="token",
            discord_allowed_channels="channel-2",
        ),
        client=fake_client,
    )

    messages = cast(list[dict[str, object]], result["messages"])
    assert result["status"] == "ok"
    assert result["count"] == 2
    assert result["channels_searched"] == 1
    assert [message["id"] for message in messages] == ["104", "103"]


@pytest.mark.asyncio
async def test_discord_search_messages_filters_author_and_attachments() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_search_messages(
        contains="deploy",
        channel_ids=["channel-1", "channel-2"],
        author_id="user-1",
        has_attachments=True,
        settings=make_settings(discord_bot_token="token"),
        client=fake_client,
    )

    messages = cast(list[dict[str, object]], result["messages"])
    assert [message["id"] for message in messages] == ["103"]
