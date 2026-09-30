"""Add tenant-owned checklists and pin WorkOrder attempts to a version.

Revision ID: 0009_vh_checklist_execution
Revises: 0008_vh_work_order_assignment
Create Date: 2026-09-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_vh_checklist_execution"
down_revision: Union[str, None] = "0008_vh_work_order_assignment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vh_checklist",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_vh_checklist"),
    )
    op.create_index(
        "ix_vh_checklist_tenant_category",
        "vh_checklist",
        ["tenant_id", "category"],
    )
    op.create_table(
        "vh_checklist_version",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("checklist_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column(
            "criteria_json",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.CheckConstraint("version_no > 0", name="ck_vh_checklist_version_positive"),
        sa.ForeignKeyConstraint(
            ["checklist_id"],
            ["vh_checklist.id"],
            name="fk_vh_checklist_version_checklist_id_vh_checklist",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_vh_checklist_version"),
        sa.UniqueConstraint(
            "checklist_id", "version_no", name="uq_vh_checklist_version_no"
        ),
    )
    op.create_index(
        "ix_vh_checklist_version_checklist_status",
        "vh_checklist_version",
        ["checklist_id", "status"],
    )

    with op.batch_alter_table("vh_work_order") as batch_op:
        batch_op.create_foreign_key(
            "fk_vh_work_order_checklist_version_id_vh_checklist_version",
            "vh_checklist_version",
            ["checklist_version_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("vh_work_order") as batch_op:
        batch_op.drop_constraint(
            "fk_vh_work_order_checklist_version_id_vh_checklist_version",
            type_="foreignkey",
        )
    op.drop_index(
        "ix_vh_checklist_version_checklist_status",
        table_name="vh_checklist_version",
    )
    op.drop_table("vh_checklist_version")
    op.drop_index("ix_vh_checklist_tenant_category", table_name="vh_checklist")
    op.drop_table("vh_checklist")
