from __future__ import annotations

from typing import Any, cast

import pytest
from fastmcp.server.auth import AccessToken

from guildspan.authorization import DiscordGuildAccess
from guildspan.errors import DiscordConfigurationError
from guildspan.tools import guilds as guilds_module


class FakeAuthorizationService:
    def __init__(self) -> None:
        self.tokens: list[AccessToken] = []

    async def list_available_guilds(
        self,
        *,
        token: AccessToken,
    ) -> list[DiscordGuildAccess]:
        self.tokens.append(token)
        return [
            DiscordGuildAccess(
                id="guild-1",
                name="Guild One",
                icon_url="https://example.com/icon.png",
                owner=True,
                status="authorized",
            ),
            DiscordGuildAccess(
                id="guild-2",
                name="Guild Two",
                icon_url=None,
                owner=False,
                status="eligible_to_initialize",
            ),
        ]


def access_token() -> AccessToken:
    return AccessToken(
        token="discord-user-token",
        client_id="discord-app",
        scopes=["identify", "guilds"],
        claims={"sub": "user-1"},
    )


@pytest.mark.asyncio
async def test_discord_list_guilds_returns_safe_authorization_states(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = access_token()
    service = FakeAuthorizationService()
    monkeypatch.setattr(guilds_module, "get_access_token", lambda: token)
    monkeypatch.setattr(
        guilds_module,
        "_hosted_authorization",
        lambda: cast(Any, service),
    )

    result = await guilds_module.discord_list_guilds()

    assert result == {
        "status": "ok",
        "count": 2,
        "guilds": [
            {
                "id": "guild-1",
                "name": "Guild One",
                "icon_url": "https://example.com/icon.png",
                "owner": True,
                "authorization_status": "authorized",
                "bot_accessible": True,
            },
            {
                "id": "guild-2",
                "name": "Guild Two",
                "icon_url": None,
                "owner": False,
                "authorization_status": "eligible_to_initialize",
                "bot_accessible": True,
            },
        ],
    }
    assert service.tokens == [token]


@pytest.mark.asyncio
async def test_discord_list_guilds_requires_hosted_oauth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(guilds_module, "get_access_token", lambda: None)

    with pytest.raises(DiscordConfigurationError, match="hosted MCP runtime"):
        await guilds_module.discord_list_guilds()
