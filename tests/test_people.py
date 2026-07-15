from typing import Any, cast

import pytest

from discord_mcp_bridge.config import Settings
from discord_mcp_bridge.errors import DiscordConfigurationError, DiscordPermissionError
from discord_mcp_bridge.tools.people import (
    _discord_get_current_bot_user,
    _discord_get_member,
    _discord_get_user,
    _discord_list_roles,
    _discord_search_members,
)


def make_settings(**kwargs: object) -> Settings:
    settings_ctor = cast(Any, Settings)
    return cast(Settings, settings_ctor(_env_file=None, **kwargs))


class FakeDiscordPeopleClient:
    def __init__(self) -> None:
        self.closed = False
        self.search_calls: list[tuple[str, str, int]] = []
        self.user: dict[str, object] = {
            "id": "user-1",
            "username": "southviking",
            "global_name": "SouthViking",
            "discriminator": "0",
            "avatar": "avatar-hash",
            "bot": False,
            "system": False,
            "public_flags": 64,
        }
        self.member: dict[str, object] = {
            "user": self.user,
            "nick": "Viking",
            "avatar": None,
            "roles": ["guild-1", "role-1"],
            "joined_at": "2026-07-01T12:00:00+00:00",
            "premium_since": None,
            "pending": False,
            "communication_disabled_until": None,
            "deaf": False,
            "mute": False,
            "flags": 0,
        }
        self.roles: list[dict[str, object]] = [
            {
                "id": "guild-1",
                "name": "@everyone",
                "position": 0,
                "permissions": "1024",
                "color": 0,
                "managed": False,
                "mentionable": False,
                "hoist": False,
                "flags": 0,
            },
            {
                "id": "role-1",
                "name": "Developer",
                "description": "Builds integrations",
                "position": 5,
                "permissions": "3072",
                "color": 5793266,
                "managed": False,
                "mentionable": True,
                "hoist": True,
                "flags": 0,
            },
        ]

    async def get_current_user(self) -> dict[str, object]:
        return {**self.user, "id": "bot-1", "username": "VirtualViking", "bot": True}

    async def get_user(self, user_id: str) -> dict[str, object]:
        assert user_id == "user-1"
        return self.user

    async def get_guild_member(
        self,
        *,
        guild_id: str,
        user_id: str,
    ) -> dict[str, object]:
        assert guild_id == "guild-1"
        assert user_id == "user-1"
        return self.member

    async def search_guild_members(
        self,
        *,
        guild_id: str,
        query: str,
        limit: int,
    ) -> list[dict[str, object]]:
        self.search_calls.append((guild_id, query, limit))
        return [self.member]

    async def list_guild_roles(self, guild_id: str) -> list[dict[str, object]]:
        assert guild_id == "guild-1"
        return self.roles

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_discord_get_current_bot_user_requires_token() -> None:
    with pytest.raises(DiscordConfigurationError, match="DISCORD_BOT_TOKEN is required"):
        await _discord_get_current_bot_user(
            settings=make_settings(discord_bot_token=None),
        )


@pytest.mark.asyncio
async def test_discord_get_current_bot_user_returns_identity() -> None:
    result = await _discord_get_current_bot_user(
        settings=make_settings(discord_bot_token="token"),
        client=FakeDiscordPeopleClient(),
    )

    user = cast(dict[str, object], result["user"])
    assert result["status"] == "ok"
    assert user["id"] == "bot-1"
    assert user["username"] == "VirtualViking"
    assert user["display_name"] == "SouthViking"
    assert user["bot"] is True


@pytest.mark.asyncio
async def test_discord_get_user_returns_public_profile() -> None:
    result = await _discord_get_user(
        user_id="user-1",
        settings=make_settings(discord_bot_token="token"),
        client=FakeDiscordPeopleClient(),
    )

    assert result == {
        "status": "ok",
        "user": {
            "id": "user-1",
            "username": "southviking",
            "global_name": "SouthViking",
            "display_name": "SouthViking",
            "discriminator": "0",
            "avatar": "avatar-hash",
            "bot": False,
            "system": False,
            "public_flags": 64,
        },
    }


@pytest.mark.asyncio
async def test_discord_get_member_resolves_role_names() -> None:
    result = await _discord_get_member(
        user_id="user-1",
        settings=make_settings(
            discord_bot_token="token",
            discord_default_guild_id="guild-1",
        ),
        client=FakeDiscordPeopleClient(),
    )

    member = cast(dict[str, object], result["member"])
    roles = cast(list[dict[str, object]], member["roles"])
    assert result["guild_id"] == "guild-1"
    assert member["display_name"] == "Viking"
    assert member["role_ids"] == ["guild-1", "role-1"]
    assert [role["name"] for role in roles] == ["@everyone", "Developer"]


@pytest.mark.asyncio
async def test_discord_get_member_respects_guild_allowlist() -> None:
    with pytest.raises(DiscordPermissionError, match="not in DISCORD_ALLOWED_GUILDS"):
        await _discord_get_member(
            user_id="user-1",
            guild_id="guild-1",
            settings=make_settings(
                discord_bot_token="token",
                discord_allowed_guilds="guild-2",
            ),
            client=FakeDiscordPeopleClient(),
        )


@pytest.mark.asyncio
async def test_discord_search_members_bounds_and_normalizes_query() -> None:
    fake_client = FakeDiscordPeopleClient()

    result = await _discord_search_members(
        query="  South  ",
        guild_id="guild-1",
        limit=10,
        resolve_roles=False,
        settings=make_settings(discord_bot_token="token"),
        client=fake_client,
    )

    member = cast(dict[str, object], cast(list[object], result["members"])[0])
    assert result["query"] == "South"
    assert result["count"] == 1
    assert "roles" not in member
    assert fake_client.search_calls == [("guild-1", "South", 10)]

    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        await _discord_search_members(
            query="South",
            guild_id="guild-1",
            limit=101,
            settings=make_settings(discord_bot_token="token"),
            client=fake_client,
        )


@pytest.mark.asyncio
async def test_discord_list_roles_orders_highest_role_first() -> None:
    result = await _discord_list_roles(
        guild_id="guild-1",
        settings=make_settings(discord_bot_token="token"),
        client=FakeDiscordPeopleClient(),
    )

    roles = cast(list[dict[str, object]], result["roles"])
    assert result["count"] == 2
    assert [role["name"] for role in roles] == ["Developer", "@everyone"]
