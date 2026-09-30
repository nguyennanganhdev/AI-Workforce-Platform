"""Create the canonical Vinhomes Incident table.

Revision ID: 0002_vh_incident
Revises: 0001_vinhomes_schema_baseline
Create Date: 2026-09-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_vh_incident"
down_revision: Union[str, None] = "0001_vinhomes_schema_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vh_incident",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("tower_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column(
            "location_json",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "NEW",
                "OPEN",
                "RESOLVED",
                "CLOSED",
                name="ck_vh_incident_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "stage",
            sa.Enum(
                "INTAKE",
                "TRIAGE",
                "PLANNING",
                "EXECUTION",
                "QC",
                "RESIDENT_CONFIRMATION",
                name="ck_vh_incident_stage",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("owner_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_vh_incident"),
    )
    op.create_index(
        "ix_vh_incident_tenant_project_status_severity",
        "vh_incident",
        ["tenant_id", "project_id", "status", "severity"],
        unique=False,
    )
    op.create_index(
        "ix_vh_incident_tower_status",
        "vh_incident",
        ["tower_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_vh_incident_tower_status", table_name="vh_incident")
    op.drop_index(
        "ix_vh_incident_tenant_project_status_severity", table_name="vh_incident"
    )
    op.drop_table("vh_incident")
