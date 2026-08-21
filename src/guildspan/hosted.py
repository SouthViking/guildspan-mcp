"""Authenticated resources for GuildSpan's hosted MCP runtime."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.server.auth import AuthProvider
from fastmcp.server.auth.providers.discord import DiscordProvider
from key_value.aio.protocols import AsyncKeyValue
from key_value.aio.stores.postgresql import PostgreSQLStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper

from guildspan.authorization import (
    GuildAuthorizationService,
    create_authorization_service,
    create_oauth_http_client,
)
from guildspan.config import Settings
from guildspan.persistence import Database

OAUTH_STATE_TABLE = "oauth_state"
OAUTH_STORAGE_SALT = "guildspan-mcp-oauth-state-v1"


class HostedRuntime:
    """Own OAuth, database, and Discord identity resources for HTTP serving."""

    def __init__(
        self,
        *,
        auth: AuthProvider,
        database: Database,
        authorization_service: GuildAuthorizationService,
        http_client: httpx.AsyncClient,
        managed_oauth_store: PostgreSQLStore | None,
    ) -> None:
        self.auth = auth
        self._database = database
        self._authorization_service = authorization_service
        self._http_client = http_client
        self._managed_oauth_store = managed_oauth_store

    @asynccontextmanager
    async def lifespan(
        self,
        _server: FastMCP[Any],
    ) -> AsyncIterator[dict[str, object]]:
        """Start persistent resources and expose authorization to MCP tools."""

        try:
            if self._managed_oauth_store is not None:
                async with self._managed_oauth_store:
                    yield {
                        "database": self._database,
                        "guild_authorization": self._authorization_service,
                    }
            else:
                yield {
                    "database": self._database,
                    "guild_authorization": self._authorization_service,
                }
        finally:
            await self._http_client.aclose()
            await self._database.dispose()


def create_hosted_runtime(
    settings: Settings,
    *,
    client_storage: AsyncKeyValue | None = None,
    database: Database | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> HostedRuntime:
    """Build the generic MCP OAuth runtime backed by Discord and PostgreSQL."""

    auth_settings = settings.require_hosted_auth_settings()
    resolved_database = database or Database.from_settings(settings)
    resolved_http_client = http_client or create_oauth_http_client()

    managed_oauth_store: PostgreSQLStore | None = None
    resolved_client_storage = client_storage
    if resolved_client_storage is None:
        managed_oauth_store = PostgreSQLStore(
            url=normalize_asyncpg_url(settings.require_database_url()),
            table_name=OAUTH_STATE_TABLE,
            auto_create=False,
        )
        resolved_client_storage = managed_oauth_store

    encrypted_storage = FernetEncryptionWrapper(
        resolved_client_storage,
        source_material=auth_settings.auth_secret,
        salt=OAUTH_STORAGE_SALT,
    )
    auth = DiscordProvider(
        client_id=auth_settings.discord_client_id,
        client_secret=auth_settings.discord_client_secret,
        base_url=auth_settings.public_base_url,
        required_scopes=["identify", "guilds"],
        client_storage=encrypted_storage,
        jwt_signing_key=auth_settings.auth_secret,
        require_authorization_consent=True,
        http_client=resolved_http_client,
        enable_cimd=True,
    )
    authorization_service = create_authorization_service(
        settings=settings,
        database=resolved_database,
        http_client=resolved_http_client,
    )
    return HostedRuntime(
        auth=auth,
        database=resolved_database,
        authorization_service=authorization_service,
        http_client=resolved_http_client,
        managed_oauth_store=managed_oauth_store,
    )


def normalize_asyncpg_url(database_url: str) -> str:
    """Normalize Railway and SQLAlchemy PostgreSQL URLs for asyncpg."""

    normalized = database_url.strip()
    if normalized.startswith("postgres://"):
        return normalized.replace("postgres://", "postgresql://", 1)
    if normalized.startswith("postgresql+") and "://" in normalized:
        _, separator, connection = normalized.partition("://")
        return f"postgresql{separator}{connection}"
    return normalized
