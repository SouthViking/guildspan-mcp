"""Read-only Discord user, member, and role tools."""

from __future__ import annotations

from typing import Protocol, cast

from discord_mcp_bridge.config import Settings
from discord_mcp_bridge.discord_client import DiscordClient
from discord_mcp_bridge.errors import DiscordApiError
from discord_mcp_bridge.tools._common import (
    assert_guild_is_allowed,
    bounded_int,
    optional_id,
    required_id,
    required_text,
    require_bot_token,
    resolve_settings,
)

DEFAULT_MEMBER_SEARCH_LIMIT = 25
MAX_MEMBER_SEARCH_LIMIT = 100


class DiscordPeopleClientProtocol(Protocol):
    """Client operations required by the read-only people tools."""

    async def get_current_user(self) -> dict[str, object]:
        """Fetch the configured bot user."""

    async def get_user(self, user_id: str) -> dict[str, object]:
        """Fetch a Discord user by ID."""

    async def get_guild_member(
        self,
        *,
        guild_id: str,
        user_id: str,
    ) -> dict[str, object]:
        """Fetch one member from a guild."""

    async def search_guild_members(
        self,
        *,
        guild_id: str,
        query: str,
        limit: int,
    ) -> list[dict[str, object]]:
        """Search guild members by username or nickname prefix."""

    async def list_guild_roles(self, guild_id: str) -> list[dict[str, object]]:
        """Fetch roles configured in a guild."""

    async def aclose(self) -> None:
        """Close network resources."""


async def discord_get_current_bot_user() -> dict[str, object]:
    """Get the Discord user represented by the configured bot token."""

    return await _discord_get_current_bot_user()


async def discord_get_user(user_id: str) -> dict[str, object]:
    """Get public Discord profile fields for a user ID."""

    return await _discord_get_user(user_id=user_id)


async def discord_get_member(
    user_id: str,
    guild_id: str | None = None,
    resolve_roles: bool = True,
) -> dict[str, object]:
    """Get a guild member and optionally resolve their role IDs."""

    return await _discord_get_member(
        user_id=user_id,
        guild_id=guild_id,
        resolve_roles=resolve_roles,
    )


async def discord_search_members(
    query: str,
    guild_id: str | None = None,
    limit: int = DEFAULT_MEMBER_SEARCH_LIMIT,
    resolve_roles: bool = True,
) -> dict[str, object]:
    """Search guild members by username or nickname prefix."""

    return await _discord_search_members(
        query=query,
        guild_id=guild_id,
        limit=limit,
        resolve_roles=resolve_roles,
    )


async def discord_list_roles(guild_id: str | None = None) -> dict[str, object]:
    """List roles in an allowed guild without modifying them."""

    return await _discord_list_roles(guild_id=guild_id)


async def _discord_get_current_bot_user(
    *,
    settings: Settings | None = None,
    client: DiscordPeopleClientProtocol | None = None,
) -> dict[str, object]:
    resolved_settings = resolve_settings(settings)
    bot_token = require_bot_token(resolved_settings)
    managed_client = client is None
    discord_client = client or _build_people_client(bot_token=bot_token)

    try:
        user = await discord_client.get_current_user()
    finally:
        if managed_client:
            await discord_client.aclose()

    return {"status": "ok", "user": _summarize_user(user)}


async def _discord_get_user(
    *,
    user_id: str,
    settings: Settings | None = None,
    client: DiscordPeopleClientProtocol | None = None,
) -> dict[str, object]:
    normalized_user_id = required_id(user_id, "user_id")
    resolved_settings = resolve_settings(settings)
    bot_token = require_bot_token(resolved_settings)
    managed_client = client is None
    discord_client = client or _build_people_client(bot_token=bot_token)

    try:
        user = await discord_client.get_user(normalized_user_id)
    finally:
        if managed_client:
            await discord_client.aclose()

    return {"status": "ok", "user": _summarize_user(user)}


async def _discord_get_member(
    *,
    user_id: str,
    guild_id: str | None = None,
    resolve_roles: bool = True,
    settings: Settings | None = None,
    client: DiscordPeopleClientProtocol | None = None,
) -> dict[str, object]:
    normalized_user_id = required_id(user_id, "user_id")
    resolved_settings = resolve_settings(settings)
    normalized_guild_id = _resolve_guild_id(
        guild_id=guild_id,
        settings=resolved_settings,
    )
    assert_guild_is_allowed(guild_id=normalized_guild_id, settings=resolved_settings)
    bot_token = require_bot_token(resolved_settings)
    managed_client = client is None
    discord_client = client or _build_people_client(bot_token=bot_token)

    try:
        member = await discord_client.get_guild_member(
            guild_id=normalized_guild_id,
            user_id=normalized_user_id,
        )
        role_index = await _get_role_index(
            guild_id=normalized_guild_id,
            resolve_roles=resolve_roles,
            client=discord_client,
        )
    finally:
        if managed_client:
            await discord_client.aclose()

    return {
        "status": "ok",
        "guild_id": normalized_guild_id,
        "member": _summarize_member(member, role_index=role_index),
    }


async def _discord_search_members(
    *,
    query: str,
    guild_id: str | None = None,
    limit: int = DEFAULT_MEMBER_SEARCH_LIMIT,
    resolve_roles: bool = True,
    settings: Settings | None = None,
    client: DiscordPeopleClientProtocol | None = None,
) -> dict[str, object]:
    normalized_query = required_text(query, "query")
    normalized_limit = bounded_int(
        value=limit,
        name="limit",
        minimum=1,
        maximum=MAX_MEMBER_SEARCH_LIMIT,
    )
    resolved_settings = resolve_settings(settings)
    normalized_guild_id = _resolve_guild_id(
        guild_id=guild_id,
        settings=resolved_settings,
    )
    assert_guild_is_allowed(guild_id=normalized_guild_id, settings=resolved_settings)
    bot_token = require_bot_token(resolved_settings)
    managed_client = client is None
    discord_client = client or _build_people_client(bot_token=bot_token)

    try:
        members = await discord_client.search_guild_members(
            guild_id=normalized_guild_id,
            query=normalized_query,
            limit=normalized_limit,
        )
        role_index = await _get_role_index(
            guild_id=normalized_guild_id,
            resolve_roles=resolve_roles,
            client=discord_client,
        )
    finally:
        if managed_client:
            await discord_client.aclose()

    summarized_members = [
        _summarize_member(member, role_index=role_index) for member in members
    ]
    return {
        "status": "ok",
        "guild_id": normalized_guild_id,
        "query": normalized_query,
        "count": len(summarized_members),
        "members": summarized_members,
    }


async def _discord_list_roles(
    *,
    guild_id: str | None = None,
    settings: Settings | None = None,
    client: DiscordPeopleClientProtocol | None = None,
) -> dict[str, object]:
    resolved_settings = resolve_settings(settings)
    normalized_guild_id = _resolve_guild_id(
        guild_id=guild_id,
        settings=resolved_settings,
    )
    assert_guild_is_allowed(guild_id=normalized_guild_id, settings=resolved_settings)
    bot_token = require_bot_token(resolved_settings)
    managed_client = client is None
    discord_client = client or _build_people_client(bot_token=bot_token)

    try:
        raw_roles = await discord_client.list_guild_roles(normalized_guild_id)
    finally:
        if managed_client:
            await discord_client.aclose()

    roles = [_summarize_role(role) for role in raw_roles]
    roles.sort(key=_role_position, reverse=True)
    return {
        "status": "ok",
        "guild_id": normalized_guild_id,
        "count": len(roles),
        "roles": roles,
    }


def _build_people_client(*, bot_token: str) -> DiscordPeopleClientProtocol:
    return DiscordClient(bot_token=bot_token)


async def _get_role_index(
    *,
    guild_id: str,
    resolve_roles: bool,
    client: DiscordPeopleClientProtocol,
) -> dict[str, dict[str, object]] | None:
    if not resolve_roles:
        return None
    roles = await client.list_guild_roles(guild_id)
    return {
        _required_id_field(role, "role"): _summarize_role(role) for role in roles
    }


def _summarize_user(user: dict[str, object]) -> dict[str, object]:
    username = _required_string_field(user, "username", "user")
    global_name = _optional_string_field(user, "global_name")
    return {
        "id": _required_id_field(user, "user"),
        "username": username,
        "global_name": global_name,
        "display_name": global_name or username,
        "discriminator": _optional_string_field(user, "discriminator"),
        "avatar": _optional_string_field(user, "avatar"),
        "bot": _optional_bool_field(user, "bot"),
        "system": _optional_bool_field(user, "system"),
        "public_flags": _optional_int_field(user, "public_flags"),
    }


def _summarize_member(
    member: dict[str, object],
    *,
    role_index: dict[str, dict[str, object]] | None,
) -> dict[str, object]:
    user_value = member.get("user")
    if not isinstance(user_value, dict):
        raise DiscordApiError("Discord member response did not include a valid user object.")
    user = _summarize_user(cast(dict[str, object], user_value))
    nickname = _optional_string_field(member, "nick")
    role_ids = _string_list_field(member, "roles")
    summary: dict[str, object] = {
        "user": user,
        "display_name": nickname or user["display_name"],
        "nick": nickname,
        "avatar": _optional_string_field(member, "avatar"),
        "role_ids": role_ids,
        "joined_at": _optional_string_field(member, "joined_at"),
        "premium_since": _optional_string_field(member, "premium_since"),
        "pending": _optional_bool_field(member, "pending"),
        "communication_disabled_until": _optional_string_field(
            member,
            "communication_disabled_until",
        ),
        "deaf": _optional_bool_field(member, "deaf"),
        "mute": _optional_bool_field(member, "mute"),
        "flags": _optional_int_field(member, "flags"),
    }
    if role_index is not None:
        summary["roles"] = [
            role_index.get(role_id, {"id": role_id, "name": None})
            for role_id in role_ids
        ]
    return summary


def _summarize_role(role: dict[str, object]) -> dict[str, object]:
    return {
        "id": _required_id_field(role, "role"),
        "name": _required_string_field(role, "name", "role"),
        "description": _optional_string_field(role, "description"),
        "color": _optional_int_field(role, "color"),
        "position": _optional_int_field(role, "position"),
        "permissions": _optional_string_field(role, "permissions"),
        "managed": _optional_bool_field(role, "managed"),
        "mentionable": _optional_bool_field(role, "mentionable"),
        "hoist": _optional_bool_field(role, "hoist"),
        "icon": _optional_string_field(role, "icon"),
        "unicode_emoji": _optional_string_field(role, "unicode_emoji"),
        "flags": _optional_int_field(role, "flags"),
    }


def _resolve_guild_id(*, guild_id: str | None, settings: Settings) -> str:
    normalized_guild_id = optional_id(guild_id)
    if normalized_guild_id is not None:
        return normalized_guild_id
    default_guild_id = settings.default_guild_id
    if default_guild_id is not None:
        return default_guild_id
    raise ValueError(
        "guild_id is required unless DISCORD_DEFAULT_GUILD_ID is configured."
    )


def _required_id_field(source: dict[str, object], resource_name: str) -> str:
    value = source.get("id")
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise DiscordApiError(
            f"Discord {resource_name} response did not include a valid id."
        )
    return str(value)


def _required_string_field(
    source: dict[str, object],
    key: str,
    resource_name: str,
) -> str:
    value = source.get(key)
    if not isinstance(value, str):
        raise DiscordApiError(
            f"Discord {resource_name} response did not include a valid {key}."
        )
    return value


def _optional_string_field(source: dict[str, object], key: str) -> str | None:
    value = source.get(key)
    if isinstance(value, str):
        return value
    return None


def _optional_bool_field(source: dict[str, object], key: str) -> bool | None:
    value = source.get(key)
    if isinstance(value, bool):
        return value
    return None


def _optional_int_field(source: dict[str, object], key: str) -> int | None:
    value = source.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _string_list_field(source: dict[str, object], key: str) -> list[str]:
    value = source.get(key)
    if not isinstance(value, list):
        return []
    return [
        str(item)
        for item in value
        if isinstance(item, (str, int)) and not isinstance(item, bool)
    ]


def _role_position(role: dict[str, object]) -> int:
    position = role.get("position")
    if isinstance(position, bool) or not isinstance(position, int):
        return -1
    return position
