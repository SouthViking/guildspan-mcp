"""Search-related MCP tools."""

from __future__ import annotations

from typing import cast

from discord_mcp_bridge.config import Settings
from discord_mcp_bridge.tools._common import (
    DiscordClientProtocol,
    assert_guild_is_allowed,
    bounded_int,
    build_client,
    filter_allowed_channels,
    optional_id,
    required_id,
    required_text,
    require_bot_token,
    resolve_settings,
)
from discord_mcp_bridge.tools.history import _discord_read_messages

DEFAULT_LIMIT = 25
DEFAULT_SCAN_LIMIT_PER_CHANNEL = 200
MAX_SEARCH_RESULTS = 100
MAX_SCAN_LIMIT_PER_CHANNEL = 1000


async def discord_search_messages(
    contains: str,
    channel_ids: list[str] | None = None,
    guild_id: str | None = None,
    limit: int = DEFAULT_LIMIT,
    scan_limit_per_channel: int = DEFAULT_SCAN_LIMIT_PER_CHANNEL,
    case_sensitive: bool = False,
    author_id: str | None = None,
    has_attachments: bool | None = None,
    oldest_first: bool = False,
) -> dict[str, object]:
    """Search visible Discord messages by scanning recent channel history."""

    return await _discord_search_messages(
        contains=contains,
        channel_ids=channel_ids,
        guild_id=guild_id,
        limit=limit,
        scan_limit_per_channel=scan_limit_per_channel,
        case_sensitive=case_sensitive,
        author_id=author_id,
        has_attachments=has_attachments,
        oldest_first=oldest_first,
    )


async def _discord_search_messages(
    *,
    contains: str,
    channel_ids: list[str] | None = None,
    guild_id: str | None = None,
    limit: int = DEFAULT_LIMIT,
    scan_limit_per_channel: int = DEFAULT_SCAN_LIMIT_PER_CHANNEL,
    case_sensitive: bool = False,
    author_id: str | None = None,
    has_attachments: bool | None = None,
    oldest_first: bool = False,
    settings: Settings | None = None,
    client: DiscordClientProtocol | None = None,
) -> dict[str, object]:
    normalized_contains = required_text(contains, "contains")
    normalized_limit = bounded_int(
        value=limit,
        name="limit",
        minimum=1,
        maximum=MAX_SEARCH_RESULTS,
    )
    normalized_scan_limit = bounded_int(
        value=scan_limit_per_channel,
        name="scan_limit_per_channel",
        minimum=1,
        maximum=MAX_SCAN_LIMIT_PER_CHANNEL,
    )
    normalized_author_id = optional_id(author_id)

    resolved_settings = resolve_settings(settings)
    bot_token = require_bot_token(resolved_settings)

    managed_client = client is None
    discord_client = client or build_client(bot_token=bot_token)

    try:
        search_channel_ids = await _resolve_search_channel_ids(
            channel_ids=channel_ids,
            guild_id=guild_id,
            settings=resolved_settings,
            client=discord_client,
        )
        messages: list[dict[str, object]] = []
        scanned_channels: list[dict[str, object]] = []

        for channel_id in search_channel_ids:
            remaining = normalized_limit - len(messages)
            if remaining <= 0:
                break

            result = await _discord_read_messages(
                channel_id=channel_id,
                limit=remaining,
                scan_limit=normalized_scan_limit,
                contains=normalized_contains,
                case_sensitive=case_sensitive,
                author_id=normalized_author_id,
                has_attachments=has_attachments,
                oldest_first=oldest_first,
                settings=resolved_settings,
                client=discord_client,
            )
            channel_messages = cast(list[dict[str, object]], result["messages"])
            messages.extend(channel_messages)
            scanned_channels.append(
                {
                    "channel_id": channel_id,
                    "matched_count": result["count"],
                    "scanned_count": result["scanned_count"],
                    "next_before": result["next_before"],
                    "has_more": result["has_more"],
                }
            )
    finally:
        if managed_client:
            await discord_client.aclose()

    return {
        "status": "ok",
        "query": normalized_contains,
        "count": len(messages),
        "channels_searched": len(scanned_channels),
        "scanned_channels": scanned_channels,
        "messages": messages,
    }


async def _resolve_search_channel_ids(
    *,
    channel_ids: list[str] | None,
    guild_id: str | None,
    settings: Settings,
    client: DiscordClientProtocol,
) -> list[str]:
    if channel_ids is not None:
        normalized_channel_ids = [required_id(channel_id, "channel_id") for channel_id in channel_ids]
        if not normalized_channel_ids:
            raise ValueError("channel_ids must not be empty when provided")
        return normalized_channel_ids

    normalized_guild_id = _resolve_guild_id(guild_id=guild_id, settings=settings)
    assert_guild_is_allowed(guild_id=normalized_guild_id, settings=settings)
    channels = await client.list_guild_channels(normalized_guild_id)
    return [channel.id for channel in filter_allowed_channels(channels=channels, settings=settings)]


def _resolve_guild_id(*, guild_id: str | None, settings: Settings) -> str:
    if guild_id is not None and guild_id.strip():
        return guild_id.strip()

    default_guild_id = settings.default_guild_id
    if default_guild_id is not None:
        return default_guild_id

    raise ValueError(
        "guild_id is required unless DISCORD_DEFAULT_GUILD_ID is configured."
    )
