"""Validation and bounded loading for outgoing Discord attachments."""

from __future__ import annotations

import asyncio
import base64
import binascii
import ipaddress
import mimetypes
import re
import socket
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Annotated, Literal, Protocol
from urllib.parse import unquote, urljoin, urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field

from guildspan import __version__
from guildspan.config import Settings
from guildspan.discord_client import DiscordUpload
from guildspan.errors import (
    DiscordConfigurationError,
    DiscordPermissionError,
    DiscordUploadError,
)

MAX_OUTGOING_ATTACHMENTS = 10
MAX_REDIRECTS = 3
MIME_TYPE_RE = re.compile(
    r"^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$"
)
MIME_PATTERN_RE = re.compile(
    r"^(?:\*/\*|[a-z0-9][a-z0-9!#$&^_.+-]*/(?:\*|[a-z0-9][a-z0-9!#$&^_.+-]*))$"
)
CONTROL_CHARACTERS_RE = re.compile(r"[\x00-\x1f\x7f]")
REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})


class _AttachmentMetadata(BaseModel):
    """Fields shared by every outgoing attachment source."""

    model_config = ConfigDict(extra="forbid")

    filename: str | None = None
    content_type: str | None = None
    description: str | None = Field(default=None, max_length=1024)
    spoiler: bool = False


class PathAttachment(_AttachmentMetadata):
    """An outgoing attachment loaded from an explicitly allowed local path."""

    source_type: Literal["path"]
    path: str


class UrlAttachment(_AttachmentMetadata):
    """An outgoing attachment downloaded from a public HTTPS URL."""

    source_type: Literal["url"]
    url: str


class Base64Attachment(_AttachmentMetadata):
    """An outgoing attachment supplied as strict base64 data."""

    source_type: Literal["base64"]
    data_base64: str
    filename: str


OutgoingAttachment = Annotated[
    PathAttachment | UrlAttachment | Base64Attachment,
    Field(discriminator="source_type"),
]


@dataclass(frozen=True)
class DownloadedUpload:
    """Bounded bytes and headers retrieved from one public URL."""

    data: bytes
    content_type: str | None
    final_url: str


class HostResolverProtocol(Protocol):
    """DNS resolver used to reject non-public upload URL destinations."""

    async def resolve(self, hostname: str) -> set[str]:
        """Resolve a hostname to textual IP addresses."""


class UploadDownloaderProtocol(Protocol):
    """Bounded public URL downloader used while preparing uploads."""

    async def download(
        self,
        *,
        url: str,
        max_bytes: int,
        allowed_hosts: set[str],
    ) -> DownloadedUpload:
        """Download one validated public URL."""

    async def aclose(self) -> None:
        """Close downloader resources."""


class SystemHostResolver:
    """Resolve hostnames without blocking the event loop."""

    async def resolve(self, hostname: str) -> set[str]:
        """Return every address reported by the operating system resolver."""

        loop = asyncio.get_running_loop()
        try:
            records = await loop.getaddrinfo(
                hostname,
                443,
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise DiscordUploadError(
                f"Could not resolve upload URL host {hostname}."
            ) from exc
        return {str(record[4][0]) for record in records}


class UploadUrlDownloader:
    """Download public HTTPS files without carrying Discord credentials."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver: HostResolverProtocol | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            headers={"User-Agent": f"guildspan/{__version__}"},
            timeout=timeout_seconds,
            follow_redirects=False,
            transport=transport,
        )
        self._resolver = resolver or SystemHostResolver()

    async def download(
        self,
        *,
        url: str,
        max_bytes: int,
        allowed_hosts: set[str],
    ) -> DownloadedUpload:
        """Follow a bounded redirect chain and stream at most max_bytes."""

        current_url = url
        for redirect_count in range(MAX_REDIRECTS + 1):
            await _validate_public_https_url(
                current_url,
                allowed_hosts=allowed_hosts,
                resolver=self._resolver,
            )
            try:
                async with self._client.stream("GET", current_url) as response:
                    if response.status_code in REDIRECT_STATUS_CODES:
                        location = response.headers.get("Location")
                        if location is None:
                            raise DiscordUploadError(
                                "Upload URL redirect did not include a Location header."
                            )
                        if redirect_count == MAX_REDIRECTS:
                            raise DiscordUploadError(
                                f"Upload URL exceeded the maximum of {MAX_REDIRECTS} redirects."
                            )
                        current_url = urljoin(current_url, location)
                        continue

                    if not response.is_success:
                        raise DiscordUploadError(
                            "Upload URL download failed with status "
                            f"{response.status_code}."
                        )

                    content_length = _parse_content_length(
                        response.headers.get("Content-Length")
                    )
                    if content_length is not None and content_length > max_bytes:
                        raise DiscordUploadError(
                            f"Upload URL is {content_length} bytes; the maximum is "
                            f"{max_bytes} bytes."
                        )

                    payload = bytearray()
                    async for chunk in response.aiter_bytes():
                        payload.extend(chunk)
                        if len(payload) > max_bytes:
                            raise DiscordUploadError(
                                "Upload URL exceeded the maximum of "
                                f"{max_bytes} bytes while downloading."
                            )
                    return DownloadedUpload(
                        data=bytes(payload),
                        content_type=response.headers.get("Content-Type"),
                        final_url=str(response.url),
                    )
            except httpx.HTTPError as exc:
                raise DiscordUploadError(
                    f"Upload URL download failed: {exc}"
                ) from exc

        raise AssertionError("redirect loop must return or raise")

    async def aclose(self) -> None:
        """Close the isolated public URL client."""

        await self._client.aclose()


async def resolve_outgoing_attachments(
    *,
    attachments: list[OutgoingAttachment],
    settings: Settings,
    downloader: UploadDownloaderProtocol | None = None,
) -> list[DiscordUpload]:
    """Load and validate all outgoing attachment inputs."""

    if len(attachments) > MAX_OUTGOING_ATTACHMENTS:
        raise ValueError(
            f"attachments cannot contain more than {MAX_OUTGOING_ATTACHMENTS} items"
        )
    if not attachments:
        return []

    mime_patterns = settings.allowed_upload_mime_patterns
    _validate_mime_patterns(mime_patterns)
    needs_downloader = any(isinstance(item, UrlAttachment) for item in attachments)
    managed_downloader = downloader is None and needs_downloader
    url_downloader = downloader or (
        UploadUrlDownloader() if needs_downloader else None
    )
    resolved: list[DiscordUpload] = []
    used_filenames: set[str] = set()
    total_bytes = 0

    try:
        for attachment in attachments:
            data: bytes
            inferred_name: str | None
            response_mime: str | None
            if isinstance(attachment, PathAttachment):
                data, inferred_name, response_mime = await _load_path_attachment(
                    attachment,
                    settings=settings,
                )
            elif isinstance(attachment, UrlAttachment):
                if url_downloader is None:
                    raise AssertionError("URL attachments require a downloader")
                downloaded = await url_downloader.download(
                    url=attachment.url,
                    max_bytes=settings.discord_max_upload_bytes,
                    allowed_hosts=settings.allowed_upload_url_hosts,
                )
                data = downloaded.data
                inferred_name = _filename_from_url(downloaded.final_url)
                response_mime = downloaded.content_type
            else:
                data = _decode_base64_attachment(
                    attachment.data_base64,
                    max_bytes=settings.discord_max_upload_bytes,
                )
                inferred_name = attachment.filename
                response_mime = None

            if len(data) > settings.discord_max_upload_bytes:
                raise DiscordUploadError(
                    f"Attachment is {len(data)} bytes; the maximum is "
                    f"{settings.discord_max_upload_bytes} bytes."
                )
            total_bytes += len(data)
            if total_bytes > settings.discord_max_upload_total_bytes:
                raise DiscordUploadError(
                    "Combined attachments exceeded the maximum of "
                    f"{settings.discord_max_upload_total_bytes} bytes."
                )

            requested_name = attachment.filename or inferred_name
            filename = _unique_filename(
                _sanitize_filename(
                    requested_name or _fallback_filename(
                        attachment.content_type or response_mime
                    ),
                    spoiler=attachment.spoiler,
                ),
                used=used_filenames,
            )
            mime_type = _resolve_mime_type(
                declared=attachment.content_type,
                response=response_mime,
                filename=filename,
            )
            if isinstance(attachment, UrlAttachment) and mime_type in {
                "text/html",
                "application/xhtml+xml",
            }:
                raise DiscordUploadError(
                    "URL attachments must point directly to a file, not an HTML page. "
                    "Put share-page URLs such as Tenor or Giphy in content instead."
                )
            _assert_mime_allowed(mime_type, mime_patterns)
            resolved.append(
                DiscordUpload(
                    data=data,
                    filename=filename,
                    content_type=mime_type,
                    description=_normalized_description(attachment.description),
                )
            )
    finally:
        if managed_downloader and url_downloader is not None:
            await url_downloader.aclose()

    return resolved


async def _load_path_attachment(
    attachment: PathAttachment,
    *,
    settings: Settings,
) -> tuple[bytes, str, str | None]:
    path = Path(attachment.path)
    if not path.is_absolute():
        raise DiscordPermissionError("Outgoing attachment paths must be absolute.")
    allowed_roots = _resolved_allowed_roots(settings.allowed_upload_paths)
    if not allowed_roots:
        raise DiscordPermissionError(
            "Local attachment uploads are disabled. Configure "
            "DISCORD_ALLOWED_UPLOAD_PATHS first."
        )
    try:
        resolved_path = path.resolve(strict=True)
    except OSError as exc:
        raise DiscordUploadError(
            f"Attachment path is not accessible: {path}."
        ) from exc
    if not any(resolved_path.is_relative_to(root) for root in allowed_roots):
        raise DiscordPermissionError(
            f"Attachment path {resolved_path} is outside DISCORD_ALLOWED_UPLOAD_PATHS."
        )
    if not resolved_path.is_file():
        raise DiscordUploadError("Attachment path must reference a regular file.")
    try:
        size = resolved_path.stat().st_size
    except OSError as exc:
        raise DiscordUploadError("Could not inspect attachment path.") from exc
    if size > settings.discord_max_upload_bytes:
        raise DiscordUploadError(
            f"Attachment is {size} bytes; the maximum is "
            f"{settings.discord_max_upload_bytes} bytes."
        )
    try:
        data = await asyncio.to_thread(resolved_path.read_bytes)
    except OSError as exc:
        raise DiscordUploadError("Could not read attachment path.") from exc
    return data, resolved_path.name, None


def _resolved_allowed_roots(raw_roots: tuple[str, ...]) -> tuple[Path, ...]:
    roots: list[Path] = []
    for raw_root in raw_roots:
        root = Path(raw_root)
        if not root.is_absolute():
            raise DiscordConfigurationError(
                "DISCORD_ALLOWED_UPLOAD_PATHS must contain absolute paths."
            )
        try:
            resolved = root.resolve(strict=True)
        except OSError as exc:
            raise DiscordConfigurationError(
                f"Configured upload root is not accessible: {root}."
            ) from exc
        if not resolved.is_dir():
            raise DiscordConfigurationError(
                f"Configured upload root is not a directory: {resolved}."
            )
        roots.append(resolved)
    return tuple(roots)


async def _validate_public_https_url(
    url: str,
    *,
    allowed_hosts: set[str],
    resolver: HostResolverProtocol,
) -> None:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise DiscordPermissionError("Upload URL is invalid.") from exc
    hostname = parsed.hostname
    if hostname is None:
        raise DiscordPermissionError("Upload URL must include a hostname.")
    try:
        normalized_host = hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise DiscordPermissionError("Upload URL hostname is invalid.") from exc
    if (
        parsed.scheme.lower() != "https"
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        raise DiscordPermissionError(
            "Upload URLs must use public HTTPS without credentials or custom ports."
        )
    if allowed_hosts and normalized_host not in allowed_hosts:
        raise DiscordPermissionError(
            f"Upload URL host {normalized_host} is not in "
            "DISCORD_ALLOWED_UPLOAD_URL_HOSTS."
        )
    addresses = await resolver.resolve(normalized_host)
    if not addresses:
        raise DiscordPermissionError("Upload URL hostname did not resolve.")
    for raw_address in addresses:
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError as exc:
            raise DiscordPermissionError(
                "Upload URL hostname resolved to an invalid address."
            ) from exc
        if not address.is_global:
            raise DiscordPermissionError(
                "Upload URLs cannot resolve to private, local, reserved, or "
                "otherwise non-public addresses."
            )


def _decode_base64_attachment(value: str, *, max_bytes: int) -> bytes:
    if not value:
        raise DiscordUploadError("data_base64 is required for base64 attachments.")
    estimated_size = (len(value) * 3) // 4
    if estimated_size > max_bytes + 2:
        raise DiscordUploadError(
            f"Base64 attachment exceeds the maximum of {max_bytes} bytes."
        )
    try:
        data = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise DiscordUploadError("data_base64 is not valid base64.") from exc
    if len(data) > max_bytes:
        raise DiscordUploadError(
            f"Base64 attachment is {len(data)} bytes; the maximum is "
            f"{max_bytes} bytes."
        )
    return data


def _filename_from_url(url: str) -> str | None:
    path = urlsplit(url).path
    candidate = unquote(path.rsplit("/", maxsplit=1)[-1])
    return candidate or None


def _fallback_filename(content_type: str | None) -> str:
    normalized = _normalize_mime_type(content_type, source="Attachment content_type")
    extension = mimetypes.guess_extension(normalized) if normalized is not None else None
    return f"attachment{extension or ''}"


def _sanitize_filename(value: str, *, spoiler: bool) -> str:
    sanitized = CONTROL_CHARACTERS_RE.sub("", value.strip())
    sanitized = sanitized.replace("/", "_").replace("\\", "_")
    if sanitized in {"", ".", ".."}:
        raise DiscordUploadError("Attachment filename is empty after sanitization.")
    if spoiler and not sanitized.startswith("SPOILER_"):
        sanitized = f"SPOILER_{sanitized}"
    return sanitized


def _unique_filename(filename: str, *, used: set[str]) -> str:
    candidate = filename
    suffix = Path(filename).suffix
    stem = filename[: -len(suffix)] if suffix else filename
    sequence = 2
    while candidate.casefold() in used:
        candidate = f"{stem}_{sequence}{suffix}"
        sequence += 1
    used.add(candidate.casefold())
    return candidate


def _resolve_mime_type(
    *,
    declared: str | None,
    response: str | None,
    filename: str,
) -> str:
    generic = "application/octet-stream"
    normalized_declared = _normalize_mime_type(
        declared,
        source="Attachment content_type",
    )
    normalized_response = _normalize_mime_type(
        response,
        source="Attachment HTTP response",
    )
    guessed, _ = mimetypes.guess_type(filename)
    normalized_guess = _normalize_mime_type(guessed, source="Attachment filename")
    specific = {
        value
        for value in (normalized_declared, normalized_response, normalized_guess)
        if value is not None and value != generic
    }
    if len(specific) > 1:
        raise DiscordUploadError(
            "Attachment MIME type does not match its response headers or filename."
        )
    return next(iter(specific), normalized_declared or normalized_response or generic)


def _normalize_mime_type(value: str | None, *, source: str) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = value.split(";", maxsplit=1)[0].strip().lower()
    if MIME_TYPE_RE.fullmatch(normalized) is None:
        raise DiscordUploadError(f"{source} contains an invalid MIME type.")
    return normalized


def _validate_mime_patterns(patterns: set[str]) -> None:
    invalid = sorted(
        pattern for pattern in patterns if MIME_PATTERN_RE.fullmatch(pattern) is None
    )
    if invalid:
        raise DiscordPermissionError(
            "DISCORD_ALLOWED_UPLOAD_MIME_TYPES contains invalid patterns: "
            + ", ".join(invalid)
        )


def _assert_mime_allowed(mime_type: str, patterns: set[str]) -> None:
    if patterns and not any(fnmatchcase(mime_type, pattern) for pattern in patterns):
        raise DiscordPermissionError(
            f"MIME type {mime_type} is not in DISCORD_ALLOWED_UPLOAD_MIME_TYPES."
        )


def _parse_content_length(raw_value: str | None) -> int | None:
    if raw_value is None:
        return None
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise DiscordUploadError(
            "Upload URL returned an invalid Content-Length header."
        ) from exc
    if value < 0:
        raise DiscordUploadError(
            "Upload URL returned a negative Content-Length header."
        )
    return value


def _normalized_description(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
