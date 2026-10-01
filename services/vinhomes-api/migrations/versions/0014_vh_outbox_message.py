"""Create transactional outbox for committed business events.

Revision ID: 0014_vh_outbox_message
Revises: 0013_vh_command_receipt
Create Date: 2026-09-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_vh_outbox_message"
down_revision: Union[str, None] = "0013_vh_command_receipt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vh_outbox_message",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("business_event_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "PUBLISHED",
                "DEAD_LETTER",
                name="ck_vh_outbox_message_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("attempt_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_vh_outbox_message"),
        sa.ForeignKeyConstraint(
            ["business_event_id"],
            ["vh_business_event.id"],
            name="fk_vh_outbox_business_event_id_vh_business_event",
        ),
        sa.UniqueConstraint("business_event_id", name="uq_vh_outbox_business_event"),
    )
    op.create_index(
        "ix_vh_outbox_status_created",
        "vh_outbox_message",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_vh_outbox_status_created", table_name="vh_outbox_message")
    op.drop_table("vh_outbox_message")
