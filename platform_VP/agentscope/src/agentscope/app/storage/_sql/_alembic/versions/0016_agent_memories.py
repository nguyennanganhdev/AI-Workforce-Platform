"""Long-term memory of business agents.

Revision ID: 0016_agent_memories
Revises: 0015_shared_context_backfill
Create Date: 2026-10-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_agent_memories"
down_revision: str | None = "0015_shared_context_backfill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_memories",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("agent_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
    )
    for column in ("created_at", "updated_at", "user_id", "agent_id", "status"):
        op.create_index(
            f"ix_agent_memories_{column}",
            "agent_memories",
            [column],
        )


def downgrade() -> None:
    for column in ("status", "agent_id", "user_id", "updated_at", "created_at"):
        op.drop_index(f"ix_agent_memories_{column}", table_name="agent_memories")
    op.drop_table("agent_memories")
