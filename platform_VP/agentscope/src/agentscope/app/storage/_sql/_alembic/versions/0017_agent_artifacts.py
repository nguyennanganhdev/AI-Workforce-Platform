"""Eval cases, eval runs and memories that belong to one agent.

Revision ID: 0017_agent_artifacts
Revises: 0016_default_workspace
Create Date: 2026-10-22 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_agent_artifacts"
down_revision: str | None = "0016_default_workspace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create ``agent_artifacts``."""
    op.create_table(
        "agent_artifacts",
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("agent_id", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("agent_artifacts", schema=None) as batch_op:
        for column in ("created_at", "updated_at", "user_id", "agent_id", "kind"):
            batch_op.create_index(
                batch_op.f(f"ix_agent_artifacts_{column}"),
                [column],
                unique=False,
            )


def downgrade() -> None:
    """Drop ``agent_artifacts``."""
    op.drop_table("agent_artifacts")
