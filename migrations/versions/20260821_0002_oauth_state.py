"""Add durable encrypted OAuth state storage.

Revision ID: 20260821_0002
Revises: 20260821_0001
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260821_0002"
down_revision: str | None = "20260821_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the key-value table used by the OAuth provider."""

    op.create_table(
        "oauth_state",
        sa.Column("collection", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("ttl", sa.Double(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("collection", "key", name="pk_oauth_state"),
    )
    op.create_index(
        "idx_oauth_state_expires_at",
        "oauth_state",
        ["expires_at"],
        unique=False,
        postgresql_where=sa.text("expires_at IS NOT NULL"),
    )


def downgrade() -> None:
    """Remove OAuth state storage."""

    op.drop_index("idx_oauth_state_expires_at", table_name="oauth_state")
    op.drop_table("oauth_state")
