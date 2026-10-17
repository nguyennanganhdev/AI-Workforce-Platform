"""Durable team turns and recipient handoff delivery.

Revision ID: 0014_durable_team_handoffs
Revises: 0013_team_shared_context
Create Date: 2026-10-13 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_durable_team_handoffs"
down_revision: str | None = "0013_team_shared_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "team_shared_contexts",
        sa.Column("state_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_team_shared_contexts_state_revision",
        "team_shared_contexts",
        ["state_revision"],
    )
    for column in (
        "tenant_id",
        "domain_id",
        "area_id",
        "manager_account_id",
        "workflow_id",
    ):
        op.add_column(
            "team_shared_contexts",
            sa.Column(column, sa.String(length=255), nullable=True),
        )
        op.create_index(
            f"ix_team_shared_contexts_{column}",
            "team_shared_contexts",
            [column],
        )
    op.create_table(
        "team_shared_context_snapshots",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("team_id", sa.String(length=255), nullable=False),
        sa.Column("state_revision", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "team_id",
            "state_revision",
            name="uq_team_shared_context_snapshot_revision",
        ),
    )
    for column in ("user_id", "team_id", "state_revision"):
        op.create_index(
            f"ix_team_shared_context_snapshots_{column}",
            "team_shared_context_snapshots",
            [column],
        )
    op.create_table(
        "team_turns",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("team_id", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("team_id", name="uq_team_turn_team"),
    )
    op.create_index("ix_team_turns_user_id", "team_turns", ["user_id"])
    op.create_index("ix_team_turns_team_id", "team_turns", ["team_id"])

    op.create_table(
        "team_handoffs",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("team_id", sa.String(length=255), nullable=False),
        sa.Column("handoff_id", sa.String(length=255), nullable=False),
        sa.Column("recipient_session_id", sa.String(length=255), nullable=False),
        sa.Column("delivery_status", sa.String(length=32), nullable=False),
        sa.UniqueConstraint(
            "handoff_id",
            "recipient_session_id",
            name="uq_team_handoff_recipient",
        ),
    )
    for column in (
        "user_id",
        "team_id",
        "handoff_id",
        "recipient_session_id",
        "delivery_status",
    ):
        op.create_index(
            f"ix_team_handoffs_{column}",
            "team_handoffs",
            [column],
        )


def downgrade() -> None:
    for column in reversed(
        (
            "user_id",
            "team_id",
            "handoff_id",
            "recipient_session_id",
            "delivery_status",
        ),
    ):
        op.drop_index(f"ix_team_handoffs_{column}", table_name="team_handoffs")
    op.drop_table("team_handoffs")
    op.drop_index("ix_team_turns_team_id", table_name="team_turns")
    op.drop_index("ix_team_turns_user_id", table_name="team_turns")
    op.drop_table("team_turns")
    for column in reversed(("user_id", "team_id", "state_revision")):
        op.drop_index(
            f"ix_team_shared_context_snapshots_{column}",
            table_name="team_shared_context_snapshots",
        )
    op.drop_table("team_shared_context_snapshots")
    op.drop_index(
        "ix_team_shared_contexts_state_revision",
        table_name="team_shared_contexts",
    )
    op.drop_column("team_shared_contexts", "state_revision")
    for column in reversed(
        (
            "tenant_id",
            "domain_id",
            "area_id",
            "manager_account_id",
            "workflow_id",
        ),
    ):
        op.drop_index(
            f"ix_team_shared_contexts_{column}",
            table_name="team_shared_contexts",
        )
        op.drop_column("team_shared_contexts", column)
