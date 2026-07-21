import json

import httpx
import pytest

from discord_mcp_bridge.discord_client import DiscordClient, DiscordUpload
from discord_mcp_bridge.errors import DiscordPermissionError


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


@pytest.mark.asyncio
async def test_discord_client_fetches_one_message() -> None:
    requested_urls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(
            status_code=200,
            json={"id": "message-1", "attachments": []},
        )

    client = DiscordClient(
        bot_token="token",
        base_url="https://discord.example/api/v10",
        transport=httpx.MockTransport(handler),
    )

    try:
        message = await client.get_channel_message(
            channel_id="channel-1",
            message_id="message-1",
        )
    finally:
        await client.aclose()

    assert message["id"] == "message-1"
    assert requested_urls == [
        "https://discord.example/api/v10/channels/channel-1/messages/message-1"
    ]


@pytest.mark.asyncio
async def test_discord_client_sends_json_text_and_stickers() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = json.loads(request.content)
        return httpx.Response(
            status_code=200,
            json={
                "id": "message-1",
                "channel_id": "channel-1",
                "content": payload.get("content", ""),
                "author": {"username": "bridge-bot"},
                "attachments": [],
                "sticker_items": [
                    {"id": sticker_id, "name": "wave", "format_type": 1}
                    for sticker_id in payload.get("sticker_ids", [])
                ],
            },
        )

    client = DiscordClient(
        bot_token="token",
        base_url="https://discord.example/api/v10",
        transport=httpx.MockTransport(handler),
    )
    try:
        message = await client.send_message(
            channel_id="channel-1",
            content="hello",
            sticker_ids=["sticker-1"],
        )
    finally:
        await client.aclose()

    assert json.loads(requests[0].content) == {
        "content": "hello",
        "sticker_ids": ["sticker-1"],
    }
    assert requests[0].headers["Content-Type"] == "application/json"
    assert message.content == "hello"
    assert message.stickers[0]["id"] == "sticker-1"


@pytest.mark.asyncio
async def test_discord_client_sends_multipart_attachments() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            status_code=200,
            json={
                "id": "message-1",
                "channel_id": "channel-1",
                "content": "look",
                "author": {"username": "bridge-bot"},
                "attachments": [
                    {
                        "id": "attachment-1",
                        "filename": "image.png",
                        "content_type": "image/png",
                        "size": 3,
                    }
                ],
                "sticker_items": [],
            },
        )

    client = DiscordClient(
        bot_token="token",
        base_url="https://discord.example/api/v10",
        transport=httpx.MockTransport(handler),
    )
    try:
        message = await client.send_message(
            channel_id="channel-1",
            content="look",
            attachments=[
                DiscordUpload(
                    data=b"PNG",
                    filename="image.png",
                    content_type="image/png",
                    description="A diagram",
                )
            ],
        )
    finally:
        await client.aclose()

    content_type = requests[0].headers["Content-Type"]
    body = requests[0].content
    assert content_type.startswith("multipart/form-data; boundary=")
    assert b'name="payload_json"' in body
    assert b'"content": "look"' in body
    assert b'"filename": "image.png"' in body
    assert b'"description": "A diagram"' in body
    assert b'name="files[0]"; filename="image.png"' in body
    assert b"Content-Type: image/png" in body
    assert b"PNG" in body
    assert message.attachments[0]["filename"] == "image.png"


@pytest.mark.asyncio
async def test_discord_client_reports_actionable_upload_permission_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=403,
            json={"message": "Missing Permissions", "code": 50013},
        )

    client = DiscordClient(
        bot_token="token",
        base_url="https://discord.example/api/v10",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(
            DiscordPermissionError,
            match="SEND_MESSAGES, ATTACH_FILES",
        ):
            await client.send_message(
                channel_id="channel-1",
                content=None,
                attachments=[
                    DiscordUpload(
                        data=b"file",
                        filename="file.bin",
                        content_type="application/octet-stream",
                    )
                ],
            )
    finally:
        await client.aclose()
