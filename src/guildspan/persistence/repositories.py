"""Transaction-bound repositories for GuildSpan persistence."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from guildspan.persistence.models import (
    ACTIVE_STATUS,
    REVOKED_STATUS,
    GuildInstallation,
    User,
    UserGuildAccess,
)


class UserRepository:
    """Persist and resolve Discord-backed GuildSpan users."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_discord_id(self, discord_user_id: str) -> User | None:
        """Return a user by their immutable Discord snowflake."""

        result = await self.session.execute(
            select(User).where(User.discord_user_id == discord_user_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        discord_user_id: str,
        username: str | None = None,
        display_name: str | None = None,
        avatar_url: str | None = None,
    ) -> User:
        """Create or refresh a Discord user profile in the current transaction."""

        user = await self.get_by_discord_id(discord_user_id)
        if user is None:
            user = User(
                discord_user_id=discord_user_id,
                username=username,
                display_name=display_name,
                avatar_url=avatar_url,
            )
            self.session.add(user)
        else:
            user.username = username
            user.display_name = display_name
            user.avatar_url = avatar_url
            user.is_active = True

        await self.session.flush()
        return user


class GuildInstallationRepository:
    """Persist Discord guild installations owned by the GuildSpan bot."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_discord_id(
        self,
        discord_guild_id: str,
    ) -> GuildInstallation | None:
        """Return a guild installation by its Discord snowflake."""

        result = await self.session.execute(
            select(GuildInstallation).where(
                GuildInstallation.discord_guild_id == discord_guild_id
            )
        )
        return result.scalar_one_or_none()

    async def install(
        self,
        *,
        discord_guild_id: str,
        name: str,
        installed_by_user_id: UUID | None,
        icon_url: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> GuildInstallation:
        """Create or reactivate a bot installation for a Discord guild."""

        installation = await self.get_by_discord_id(discord_guild_id)
        if installation is None:
            installation = GuildInstallation(
                discord_guild_id=discord_guild_id,
                name=name,
                icon_url=icon_url,
                installed_by_user_id=installed_by_user_id,
                installation_metadata=dict(metadata or {}),
            )
            self.session.add(installation)
        else:
            installation.name = name
            installation.icon_url = icon_url
            installation.installed_by_user_id = installed_by_user_id
            installation.installation_metadata = dict(metadata or {})
            installation.status = ACTIVE_STATUS
            installation.revoked_at = None

        await self.session.flush()
        return installation

    async def revoke(self, discord_guild_id: str) -> bool:
        """Mark a guild installation as revoked without deleting history."""

        installation = await self.get_by_discord_id(discord_guild_id)
        if installation is None or installation.status == REVOKED_STATUS:
            return False
        installation.status = REVOKED_STATUS
        installation.revoked_at = datetime.now(UTC)
        await self.session.flush()
        return True


class GuildAccessRepository:
    """Manage per-user authorization for installed Discord guilds."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def grant(
        self,
        *,
        user_id: UUID,
        guild_installation_id: UUID,
    ) -> UserGuildAccess:
        """Create or reactivate a user's access to an installed guild."""

        access = await self.session.get(
            UserGuildAccess,
            (user_id, guild_installation_id),
        )
        if access is None:
            access = UserGuildAccess(
                user_id=user_id,
                guild_installation_id=guild_installation_id,
            )
            self.session.add(access)
        else:
            access.status = ACTIVE_STATUS
            access.revoked_at = None

        await self.session.flush()
        return access

    async def revoke(
        self,
        *,
        user_id: UUID,
        guild_installation_id: UUID,
    ) -> bool:
        """Revoke a user's guild access without removing the record."""

        access = await self.session.get(
            UserGuildAccess,
            (user_id, guild_installation_id),
        )
        if access is None or access.status == REVOKED_STATUS:
            return False
        access.status = REVOKED_STATUS
        access.revoked_at = datetime.now(UTC)
        await self.session.flush()
        return True

    async def has_access(
        self,
        *,
        user_id: UUID,
        discord_guild_id: str,
    ) -> bool:
        """Return whether a user and installation are both currently active."""

        statement = (
            select(UserGuildAccess.user_id)
            .join(UserGuildAccess.guild_installation)
            .where(
                UserGuildAccess.user_id == user_id,
                UserGuildAccess.status == ACTIVE_STATUS,
                GuildInstallation.discord_guild_id == discord_guild_id,
                GuildInstallation.status == ACTIVE_STATUS,
            )
        )
        return (await self.session.scalar(statement)) is not None

    async def list_active_guild_ids(self, user_id: UUID) -> list[str]:
        """List the Discord guild IDs currently authorized for a user."""

        statement = (
            select(GuildInstallation.discord_guild_id)
            .join(UserGuildAccess)
            .where(
                UserGuildAccess.user_id == user_id,
                UserGuildAccess.status == ACTIVE_STATUS,
                GuildInstallation.status == ACTIVE_STATUS,
            )
            .order_by(GuildInstallation.discord_guild_id)
        )
        return list((await self.session.scalars(statement)).all())
