from collections.abc import Sequence
from typing import Any, cast

import pytest

from guildspan.config import Settings
from guildspan.discord_client import (
    DiscordChannel,
    DiscordMessage,
    DiscordThread,
    DiscordUpload,
)
from guildspan.errors import DiscordConfigurationError, DiscordPermissionError
from guildspan.tools.threads import _discord_create_thread


def make_settings(**kwargs: object) -> Settings:
    settings_ctor = cast(Any, Settings)
    return cast(Settings, settings_ctor(_env_file=None, **kwargs))


class FakeDiscordClient:
    def __init__(self) -> None:
        self.thread_calls: list[dict[str, object]] = []
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
        raise AssertionError(
            "list_guild_channels should not be called by discord_create_thread"
        )

    async def list_channel_messages(
        self,
        *,
        channel_id: str,
        limit: int,
        before: str | None = None,
        after: str | None = None,
        around: str | None = None,
    ) -> list[dict[str, object]]:
        raise AssertionError(
            "list_channel_messages should not be called by discord_create_thread"
        )

    async def send_message(
        self,
        *,
        channel_id: str,
        content: str | None,
        attachments: Sequence[DiscordUpload] = (),
        sticker_ids: Sequence[str] = (),
    ) -> DiscordMessage:
        raise AssertionError(
            "send_message should not be called by discord_create_thread"
        )

    async def edit_message(
        self,
        *,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> DiscordMessage:
        raise AssertionError(
            "edit_message should not be called by discord_create_thread"
        )

    async def add_reaction(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        raise AssertionError(
            "add_reaction should not be called by discord_create_thread"
        )

    async def create_thread(
        self,
        *,
        channel_id: str,
        name: str,
        message_id: str | None = None,
        auto_archive_duration: int = 1440,
    ) -> DiscordThread:
        self.thread_calls.append(
            {
                "channel_id": channel_id,
                "name": name,
                "message_id": message_id,
                "auto_archive_duration": auto_archive_duration,
            }
        )
        return DiscordThread(
            id="thread-1",
            name=name,
            parent_id=channel_id,
            guild_id="guild-1",
            type=11,
        )

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_discord_create_thread_requires_bot_token() -> None:
    with pytest.raises(
        DiscordConfigurationError, match="DISCORD_BOT_TOKEN is required"
    ):
        await _discord_create_thread(
            channel_id="channel-1",
            name="Incident follow-up",
            settings=make_settings(discord_bot_token=None),
        )


@pytest.mark.asyncio
async def test_discord_create_thread_from_channel() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_create_thread(
        channel_id="channel-1",
        name="Incident follow-up",
        settings=make_settings(discord_bot_token="token"),
        client=fake_client,
    )

    assert result == {
        "status": "created",
        "thread_id": "thread-1",
        "channel_id": "thread-1",
        "name": "Incident follow-up",
        "parent_channel_id": "channel-1",
        "guild_id": "guild-1",
        "type": 11,
    }
    assert fake_client.thread_calls == [
        {
            "channel_id": "channel-1",
            "name": "Incident follow-up",
            "message_id": None,
            "auto_archive_duration": 1440,
        }
    ]


@pytest.mark.asyncio
async def test_discord_create_thread_from_message() -> None:
    fake_client = FakeDiscordClient()

    await _discord_create_thread(
        channel_id="channel-1",
        message_id="message-1",
        name="Incident follow-up",
        auto_archive_duration=60,
        settings=make_settings(discord_bot_token="token"),
        client=fake_client,
    )

    assert fake_client.thread_calls == [
        {
            "channel_id": "channel-1",
            "name": "Incident follow-up",
            "message_id": "message-1",
            "auto_archive_duration": 60,
        }
    ]


@pytest.mark.asyncio
async def test_discord_create_thread_respects_allowed_guilds() -> None:
    fake_client = FakeDiscordClient()

    with pytest.raises(DiscordPermissionError, match="not in DISCORD_ALLOWED_GUILDS"):
        await _discord_create_thread(
            channel_id="channel-1",
            name="Incident follow-up",
            settings=make_settings(
                discord_bot_token="token",
                discord_allowed_guilds="guild-2",
            ),
            client=fake_client,
        )
