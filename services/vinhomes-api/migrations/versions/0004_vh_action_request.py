"""Create the Vinhomes ActionRequest table.

Revision ID: 0004_vh_action_request
Revises: 0003_vh_task
Create Date: 2026-09-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_vh_action_request"
down_revision: Union[str, None] = "0003_vh_task"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vh_action_request",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("incident_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "requested_by_type",
            sa.Enum(
                "HUMAN",
                "SYSTEM",
                "AUTOMATION",
                "AGENT",
                "EXTERNAL_SERVICE",
                name="ck_vh_action_request_requested_by_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("requested_by_id", sa.String(), nullable=False),
        sa.Column("requested_by_version", sa.BigInteger(), nullable=True),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("payload_hash", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("version", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("correlation_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_vh_action_request"),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["vh_incident.id"],
            name="fk_vh_action_request_incident_id_vh_incident",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["vh_task.id"],
            name="fk_vh_action_request_task_id_vh_task",
        ),
    )
    op.create_index(
        "ix_vh_action_request_incident_status",
        "vh_action_request",
        ["incident_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_vh_action_request_incident_status", table_name="vh_action_request"
    )
    op.drop_table("vh_action_request")
