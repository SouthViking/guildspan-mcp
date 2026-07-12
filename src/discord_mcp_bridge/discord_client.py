"""Discord REST client helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import httpx

from discord_mcp_bridge.errors import DiscordApiError

DISCORD_API_BASE_URL = "https://discord.com/api/v10"


@dataclass(frozen=True)
class DiscordMessage:
    """Normalized subset of a Discord message response."""

    id: str
    channel_id: str
    content: str
    author_username: str


@dataclass(frozen=True)
class DiscordChannel:
    """Normalized subset of a Discord channel response."""

    id: str
    name: str | None
    guild_id: str | None
    type: int | None
    position: int | None


class DiscordClient:
    """Small async Discord REST client for MCP tools."""

    def __init__(
        self,
        *,
        bot_token: str,
        base_url: str = DISCORD_API_BASE_URL,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bot {bot_token}",
                "Content-Type": "application/json",
                "User-Agent": "discord-mcp-bridge/0.1.0",
            },
            timeout=timeout_seconds,
            transport=transport,
        )

    async def aclose(self) -> None:
        """Close underlying HTTP resources."""

        await self._client.aclose()

    async def get_channel(self, channel_id: str) -> DiscordChannel:
        """Fetch channel metadata for validation and policy checks."""

        response = await self._client.get(f"/channels/{channel_id}")
        data = self._decode_response(response)

        return DiscordChannel(
            id=str(data["id"]),
            name=self._as_optional_str(data.get("name")),
            guild_id=self._as_optional_str(data.get("guild_id")),
            type=self._as_optional_int(data.get("type")),
            position=self._as_optional_int(data.get("position")),
        )

    async def list_guild_channels(self, guild_id: str) -> list[DiscordChannel]:
        """Fetch channels visible to the bot in a guild."""

        response = await self._client.get(f"/guilds/{guild_id}/channels")
        if not response.is_success:
            message = self._extract_error_message(response)
            raise DiscordApiError(
                f"Discord API request failed with status {response.status_code}: {message}"
            )

        payload = response.json()
        if not isinstance(payload, list):
            raise DiscordApiError("Discord response payload was not a JSON array.")

        channels: list[DiscordChannel] = []
        for item in payload:
            if not isinstance(item, dict):
                raise DiscordApiError("Discord channel payload item was not a JSON object.")
            typed_item = cast(dict[str, object], item)
            channel_id = typed_item.get("id")
            if not isinstance(channel_id, (str, int)):
                raise DiscordApiError("Discord channel payload did not include a valid id.")
            channels.append(
                DiscordChannel(
                    id=str(channel_id),
                    name=self._as_optional_str(typed_item.get("name")),
                    guild_id=self._as_optional_str(typed_item.get("guild_id")),
                    type=self._as_optional_int(typed_item.get("type")),
                    position=self._as_optional_int(typed_item.get("position")),
                )
            )
        return channels

    async def send_message(self, *, channel_id: str, content: str) -> DiscordMessage:
        """Send a message to a Discord channel."""

        response = await self._client.post(
            f"/channels/{channel_id}/messages",
            json={"content": content},
        )
        data = self._decode_response(response)
        author_object = data.get("author", {})
        if not isinstance(author_object, dict):
            raise DiscordApiError("Discord response did not include a valid author object.")
        author = cast(dict[str, object], author_object)
        author_username = author.get("username")
        if not isinstance(author_username, str):
            raise DiscordApiError("Discord response did not include a valid author username.")

        return DiscordMessage(
            id=str(data["id"]),
            channel_id=str(data["channel_id"]),
            content=str(data["content"]),
            author_username=author_username,
        )

    def _decode_response(self, response: httpx.Response) -> dict[str, object]:
        if response.is_success:
            payload = response.json()
            if not isinstance(payload, dict):
                raise DiscordApiError("Discord response payload was not a JSON object.")
            return cast(dict[str, object], payload)

        message = self._extract_error_message(response)
        raise DiscordApiError(
            f"Discord API request failed with status {response.status_code}: {message}"
        )

    def _extract_error_message(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text or "unknown error"

        if isinstance(payload, dict):
            typed_payload = cast(dict[str, object], payload)
            message = typed_payload.get("message")
            if isinstance(message, str):
                return message
        return "unknown error"

    def _as_optional_str(self, value: object) -> str | None:
        if isinstance(value, str):
            return value
        return None

    def _as_optional_int(self, value: object) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        return None
