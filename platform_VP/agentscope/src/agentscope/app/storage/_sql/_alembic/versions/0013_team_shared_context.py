"""Durable shared context for team/ticket conversations.

Revision ID: 0013_team_shared_context
Revises: 0012_workforce_assets
Create Date: 2026-10-12 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_team_shared_context"
down_revision: str | None = "0012_workforce_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "team_shared_contexts",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("team_id", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("team_id", name="uq_team_shared_context_team"),
    )
    op.create_index(
        "ix_team_shared_contexts_user_id",
        "team_shared_contexts",
        ["user_id"],
    )
    op.create_index(
        "ix_team_shared_contexts_team_id",
        "team_shared_contexts",
        ["team_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_team_shared_contexts_team_id",
        table_name="team_shared_contexts",
    )
    op.drop_index(
        "ix_team_shared_contexts_user_id",
        table_name="team_shared_contexts",
    )
    op.drop_table("team_shared_contexts")
