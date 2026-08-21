"""Relational models for GuildSpan identities and guild authorization."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

ACTIVE_STATUS = "active"
REVOKED_STATUS = "revoked"


def utc_now() -> datetime:
    """Return an aware UTC timestamp for ORM-side defaults."""

    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base shared by all GuildSpan tables."""


class TimestampMixin:
    """Standard creation and update timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class User(TimestampMixin, Base):
    """A person authenticated through their Discord identity."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("discord_user_id", name="uq_users_discord_user_id"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    discord_user_id: Mapped[str] = mapped_column(String(20), nullable=False)
    username: Mapped[str | None] = mapped_column(String(80))
    display_name: Mapped[str | None] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    installed_guilds: Mapped[list[GuildInstallation]] = relationship(
        back_populates="installed_by",
        foreign_keys="GuildInstallation.installed_by_user_id",
    )
    guild_accesses: Mapped[list[UserGuildAccess]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserGuildAccess.user_id",
    )


class GuildInstallation(Base):
    """A Discord guild in which the GuildSpan bot has been installed."""

    __tablename__ = "guild_installations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_guild_installations_status",
        ),
        UniqueConstraint(
            "discord_guild_id",
            name="uq_guild_installations_discord_guild_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    discord_guild_id: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    icon_url: Mapped[str | None] = mapped_column(Text)
    installed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default=ACTIVE_STATUS,
        nullable=False,
    )
    installation_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB(), "postgresql"),
        default=dict,
        nullable=False,
    )
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    installed_by: Mapped[User | None] = relationship(
        back_populates="installed_guilds",
        foreign_keys=[installed_by_user_id],
    )
    user_accesses: Mapped[list[UserGuildAccess]] = relationship(
        back_populates="guild_installation",
        cascade="all, delete-orphan",
    )


class UserGuildAccess(Base):
    """An explicit authorization for a user to operate in a guild."""

    __tablename__ = "user_guild_access"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_user_guild_access_status",
        ),
        Index(
            "ix_user_guild_access_guild_installation_id",
            "guild_installation_id",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    guild_installation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("guild_installations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default=ACTIVE_STATUS,
        nullable=False,
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(
        back_populates="guild_accesses",
        foreign_keys=[user_id],
    )
    guild_installation: Mapped[GuildInstallation] = relationship(
        back_populates="user_accesses",
    )
