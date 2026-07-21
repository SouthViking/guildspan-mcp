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
from guildspan.tools.reactions import _discord_add_reaction


def make_settings(**kwargs: object) -> Settings:
    settings_ctor = cast(Any, Settings)
    return cast(Settings, settings_ctor(_env_file=None, **kwargs))


class FakeDiscordClient:
    def __init__(self) -> None:
        self.reactions: list[tuple[str, str, str]] = []
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
        raise AssertionError("list_guild_channels should not be called by discord_add_reaction")

    async def list_channel_messages(
        self,
        *,
        channel_id: str,
        limit: int,
        before: str | None = None,
        after: str | None = None,
        around: str | None = None,
    ) -> list[dict[str, object]]:
        raise AssertionError("list_channel_messages should not be called by discord_add_reaction")

    async def send_message(
        self,
        *,
        channel_id: str,
        content: str | None,
        attachments: Sequence[DiscordUpload] = (),
        sticker_ids: Sequence[str] = (),
    ) -> DiscordMessage:
        raise AssertionError("send_message should not be called by discord_add_reaction")

    async def edit_message(
        self,
        *,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> DiscordMessage:
        raise AssertionError("edit_message should not be called by discord_add_reaction")

    async def add_reaction(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        self.reactions.append((channel_id, message_id, emoji))

    async def create_thread(
        self,
        *,
        channel_id: str,
        name: str,
        message_id: str | None = None,
        auto_archive_duration: int = 1440,
    ) -> DiscordThread:
        raise AssertionError("create_thread should not be called by discord_add_reaction")

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_discord_add_reaction_requires_bot_token() -> None:
    with pytest.raises(DiscordConfigurationError, match="DISCORD_BOT_TOKEN is required"):
        await _discord_add_reaction(
            channel_id="channel-1",
            message_id="message-1",
            emoji="👍",
            settings=make_settings(discord_bot_token=None),
        )


@pytest.mark.asyncio
async def test_discord_add_reaction_records_reaction() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_add_reaction(
        channel_id="channel-1",
        message_id="message-1",
        emoji="👍",
        settings=make_settings(discord_bot_token="token"),
        client=fake_client,
    )

    assert result == {
        "status": "reacted",
        "channel_id": "channel-1",
        "message_id": "message-1",
        "emoji": "👍",
    }
    assert fake_client.reactions == [("channel-1", "message-1", "👍")]


@pytest.mark.asyncio
async def test_discord_add_reaction_respects_allowed_channels() -> None:
    fake_client = FakeDiscordClient()

    with pytest.raises(DiscordPermissionError, match="not in DISCORD_ALLOWED_CHANNELS"):
        await _discord_add_reaction(
            channel_id="channel-1",
            message_id="message-1",
            emoji="👍",
            settings=make_settings(
                discord_bot_token="token",
                discord_allowed_channels="channel-2",
            ),
            client=fake_client,
        )
