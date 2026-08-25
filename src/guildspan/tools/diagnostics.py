"""Diagnostic MCP tools."""

from __future__ import annotations

from guildspan.config import Settings
from guildspan.errors import DiscordPermissionError, GuildSpanError
from guildspan.tools._common import (
    DiscordClientProtocol,
    assert_guild_is_allowed,
    build_client,
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
    guild_authorization_results: dict[str, GuildSpanError | None] = {}

    async def assert_guild_once(guild_id: str) -> None:
        if guild_id in guild_authorization_results:
            previous_error = guild_authorization_results[guild_id]
            if previous_error is not None:
                raise previous_error
            return
        try:
            await assert_guild_is_allowed(
                guild_id=guild_id,
                settings=resolved_settings,
            )
        except GuildSpanError as error:
            guild_authorization_results[guild_id] = error
            raise
        guild_authorization_results[guild_id] = None

    try:
        if normalized_guild_id is not None:
            guild_allowed = False
            try:
                await assert_guild_once(normalized_guild_id)
                guild_allowed = True
                checks.append(
                    _ok_check("guild_policy", "Guild is allowed by local policy.")
                )
            except GuildSpanError as error:
                checks.append(_failed_check("guild_policy", str(error)))

            if include_channel_sample and guild_allowed:
                try:
                    channels = await discord_client.list_guild_channels(
                        normalized_guild_id
                    )
                    checks.append(
                        {
                            "name": "guild_access",
                            "status": "ok",
                            "message": "Guild channels are readable.",
                            "visible_channel_count": len(channels),
                        }
                    )
                except Exception as error:  # noqa: BLE001
                    checks.append(_failed_check("guild_access", str(error)))

        if normalized_channel_id is not None:
            try:
                channel = await discord_client.get_channel(normalized_channel_id)
                channel_guild_id = channel.guild_id
                if channel_guild_id is None:
                    raise DiscordPermissionError(
                        f"Channel {normalized_channel_id} is not a Discord guild channel."
                    )
                if (
                    normalized_guild_id is not None
                    and channel_guild_id != normalized_guild_id
                ):
                    raise DiscordPermissionError(
                        f"Channel {normalized_channel_id} belongs to guild "
                        f"{channel_guild_id}, not requested guild "
                        f"{normalized_guild_id}."
                    )
                await assert_guild_once(channel_guild_id)
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
