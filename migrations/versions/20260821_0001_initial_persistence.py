"""Create identity, guild installation, and authorization tables.

Revision ID: 20260821_0001
Revises:
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260821_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create GuildSpan's initial persistence schema."""

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discord_user_id", sa.String(length=20), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=True),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint(
            "discord_user_id",
            name="uq_users_discord_user_id",
        ),
    )
    op.create_table(
        "guild_installations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discord_guild_id", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("icon_url", sa.Text(), nullable=True),
        sa.Column(
            "installed_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "installed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_guild_installations_status",
        ),
        sa.ForeignKeyConstraint(
            ["installed_by_user_id"],
            ["users.id"],
            name="fk_guild_installations_installed_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_guild_installations"),
        sa.UniqueConstraint(
            "discord_guild_id",
            name="uq_guild_installations_discord_guild_id",
        ),
    )
    op.create_table(
        "user_guild_access",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "guild_installation_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_user_guild_access_status",
        ),
        sa.ForeignKeyConstraint(
            ["guild_installation_id"],
            ["guild_installations.id"],
            name=(
                "fk_user_guild_access_guild_installation_id_"
                "guild_installations"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_guild_access_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id",
            "guild_installation_id",
            name="pk_user_guild_access",
        ),
    )
    op.create_index(
        "ix_user_guild_access_guild_installation_id",
        "user_guild_access",
        ["guild_installation_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove GuildSpan's initial persistence schema."""

    op.drop_index(
        "ix_user_guild_access_guild_installation_id",
        table_name="user_guild_access",
    )
    op.drop_table("user_guild_access")
    op.drop_table("guild_installations")
    op.drop_table("users")
