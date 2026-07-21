"""Message-related MCP tools."""

from __future__ import annotations

from discord_mcp_bridge.config import Settings
from discord_mcp_bridge.tools._common import (
    DiscordClientProtocol,
    assert_channel_is_allowed,
    build_client,
    required_id,
    required_text,
    require_bot_token,
    resolve_settings,
)


async def discord_send_message(channel_id: str, content: str) -> dict[str, str]:
    """Send a message to a Discord channel using the configured Discord bot."""

    return await _discord_send_message(channel_id=channel_id, content=content)


async def discord_edit_own_message(
    channel_id: str,
    message_id: str,
    content: str,
) -> dict[str, str]:
    """Edit a Discord message previously sent by the configured bot."""

    return await _discord_edit_own_message(
        channel_id=channel_id,
        message_id=message_id,
        content=content,
    )


async def _discord_send_message(
    *,
    channel_id: str,
    content: str,
    settings: Settings | None = None,
    client: DiscordClientProtocol | None = None,
) -> dict[str, str]:
    normalized_channel_id = required_id(channel_id, "channel_id")
    normalized_content = required_text(content, "content")

    resolved_settings = resolve_settings(settings)
    bot_token = require_bot_token(resolved_settings)

    managed_client = client is None
    discord_client = client or build_client(bot_token=bot_token)

    try:
        await assert_channel_is_allowed(
            channel_id=normalized_channel_id,
            settings=resolved_settings,
            client=discord_client,
        )
        final_content = _format_message_content(
            content=normalized_content,
            settings=resolved_settings,
        )
        message = await discord_client.send_message(
            channel_id=normalized_channel_id,
            content=final_content,
        )
    finally:
        if managed_client:
            await discord_client.aclose()

    return {
        "status": "sent",
        "message_id": message.id,
        "channel_id": message.channel_id,
        "content": message.content,
        "author_username": message.author_username,
    }


async def _discord_edit_own_message(
    *,
    channel_id: str,
    message_id: str,
    content: str,
    settings: Settings | None = None,
    client: DiscordClientProtocol | None = None,
) -> dict[str, str]:
    normalized_channel_id = required_id(channel_id, "channel_id")
    normalized_message_id = required_id(message_id, "message_id")
    normalized_content = required_text(content, "content")

    resolved_settings = resolve_settings(settings)
    bot_token = require_bot_token(resolved_settings)

    managed_client = client is None
    discord_client = client or build_client(bot_token=bot_token)

    try:
        await assert_channel_is_allowed(
            channel_id=normalized_channel_id,
            settings=resolved_settings,
            client=discord_client,
        )
        final_content = _format_message_content(
            content=normalized_content,
            settings=resolved_settings,
        )
        message = await discord_client.edit_message(
            channel_id=normalized_channel_id,
            message_id=normalized_message_id,
            content=final_content,
        )
    finally:
        if managed_client:
            await discord_client.aclose()

    return {
        "status": "edited",
        "message_id": message.id,
        "channel_id": message.channel_id,
        "content": message.content,
        "author_username": message.author_username,
    }


def _format_message_content(*, content: str, settings: Settings) -> str:
    if not settings.discord_append_attribution:
        return content

    attribution_text = _normalized_or_none(settings.discord_attribution_text)
    actor_label = _format_actor_label(settings)
    if attribution_text is not None:
        attributed_content = (
            f"{actor_label}\n{content}" if actor_label is not None else content
        )
        return f"{attributed_content}\n\n-# {attribution_text}"

    # Preserve the former actor-specific format when the branded text is
    # explicitly configured as blank.
    actor_name = _normalized_or_none(settings.discord_actor_name)
    actor_discord_id = _normalized_or_none(settings.discord_actor_discord_id)

    if actor_discord_id is not None:
        return f"{content}\n\n-# sent via MCP by <@{actor_discord_id}>"
    if actor_name is not None:
        return f"{content}\n\n-# sent via MCP by {actor_name}"
    return content


def _format_actor_label(settings: Settings) -> str | None:
    actor_name = _normalized_or_none(settings.discord_actor_name)
    if actor_name is not None:
        return f"**{actor_name}**"

    actor_discord_id = _normalized_or_none(settings.discord_actor_discord_id)
    if actor_discord_id is not None:
        return f"<@{actor_discord_id}>"
    return None


def _normalized_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return stripped
