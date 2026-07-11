import pytest

from discord_mcp_bridge.errors import DiscordToolNotImplementedError
from discord_mcp_bridge.tools.messages import discord_send_message


@pytest.mark.asyncio
async def test_discord_send_message_is_intentionally_not_implemented() -> None:
    with pytest.raises(DiscordToolNotImplementedError, match="not implemented yet"):
        await discord_send_message(channel_id="1234567890", content="hello")


@pytest.mark.asyncio
async def test_discord_send_message_rejects_blank_channel_id() -> None:
    with pytest.raises(ValueError, match="channel_id is required"):
        await discord_send_message(channel_id=" ", content="hello")


@pytest.mark.asyncio
async def test_discord_send_message_rejects_blank_content() -> None:
    with pytest.raises(ValueError, match="content is required"):
        await discord_send_message(channel_id="1234567890", content=" ")
