import base64
from typing import Any, cast

import httpx
import pytest
from mcp.types import AudioContent, BlobResourceContents, EmbeddedResource, ImageContent

from discord_mcp_bridge.config import Settings
from discord_mcp_bridge.discord_client import DiscordChannel
from discord_mcp_bridge.errors import DiscordAttachmentError, DiscordPermissionError
from discord_mcp_bridge.tools.attachments import (
    DiscordAttachmentDownloader,
    DownloadedAttachment,
    _discord_download_attachment,
)


def make_settings(**kwargs: object) -> Settings:
    settings_ctor = cast(Any, Settings)
    return cast(Settings, settings_ctor(_env_file=None, **kwargs))


def make_attachment_message(
    *,
    url: str = "https://cdn.discordapp.com/attachments/1/2/report.pdf?ex=abc&hm=def",
    content_type: str = "application/pdf",
    size: int = 4,
) -> dict[str, object]:
    return {
        "id": "message-1",
        "attachments": [
            {
                "id": "attachment-1",
                "filename": "report.pdf",
                "url": url,
                "content_type": content_type,
                "size": size,
            }
        ],
    }


class FakeAttachmentClient:
    def __init__(self, message: dict[str, object]) -> None:
        self.message = message
        self.closed = False
        self.message_calls: list[tuple[str, str]] = []

    async def get_channel(self, channel_id: str) -> DiscordChannel:
        return DiscordChannel(
            id=channel_id,
            name="general",
            guild_id="guild-1",
            type=0,
            position=0,
        )

    async def get_channel_message(
        self,
        *,
        channel_id: str,
        message_id: str,
    ) -> dict[str, object]:
        self.message_calls.append((channel_id, message_id))
        return self.message

    async def aclose(self) -> None:
        self.closed = True


class FakeDownloader:
    def __init__(self, downloaded: DownloadedAttachment) -> None:
        self.downloaded = downloaded
        self.calls: list[tuple[str, int]] = []
        self.closed = False

    async def download(self, *, url: str, max_bytes: int) -> DownloadedAttachment:
        self.calls.append((url, max_bytes))
        return self.downloaded

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_download_attachment_returns_generic_file_as_embedded_resource() -> None:
    client = FakeAttachmentClient(make_attachment_message())
    downloader = FakeDownloader(
        DownloadedAttachment(data=b"%PDF", content_type="application/pdf")
    )

    result = await _discord_download_attachment(
        channel_id="channel-1",
        message_id="message-1",
        attachment_id="attachment-1",
        settings=make_settings(discord_bot_token="token"),
        client=client,
        downloader=downloader,
    )

    assert result.structured_content == {
        "status": "downloaded",
        "channel_id": "channel-1",
        "message_id": "message-1",
        "attachment_id": "attachment-1",
        "filename": "report.pdf",
        "mime_type": "application/pdf",
        "size": 4,
    }
    resource = result.content[1]
    assert isinstance(resource, EmbeddedResource)
    assert isinstance(resource.resource, BlobResourceContents)
    assert base64.b64decode(resource.resource.blob) == b"%PDF"
    assert resource.resource.mimeType == "application/pdf"
    assert client.message_calls == [("channel-1", "message-1")]
    assert downloader.calls == [
        (
            "https://cdn.discordapp.com/attachments/1/2/report.pdf?ex=abc&hm=def",
            10 * 1024 * 1024,
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mime_type", "payload", "content_class"),
    [
        ("image/png", b"png", ImageContent),
        ("audio/ogg", b"ogg", AudioContent),
    ],
)
async def test_download_attachment_uses_native_mcp_media_blocks(
    mime_type: str,
    payload: bytes,
    content_class: type[ImageContent] | type[AudioContent],
) -> None:
    message = make_attachment_message(content_type=mime_type, size=len(payload))
    attachment = cast(list[dict[str, object]], message["attachments"])[0]
    attachment["filename"] = "media.bin"
    client = FakeAttachmentClient(message)
    downloader = FakeDownloader(
        DownloadedAttachment(data=payload, content_type=mime_type)
    )

    result = await _discord_download_attachment(
        channel_id="channel-1",
        message_id="message-1",
        attachment_id="attachment-1",
        settings=make_settings(discord_bot_token="token"),
        client=client,
        downloader=downloader,
    )

    content = result.content[1]
    assert isinstance(content, content_class)
    assert base64.b64decode(content.data) == payload
    assert content.mimeType == mime_type


@pytest.mark.asyncio
async def test_download_attachment_rejects_non_discord_cdn_url() -> None:
    client = FakeAttachmentClient(
        make_attachment_message(url="https://example.com/attachments/1/2/report.pdf")
    )
    downloader = FakeDownloader(
        DownloadedAttachment(data=b"%PDF", content_type="application/pdf")
    )

    with pytest.raises(DiscordPermissionError, match="allowed Discord CDN"):
        await _discord_download_attachment(
            channel_id="channel-1",
            message_id="message-1",
            attachment_id="attachment-1",
            settings=make_settings(discord_bot_token="token"),
            client=client,
            downloader=downloader,
        )

    assert downloader.calls == []


@pytest.mark.asyncio
async def test_download_attachment_rejects_metadata_over_effective_limit() -> None:
    client = FakeAttachmentClient(make_attachment_message(size=2049))
    downloader = FakeDownloader(
        DownloadedAttachment(data=b"", content_type="application/pdf")
    )

    with pytest.raises(DiscordAttachmentError, match="maximum is 2048"):
        await _discord_download_attachment(
            channel_id="channel-1",
            message_id="message-1",
            attachment_id="attachment-1",
            max_bytes=4096,
            settings=make_settings(
                discord_bot_token="token",
                discord_max_attachment_bytes=2048,
            ),
            client=client,
            downloader=downloader,
        )

    assert downloader.calls == []


@pytest.mark.asyncio
async def test_download_attachment_rechecks_downloaded_size() -> None:
    client = FakeAttachmentClient(make_attachment_message(size=1))
    downloader = FakeDownloader(
        DownloadedAttachment(data=b"12345", content_type="application/pdf")
    )

    with pytest.raises(DiscordAttachmentError, match="maximum of 4"):
        await _discord_download_attachment(
            channel_id="channel-1",
            message_id="message-1",
            attachment_id="attachment-1",
            max_bytes=4,
            settings=make_settings(discord_bot_token="token"),
            client=client,
            downloader=downloader,
        )


@pytest.mark.asyncio
async def test_download_attachment_enforces_mime_allowlist() -> None:
    client = FakeAttachmentClient(make_attachment_message())
    downloader = FakeDownloader(
        DownloadedAttachment(data=b"%PDF", content_type="application/pdf")
    )

    with pytest.raises(DiscordPermissionError, match="not in"):
        await _discord_download_attachment(
            channel_id="channel-1",
            message_id="message-1",
            attachment_id="attachment-1",
            settings=make_settings(
                discord_bot_token="token",
                discord_allowed_attachment_mime_types="image/*",
            ),
            client=client,
            downloader=downloader,
        )


@pytest.mark.asyncio
async def test_download_attachment_rejects_mime_mismatch() -> None:
    client = FakeAttachmentClient(make_attachment_message())
    downloader = FakeDownloader(
        DownloadedAttachment(data=b"<html>", content_type="text/html")
    )

    with pytest.raises(DiscordAttachmentError, match="does not match"):
        await _discord_download_attachment(
            channel_id="channel-1",
            message_id="message-1",
            attachment_id="attachment-1",
            settings=make_settings(discord_bot_token="token"),
            client=client,
            downloader=downloader,
        )


@pytest.mark.asyncio
async def test_cdn_downloader_omits_bot_authorization_header() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            status_code=200,
            headers={"Content-Type": "image/png"},
            content=b"png",
        )

    downloader = DiscordAttachmentDownloader(transport=httpx.MockTransport(handler))
    try:
        downloaded = await downloader.download(
            url="https://cdn.discordapp.com/attachments/1/2/image.png",
            max_bytes=10,
        )
    finally:
        await downloader.aclose()

    assert downloaded.data == b"png"
    assert requests[0].headers.get("Authorization") is None


@pytest.mark.asyncio
async def test_cdn_downloader_stops_when_stream_exceeds_limit() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, content=b"12345")

    downloader = DiscordAttachmentDownloader(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(DiscordAttachmentError, match="maximum is 4"):
            await downloader.download(
                url="https://cdn.discordapp.com/attachments/1/2/file.bin",
                max_bytes=4,
            )
    finally:
        await downloader.aclose()
