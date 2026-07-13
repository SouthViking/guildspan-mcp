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
