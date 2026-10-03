"""Create the Vinhomes WorkOrder table.

Revision ID: 0006_vh_work_order
Revises: 0005_vh_action_approval
Create Date: 2026-09-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_vh_work_order"
down_revision: Union[str, None] = "0005_vh_action_approval"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vh_work_order",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("incident_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("action_request_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("executor_type", sa.String(), nullable=False),
        sa.Column("executor_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "ASSIGNED",
                "IN_PROGRESS",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                name="ck_vh_work_order_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("redo_of_work_order_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("checklist_version_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("execution_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "result",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("version", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_vh_work_order"),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["vh_incident.id"],
            name="fk_vh_work_order_incident_id_vh_incident",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["vh_task.id"],
            name="fk_vh_work_order_task_id_vh_task",
        ),
        sa.ForeignKeyConstraint(
            ["action_request_id"],
            ["vh_action_request.id"],
            name="fk_vh_work_order_action_request_id_vh_action_request",
        ),
        sa.ForeignKeyConstraint(
            ["redo_of_work_order_id"],
            ["vh_work_order.id"],
            name="fk_vh_work_order_redo_of_work_order_id_vh_work_order",
        ),
        sa.UniqueConstraint(
            "task_id",
            "attempt_no",
            name="uq_vh_work_order_task_attempt_no",
        ),
    )


def downgrade() -> None:
    op.drop_table("vh_work_order")
