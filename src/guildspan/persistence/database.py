"""Async SQLAlchemy database lifecycle and session management."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from guildspan.config import Settings


def normalize_database_url(database_url: str) -> str:
    """Normalize Railway-style PostgreSQL URLs for SQLAlchemy and psycopg 3."""

    normalized = database_url.strip()
    if normalized.startswith("postgres://"):
        return normalized.replace("postgres://", "postgresql+psycopg://", 1)
    if normalized.startswith("postgresql://"):
        return normalized.replace("postgresql://", "postgresql+psycopg://", 1)
    return normalized


class Database:
    """Own the async engine and transaction-scoped session factory."""

    def __init__(
        self,
        database_url: str,
        *,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
    ) -> None:
        normalized_url = normalize_database_url(database_url)
        engine_options: dict[str, object] = {
            "echo": echo,
            "pool_pre_ping": True,
        }
        if not normalized_url.startswith("sqlite+"):
            engine_options.update(
                pool_size=pool_size,
                max_overflow=max_overflow,
            )

        self.engine: AsyncEngine = create_async_engine(
            normalized_url,
            **engine_options,
        )
        self.sessions = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> Database:
        """Build a database instance from validated application settings."""

        return cls(
            settings.require_database_url(),
            echo=settings.database_echo,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a session and commit or roll back its transaction."""

        async with self.sessions() as session:
            try:
                yield session
                await session.commit()
            except BaseException:
                await session.rollback()
                raise

    async def ping(self) -> None:
        """Verify that the database accepts a simple query."""

        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        """Release all pooled database connections."""

        await self.engine.dispose()
