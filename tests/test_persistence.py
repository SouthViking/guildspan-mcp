from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import select

from guildspan.config import Settings
from guildspan.persistence import (
    Base,
    Database,
    GuildAccessRepository,
    GuildInstallation,
    GuildInstallationRepository,
    User,
    UserGuildAccess,
    UserRepository,
    normalize_database_url,
)


async def create_test_database() -> Database:
    database = Database("sqlite+aiosqlite:///:memory:")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return database


def test_database_url_normalizes_railway_and_standard_postgres_urls() -> None:
    assert (
        normalize_database_url("postgres://user:pass@host/db")
        == "postgresql+psycopg://user:pass@host/db"
    )
    assert (
        normalize_database_url("postgresql://user:pass@host/db")
        == "postgresql+psycopg://user:pass@host/db"
    )
    assert (
        normalize_database_url("postgresql+psycopg://user:pass@host/db")
        == "postgresql+psycopg://user:pass@host/db"
    )


def test_database_builds_from_application_settings() -> None:
    settings = Settings.model_validate(
        {
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "GUILDSPAN_DATABASE_POOL_SIZE": 3,
            "GUILDSPAN_DATABASE_MAX_OVERFLOW": 2,
        }
    )

    database = Database.from_settings(settings)

    assert database.engine.url.drivername == "sqlite+aiosqlite"


@pytest.mark.asyncio
async def test_database_session_commits_and_rolls_back() -> None:
    database = await create_test_database()
    try:
        async with database.session() as session:
            session.add(User(discord_user_id="100", username="committed"))

        with pytest.raises(RuntimeError, match="abort transaction"):
            async with database.session() as session:
                session.add(User(discord_user_id="200", username="rolled-back"))
                raise RuntimeError("abort transaction")

        async with database.session() as session:
            users = list((await session.scalars(select(User))).all())

        assert [user.discord_user_id for user in users] == ["100"]
        await database.ping()
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_repositories_manage_identity_installation_and_access() -> None:
    database = await create_test_database()
    try:
        async with database.session() as session:
            user = await UserRepository(session).upsert(
                discord_user_id="100",
                username="before",
                display_name="Guild Owner",
            )
            installation = await GuildInstallationRepository(session).install(
                discord_guild_id="900",
                name="Test Guild",
                installed_by_user_id=user.id,
                metadata={"source": "oauth"},
            )
            access = await GuildAccessRepository(session).grant(
                user_id=user.id,
                guild_installation_id=installation.id,
            )
            user_id = user.id
            installation_id = installation.id

            assert access.status == "active"

        async with database.session() as session:
            users = UserRepository(session)
            installations = GuildInstallationRepository(session)
            accesses = GuildAccessRepository(session)

            updated_user = await users.upsert(
                discord_user_id="100",
                username="after",
                display_name="Guild Owner",
            )
            stored_installation = await installations.get_by_discord_id("900")

            assert updated_user.id == user_id
            assert updated_user.username == "after"
            assert stored_installation is not None
            assert stored_installation.id == installation_id
            assert stored_installation.installation_metadata == {"source": "oauth"}
            assert await accesses.has_access(
                user_id=user_id,
                discord_guild_id="900",
            )
            assert await accesses.list_active_guild_ids(user_id) == ["900"]
            assert await accesses.revoke(
                user_id=user_id,
                guild_installation_id=installation_id,
            )
            assert not await accesses.revoke(
                user_id=user_id,
                guild_installation_id=installation_id,
            )

        async with database.session() as session:
            accesses = GuildAccessRepository(session)
            installations = GuildInstallationRepository(session)

            assert not await accesses.has_access(
                user_id=user_id,
                discord_guild_id="900",
            )
            await accesses.grant(
                user_id=user_id,
                guild_installation_id=installation_id,
            )
            assert await installations.revoke("900")
            assert not await installations.revoke("900")
            assert not await accesses.has_access(
                user_id=user_id,
                discord_guild_id="900",
            )

        async with database.session() as session:
            assert await session.get(UserGuildAccess, (user_id, installation_id))
            assert await session.get(GuildInstallation, installation_id)
    finally:
        await database.dispose()


def test_initial_alembic_migration_renders_postgres_sql() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["DATABASE_URL"] = "postgresql://user:pass@localhost/guildspan"

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=repository_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "CREATE TABLE users" in result.stdout
    assert "CREATE TABLE guild_installations" in result.stdout
    assert "CREATE TABLE user_guild_access" in result.stdout
