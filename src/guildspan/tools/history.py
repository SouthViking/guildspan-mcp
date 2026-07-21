"""Message history MCP tools."""

from __future__ import annotations

from guildspan.config import Settings
from guildspan.tools._common import (
    DiscordClientProtocol,
    assert_channel_is_allowed,
    build_client,
    require_bot_token,
    resolve_settings,
)

DEFAULT_LIMIT = 50
DEFAULT_PAGE_SIZE = 100
MAX_RETURNED_MESSAGES = 500
MAX_SCAN_MESSAGES = 1000
MAX_PAGE_SIZE = 100


async def discord_read_messages(
    channel_id: str,
    limit: int = DEFAULT_LIMIT,
    before: str | None = None,
    after: str | None = None,
    around: str | None = None,
    scan_limit: int | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    author_id: str | None = None,
    author_is_bot: bool | None = None,
    contains: str | None = None,
    case_sensitive: bool = False,
    has_attachments: bool | None = None,
    has_embeds: bool | None = None,
    pinned: bool | None = None,
    mentions_user_id: str | None = None,
    message_type: int | None = None,
    include_content: bool = True,
    include_attachments: bool = True,
    include_embeds: bool = True,
    include_stickers: bool = True,
    include_poll: bool = True,
    include_components: bool = True,
    include_reactions: bool = True,
    include_mentions: bool = True,
    include_referenced_message: bool = True,
    oldest_first: bool = False,
) -> dict[str, object]:
    """Read recent or ranged messages from a Discord channel."""

    return await _discord_read_messages(
        channel_id=channel_id,
        limit=limit,
        before=before,
        after=after,
        around=around,
        scan_limit=scan_limit,
        page_size=page_size,
        author_id=author_id,
        author_is_bot=author_is_bot,
        contains=contains,
        case_sensitive=case_sensitive,
        has_attachments=has_attachments,
        has_embeds=has_embeds,
        pinned=pinned,
        mentions_user_id=mentions_user_id,
        message_type=message_type,
        include_content=include_content,
        include_attachments=include_attachments,
        include_embeds=include_embeds,
        include_stickers=include_stickers,
        include_poll=include_poll,
        include_components=include_components,
        include_reactions=include_reactions,
        include_mentions=include_mentions,
        include_referenced_message=include_referenced_message,
        oldest_first=oldest_first,
    )


async def _discord_read_messages(
    *,
    channel_id: str,
    limit: int = DEFAULT_LIMIT,
    before: str | None = None,
    after: str | None = None,
    around: str | None = None,
    scan_limit: int | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    author_id: str | None = None,
    author_is_bot: bool | None = None,
    contains: str | None = None,
    case_sensitive: bool = False,
    has_attachments: bool | None = None,
    has_embeds: bool | None = None,
    pinned: bool | None = None,
    mentions_user_id: str | None = None,
    message_type: int | None = None,
    include_content: bool = True,
    include_attachments: bool = True,
    include_embeds: bool = True,
    include_stickers: bool = True,
    include_poll: bool = True,
    include_components: bool = True,
    include_reactions: bool = True,
    include_mentions: bool = True,
    include_referenced_message: bool = True,
    oldest_first: bool = False,
    settings: Settings | None = None,
    client: DiscordClientProtocol | None = None,
) -> dict[str, object]:
    normalized_channel_id = _required_id(channel_id, "channel_id")
    normalized_before = _optional_id(before)
    normalized_after = _optional_id(after)
    normalized_around = _optional_id(around)
    normalized_author_id = _optional_id(author_id)
    normalized_mentions_user_id = _optional_id(mentions_user_id)
    normalized_contains = _optional_text(contains)
    normalized_limit = _bounded_int(
        value=limit,
        name="limit",
        minimum=1,
        maximum=MAX_RETURNED_MESSAGES,
    )
    normalized_scan_limit = _bounded_int(
        value=scan_limit if scan_limit is not None else normalized_limit,
        name="scan_limit",
        minimum=1,
        maximum=MAX_SCAN_MESSAGES,
    )
    normalized_page_size = _bounded_int(
        value=page_size,
        name="page_size",
        minimum=1,
        maximum=MAX_PAGE_SIZE,
    )

    if normalized_around is not None and (
        normalized_before is not None or normalized_after is not None
    ):
        raise ValueError("around cannot be combined with before or after")

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
        messages, scanned_count, next_before = await _fetch_matching_messages(
            client=discord_client,
            channel_id=normalized_channel_id,
            limit=normalized_limit,
            scan_limit=normalized_scan_limit,
            page_size=normalized_page_size,
            before=normalized_before,
            after=normalized_after,
            around=normalized_around,
            author_id=normalized_author_id,
            author_is_bot=author_is_bot,
            contains=normalized_contains,
            case_sensitive=case_sensitive,
            has_attachments=has_attachments,
            has_embeds=has_embeds,
            pinned=pinned,
            mentions_user_id=normalized_mentions_user_id,
            message_type=message_type,
        )
    finally:
        if managed_client:
            await discord_client.aclose()

    returned_messages = list(reversed(messages)) if oldest_first else messages

    return {
        "status": "ok",
        "channel_id": normalized_channel_id,
        "count": len(messages),
        "scanned_count": scanned_count,
        "has_more": scanned_count >= normalized_scan_limit,
        "next_before": next_before,
        "messages": [
            _summarize_message(
                message,
                include_content=include_content,
                include_attachments=include_attachments,
                include_embeds=include_embeds,
                include_stickers=include_stickers,
                include_poll=include_poll,
                include_components=include_components,
                include_reactions=include_reactions,
                include_mentions=include_mentions,
                include_referenced_message=include_referenced_message,
            )
            for message in returned_messages
        ],
    }


async def _fetch_matching_messages(
    *,
    client: DiscordClientProtocol,
    channel_id: str,
    limit: int,
    scan_limit: int,
    page_size: int,
    before: str | None,
    after: str | None,
    around: str | None,
    author_id: str | None,
    author_is_bot: bool | None,
    contains: str | None,
    case_sensitive: bool,
    has_attachments: bool | None,
    has_embeds: bool | None,
    pinned: bool | None,
    mentions_user_id: str | None,
    message_type: int | None,
) -> tuple[list[dict[str, object]], int, str | None]:
    matched_messages: list[dict[str, object]] = []
    scanned_count = 0
    next_before = before
    last_inspected_message_id: str | None = None

    while scanned_count < scan_limit and len(matched_messages) < limit:
        current_page_size = min(page_size, scan_limit - scanned_count)
        page = await client.list_channel_messages(
            channel_id=channel_id,
            limit=current_page_size,
            before=next_before,
            after=after if next_before is None else None,
            around=around,
        )
        if not page:
            break

        for message in page:
            message_id = _str_field(message, "id")
            if message_id is not None:
                last_inspected_message_id = message_id
            scanned_count += 1
            if after is not None and not _snowflake_is_greater(_str_field(message, "id"), after):
                continue
            if _message_matches(
                message,
                author_id=author_id,
                author_is_bot=author_is_bot,
                contains=contains,
                case_sensitive=case_sensitive,
                has_attachments=has_attachments,
                has_embeds=has_embeds,
                pinned=pinned,
                mentions_user_id=mentions_user_id,
                message_type=message_type,
            ):
                matched_messages.append(message)
                if len(matched_messages) >= limit:
                    break

        if around is not None or len(page) < current_page_size:
            break
        if len(matched_messages) >= limit or scanned_count >= scan_limit:
            break

        oldest_message_id = _str_field(page[-1], "id")
        if oldest_message_id is None:
            break
        next_before = oldest_message_id

    return matched_messages, scanned_count, last_inspected_message_id or next_before


def _message_matches(
    message: dict[str, object],
    *,
    author_id: str | None,
    author_is_bot: bool | None,
    contains: str | None,
    case_sensitive: bool,
    has_attachments: bool | None,
    has_embeds: bool | None,
    pinned: bool | None,
    mentions_user_id: str | None,
    message_type: int | None,
) -> bool:
    author = _dict_field(message, "author")
    if author_id is not None and (
        author is None or _str_field(author, "id") != author_id
    ):
        return False
    if author_is_bot is not None and (
        author is None or _bool_field(author, "bot") is not author_is_bot
    ):
        return False
    if contains is not None:
        content = _str_field(message, "content") or ""
        if case_sensitive:
            if contains not in content:
                return False
        elif contains.lower() not in content.lower():
            return False
    if has_attachments is not None and _has_list_items(message, "attachments") is not has_attachments:
        return False
    if has_embeds is not None and _has_list_items(message, "embeds") is not has_embeds:
        return False
    if pinned is not None and _bool_field(message, "pinned") is not pinned:
        return False
    if mentions_user_id is not None and not _mentions_user(message, mentions_user_id):
        return False
    if message_type is not None and _int_field(message, "type") != message_type:
        return False
    return True


def _summarize_message(
    message: dict[str, object],
    *,
    include_content: bool,
    include_attachments: bool,
    include_embeds: bool,
    include_stickers: bool,
    include_poll: bool,
    include_components: bool,
    include_reactions: bool,
    include_mentions: bool,
    include_referenced_message: bool,
) -> dict[str, object]:
    summary: dict[str, object] = {
        "id": _str_field(message, "id"),
        "channel_id": _str_field(message, "channel_id"),
        "guild_id": _str_field(message, "guild_id"),
        "type": _int_field(message, "type"),
        "timestamp": _str_field(message, "timestamp"),
        "edited_timestamp": _str_field(message, "edited_timestamp"),
        "pinned": _bool_field(message, "pinned"),
        "mention_everyone": _bool_field(message, "mention_everyone"),
        "author": _summarize_user(_dict_field(message, "author")),
        "message_reference": _summarize_message_reference(
            _dict_field(message, "message_reference")
        ),
    }
    if include_content:
        summary["content"] = _str_field(message, "content") or ""
    if include_attachments:
        summary["attachments"] = [
            _summarize_attachment(item)
            for item in _dict_list_field(message, "attachments")
        ]
    if include_embeds:
        summary["embeds"] = [
            _summarize_embed(item)
            for item in _dict_list_field(message, "embeds")
        ]
    if include_stickers:
        summary["stickers"] = [
            _summarize_sticker(item)
            for item in _dict_list_field(message, "sticker_items")
        ]
    if include_poll:
        poll = _dict_field(message, "poll")
        summary["poll"] = _summarize_poll(poll) if poll is not None else None
    if include_components:
        summary["components"] = [
            _copy_discord_object(item)
            for item in _dict_list_field(message, "components")
        ]
    if include_reactions:
        summary["reactions"] = [
            _summarize_reaction(item)
            for item in _dict_list_field(message, "reactions")
        ]
    if include_mentions:
        summary["mentions"] = [
            _summarize_user(item)
            for item in _dict_list_field(message, "mentions")
        ]
        summary["mention_roles"] = _str_list_field(message, "mention_roles")
    if include_referenced_message:
        referenced_message = _dict_field(message, "referenced_message")
        summary["referenced_message"] = (
            _summarize_referenced_message(referenced_message)
            if referenced_message is not None
            else None
        )
    return summary


def _summarize_referenced_message(
    message: dict[str, object],
) -> dict[str, object]:
    summary: dict[str, object] = {
        "id": _str_field(message, "id"),
        "channel_id": _str_field(message, "channel_id"),
        "type": _int_field(message, "type"),
        "content": _str_field(message, "content") or "",
        "timestamp": _str_field(message, "timestamp"),
        "author": _summarize_user(_dict_field(message, "author")),
    }
    summary["attachments"] = [
        _summarize_attachment(item)
        for item in _dict_list_field(message, "attachments")
    ]
    summary["embeds"] = [
        _summarize_embed(item)
        for item in _dict_list_field(message, "embeds")
    ]
    summary["stickers"] = [
        _summarize_sticker(item)
        for item in _dict_list_field(message, "sticker_items")
    ]
    poll = _dict_field(message, "poll")
    summary["poll"] = _summarize_poll(poll) if poll is not None else None
    summary["components"] = [
        _copy_discord_object(item)
        for item in _dict_list_field(message, "components")
    ]
    return summary


def _summarize_user(user: dict[str, object] | None) -> dict[str, object] | None:
    if user is None:
        return None
    return {
        "id": _str_field(user, "id"),
        "username": _str_field(user, "username"),
        "global_name": _str_field(user, "global_name"),
        "bot": _bool_field(user, "bot"),
    }


def _summarize_attachment(attachment: dict[str, object]) -> dict[str, object]:
    return {
        "id": _str_field(attachment, "id"),
        "filename": _str_field(attachment, "filename"),
        "title": _str_field(attachment, "title"),
        "description": _str_field(attachment, "description"),
        "url": _str_field(attachment, "url"),
        "proxy_url": _str_field(attachment, "proxy_url"),
        "content_type": _str_field(attachment, "content_type"),
        "size": _int_field(attachment, "size"),
        "width": _int_field(attachment, "width"),
        "height": _int_field(attachment, "height"),
        "ephemeral": _bool_field(attachment, "ephemeral"),
        "duration_secs": _number_field(attachment, "duration_secs"),
        "waveform": _str_field(attachment, "waveform"),
        "flags": _int_field(attachment, "flags"),
        "placeholder": _str_field(attachment, "placeholder"),
        "placeholder_version": _int_field(attachment, "placeholder_version"),
        "clip_created_at": _str_field(attachment, "clip_created_at"),
        "application": _copy_optional_discord_object(
            _dict_field(attachment, "application")
        ),
        "clip_participants": [
            _summarize_user(item)
            for item in _dict_list_field(attachment, "clip_participants")
        ],
    }


def _summarize_embed(embed: dict[str, object]) -> dict[str, object]:
    return {
        "type": _str_field(embed, "type"),
        "title": _str_field(embed, "title"),
        "description": _str_field(embed, "description"),
        "url": _str_field(embed, "url"),
        "timestamp": _str_field(embed, "timestamp"),
        "color": _int_field(embed, "color"),
        "footer": _summarize_embed_footer(_dict_field(embed, "footer")),
        "image": _summarize_embed_media(_dict_field(embed, "image")),
        "thumbnail": _summarize_embed_media(_dict_field(embed, "thumbnail")),
        "video": _summarize_embed_media(_dict_field(embed, "video")),
        "provider": _summarize_embed_provider(_dict_field(embed, "provider")),
        "author": _summarize_embed_author(_dict_field(embed, "author")),
        "fields": [
            {
                "name": _str_field(field, "name"),
                "value": _str_field(field, "value"),
                "inline": _bool_field(field, "inline"),
            }
            for field in _dict_list_field(embed, "fields")
        ],
    }


def _summarize_embed_media(
    media: dict[str, object] | None,
) -> dict[str, object] | None:
    if media is None:
        return None
    return {
        "url": _str_field(media, "url"),
        "proxy_url": _str_field(media, "proxy_url"),
        "height": _int_field(media, "height"),
        "width": _int_field(media, "width"),
        "content_type": _str_field(media, "content_type"),
        "placeholder": _str_field(media, "placeholder"),
        "placeholder_version": _int_field(media, "placeholder_version"),
        "flags": _int_field(media, "flags"),
    }


def _summarize_embed_footer(
    footer: dict[str, object] | None,
) -> dict[str, object] | None:
    if footer is None:
        return None
    return {
        "text": _str_field(footer, "text"),
        "icon_url": _str_field(footer, "icon_url"),
        "proxy_icon_url": _str_field(footer, "proxy_icon_url"),
    }


def _summarize_embed_provider(
    provider: dict[str, object] | None,
) -> dict[str, object] | None:
    if provider is None:
        return None
    return {
        "name": _str_field(provider, "name"),
        "url": _str_field(provider, "url"),
    }


def _summarize_embed_author(
    author: dict[str, object] | None,
) -> dict[str, object] | None:
    if author is None:
        return None
    return {
        "name": _str_field(author, "name"),
        "url": _str_field(author, "url"),
        "icon_url": _str_field(author, "icon_url"),
        "proxy_icon_url": _str_field(author, "proxy_icon_url"),
    }


def _summarize_sticker(sticker: dict[str, object]) -> dict[str, object]:
    return {
        "id": _str_field(sticker, "id"),
        "name": _str_field(sticker, "name"),
        "format_type": _int_field(sticker, "format_type"),
    }


def _summarize_poll(poll: dict[str, object]) -> dict[str, object]:
    return _copy_discord_object(poll)


def _copy_optional_discord_object(
    value: dict[str, object] | None,
) -> dict[str, object] | None:
    return _copy_discord_object(value) if value is not None else None


def _copy_discord_object(value: dict[str, object]) -> dict[str, object]:
    """Copy a JSON object while preserving Discord fields added after this release."""

    return dict(value)


def _summarize_reaction(reaction: dict[str, object]) -> dict[str, object]:
    return {
        "count": _int_field(reaction, "count"),
        "me": _bool_field(reaction, "me"),
        "emoji": _summarize_emoji(_dict_field(reaction, "emoji")),
    }


def _summarize_emoji(emoji: dict[str, object] | None) -> dict[str, object] | None:
    if emoji is None:
        return None
    return {
        "id": _str_field(emoji, "id"),
        "name": _str_field(emoji, "name"),
        "animated": _bool_field(emoji, "animated"),
    }


def _summarize_message_reference(
    reference: dict[str, object] | None,
) -> dict[str, object] | None:
    if reference is None:
        return None
    return {
        "message_id": _str_field(reference, "message_id"),
        "channel_id": _str_field(reference, "channel_id"),
        "guild_id": _str_field(reference, "guild_id"),
        "type": _int_field(reference, "type"),
    }


def _mentions_user(message: dict[str, object], user_id: str) -> bool:
    return any(_str_field(user, "id") == user_id for user in _dict_list_field(message, "mentions"))


def _has_list_items(source: dict[str, object], key: str) -> bool:
    value = source.get(key)
    return isinstance(value, list) and len(value) > 0


def _dict_list_field(source: dict[str, object], key: str) -> list[dict[str, object]]:
    value = source.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _str_list_field(source: dict[str, object], key: str) -> list[str]:
    value = source.get(key)
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int))]


def _dict_field(source: dict[str, object], key: str) -> dict[str, object] | None:
    value = source.get(key)
    if isinstance(value, dict):
        return value
    return None


def _str_field(source: dict[str, object], key: str) -> str | None:
    value = source.get(key)
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    return None


def _int_field(source: dict[str, object], key: str) -> int | None:
    value = source.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _number_field(source: dict[str, object], key: str) -> int | float | None:
    value = source.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _bool_field(source: dict[str, object], key: str) -> bool | None:
    value = source.get(key)
    if isinstance(value, bool):
        return value
    return None


def _snowflake_is_greater(left: str | None, right: str) -> bool:
    if left is None:
        return False
    try:
        return int(left) > int(right)
    except ValueError:
        return left > right


def _bounded_int(*, value: int, name: str, minimum: int, maximum: int) -> int:
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _required_id(value: str, name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def _optional_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized
