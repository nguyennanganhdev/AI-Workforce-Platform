"""Create append-only WorkOrder assignment history.

Revision ID: 0008_vh_work_order_assignment
Revises: 0007_vh_business_event
Create Date: 2026-09-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_vh_work_order_assignment"
down_revision: Union[str, None] = "0007_vh_business_event"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vh_work_order_assignment",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("work_order_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("work_order_version", sa.BigInteger(), nullable=False),
        sa.Column("executor_type", sa.String(), nullable=False),
        sa.Column("executor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("assigned_by_type", sa.String(), nullable=False),
        sa.Column("assigned_by_id", sa.String(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_vh_work_order_assignment"),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["vh_work_order.id"],
            name="fk_vh_work_order_assignment_work_order_id_vh_work_order",
        ),
        sa.UniqueConstraint(
            "work_order_id",
            "work_order_version",
            name="uq_vh_work_order_assignment_version",
        ),
    )
    op.create_index(
        "ix_vh_work_order_assignment_order_assigned_at",
        "vh_work_order_assignment",
        ["work_order_id", "assigned_at"],
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION vh_reject_work_order_assignment_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'vh_work_order_assignment is append-only'
                    USING ERRCODE = '55000';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_vh_work_order_assignment_append_only
            BEFORE UPDATE OR DELETE ON vh_work_order_assignment
            FOR EACH ROW EXECUTE FUNCTION vh_reject_work_order_assignment_mutation()
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER trg_vh_work_order_assignment_append_only ON vh_work_order_assignment")
        op.execute("DROP FUNCTION vh_reject_work_order_assignment_mutation()")
    op.drop_index(
        "ix_vh_work_order_assignment_order_assigned_at",
        table_name="vh_work_order_assignment",
    )
    op.drop_table("vh_work_order_assignment")
