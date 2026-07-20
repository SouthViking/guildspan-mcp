"""Secure Discord attachment download MCP tool."""

from __future__ import annotations

import base64
import json
import mimetypes
import re
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from fastmcp.tools.tool import ToolResult
from mcp.types import (
    AudioContent,
    BlobResourceContents,
    EmbeddedResource,
    ImageContent,
    TextContent,
)
from pydantic import AnyUrl

from discord_mcp_bridge.config import Settings
from discord_mcp_bridge.discord_client import DiscordClient
from discord_mcp_bridge.errors import DiscordAttachmentError, DiscordPermissionError
from discord_mcp_bridge.tools._common import (
    ChannelAccessClientProtocol,
    assert_channel_is_allowed,
    require_bot_token,
    required_id,
    resolve_settings,
)

ALLOWED_CDN_HOSTS = frozenset({"cdn.discordapp.com", "media.discordapp.net"})
ALLOWED_ATTACHMENT_PATH_PREFIXES = ("/attachments/", "/ephemeral-attachments/")
MIME_TYPE_RE = re.compile(
    r"^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$"
)
MIME_PATTERN_RE = re.compile(
    r"^(?:\*/\*|[a-z0-9][a-z0-9!#$&^_.+-]*/(?:\*|[a-z0-9][a-z0-9!#$&^_.+-]*))$"
)


@dataclass(frozen=True)
class DownloadedAttachment:
    """Bounded attachment bytes and relevant CDN response metadata."""

    data: bytes
    content_type: str | None


class DiscordAttachmentClientProtocol(ChannelAccessClientProtocol, Protocol):
    """Discord API operations required to resolve an attachment."""

    async def get_channel_message(
        self,
        *,
        channel_id: str,
        message_id: str,
    ) -> dict[str, object]:
        """Fetch one message."""

    async def aclose(self) -> None:
        """Close network resources."""


class AttachmentDownloaderProtocol(Protocol):
    """Unauthenticated CDN downloader used by the attachment tool."""

    async def download(
        self,
        *,
        url: str,
        max_bytes: int,
    ) -> DownloadedAttachment:
        """Download at most max_bytes from an already validated URL."""

    async def aclose(self) -> None:
        """Close network resources."""


class DiscordAttachmentDownloader:
    """Stream attachment bytes without forwarding Discord bot credentials."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            headers={"User-Agent": "discord-mcp-bridge/0.1.0"},
            timeout=timeout_seconds,
            follow_redirects=False,
            transport=transport,
        )

    async def download(
        self,
        *,
        url: str,
        max_bytes: int,
    ) -> DownloadedAttachment:
        """Stream a CDN response while enforcing the configured byte limit."""

        try:
            async with self._client.stream("GET", url) as response:
                if not response.is_success:
                    raise DiscordAttachmentError(
                        "Discord CDN download failed with status "
                        f"{response.status_code}. Refresh the message and retry."
                    )

                content_length = _parse_content_length(
                    response.headers.get("Content-Length")
                )
                if content_length is not None and content_length > max_bytes:
                    raise DiscordAttachmentError(
                        f"Attachment is {content_length} bytes; the maximum is "
                        f"{max_bytes} bytes."
                    )

                payload = bytearray()
                async for chunk in response.aiter_bytes():
                    payload.extend(chunk)
                    if len(payload) > max_bytes:
                        raise DiscordAttachmentError(
                            "Attachment exceeded the maximum of "
                            f"{max_bytes} bytes while downloading."
                        )
        except httpx.HTTPError as exc:
            raise DiscordAttachmentError(
                f"Discord CDN download failed: {exc}"
            ) from exc

        return DownloadedAttachment(
            data=bytes(payload),
            content_type=response.headers.get("Content-Type"),
        )

    async def aclose(self) -> None:
        """Close the unauthenticated CDN HTTP client."""

        await self._client.aclose()


async def discord_download_attachment(
    channel_id: str,
    message_id: str,
    attachment_id: str,
    max_bytes: int | None = None,
) -> ToolResult:
    """Download one Discord attachment and return its bytes as MCP content."""

    return await _discord_download_attachment(
        channel_id=channel_id,
        message_id=message_id,
        attachment_id=attachment_id,
        max_bytes=max_bytes,
    )


async def _discord_download_attachment(
    *,
    channel_id: str,
    message_id: str,
    attachment_id: str,
    max_bytes: int | None = None,
    settings: Settings | None = None,
    client: DiscordAttachmentClientProtocol | None = None,
    downloader: AttachmentDownloaderProtocol | None = None,
) -> ToolResult:
    normalized_channel_id = required_id(channel_id, "channel_id")
    normalized_message_id = required_id(message_id, "message_id")
    normalized_attachment_id = required_id(attachment_id, "attachment_id")
    resolved_settings = resolve_settings(settings)
    bot_token = require_bot_token(resolved_settings)
    effective_max_bytes = _effective_max_bytes(
        requested=max_bytes,
        configured=resolved_settings.discord_max_attachment_bytes,
    )
    allowed_mime_patterns = resolved_settings.allowed_attachment_mime_patterns
    _validate_mime_patterns(allowed_mime_patterns)

    managed_client = client is None
    discord_client = client or DiscordClient(bot_token=bot_token)
    managed_downloader = downloader is None
    attachment_downloader = downloader or DiscordAttachmentDownloader()

    try:
        await assert_channel_is_allowed(
            channel_id=normalized_channel_id,
            settings=resolved_settings,
            client=discord_client,
        )
        message = await discord_client.get_channel_message(
            channel_id=normalized_channel_id,
            message_id=normalized_message_id,
        )
        attachment = _find_attachment(message, normalized_attachment_id)
        source_url = _required_string(attachment, "url")
        _validate_discord_attachment_url(source_url)
        filename = _required_string(attachment, "filename")
        declared_size = _optional_int(attachment, "size")
        if declared_size is not None:
            if declared_size < 0:
                raise DiscordAttachmentError(
                    "Discord returned a negative attachment size."
                )
            if declared_size > effective_max_bytes:
                raise DiscordAttachmentError(
                    f"Attachment is {declared_size} bytes; the maximum is "
                    f"{effective_max_bytes} bytes."
                )

        declared_mime = _normalize_mime_type(
            _optional_string(attachment, "content_type"),
            source="Discord attachment metadata",
        )
        downloaded = await attachment_downloader.download(
            url=source_url,
            max_bytes=effective_max_bytes,
        )
        if len(downloaded.data) > effective_max_bytes:
            raise DiscordAttachmentError(
                "Attachment exceeded the maximum of "
                f"{effective_max_bytes} bytes while downloading."
            )
        response_mime = _normalize_mime_type(
            downloaded.content_type,
            source="Discord CDN response",
        )
        mime_type = _resolve_mime_type(
            declared=declared_mime,
            response=response_mime,
            filename=filename,
        )
        _assert_mime_allowed(mime_type, allowed_mime_patterns)
    finally:
        if managed_downloader:
            await attachment_downloader.aclose()
        if managed_client:
            await discord_client.aclose()

    metadata: dict[str, object] = {
        "status": "downloaded",
        "channel_id": normalized_channel_id,
        "message_id": normalized_message_id,
        "attachment_id": normalized_attachment_id,
        "filename": filename,
        "mime_type": mime_type,
        "size": len(downloaded.data),
    }
    encoded_data = base64.b64encode(downloaded.data).decode("ascii")
    binary_content: ImageContent | AudioContent | EmbeddedResource
    if mime_type.startswith("image/"):
        binary_content = ImageContent(
            type="image",
            data=encoded_data,
            mimeType=mime_type,
        )
    elif mime_type.startswith("audio/"):
        binary_content = AudioContent(
            type="audio",
            data=encoded_data,
            mimeType=mime_type,
        )
    else:
        binary_content = EmbeddedResource(
            type="resource",
            resource=BlobResourceContents(
                uri=AnyUrl(source_url),
                blob=encoded_data,
                mimeType=mime_type,
            ),
        )

    return ToolResult(
        content=[
            TextContent(type="text", text=json.dumps(metadata, ensure_ascii=False)),
            binary_content,
        ],
        structured_content=metadata,
    )


def _find_attachment(
    message: dict[str, object],
    attachment_id: str,
) -> dict[str, object]:
    attachments = message.get("attachments")
    if not isinstance(attachments, list):
        raise DiscordAttachmentError(
            "Discord message did not include a valid attachments list."
        )
    for item in attachments:
        if not isinstance(item, dict):
            continue
        attachment = dict(item)
        if _optional_string(attachment, "id") == attachment_id:
            return attachment
    raise DiscordAttachmentError(
        f"Attachment {attachment_id} was not found in message {message.get('id')}."
    )


def _validate_discord_attachment_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise DiscordPermissionError("Discord attachment URL is invalid.") from exc

    hostname = parsed.hostname.lower() if parsed.hostname is not None else None
    if (
        parsed.scheme.lower() != "https"
        or hostname not in ALLOWED_CDN_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or not parsed.path.startswith(ALLOWED_ATTACHMENT_PATH_PREFIXES)
    ):
        raise DiscordPermissionError(
            "Attachment URL is not an allowed Discord CDN attachment URL."
        )


def _effective_max_bytes(*, requested: int | None, configured: int) -> int:
    if requested is None:
        return configured
    if requested <= 0:
        raise ValueError("max_bytes must be greater than zero")
    return min(requested, configured)


def _parse_content_length(raw_value: str | None) -> int | None:
    if raw_value is None:
        return None
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise DiscordAttachmentError(
            "Discord CDN returned an invalid Content-Length header."
        ) from exc
    if value < 0:
        raise DiscordAttachmentError(
            "Discord CDN returned a negative Content-Length header."
        )
    return value


def _normalize_mime_type(value: str | None, *, source: str) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = value.split(";", maxsplit=1)[0].strip().lower()
    if MIME_TYPE_RE.fullmatch(normalized) is None:
        raise DiscordAttachmentError(f"{source} returned an invalid MIME type.")
    return normalized


def _resolve_mime_type(
    *,
    declared: str | None,
    response: str | None,
    filename: str,
) -> str:
    generic = "application/octet-stream"
    if (
        declared is not None
        and response is not None
        and declared != generic
        and response != generic
        and declared != response
    ):
        raise DiscordAttachmentError(
            "Discord attachment metadata MIME type does not match the CDN response."
        )
    guessed, _ = mimetypes.guess_type(filename)
    normalized_guess = _normalize_mime_type(guessed, source="Attachment filename")
    if declared is not None and declared != generic:
        return declared
    if response is not None and response != generic:
        return response
    return declared or response or normalized_guess or generic


def _validate_mime_patterns(patterns: set[str]) -> None:
    invalid = sorted(
        pattern for pattern in patterns if MIME_PATTERN_RE.fullmatch(pattern) is None
    )
    if invalid:
        raise DiscordPermissionError(
            "DISCORD_ALLOWED_ATTACHMENT_MIME_TYPES contains invalid patterns: "
            + ", ".join(invalid)
        )


def _assert_mime_allowed(mime_type: str, patterns: set[str]) -> None:
    if patterns and not any(fnmatchcase(mime_type, pattern) for pattern in patterns):
        raise DiscordPermissionError(
            f"MIME type {mime_type} is not in "
            "DISCORD_ALLOWED_ATTACHMENT_MIME_TYPES."
        )


def _required_string(source: dict[str, object], key: str) -> str:
    value = _optional_string(source, key)
    if value is None or not value.strip():
        raise DiscordAttachmentError(
            f"Discord attachment did not include a valid {key}."
        )
    return value.strip()


def _optional_string(source: dict[str, object], key: str) -> str | None:
    value = source.get(key)
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    return None


def _optional_int(source: dict[str, object], key: str) -> int | None:
    value = source.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None
