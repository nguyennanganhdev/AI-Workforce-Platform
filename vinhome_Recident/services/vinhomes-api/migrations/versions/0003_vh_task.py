"""Create the Vinhomes business Task table.

Revision ID: 0003_vh_task
Revises: 0002_vh_incident
Create Date: 2026-09-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_vh_task"
down_revision: Union[str, None] = "0002_vh_incident"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vh_task",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("incident_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column(
            "domain_type",
            sa.Enum(
                "SANITATION",
                "LANDSCAPE",
                name="ck_vh_task_domain_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "domain_data",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("domain_schema_version", sa.Integer(), nullable=False),
        sa.Column("assignee_type", sa.String(), nullable=False),
        sa.Column("assignee_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "ASSIGNED",
                "IN_PROGRESS",
                "BLOCKED",
                "DONE",
                "CANCELLED",
                name="ck_vh_task_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("priority", sa.String(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_vh_task"),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["vh_incident.id"],
            name="fk_vh_task_incident_id_vh_incident",
        ),
    )
    op.create_index(
        "ix_vh_task_incident_status",
        "vh_task",
        ["incident_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_vh_task_incident_status", table_name="vh_task")
    op.drop_table("vh_task")
