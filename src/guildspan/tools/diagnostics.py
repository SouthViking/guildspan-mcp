"""Diagnostic MCP tools."""

from __future__ import annotations

from guildspan.config import Settings
from guildspan.errors import GuildSpanError
from guildspan.tools._common import (
    DiscordClientProtocol,
    assert_channel_is_allowed,
    assert_guild_is_allowed,
    build_client,
    filter_allowed_channels,
    optional_id,
    require_bot_token,
    resolve_settings,
)


async def discord_health_check(
    guild_id: str | None = None,
    channel_id: str | None = None,
    include_channel_sample: bool = True,
) -> dict[str, object]:
    """Check Discord MCP configuration, policy, and basic API access."""

    return await _discord_health_check(
        guild_id=guild_id,
        channel_id=channel_id,
        include_channel_sample=include_channel_sample,
    )


async def _discord_health_check(
    *,
    guild_id: str | None = None,
    channel_id: str | None = None,
    include_channel_sample: bool = True,
    settings: Settings | None = None,
    client: DiscordClientProtocol | None = None,
) -> dict[str, object]:
    resolved_settings = resolve_settings(settings)
    normalized_guild_id = _resolve_optional_guild_id(
        guild_id=guild_id, settings=resolved_settings
    )
    normalized_channel_id = optional_id(channel_id)
    checks: list[dict[str, object]] = []

    try:
        bot_token = require_bot_token(resolved_settings)
        checks.append(_ok_check("configuration", "DISCORD_BOT_TOKEN is configured."))
    except GuildSpanError as error:
        checks.append(_failed_check("configuration", str(error)))
        return _health_result(
            checks=checks,
            guild_id=normalized_guild_id,
            channel_id=normalized_channel_id,
        )

    managed_client = client is None
    discord_client = client or build_client(bot_token=bot_token)

    try:
        if normalized_guild_id is not None:
            try:
                assert_guild_is_allowed(
                    guild_id=normalized_guild_id,
                    settings=resolved_settings,
                )
                checks.append(
                    _ok_check("guild_policy", "Guild is allowed by local policy.")
                )
            except GuildSpanError as error:
                checks.append(_failed_check("guild_policy", str(error)))

            if include_channel_sample:
                try:
                    channels = await discord_client.list_guild_channels(
                        normalized_guild_id
                    )
                    filtered_channels = filter_allowed_channels(
                        channels=channels,
                        settings=resolved_settings,
                    )
                    checks.append(
                        {
                            "name": "guild_access",
                            "status": "ok",
                            "message": "Guild channels are readable.",
                            "visible_channel_count": len(filtered_channels),
                        }
                    )
                except Exception as error:  # noqa: BLE001
                    checks.append(_failed_check("guild_access", str(error)))

        if normalized_channel_id is not None:
            try:
                await assert_channel_is_allowed(
                    channel_id=normalized_channel_id,
                    settings=resolved_settings,
                    client=discord_client,
                )
                channel = await discord_client.get_channel(normalized_channel_id)
                checks.append(
                    {
                        "name": "channel_access",
                        "status": "ok",
                        "message": "Channel is readable.",
                        "channel": {
                            "id": channel.id,
                            "name": channel.name,
                            "guild_id": channel.guild_id,
                            "type": channel.type,
                            "position": channel.position,
                        },
                    }
                )
            except Exception as error:  # noqa: BLE001
                checks.append(_failed_check("channel_access", str(error)))
    finally:
        if managed_client:
            await discord_client.aclose()

    return _health_result(
        checks=checks,
        guild_id=normalized_guild_id,
        channel_id=normalized_channel_id,
    )


def _resolve_optional_guild_id(
    *, guild_id: str | None, settings: Settings
) -> str | None:
    if guild_id is not None and guild_id.strip():
        return guild_id.strip()
    return settings.default_guild_id


def _ok_check(name: str, message: str) -> dict[str, object]:
    return {"name": name, "status": "ok", "message": message}


def _failed_check(name: str, message: str) -> dict[str, object]:
    return {"name": name, "status": "failed", "message": message}


def _health_result(
    *,
    checks: list[dict[str, object]],
    guild_id: str | None,
    channel_id: str | None,
) -> dict[str, object]:
    status = "ok" if all(check["status"] == "ok" for check in checks) else "degraded"
    return {
        "status": status,
        "guild_id": guild_id,
        "channel_id": channel_id,
        "checks": checks,
    }
