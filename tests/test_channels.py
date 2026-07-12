from typing import Any, cast

import pytest

from discord_mcp_bridge.config import Settings
from discord_mcp_bridge.discord_client import DiscordChannel, DiscordMessage
from discord_mcp_bridge.errors import DiscordConfigurationError, DiscordPermissionError
from discord_mcp_bridge.tools.channels import _discord_list_channels


def make_settings(**kwargs: object) -> Settings:
    settings_ctor = cast(Any, Settings)
    return cast(Settings, settings_ctor(_env_file=None, **kwargs))


class FakeDiscordClient:
    def __init__(self, *, channels: list[DiscordChannel] | None = None) -> None:
        self.channels = channels or [
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

    async def send_message(self, *, channel_id: str, content: str) -> DiscordMessage:
        raise AssertionError("send_message should not be called by discord_list_channels")

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_discord_list_channels_requires_bot_token() -> None:
    with pytest.raises(DiscordConfigurationError, match="DISCORD_BOT_TOKEN is required"):
        await _discord_list_channels(
            guild_id="guild-1",
            settings=make_settings(discord_bot_token=None),
        )


@pytest.mark.asyncio
async def test_discord_list_channels_rejects_blank_guild_id() -> None:
    with pytest.raises(
        ValueError,
        match="guild_id is required unless DISCORD_DEFAULT_GUILD_ID is configured",
    ):
        await _discord_list_channels(
            guild_id=" ",
            settings=make_settings(discord_bot_token="token"),
        )


@pytest.mark.asyncio
async def test_discord_list_channels_uses_default_guild_id() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_list_channels(
        guild_id=None,
        settings=make_settings(
            discord_bot_token="token",
            discord_default_guild_id="guild-1",
        ),
        client=fake_client,
    )

    assert result["guild_id"] == "guild-1"
    assert result["count"] == 2


@pytest.mark.asyncio
async def test_discord_list_channels_returns_channels_sorted_by_position() -> None:
    fake_client = FakeDiscordClient(
        channels=[
            DiscordChannel(
                id="channel-2",
                name="dev",
                guild_id="guild-1",
                type=0,
                position=2,
            ),
            DiscordChannel(
                id="channel-1",
                name="general",
                guild_id="guild-1",
                type=0,
                position=1,
            ),
        ]
    )

    result = await _discord_list_channels(
        guild_id="guild-1",
        settings=make_settings(discord_bot_token="token"),
        client=fake_client,
    )

    assert result == {
        "status": "ok",
        "guild_id": "guild-1",
        "count": 2,
        "channels": [
            {
                "id": "channel-1",
                "name": "general",
                "guild_id": "guild-1",
                "type": 0,
                "position": 1,
            },
            {
                "id": "channel-2",
                "name": "dev",
                "guild_id": "guild-1",
                "type": 0,
                "position": 2,
            },
        ],
    }


@pytest.mark.asyncio
async def test_discord_list_channels_filters_channel_allowlist() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_list_channels(
        guild_id="guild-1",
        settings=make_settings(
            discord_bot_token="token",
            discord_allowed_channels="channel-2",
        ),
        client=fake_client,
    )

    assert result["count"] == 1
    assert result["channels"] == [
        {
            "id": "channel-2",
            "name": "dev",
            "guild_id": "guild-1",
            "type": 0,
            "position": 2,
        }
    ]


@pytest.mark.asyncio
async def test_discord_list_channels_blocks_non_allowed_guild() -> None:
    fake_client = FakeDiscordClient()

    with pytest.raises(DiscordPermissionError, match="not in DISCORD_ALLOWED_GUILDS"):
        await _discord_list_channels(
            guild_id="guild-1",
            settings=make_settings(
                discord_bot_token="token",
                discord_allowed_guilds="guild-2",
            ),
            client=fake_client,
        )
