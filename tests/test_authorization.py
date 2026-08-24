from __future__ import annotations

from typing import Any, cast

import httpx
import pytest
from fastmcp.server.auth import AccessToken

from guildspan.authorization import (
    DISCORD_GUILD_PAGE_SIZE,
    MANAGE_GUILD_PERMISSION,
    BotGuildVerifierProtocol,
    DiscordIdentityClient,
    DiscordIdentityClientProtocol,
    DiscordOAuthGuild,
    GuildAuthorizationService,
)
from guildspan.config import Settings
from guildspan.errors import DiscordApiError, DiscordPermissionError
from guildspan.persistence import (
    Base,
    Database,
    GuildAccessRepository,
    GuildInstallationRepository,
    UserRepository,
)


def make_settings(**kwargs: object) -> Settings:
    settings_ctor = cast(Any, Settings)
    defaults: dict[str, object] = {
        "discord_bot_token": "bot-token",
        "discord_allowed_guilds": "guild-1",
    }
    defaults.update(kwargs)
    return cast(Settings, settings_ctor(_env_file=None, **defaults))


async def create_test_database() -> Database:
    database = Database("sqlite+aiosqlite:///:memory:")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return database


class FakeIdentityClient(DiscordIdentityClientProtocol):
    def __init__(
        self,
        guild: DiscordOAuthGuild | None,
        *,
        guilds: list[DiscordOAuthGuild] | None = None,
    ) -> None:
        self.guild = guild
        self.guilds = guilds
        self.calls: list[tuple[str, str]] = []
        self.list_calls: list[str] = []

    async def list_guilds(
        self,
        *,
        access_token: str,
    ) -> list[DiscordOAuthGuild]:
        self.list_calls.append(access_token)
        if self.guilds is not None:
            return self.guilds
        return [] if self.guild is None else [self.guild]

    async def get_guild(
        self,
        *,
        access_token: str,
        guild_id: str,
    ) -> DiscordOAuthGuild | None:
        self.calls.append((access_token, guild_id))
        return self.guild


class FakeBotVerifier(BotGuildVerifierProtocol):
    def __init__(self, *, inaccessible: set[str] | None = None) -> None:
        self.calls: list[str] = []
        self.inaccessible = inaccessible or set()

    async def verify(self, guild_id: str) -> None:
        self.calls.append(guild_id)
        if guild_id in self.inaccessible:
            raise DiscordApiError("bot cannot access guild")


def access_token(*, user_id: str = "user-1") -> AccessToken:
    return AccessToken(
        token="discord-user-token",
        client_id="discord-app",
        scopes=["identify", "guilds"],
        claims={
            "sub": user_id,
            "discord_user": {
                "id": user_id,
                "username": "ada",
                "global_name": "Ada Lovelace",
                "avatar": "avatar-hash",
            },
        },
    )


@pytest.mark.asyncio
async def test_authorization_bootstraps_admin_and_reuses_persisted_grant() -> None:
    database = await create_test_database()
    identity = FakeIdentityClient(
        DiscordOAuthGuild(
            id="guild-1",
            name="Guild One",
            icon_url="https://example.com/icon.png",
            owner=False,
            permissions=MANAGE_GUILD_PERMISSION,
        )
    )
    verifier = FakeBotVerifier()
    service = GuildAuthorizationService(
        settings=make_settings(),
        database=database,
        identity_client=identity,
        bot_verifier=verifier,
    )

    try:
        await service.authorize(guild_id="guild-1", token=access_token())

        assert verifier.calls == ["guild-1"]
        async with database.session() as session:
            user = await UserRepository(session).get_by_discord_id("user-1")
            installation = await GuildInstallationRepository(session).get_by_discord_id(
                "guild-1"
            )
            assert user is not None
            assert user.display_name == "Ada Lovelace"
            assert user.avatar_url is not None
            assert installation is not None
            assert installation.name == "Guild One"
            assert installation.installation_metadata["source"] == (
                "discord_oauth_bootstrap"
            )
            assert await GuildAccessRepository(session).has_access(
                user_id=user.id,
                discord_guild_id="guild-1",
            )

        identity.guild = DiscordOAuthGuild(
            id="guild-1",
            name="Guild One",
            icon_url=None,
            owner=False,
            permissions=0,
        )
        await service.authorize(guild_id="guild-1", token=access_token())

        assert verifier.calls == ["guild-1"]
        assert identity.calls == [
            ("discord-user-token", "guild-1"),
            ("discord-user-token", "guild-1"),
        ]
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_authorization_rejects_unprivileged_first_user() -> None:
    database = await create_test_database()
    identity = FakeIdentityClient(
        DiscordOAuthGuild(
            id="guild-1",
            name="Guild One",
            icon_url=None,
            owner=False,
            permissions=0,
        )
    )
    verifier = FakeBotVerifier()
    service = GuildAuthorizationService(
        settings=make_settings(),
        database=database,
        identity_client=identity,
        bot_verifier=verifier,
    )

    try:
        with pytest.raises(DiscordPermissionError, match="Manage Server"):
            await service.authorize(guild_id="guild-1", token=access_token())
        assert verifier.calls == []
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_authorization_rejects_user_outside_target_guild() -> None:
    database = await create_test_database()
    service = GuildAuthorizationService(
        settings=make_settings(),
        database=database,
        identity_client=FakeIdentityClient(None),
        bot_verifier=FakeBotVerifier(),
    )

    try:
        with pytest.raises(DiscordPermissionError, match="not a member"):
            await service.authorize(guild_id="guild-1", token=access_token())
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_authorization_rejects_guild_outside_operator_allowlist() -> None:
    database = await create_test_database()
    service = GuildAuthorizationService(
        settings=make_settings(),
        database=database,
        identity_client=FakeIdentityClient(None),
        bot_verifier=FakeBotVerifier(),
    )

    try:
        with pytest.raises(DiscordPermissionError, match="DISCORD_ALLOWED_GUILDS"):
            await service.authorize(guild_id="guild-2", token=access_token())
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_list_available_guilds_returns_only_authorized_or_eligible() -> None:
    database = await create_test_database()
    identity = FakeIdentityClient(
        None,
        guilds=[
            DiscordOAuthGuild(
                id="guild-authorized",
                name="Authorized",
                icon_url=None,
                owner=False,
                permissions=0,
            ),
            DiscordOAuthGuild(
                id="guild-eligible",
                name="Eligible",
                icon_url="https://example.com/eligible.png",
                owner=False,
                permissions=MANAGE_GUILD_PERMISSION,
            ),
            DiscordOAuthGuild(
                id="guild-unprivileged",
                name="Unprivileged",
                icon_url=None,
                owner=False,
                permissions=0,
            ),
            DiscordOAuthGuild(
                id="guild-bot-missing",
                name="Bot Missing",
                icon_url=None,
                owner=True,
                permissions=0,
            ),
            DiscordOAuthGuild(
                id="guild-not-allowed",
                name="Not Allowed",
                icon_url=None,
                owner=True,
                permissions=0,
            ),
        ],
    )
    verifier = FakeBotVerifier(inaccessible={"guild-bot-missing"})
    service = GuildAuthorizationService(
        settings=make_settings(
            discord_allowed_guilds=(
                "guild-authorized,guild-eligible,guild-unprivileged,"
                "guild-bot-missing"
            )
        ),
        database=database,
        identity_client=identity,
        bot_verifier=verifier,
    )

    try:
        async with database.session() as session:
            user = await UserRepository(session).upsert(discord_user_id="user-1")
            installation = await GuildInstallationRepository(session).install(
                discord_guild_id="guild-authorized",
                name="Authorized",
                installed_by_user_id=user.id,
            )
            await GuildAccessRepository(session).grant(
                user_id=user.id,
                guild_installation_id=installation.id,
            )

        guilds = await service.list_available_guilds(token=access_token())

        assert [(guild.id, guild.status) for guild in guilds] == [
            ("guild-authorized", "authorized"),
            ("guild-eligible", "eligible_to_initialize"),
        ]
        assert verifier.calls == [
            "guild-authorized",
            "guild-eligible",
            "guild-bot-missing",
        ]
        async with database.session() as session:
            stored_user = await UserRepository(session).get_by_discord_id("user-1")
            assert stored_user is not None
            assert await GuildAccessRepository(session).list_active_guild_ids(
                stored_user.id
            ) == ["guild-authorized"]
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_discord_identity_client_sends_bearer_token_and_parses_guild() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=[
                {
                    "id": "guild-1",
                    "name": "Guild One",
                    "icon": "icon-hash",
                    "owner": True,
                    "permissions": "0",
                }
            ],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        guilds = await DiscordIdentityClient(client).list_guilds(
            access_token="secret-user-token",
        )

    guild = guilds[0]
    assert guild is not None
    assert guild.owner is True
    assert guild.can_bootstrap_access is True
    assert guild.icon_url == (
        "https://cdn.discordapp.com/icons/guild-1/icon-hash.png?size=256"
    )
    assert requests[0].headers["Authorization"] == "Bearer secret-user-token"
    assert requests[0].url.params["limit"] == "200"


@pytest.mark.asyncio
async def test_discord_identity_client_paginates_guilds() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                200,
                json=[
                    {
                        "id": str(index),
                        "name": f"Guild {index}",
                        "owner": False,
                        "permissions": "0",
                    }
                    for index in range(DISCORD_GUILD_PAGE_SIZE)
                ],
            )
        return httpx.Response(
            200,
            json=[
                {
                    "id": "final",
                    "name": "Final Guild",
                    "owner": True,
                    "permissions": "0",
                }
            ],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        guilds = await DiscordIdentityClient(client).list_guilds(
            access_token="secret-user-token"
        )

    assert len(guilds) == DISCORD_GUILD_PAGE_SIZE + 1
    assert requests[0].url.params.get("after") is None
    assert requests[1].url.params["after"] == str(DISCORD_GUILD_PAGE_SIZE - 1)
