import httpx
import pytest

from discord_mcp_bridge.discord_client import DiscordClient


@pytest.mark.asyncio
async def test_discord_client_url_encodes_reaction_emoji() -> None:
    requested_urls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(status_code=204)

    client = DiscordClient(
        bot_token="token",
        base_url="https://discord.example/api/v10",
        transport=httpx.MockTransport(handler),
    )

    try:
        await client.add_reaction(
            channel_id="channel-1",
            message_id="message-1",
            emoji="🚀",
        )
    finally:
        await client.aclose()

    assert requested_urls == [
        "https://discord.example/api/v10/channels/channel-1/messages/message-1/reactions/%F0%9F%9A%80/@me"
    ]


@pytest.mark.asyncio
async def test_discord_client_calls_read_only_people_endpoints() -> None:
    requested_urls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.path.endswith("/roles"):
            return httpx.Response(status_code=200, json=[{"id": "role-1"}])
        if request.url.path.endswith("/members/search"):
            return httpx.Response(status_code=200, json=[{"user": {"id": "user-1"}}])
        if "/members/" in request.url.path:
            return httpx.Response(status_code=200, json={"user": {"id": "user-1"}})
        return httpx.Response(status_code=200, json={"id": "user-1"})

    client = DiscordClient(
        bot_token="token",
        base_url="https://discord.example/api/v10",
        transport=httpx.MockTransport(handler),
    )

    try:
        await client.get_current_user()
        await client.get_user("user-1")
        await client.get_guild_member(guild_id="guild-1", user_id="user-1")
        await client.search_guild_members(guild_id="guild-1", query="South", limit=25)
        await client.list_guild_roles("guild-1")
    finally:
        await client.aclose()

    assert requested_urls == [
        "https://discord.example/api/v10/users/@me",
        "https://discord.example/api/v10/users/user-1",
        "https://discord.example/api/v10/guilds/guild-1/members/user-1",
        "https://discord.example/api/v10/guilds/guild-1/members/search?query=South&limit=25",
        "https://discord.example/api/v10/guilds/guild-1/roles",
    ]
