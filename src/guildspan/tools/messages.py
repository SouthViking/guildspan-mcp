"""Message-related MCP tools."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from guildspan.config import DEFAULT_ATTRIBUTION_TEXT, Settings
from guildspan.i18n import (
    LocaleResolution,
    get_attribution_text,
    get_legacy_actor_attribution,
    resolve_message_locale,
)
from guildspan.tools._common import (
    DiscordClientProtocol,
    assert_channel_is_allowed,
    build_client,
    require_bot_token,
    required_id,
    required_text,
    resolve_settings,
)
from guildspan.tools.uploads import (
    OutgoingAttachment,
    UploadDownloaderProtocol,
    resolve_outgoing_attachments,
)

MAX_MESSAGE_CONTENT_LENGTH = 2000
MAX_STICKERS = 3


async def discord_send_message(
    channel_id: str,
    content: str | None = None,
    attachments: list[OutgoingAttachment] | None = None,
    sticker_ids: list[str] | None = None,
    locale: Annotated[
        str | None,
        Field(
            description=(
                "Locale matching the language of the outgoing message, such as "
                "en, es-CL, or fr-FR. GuildSpan uses it only to select a controlled "
                "attribution translation. Supported base languages are en, es, and "
                "fr; unsupported or invalid locales fall back to English. For "
                "media-only messages, use the language requested by the user for "
                "the attribution."
            )
        ),
    ] = None,
) -> dict[str, object]:
    """Send content to Discord using the message language as its locale."""

    return await _discord_send_message(
        channel_id=channel_id,
        content=content,
        attachments=attachments,
        sticker_ids=sticker_ids,
        locale=locale,
    )


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
    content: str | None = None,
    attachments: list[OutgoingAttachment] | None = None,
    sticker_ids: list[str] | None = None,
    locale: str | None = None,
    settings: Settings | None = None,
    client: DiscordClientProtocol | None = None,
    upload_downloader: UploadDownloaderProtocol | None = None,
) -> dict[str, object]:
    normalized_channel_id = required_id(channel_id, "channel_id")
    normalized_content = _optional_text(content)
    normalized_attachments = attachments or []
    normalized_sticker_ids = _normalize_sticker_ids(sticker_ids)
    if (
        normalized_content is None
        and not normalized_attachments
        and not normalized_sticker_ids
    ):
        raise ValueError(
            "At least one of content, attachments, or sticker_ids is required"
        )

    resolved_settings = resolve_settings(settings)
    bot_token = require_bot_token(resolved_settings)
    locale_resolution = resolve_message_locale(locale)

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
            locale=locale_resolution,
        )
        _assert_content_length(final_content)
        resolved_attachments = await resolve_outgoing_attachments(
            attachments=normalized_attachments,
            settings=resolved_settings,
            downloader=upload_downloader,
        )
        message = await discord_client.send_message(
            channel_id=normalized_channel_id,
            content=final_content,
            attachments=resolved_attachments,
            sticker_ids=normalized_sticker_ids,
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
        "attachments": [dict(item) for item in message.attachments],
        "stickers": [dict(item) for item in message.stickers],
        "requested_locale": locale_resolution.requested,
        "resolved_locale": locale_resolution.resolved,
        "locale_fallback": locale_resolution.used_fallback,
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
        if final_content is None:
            raise AssertionError("required edit content cannot format to None")
        _assert_content_length(final_content)
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


def _format_message_content(
    *,
    content: str | None,
    settings: Settings,
    locale: LocaleResolution | None = None,
) -> str | None:
    if not settings.discord_append_attribution:
        return content

    locale_resolution = locale or resolve_message_locale(None)
    attribution_text = _resolve_attribution_text(
        configured_text=settings.discord_attribution_text,
        locale=locale_resolution.resolved,
    )
    actor_label = _format_actor_label(settings)
    if attribution_text is not None:
        body_parts = [part for part in (actor_label, content) if part is not None]
        attributed_content = "\n".join(body_parts)
        if actor_label is not None:
            attributed_content = f"\n{attributed_content}"
        if attributed_content:
            return f"{attributed_content}\n\n-# {attribution_text}"
        return f"-# {attribution_text}"

    # Preserve the former actor-specific format when the branded text is
    # explicitly configured as blank.
    actor_name = _normalized_or_none(settings.discord_actor_name)
    actor_discord_id = _normalized_or_none(settings.discord_actor_discord_id)

    if actor_discord_id is not None:
        footer = "-# " + get_legacy_actor_attribution(
            locale=locale_resolution.resolved,
            actor=f"<@{actor_discord_id}>",
        )
        return f"{content}\n\n{footer}" if content is not None else footer
    if actor_name is not None:
        footer = "-# " + get_legacy_actor_attribution(
            locale=locale_resolution.resolved,
            actor=actor_name,
        )
        return f"{content}\n\n{footer}" if content is not None else footer
    return content


def _resolve_attribution_text(
    *, configured_text: str | None, locale: str
) -> str | None:
    normalized_text = _normalized_or_none(configured_text)
    if normalized_text is None:
        return None
    if normalized_text == DEFAULT_ATTRIBUTION_TEXT:
        return get_attribution_text(locale)
    return normalized_text


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


def _optional_text(value: str | None) -> str | None:
    return _normalized_or_none(value)


def _normalize_sticker_ids(values: list[str] | None) -> list[str]:
    if values is None:
        return []
    if len(values) > MAX_STICKERS:
        raise ValueError(f"sticker_ids cannot contain more than {MAX_STICKERS} items")
    normalized = [
        required_id(value, f"sticker_ids[{index}]")
        for index, value in enumerate(values)
    ]
    if len(set(normalized)) != len(normalized):
        raise ValueError("sticker_ids cannot contain duplicates")
    return normalized


def _assert_content_length(content: str | None) -> None:
    if content is not None and len(content) > MAX_MESSAGE_CONTENT_LENGTH:
        raise ValueError(
            "Message content, including configured attribution, cannot exceed "
            f"{MAX_MESSAGE_CONTENT_LENGTH} characters"
        )
