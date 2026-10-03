"""Add tenant-owned file metadata and append-only WorkOrder evidence refs.

Revision ID: 0010_vh_evidence
Revises: 0009_vh_checklist_execution
Create Date: 2026-09-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_vh_evidence"
down_revision: Union[str, None] = "0009_vh_checklist_execution"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vh_file_object",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("storage_provider", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("size_bytes > 0", name="ck_vh_file_object_size_positive"),
        sa.PrimaryKeyConstraint("id", name="pk_vh_file_object"),
        sa.UniqueConstraint(
            "tenant_id", "storage_provider", "storage_key", name="uq_vh_file_object_tenant_key"
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_vh_file_object_tenant_id"),
    )
    op.create_table(
        "vh_evidence_ref",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("incident_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("work_order_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("file_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column(
            "capture_phase",
            sa.Enum(
                "BEFORE", "AFTER", "QC", "OTHER",
                name="ck_vh_evidence_ref_capture_phase",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("uploaded_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_vh_evidence_ref"),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["vh_incident.id"],
            name="fk_vh_evidence_ref_incident_id_vh_incident",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["vh_task.id"],
            name="fk_vh_evidence_ref_task_id_vh_task",
        ),
        sa.ForeignKeyConstraint(
            ["work_order_id"], ["vh_work_order.id"],
            name="fk_vh_evidence_ref_work_order_id_vh_work_order",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"], ["vh_file_object.id"],
            name="fk_vh_evidence_ref_file_id_vh_file_object",
        ),
    )
    op.create_index(
        "ix_vh_evidence_ref_work_order_phase_created",
        "vh_evidence_ref",
        ["work_order_id", "capture_phase", "created_at"],
    )
    op.create_index(
        "ix_vh_evidence_ref_incident_created",
        "vh_evidence_ref",
        ["incident_id", "created_at"],
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION vh_reject_evidence_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'Field Operations evidence records are immutable'
                    USING ERRCODE = '55000';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_vh_file_object_immutable
            BEFORE UPDATE OR DELETE ON vh_file_object
            FOR EACH ROW EXECUTE FUNCTION vh_reject_evidence_mutation()
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_vh_evidence_ref_append_only
            BEFORE UPDATE OR DELETE ON vh_evidence_ref
            FOR EACH ROW EXECUTE FUNCTION vh_reject_evidence_mutation()
            """
        )
    elif op.get_bind().dialect.name == "sqlite":
        for table_name, mutation_name, action in (
            ("vh_file_object", "immutable", "UPDATE"),
            ("vh_file_object", "immutable_delete", "DELETE"),
            ("vh_evidence_ref", "append_only", "UPDATE"),
            ("vh_evidence_ref", "append_only_delete", "DELETE"),
        ):
            op.execute(
                f"""
                CREATE TRIGGER trg_{table_name}_{mutation_name}
                BEFORE {action} ON {table_name}
                BEGIN
                    SELECT RAISE(ABORT, 'Field Operations evidence records are immutable');
                END
                """
            )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER trg_vh_evidence_ref_append_only ON vh_evidence_ref")
        op.execute("DROP TRIGGER trg_vh_file_object_immutable ON vh_file_object")
        op.execute("DROP FUNCTION vh_reject_evidence_mutation()")
    elif op.get_bind().dialect.name == "sqlite":
        for table_name, mutation_name in (
            ("vh_evidence_ref", "append_only_delete"),
            ("vh_evidence_ref", "append_only"),
            ("vh_file_object", "immutable_delete"),
            ("vh_file_object", "immutable"),
        ):
            op.execute(f"DROP TRIGGER trg_{table_name}_{mutation_name}")
    op.drop_index("ix_vh_evidence_ref_incident_created", table_name="vh_evidence_ref")
    op.drop_index("ix_vh_evidence_ref_work_order_phase_created", table_name="vh_evidence_ref")
    op.drop_table("vh_evidence_ref")
    op.drop_table("vh_file_object")
