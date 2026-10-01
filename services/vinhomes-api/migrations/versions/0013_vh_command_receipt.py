"""Add durable command receipts for idempotent Field Operations writes.

Revision ID: 0013_vh_command_receipt
Revises: 0012_vh_rule_evaluation
Create Date: 2026-09-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_vh_command_receipt"
down_revision: Union[str, None] = "0012_vh_rule_evaluation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vh_command_receipt",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("command_type", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("payload_hash", sa.String(length=72), nullable=False),
        sa.Column("subject_type", sa.String(length=128), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=True),
        sa.Column(
            "response_json",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "IN_PROGRESS",
                "COMPLETED",
                name="ck_vh_command_receipt_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_vh_command_receipt"),
        sa.UniqueConstraint(
            "tenant_id",
            "actor_type",
            "actor_id",
            "command_type",
            "idempotency_key",
            name="uq_vh_command_receipt_tenant_actor_command_key",
        ),
    )
    op.create_index(
        "ix_vh_command_receipt_tenant_created",
        "vh_command_receipt",
        ["tenant_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_vh_command_receipt_tenant_created", table_name="vh_command_receipt")
    op.drop_table("vh_command_receipt")
