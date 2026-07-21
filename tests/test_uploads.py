import base64
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from guildspan.config import Settings
from guildspan.errors import (
    DiscordConfigurationError,
    DiscordPermissionError,
    DiscordUploadError,
)
from guildspan.tools.uploads import (
    Base64Attachment,
    HostResolverProtocol,
    PathAttachment,
    UploadUrlDownloader,
    UrlAttachment,
    resolve_outgoing_attachments,
)


def make_settings(**kwargs: object) -> Settings:
    settings_ctor = cast(Any, Settings)
    return cast(Settings, settings_ctor(_env_file=None, **kwargs))


class MappingResolver(HostResolverProtocol):
    def __init__(self, addresses: dict[str, set[str]] | None = None) -> None:
        self.addresses = addresses or {"files.example": {"93.184.216.34"}}
        self.calls: list[str] = []

    async def resolve(self, hostname: str) -> set[str]:
        self.calls.append(hostname)
        return self.addresses.get(hostname, set())


@pytest.mark.asyncio
async def test_resolve_path_attachment_inside_allowed_root(tmp_path: Path) -> None:
    file_path = tmp_path / "diagram.png"
    file_path.write_bytes(b"PNG")

    resolved = await resolve_outgoing_attachments(
        attachments=[
            PathAttachment(
                source_type="path",
                path=str(file_path),
                description="Architecture diagram",
                spoiler=True,
            )
        ],
        settings=make_settings(discord_allowed_upload_paths=str(tmp_path)),
    )

    assert len(resolved) == 1
    assert resolved[0].data == b"PNG"
    assert resolved[0].filename == "SPOILER_diagram.png"
    assert resolved[0].content_type == "image/png"
    assert resolved[0].description == "Architecture diagram"


@pytest.mark.asyncio
async def test_resolve_path_attachment_requires_configured_root(tmp_path: Path) -> None:
    file_path = tmp_path / "secret.txt"
    file_path.write_text("secret")

    with pytest.raises(DiscordPermissionError, match="uploads are disabled"):
        await resolve_outgoing_attachments(
            attachments=[PathAttachment(source_type="path", path=str(file_path))],
            settings=make_settings(),
        )


@pytest.mark.asyncio
async def test_resolve_path_attachment_rejects_escape_and_relative_path(
    tmp_path: Path,
) -> None:
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("outside")

    with pytest.raises(DiscordPermissionError, match="outside"):
        await resolve_outgoing_attachments(
            attachments=[PathAttachment(source_type="path", path=str(outside_file))],
            settings=make_settings(discord_allowed_upload_paths=str(allowed_root)),
        )
    with pytest.raises(DiscordPermissionError, match="must be absolute"):
        await resolve_outgoing_attachments(
            attachments=[PathAttachment(source_type="path", path="relative.txt")],
            settings=make_settings(discord_allowed_upload_paths=str(allowed_root)),
        )


@pytest.mark.asyncio
async def test_resolve_path_attachment_rejects_symlink_escape(tmp_path: Path) -> None:
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("outside")
    link = allowed_root / "link.txt"
    link.symlink_to(outside_file)

    with pytest.raises(DiscordPermissionError, match="outside"):
        await resolve_outgoing_attachments(
            attachments=[PathAttachment(source_type="path", path=str(link))],
            settings=make_settings(discord_allowed_upload_paths=str(allowed_root)),
        )


@pytest.mark.asyncio
async def test_resolve_path_attachment_rejects_invalid_configured_root() -> None:
    with pytest.raises(DiscordConfigurationError, match="absolute paths"):
        await resolve_outgoing_attachments(
            attachments=[PathAttachment(source_type="path", path="/tmp/file.txt")],
            settings=make_settings(discord_allowed_upload_paths="relative-root"),
        )


@pytest.mark.asyncio
async def test_resolve_base64_attachment_and_make_duplicate_names_unique() -> None:
    encoded = base64.b64encode(b"PDF").decode("ascii")

    resolved = await resolve_outgoing_attachments(
        attachments=[
            Base64Attachment(
                source_type="base64",
                data_base64=encoded,
                filename="report.pdf",
            ),
            Base64Attachment(
                source_type="base64",
                data_base64=encoded,
                filename="report.pdf",
            ),
        ],
        settings=make_settings(),
    )

    assert [item.filename for item in resolved] == ["report.pdf", "report_2.pdf"]
    assert [item.content_type for item in resolved] == [
        "application/pdf",
        "application/pdf",
    ]


@pytest.mark.asyncio
async def test_resolve_base64_attachment_rejects_invalid_data_and_mime_mismatch() -> (
    None
):
    with pytest.raises(DiscordUploadError, match="not valid base64"):
        await resolve_outgoing_attachments(
            attachments=[
                Base64Attachment(
                    source_type="base64",
                    data_base64="%%%",
                    filename="file.bin",
                )
            ],
            settings=make_settings(),
        )
    with pytest.raises(DiscordUploadError, match="does not match"):
        await resolve_outgoing_attachments(
            attachments=[
                Base64Attachment(
                    source_type="base64",
                    data_base64=base64.b64encode(b"data").decode("ascii"),
                    filename="image.png",
                    content_type="audio/mpeg",
                )
            ],
            settings=make_settings(),
        )


@pytest.mark.asyncio
async def test_resolve_attachments_enforces_count_size_total_and_mime_allowlist() -> (
    None
):
    encoded = base64.b64encode(b"1234").decode("ascii")
    attachment = Base64Attachment(
        source_type="base64",
        data_base64=encoded,
        filename="file.bin",
    )
    with pytest.raises(ValueError, match="more than 10"):
        await resolve_outgoing_attachments(
            attachments=[attachment] * 11,
            settings=make_settings(),
        )
    with pytest.raises(DiscordUploadError, match="maximum of 3"):
        await resolve_outgoing_attachments(
            attachments=[attachment],
            settings=make_settings(discord_max_upload_bytes=3),
        )
    with pytest.raises(DiscordUploadError, match="Combined attachments"):
        await resolve_outgoing_attachments(
            attachments=[attachment, attachment],
            settings=make_settings(
                discord_max_upload_bytes=4,
                discord_max_upload_total_bytes=7,
            ),
        )
    with pytest.raises(DiscordPermissionError, match="not in"):
        await resolve_outgoing_attachments(
            attachments=[attachment],
            settings=make_settings(discord_allowed_upload_mime_types="image/*"),
        )


@pytest.mark.asyncio
async def test_resolve_url_attachment_downloads_public_file_without_auth() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            status_code=200,
            headers={"Content-Type": "image/png", "Content-Length": "3"},
            content=b"PNG",
        )

    resolver = MappingResolver()
    downloader = UploadUrlDownloader(
        transport=httpx.MockTransport(handler),
        resolver=resolver,
    )
    try:
        resolved = await resolve_outgoing_attachments(
            attachments=[
                UrlAttachment(
                    source_type="url",
                    url="https://files.example/image.png",
                )
            ],
            settings=make_settings(discord_allowed_upload_url_hosts="files.example"),
            downloader=downloader,
        )
    finally:
        await downloader.aclose()

    assert resolved[0].data == b"PNG"
    assert resolved[0].filename == "image.png"
    assert resolved[0].content_type == "image/png"
    assert resolver.calls == ["files.example"]
    assert "Authorization" not in requests[0].headers


@pytest.mark.asyncio
async def test_url_downloader_revalidates_redirect_destination() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "files.example":
            return httpx.Response(
                status_code=302,
                headers={"Location": "https://internal.example/secret.png"},
            )
        return httpx.Response(status_code=200, content=b"secret")

    resolver = MappingResolver(
        {
            "files.example": {"93.184.216.34"},
            "internal.example": {"127.0.0.1"},
        }
    )
    downloader = UploadUrlDownloader(
        transport=httpx.MockTransport(handler),
        resolver=resolver,
    )
    try:
        with pytest.raises(DiscordPermissionError, match="private, local"):
            await downloader.download(
                url="https://files.example/start",
                max_bytes=1024,
                allowed_hosts=set(),
            )
    finally:
        await downloader.aclose()

    assert resolver.calls == ["files.example", "internal.example"]


@pytest.mark.asyncio
async def test_url_downloader_limits_redirects() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=302,
            headers={"Location": "https://files.example/again"},
        )

    downloader = UploadUrlDownloader(
        transport=httpx.MockTransport(handler),
        resolver=MappingResolver(),
    )
    try:
        with pytest.raises(DiscordUploadError, match="maximum of 3 redirects"):
            await downloader.download(
                url="https://files.example/start",
                max_bytes=1024,
                allowed_hosts=set(),
            )
    finally:
        await downloader.aclose()


@pytest.mark.asyncio
async def test_url_downloader_rejects_non_https_html_and_oversized_response() -> None:
    resolver = MappingResolver()
    downloader = UploadUrlDownloader(resolver=resolver)
    try:
        with pytest.raises(DiscordPermissionError, match="public HTTPS"):
            await downloader.download(
                url="http://files.example/file.png",
                max_bytes=1024,
                allowed_hosts=set(),
            )
    finally:
        await downloader.aclose()

    async def html_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"Content-Type": "text/html"},
            content=b"<html>",
        )

    html_downloader = UploadUrlDownloader(
        transport=httpx.MockTransport(html_handler),
        resolver=MappingResolver(),
    )
    try:
        with pytest.raises(DiscordUploadError, match="directly to a file"):
            await resolve_outgoing_attachments(
                attachments=[
                    UrlAttachment(
                        source_type="url",
                        url="https://files.example/share",
                    )
                ],
                settings=make_settings(),
                downloader=html_downloader,
            )
    finally:
        await html_downloader.aclose()

    async def large_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"Content-Length": "100"},
            content=b"",
        )

    large_downloader = UploadUrlDownloader(
        transport=httpx.MockTransport(large_handler),
        resolver=MappingResolver(),
    )
    try:
        with pytest.raises(DiscordUploadError, match="maximum is 10"):
            await large_downloader.download(
                url="https://files.example/large.bin",
                max_bytes=10,
                allowed_hosts=set(),
            )
    finally:
        await large_downloader.aclose()

    class OversizedStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield b"12345"

    async def streamed_large_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, stream=OversizedStream())

    streamed_large_downloader = UploadUrlDownloader(
        transport=httpx.MockTransport(streamed_large_handler),
        resolver=MappingResolver(),
    )
    try:
        with pytest.raises(DiscordUploadError, match="while downloading"):
            await streamed_large_downloader.download(
                url="https://files.example/large.bin",
                max_bytes=4,
                allowed_hosts=set(),
            )
    finally:
        await streamed_large_downloader.aclose()
