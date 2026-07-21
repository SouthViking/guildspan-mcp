"""Discord REST client helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Sequence, cast
from urllib.parse import quote

import httpx

from guildspan import __version__
from guildspan.errors import DiscordApiError, DiscordPermissionError

DISCORD_API_BASE_URL = "https://discord.com/api/v10"


@dataclass(frozen=True)
class DiscordMessage:
    """Normalized subset of a Discord message response."""

    id: str
    channel_id: str
    content: str
    author_username: str
    attachments: tuple[dict[str, object], ...] = ()
    stickers: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class DiscordUpload:
    """Validated outgoing file ready for Discord multipart upload."""

    data: bytes
    filename: str
    content_type: str
    description: str | None = None


@dataclass(frozen=True)
class DiscordThread:
    """Normalized subset of a Discord thread channel response."""

    id: str
    name: str | None
    parent_id: str | None
    guild_id: str | None
    type: int | None


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
                "User-Agent": f"guildspan/{__version__}",
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

    async def get_current_user(self) -> dict[str, object]:
        """Fetch the user object for the configured bot token."""

        response = await self._client.get("/users/@me")
        return self._decode_response(response)

    async def get_user(self, user_id: str) -> dict[str, object]:
        """Fetch a Discord user by ID."""

        response = await self._client.get(f"/users/{user_id}")
        return self._decode_response(response)

    async def get_guild_member(
        self,
        *,
        guild_id: str,
        user_id: str,
    ) -> dict[str, object]:
        """Fetch one member from a guild."""

        response = await self._client.get(f"/guilds/{guild_id}/members/{user_id}")
        return self._decode_response(response)

    async def search_guild_members(
        self,
        *,
        guild_id: str,
        query: str,
        limit: int,
    ) -> list[dict[str, object]]:
        """Search guild members by username or nickname prefix."""

        response = await self._client.get(
            f"/guilds/{guild_id}/members/search",
            params={"query": query, "limit": limit},
        )
        return self._decode_object_list_response(response, resource_name="member")

    async def list_guild_roles(self, guild_id: str) -> list[dict[str, object]]:
        """Fetch the roles configured in a guild."""

        response = await self._client.get(f"/guilds/{guild_id}/roles")
        return self._decode_object_list_response(response, resource_name="role")

    async def list_channel_messages(
        self,
        *,
        channel_id: str,
        limit: int,
        before: str | None = None,
        after: str | None = None,
        around: str | None = None,
    ) -> list[dict[str, object]]:
        """Fetch messages visible to the bot in a channel."""

        params: dict[str, str | int] = {"limit": limit}
        if before is not None:
            params["before"] = before
        if after is not None:
            params["after"] = after
        if around is not None:
            params["around"] = around

        response = await self._client.get(
            f"/channels/{channel_id}/messages",
            params=params,
        )
        if not response.is_success:
            message = self._extract_error_message(response)
            raise DiscordApiError(
                f"Discord API request failed with status {response.status_code}: {message}"
            )

        payload = response.json()
        if not isinstance(payload, list):
            raise DiscordApiError("Discord response payload was not a JSON array.")

        messages: list[dict[str, object]] = []
        for item in payload:
            if not isinstance(item, dict):
                raise DiscordApiError("Discord message payload item was not a JSON object.")
            messages.append(cast(dict[str, object], item))
        return messages

    async def get_channel_message(
        self,
        *,
        channel_id: str,
        message_id: str,
    ) -> dict[str, object]:
        """Fetch one message so attachment URLs are current when downloaded."""

        response = await self._client.get(
            f"/channels/{channel_id}/messages/{message_id}"
        )
        return self._decode_response(response)

    async def send_message(
        self,
        *,
        channel_id: str,
        content: str | None,
        attachments: Sequence[DiscordUpload] = (),
        sticker_ids: Sequence[str] = (),
    ) -> DiscordMessage:
        """Send a message to a Discord channel."""

        payload: dict[str, object] = {}
        if content is not None:
            payload["content"] = content
        if sticker_ids:
            payload["sticker_ids"] = list(sticker_ids)

        if attachments:
            attachment_metadata: list[dict[str, object]] = []
            files: list[tuple[str, tuple[str, bytes, str]]] = []
            for index, attachment in enumerate(attachments):
                metadata: dict[str, object] = {
                    "id": index,
                    "filename": attachment.filename,
                }
                if attachment.description is not None:
                    metadata["description"] = attachment.description
                attachment_metadata.append(metadata)
                files.append(
                    (
                        f"files[{index}]",
                        (
                            attachment.filename,
                            attachment.data,
                            attachment.content_type,
                        ),
                    )
                )
            payload["attachments"] = attachment_metadata
            response = await self._client.post(
                f"/channels/{channel_id}/messages",
                data={"payload_json": json.dumps(payload, ensure_ascii=False)},
                files=files,
            )
        else:
            response = await self._client.post(
                f"/channels/{channel_id}/messages",
                json=payload,
            )

        if response.status_code == 403 and (attachments or sticker_ids):
            requirements = ["SEND_MESSAGES"]
            if attachments:
                requirements.append("ATTACH_FILES")
            if sticker_ids:
                requirements.append(
                    "access to the requested stickers (and USE_EXTERNAL_STICKERS "
                    "when applicable)"
                )
            raise DiscordPermissionError(
                "Discord rejected the message for missing permissions. Verify: "
                + ", ".join(requirements)
                + "."
            )
        return self._decode_message_response(response)

    async def edit_message(
        self,
        *,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> DiscordMessage:
        """Edit a message sent by the bot."""

        response = await self._client.patch(
            f"/channels/{channel_id}/messages/{message_id}",
            json={"content": content},
        )
        return self._decode_message_response(response)

    async def add_reaction(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        """Add a reaction to a message as the bot."""

        encoded_emoji = quote(emoji, safe="")
        response = await self._client.put(
            f"/channels/{channel_id}/messages/{message_id}/reactions/{encoded_emoji}/@me"
        )
        if not response.is_success:
            message = self._extract_error_message(response)
            raise DiscordApiError(
                f"Discord API request failed with status {response.status_code}: {message}"
            )

    async def create_thread(
        self,
        *,
        channel_id: str,
        name: str,
        message_id: str | None = None,
        auto_archive_duration: int = 1440,
    ) -> DiscordThread:
        """Create a public thread in a channel or from an existing message."""

        payload: dict[str, str | int] = {
            "name": name,
            "auto_archive_duration": auto_archive_duration,
        }
        if message_id is None:
            payload["type"] = 11
            response = await self._client.post(
                f"/channels/{channel_id}/threads",
                json=payload,
            )
        else:
            response = await self._client.post(
                f"/channels/{channel_id}/messages/{message_id}/threads",
                json=payload,
            )
        data = self._decode_response(response)
        return DiscordThread(
            id=str(data["id"]),
            name=self._as_optional_str(data.get("name")),
            parent_id=self._as_optional_str(data.get("parent_id")),
            guild_id=self._as_optional_str(data.get("guild_id")),
            type=self._as_optional_int(data.get("type")),
        )

    def _decode_message_response(self, response: httpx.Response) -> DiscordMessage:
        data = self._decode_response(response)
        author_object = data.get("author", {})
        if not isinstance(author_object, dict):
            raise DiscordApiError("Discord response did not include a valid author object.")
        author = cast(dict[str, object], author_object)
        author_username = author.get("username")
        if not isinstance(author_username, str):
            raise DiscordApiError("Discord response did not include a valid author username.")

        attachments = self._as_object_tuple(
            data.get("attachments"),
            field_name="attachments",
        )
        stickers = self._as_object_tuple(
            data.get("sticker_items"),
            field_name="sticker_items",
        )

        return DiscordMessage(
            id=str(data["id"]),
            channel_id=str(data["channel_id"]),
            content=str(data["content"]),
            author_username=author_username,
            attachments=attachments,
            stickers=stickers,
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

    def _decode_object_list_response(
        self,
        response: httpx.Response,
        *,
        resource_name: str,
    ) -> list[dict[str, object]]:
        if not response.is_success:
            message = self._extract_error_message(response)
            raise DiscordApiError(
                f"Discord API request failed with status {response.status_code}: {message}"
            )

        payload = response.json()
        if not isinstance(payload, list):
            raise DiscordApiError("Discord response payload was not a JSON array.")

        items: list[dict[str, object]] = []
        for item in payload:
            if not isinstance(item, dict):
                raise DiscordApiError(
                    f"Discord {resource_name} payload item was not a JSON object."
                )
            items.append(cast(dict[str, object], item))
        return items

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

    def _as_object_tuple(
        self,
        value: object,
        *,
        field_name: str,
    ) -> tuple[dict[str, object], ...]:
        if value is None:
            return ()
        if not isinstance(value, list):
            raise DiscordApiError(
                f"Discord response did not include a valid {field_name} array."
            )
        items: list[dict[str, object]] = []
        for item in value:
            if not isinstance(item, dict):
                raise DiscordApiError(
                    f"Discord response {field_name} item was not a JSON object."
                )
            items.append(cast(dict[str, object], item))
        return tuple(items)
