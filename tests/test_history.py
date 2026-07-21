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
from discord_mcp_bridge.errors import DiscordConfigurationError, DiscordPermissionError
from discord_mcp_bridge.tools.history import _discord_read_messages


def make_settings(**kwargs: object) -> Settings:
    settings_ctor = cast(Any, Settings)
    return cast(Settings, settings_ctor(_env_file=None, **kwargs))


def make_message(
    *,
    message_id: str,
    content: str,
    author_id: str = "user-1",
    username: str = "alice",
    channel_id: str = "channel-1",
    attachments: list[dict[str, object]] | None = None,
    embeds: list[dict[str, object]] | None = None,
    stickers: list[dict[str, object]] | None = None,
    poll: dict[str, object] | None = None,
    components: list[dict[str, object]] | None = None,
    mentions: list[dict[str, object]] | None = None,
    pinned: bool = False,
    message_type: int = 0,
) -> dict[str, object]:
    return {
        "id": message_id,
        "channel_id": channel_id,
        "guild_id": "guild-1",
        "type": message_type,
        "content": content,
        "timestamp": "2026-07-12T12:00:00.000000+00:00",
        "edited_timestamp": None,
        "pinned": pinned,
        "mention_everyone": False,
        "author": {
            "id": author_id,
            "username": username,
            "global_name": username.title(),
            "bot": False,
        },
        "attachments": attachments or [],
        "embeds": embeds or [],
        "sticker_items": stickers or [],
        "poll": poll,
        "components": components or [],
        "mentions": mentions or [],
        "mention_roles": [],
    }


class FakeDiscordClient:
    def __init__(self, *, messages: list[dict[str, object]]) -> None:
        self.messages = messages
        self.calls: list[dict[str, object]] = []
        self.closed = False

    async def get_channel(self, channel_id: str) -> DiscordChannel:
        return DiscordChannel(
            id=channel_id,
            name="general",
            guild_id="guild-1",
            type=0,
            position=0,
        )

    async def list_guild_channels(self, guild_id: str) -> list[DiscordChannel]:
        raise AssertionError("list_guild_channels should not be called by discord_read_messages")

    async def list_channel_messages(
        self,
        *,
        channel_id: str,
        limit: int,
        before: str | None = None,
        after: str | None = None,
        around: str | None = None,
    ) -> list[dict[str, object]]:
        self.calls.append(
            {
                "channel_id": channel_id,
                "limit": limit,
                "before": before,
                "after": after,
                "around": around,
            }
        )
        messages = sorted(
            self.messages,
            key=lambda message: int(cast(str, message["id"])),
            reverse=True,
        )
        if around is not None:
            return [
                message
                for message in messages
                if abs(int(cast(str, message["id"])) - int(around)) <= 1
            ][:limit]
        if before is not None:
            messages = [
                message
                for message in messages
                if int(cast(str, message["id"])) < int(before)
            ]
        if after is not None:
            messages = [
                message
                for message in messages
                if int(cast(str, message["id"])) > int(after)
            ]
        return messages[:limit]

    async def send_message(
        self,
        *,
        channel_id: str,
        content: str | None,
        attachments: Sequence[DiscordUpload] = (),
        sticker_ids: Sequence[str] = (),
    ) -> DiscordMessage:
        raise AssertionError("send_message should not be called by discord_read_messages")

    async def edit_message(
        self,
        *,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> DiscordMessage:
        raise AssertionError("edit_message should not be called by discord_read_messages")

    async def add_reaction(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        raise AssertionError("add_reaction should not be called by discord_read_messages")

    async def create_thread(
        self,
        *,
        channel_id: str,
        name: str,
        message_id: str | None = None,
        auto_archive_duration: int = 1440,
    ) -> DiscordThread:
        raise AssertionError("create_thread should not be called by discord_read_messages")

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_discord_read_messages_requires_bot_token() -> None:
    with pytest.raises(DiscordConfigurationError, match="DISCORD_BOT_TOKEN is required"):
        await _discord_read_messages(
            channel_id="channel-1",
            settings=make_settings(discord_bot_token=None),
        )


@pytest.mark.asyncio
async def test_discord_read_messages_rejects_around_with_before() -> None:
    with pytest.raises(ValueError, match="around cannot be combined"):
        await _discord_read_messages(
            channel_id="channel-1",
            before="123",
            around="124",
            settings=make_settings(discord_bot_token="token"),
        )


@pytest.mark.asyncio
async def test_discord_read_messages_filters_and_summarizes_context() -> None:
    fake_client = FakeDiscordClient(
        messages=[
            make_message(message_id="103", content="deploy failed", author_id="user-2"),
            make_message(
                message_id="102",
                content="deploy done",
                attachments=[
                    {
                        "id": "attachment-1",
                        "filename": "screenshot.png",
                        "url": "https://cdn.example/screenshot.png",
                        "proxy_url": "https://proxy.example/screenshot.png",
                        "content_type": "image/png",
                        "size": 123,
                        "width": 800,
                        "height": 600,
                        "description": "deploy result",
                    }
                ],
                embeds=[
                    {
                        "type": "rich",
                        "title": "Deploy",
                        "image": {
                            "url": "https://example.com/full.png",
                            "proxy_url": "https://proxy.example/full.png",
                            "width": 800,
                            "height": 600,
                            "content_type": "image/png",
                        },
                        "thumbnail": {"url": "https://example.com/thumb.png"},
                        "video": {
                            "url": "https://example.com/demo.mp4",
                            "width": 1920,
                            "height": 1080,
                        },
                    }
                ],
                stickers=[{"id": "sticker-1", "name": "Ship it", "format_type": 1}],
                poll={
                    "question": {"text": "Ship?"},
                    "answers": [{"answer_id": 1, "poll_media": {"text": "Yes"}}],
                },
                components=[
                    {
                        "type": 1,
                        "components": [{"type": 2, "label": "Details", "custom_id": "details"}],
                    }
                ],
                mentions=[{"id": "user-9", "username": "bob", "bot": False}],
            ),
            make_message(message_id="101", content="hello"),
        ]
    )

    result = await _discord_read_messages(
        channel_id="channel-1",
        limit=5,
        author_id="user-1",
        contains="DEPLOY",
        has_attachments=True,
        mentions_user_id="user-9",
        settings=make_settings(discord_bot_token="token"),
        client=fake_client,
    )

    assert result["status"] == "ok"
    assert result["count"] == 1
    assert result["scanned_count"] == 3
    assert result["next_before"] == "101"
    messages = cast(list[dict[str, object]], result["messages"])
    assert messages[0]["id"] == "102"
    assert messages[0]["content"] == "deploy done"
    assert messages[0]["author"] == {
        "id": "user-1",
        "username": "alice",
        "global_name": "Alice",
        "bot": False,
    }
    assert messages[0]["attachments"] == [
        {
            "id": "attachment-1",
            "filename": "screenshot.png",
            "title": None,
            "description": "deploy result",
            "url": "https://cdn.example/screenshot.png",
            "proxy_url": "https://proxy.example/screenshot.png",
            "content_type": "image/png",
            "size": 123,
            "width": 800,
            "height": 600,
            "ephemeral": None,
            "duration_secs": None,
            "waveform": None,
            "flags": None,
            "placeholder": None,
            "placeholder_version": None,
            "clip_created_at": None,
            "application": None,
            "clip_participants": [],
        }
    ]
    assert messages[0]["embeds"] == [
        {
            "type": "rich",
            "title": "Deploy",
            "description": None,
            "url": None,
            "timestamp": None,
            "color": None,
            "footer": None,
            "image": {
                "url": "https://example.com/full.png",
                "proxy_url": "https://proxy.example/full.png",
                "height": 600,
                "width": 800,
                "content_type": "image/png",
                "placeholder": None,
                "placeholder_version": None,
                "flags": None,
            },
            "thumbnail": {
                "url": "https://example.com/thumb.png",
                "proxy_url": None,
                "height": None,
                "width": None,
                "content_type": None,
                "placeholder": None,
                "placeholder_version": None,
                "flags": None,
            },
            "video": {
                "url": "https://example.com/demo.mp4",
                "proxy_url": None,
                "height": 1080,
                "width": 1920,
                "content_type": None,
                "placeholder": None,
                "placeholder_version": None,
                "flags": None,
            },
            "provider": None,
            "author": None,
            "fields": [],
        }
    ]
    assert messages[0]["stickers"] == [
        {"id": "sticker-1", "name": "Ship it", "format_type": 1}
    ]
    assert messages[0]["poll"] == {
        "question": {"text": "Ship?"},
        "answers": [{"answer_id": 1, "poll_media": {"text": "Yes"}}],
    }
    assert messages[0]["components"] == [
        {
            "type": 1,
            "components": [{"type": 2, "label": "Details", "custom_id": "details"}],
        }
    ]


@pytest.mark.asyncio
async def test_discord_read_messages_can_omit_new_multimedia_sections() -> None:
    fake_client = FakeDiscordClient(
        messages=[make_message(message_id="101", content="media")]
    )

    result = await _discord_read_messages(
        channel_id="channel-1",
        include_stickers=False,
        include_poll=False,
        include_components=False,
        settings=make_settings(discord_bot_token="token"),
        client=fake_client,
    )

    messages = cast(list[dict[str, object]], result["messages"])
    assert "stickers" not in messages[0]
    assert "poll" not in messages[0]
    assert "components" not in messages[0]


@pytest.mark.asyncio
async def test_discord_read_messages_paginates_between_before_and_after() -> None:
    fake_client = FakeDiscordClient(
        messages=[
            make_message(message_id=str(message_id), content=f"message {message_id}")
            for message_id in range(100, 107)
        ]
    )

    result = await _discord_read_messages(
        channel_id="channel-1",
        limit=3,
        scan_limit=6,
        page_size=2,
        before="106",
        after="101",
        settings=make_settings(discord_bot_token="token"),
        client=fake_client,
    )

    messages = cast(list[dict[str, object]], result["messages"])
    assert [message["id"] for message in messages] == ["105", "104", "103"]
    assert result["next_before"] == "103"
    assert fake_client.calls == [
        {
            "channel_id": "channel-1",
            "limit": 2,
            "before": "106",
            "after": None,
            "around": None,
        },
        {
            "channel_id": "channel-1",
            "limit": 2,
            "before": "104",
            "after": None,
            "around": None,
        },
    ]


@pytest.mark.asyncio
async def test_discord_read_messages_can_return_oldest_first() -> None:
    fake_client = FakeDiscordClient(
        messages=[
            make_message(message_id=str(message_id), content=f"message {message_id}")
            for message_id in range(100, 104)
        ]
    )

    result = await _discord_read_messages(
        channel_id="channel-1",
        limit=3,
        oldest_first=True,
        settings=make_settings(discord_bot_token="token"),
        client=fake_client,
    )

    messages = cast(list[dict[str, object]], result["messages"])
    assert [message["id"] for message in messages] == ["101", "102", "103"]
    assert result["next_before"] == "101"


@pytest.mark.asyncio
async def test_discord_read_messages_respects_allowed_channels() -> None:
    fake_client = FakeDiscordClient(messages=[])

    with pytest.raises(DiscordPermissionError, match="not in DISCORD_ALLOWED_CHANNELS"):
        await _discord_read_messages(
            channel_id="channel-1",
            settings=make_settings(
                discord_bot_token="token",
                discord_allowed_channels="channel-2",
            ),
            client=fake_client,
        )
