"""Discord identity and per-guild authorization for the hosted MCP runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, TypedDict, cast

import httpx
from fastmcp.server.auth import AccessToken

from guildspan import __version__
from guildspan.config import Settings
from guildspan.discord_client import DiscordClient
from guildspan.errors import (
    DiscordApiError,
    DiscordConfigurationError,
    DiscordPermissionError,
)
from guildspan.persistence import (
    Database,
    GuildAccessRepository,
    GuildInstallationRepository,
    UserRepository,
)

DISCORD_API_BASE_URL = "https://discord.com/api/v10"
ADMINISTRATOR_PERMISSION = 1 << 3
MANAGE_GUILD_PERMISSION = 1 << 5
DISCORD_GUILD_PAGE_SIZE = 200


@dataclass(frozen=True)
class DiscordOAuthGuild:
    """A guild visible to the authenticated Discord user."""

    id: str
    name: str
    icon_url: str | None
    owner: bool
    permissions: int

    @property
    def can_bootstrap_access(self) -> bool:
        """Return whether this user may initialize GuildSpan for the guild."""

        required = ADMINISTRATOR_PERMISSION | MANAGE_GUILD_PERMISSION
        return self.owner or bool(self.permissions & required)


@dataclass(frozen=True)
class DiscordGuildAccess:
    """One guild the authenticated user may select in GuildSpan."""

    id: str
    name: str
    icon_url: str | None
    owner: bool
    status: Literal["authorized", "eligible_to_initialize"]


class DiscordProfile(TypedDict):
    """Profile fields accepted by the user repository."""

    discord_user_id: str
    username: str | None
    display_name: str | None
    avatar_url: str | None


class DiscordIdentityClientProtocol(Protocol):
    """Discord user-token operation required by hosted authorization."""

    async def list_guilds(
        self,
        *,
        access_token: str,
    ) -> list[DiscordOAuthGuild]:
        """Return guilds visible to the current Discord user."""

    async def get_guild(
        self,
        *,
        access_token: str,
        guild_id: str,
    ) -> DiscordOAuthGuild | None:
        """Return one guild visible to the current Discord user."""


class BotGuildVerifierProtocol(Protocol):
    """Verify that the service bot is installed in one guild."""

    async def verify(self, guild_id: str) -> None:
        """Raise if the GuildSpan bot cannot access the guild."""


class DiscordIdentityClient:
    """Read the current user's Discord guilds with their OAuth access token."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http_client = http_client

    async def list_guilds(
        self,
        *,
        access_token: str,
    ) -> list[DiscordOAuthGuild]:
        """Return all guilds visible to the current Discord user."""

        guilds: list[DiscordOAuthGuild] = []
        after: str | None = None

        while True:
            params: dict[str, str | int] = {"limit": DISCORD_GUILD_PAGE_SIZE}
            if after is not None:
                params["after"] = after
            response = await self._http_client.get(
                f"{DISCORD_API_BASE_URL}/users/@me/guilds",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
            if not response.is_success:
                raise DiscordApiError(
                    "Discord could not validate the authenticated user's guilds "
                    f"(status {response.status_code})."
                )

            payload = response.json()
            if not isinstance(payload, list):
                raise DiscordApiError(
                    "Discord returned an invalid current-user guild response."
                )

            page: list[DiscordOAuthGuild] = []
            for raw_guild in payload:
                if not isinstance(raw_guild, dict):
                    raise DiscordApiError(
                        "Discord returned an invalid guild in the current-user list."
                    )
                page.append(_parse_oauth_guild(cast(dict[str, object], raw_guild)))
            guilds.extend(page)

            if len(payload) < DISCORD_GUILD_PAGE_SIZE:
                return guilds
            if not page or page[-1].id == after:
                raise DiscordApiError(
                    "Discord returned invalid pagination for current-user guilds."
                )
            after = page[-1].id

    async def get_guild(
        self,
        *,
        access_token: str,
        guild_id: str,
    ) -> DiscordOAuthGuild | None:
        """Return a target guild from Discord's current-user guild list."""

        guilds = await self.list_guilds(access_token=access_token)
        for guild in guilds:
            if guild.id == guild_id:
                return guild
        return None


class DiscordBotGuildVerifier:
    """Confirm that the centrally managed bot can read a target guild."""

    def __init__(self, bot_token: str) -> None:
        self._bot_token = bot_token

    async def verify(self, guild_id: str) -> None:
        """Use a bot-authenticated guild request as the installation check."""

        client = DiscordClient(bot_token=self._bot_token)
        try:
            await client.list_guild_channels(guild_id)
        finally:
            await client.aclose()


class GuildAuthorizationService:
    """Authorize Discord users against persisted GuildSpan guild grants."""

    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        identity_client: DiscordIdentityClientProtocol,
        bot_verifier: BotGuildVerifierProtocol,
    ) -> None:
        self._settings = settings
        self._database = database
        self._identity_client = identity_client
        self._bot_verifier = bot_verifier

    async def list_available_guilds(
        self,
        *,
        token: AccessToken,
    ) -> list[DiscordGuildAccess]:
        """List authorized or bootstrap-eligible guilds without changing access."""

        discord_user_id = _discord_user_id(token)
        visible_guilds = await self._identity_client.list_guilds(
            access_token=token.token,
        )
        allowed_guilds = {
            guild.id: guild
            for guild in visible_guilds
            if guild.id in self._settings.allowed_guild_ids
        }

        async with self._database.session() as session:
            user = await UserRepository(session).get_by_discord_id(discord_user_id)
            authorized_guild_ids = (
                set(await GuildAccessRepository(session).list_active_guild_ids(user.id))
                if user is not None and user.is_active
                else set()
            )

        available: list[DiscordGuildAccess] = []
        for guild in allowed_guilds.values():
            is_authorized = guild.id in authorized_guild_ids
            if not is_authorized and not guild.can_bootstrap_access:
                continue
            try:
                await self._bot_verifier.verify(guild.id)
            except (DiscordApiError, DiscordPermissionError):
                continue
            available.append(
                DiscordGuildAccess(
                    id=guild.id,
                    name=guild.name,
                    icon_url=guild.icon_url,
                    owner=guild.owner,
                    status=(
                        "authorized" if is_authorized else "eligible_to_initialize"
                    ),
                )
            )

        return sorted(
            available,
            key=lambda guild: (guild.name.casefold(), guild.id),
        )

    async def authorize(self, *, guild_id: str, token: AccessToken) -> None:
        """Authorize one request, bootstrapping an eligible guild when needed."""

        if guild_id not in self._settings.allowed_guild_ids:
            raise DiscordPermissionError(
                f"Guild {guild_id} is not in DISCORD_ALLOWED_GUILDS."
            )

        discord_user_id = _discord_user_id(token)
        guild = await self._identity_client.get_guild(
            access_token=token.token,
            guild_id=guild_id,
        )
        if guild is None:
            raise DiscordPermissionError(
                f"The authenticated Discord user is not a member of guild {guild_id}."
            )

        profile = _discord_profile(token, discord_user_id=discord_user_id)
        async with self._database.session() as session:
            user = await UserRepository(session).upsert(**profile)
            user_id = user.id
            has_access = await GuildAccessRepository(session).has_access(
                user_id=user_id,
                discord_guild_id=guild_id,
            )

        if has_access:
            return

        if not guild.can_bootstrap_access:
            raise DiscordPermissionError(
                "GuildSpan access has not been granted for this guild. A Discord "
                "owner or member with Manage Server must initialize it first."
            )

        await self._bot_verifier.verify(guild_id)

        async with self._database.session() as session:
            user = await UserRepository(session).upsert(**profile)
            installation = await GuildInstallationRepository(session).install(
                discord_guild_id=guild.id,
                name=guild.name,
                icon_url=guild.icon_url,
                installed_by_user_id=user.id,
                metadata={
                    "source": "discord_oauth_bootstrap",
                    "owner": guild.owner,
                    "permissions": str(guild.permissions),
                },
            )
            await GuildAccessRepository(session).grant(
                user_id=user.id,
                guild_installation_id=installation.id,
            )


def create_authorization_service(
    *,
    settings: Settings,
    database: Database,
    http_client: httpx.AsyncClient,
) -> GuildAuthorizationService:
    """Create the production guild authorization service."""

    bot_token = settings.discord_bot_token
    if bot_token is None or not bot_token.strip():
        raise DiscordConfigurationError("DISCORD_BOT_TOKEN is required.")
    return GuildAuthorizationService(
        settings=settings,
        database=database,
        identity_client=DiscordIdentityClient(http_client),
        bot_verifier=DiscordBotGuildVerifier(bot_token.strip()),
    )


def create_oauth_http_client() -> httpx.AsyncClient:
    """Create the shared HTTP client for Discord OAuth and identity checks."""

    return httpx.AsyncClient(
        timeout=10.0,
        headers={"User-Agent": f"guildspan/{__version__}"},
    )


def _parse_oauth_guild(guild: dict[str, object]) -> DiscordOAuthGuild:
    raw_id = guild.get("id")
    raw_name = guild.get("name")
    if not isinstance(raw_id, (str, int)) or not isinstance(raw_name, str):
        raise DiscordApiError("Discord returned an invalid guild identity.")

    raw_permissions = guild.get("permissions", 0)
    try:
        permissions = int(cast(str | int, raw_permissions))
    except (TypeError, ValueError) as error:
        raise DiscordApiError("Discord returned invalid guild permissions.") from error

    raw_icon = guild.get("icon")
    icon_url = None
    if isinstance(raw_icon, str) and raw_icon:
        icon_url = f"https://cdn.discordapp.com/icons/{raw_id}/{raw_icon}.png?size=256"
    return DiscordOAuthGuild(
        id=str(raw_id),
        name=raw_name,
        icon_url=icon_url,
        owner=guild.get("owner") is True,
        permissions=permissions,
    )


def _discord_user_id(token: AccessToken) -> str:
    raw_user_id = token.claims.get("sub") or token.subject
    if not isinstance(raw_user_id, (str, int)) or not str(raw_user_id).strip():
        raise DiscordPermissionError(
            "The authenticated token does not contain a Discord user identity."
        )
    return str(raw_user_id)


def _discord_profile(
    token: AccessToken,
    *,
    discord_user_id: str,
) -> DiscordProfile:
    raw_discord_user = token.claims.get("discord_user")
    discord_user = (
        cast(dict[str, object], raw_discord_user)
        if isinstance(raw_discord_user, dict)
        else {}
    )
    username = _optional_string(discord_user.get("username")) or _optional_string(
        token.claims.get("username")
    )
    display_name = _optional_string(discord_user.get("global_name")) or username
    avatar_hash = _optional_string(discord_user.get("avatar")) or _optional_string(
        token.claims.get("avatar")
    )
    avatar_url = None
    if avatar_hash is not None:
        avatar_url = (
            f"https://cdn.discordapp.com/avatars/{discord_user_id}/"
            f"{avatar_hash}.png?size=256"
        )
    return {
        "discord_user_id": discord_user_id,
        "username": username,
        "display_name": display_name,
        "avatar_url": avatar_url,
    }


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
