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
from discord_mcp_bridge.tools.diagnostics import _discord_health_check


def make_settings(**kwargs: object) -> Settings:
    settings_ctor = cast(Any, Settings)
    return cast(Settings, settings_ctor(_env_file=None, **kwargs))


class FakeDiscordClient:
    def __init__(self) -> None:
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
        return [
            DiscordChannel(
                id="channel-1",
                name="general",
                guild_id=guild_id,
                type=0,
                position=0,
            )
        ]

    async def list_channel_messages(
        self,
        *,
        channel_id: str,
        limit: int,
        before: str | None = None,
        after: str | None = None,
        around: str | None = None,
    ) -> list[dict[str, object]]:
        raise AssertionError("list_channel_messages should not be called by discord_health_check")

    async def send_message(
        self,
        *,
        channel_id: str,
        content: str | None,
        attachments: Sequence[DiscordUpload] = (),
        sticker_ids: Sequence[str] = (),
    ) -> DiscordMessage:
        raise AssertionError("send_message should not be called by discord_health_check")

    async def edit_message(
        self,
        *,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> DiscordMessage:
        raise AssertionError("edit_message should not be called by discord_health_check")

    async def add_reaction(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        raise AssertionError("add_reaction should not be called by discord_health_check")

    async def create_thread(
        self,
        *,
        channel_id: str,
        name: str,
        message_id: str | None = None,
        auto_archive_duration: int = 1440,
    ) -> DiscordThread:
        raise AssertionError("create_thread should not be called by discord_health_check")

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_discord_health_check_reports_missing_token_as_degraded() -> None:
    result = await _discord_health_check(
        guild_id="guild-1",
        settings=make_settings(discord_bot_token=None),
    )

    assert result["status"] == "degraded"
    checks = cast(list[dict[str, object]], result["checks"])
    assert checks == [
        {
            "name": "configuration",
            "status": "failed",
            "message": "DISCORD_BOT_TOKEN is required.",
        }
    ]


@pytest.mark.asyncio
async def test_discord_health_check_reports_ok() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_health_check(
        guild_id="guild-1",
        channel_id="channel-1",
        settings=make_settings(discord_bot_token="token"),
        client=fake_client,
    )

    assert result["status"] == "ok"
    assert result["guild_id"] == "guild-1"
    assert result["channel_id"] == "channel-1"
    checks = cast(list[dict[str, object]], result["checks"])
    assert [check["name"] for check in checks] == [
        "configuration",
        "guild_policy",
        "guild_access",
        "channel_access",
    ]


@pytest.mark.asyncio
async def test_discord_health_check_reports_policy_failure_as_degraded() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_health_check(
        guild_id="guild-1",
        channel_id="channel-1",
        settings=make_settings(
            discord_bot_token="token",
            discord_allowed_channels="channel-2",
        ),
        client=fake_client,
    )

    assert result["status"] == "degraded"
    checks = cast(list[dict[str, object]], result["checks"])
    assert checks[-1]["name"] == "channel_access"
    assert checks[-1]["status"] == "failed"
