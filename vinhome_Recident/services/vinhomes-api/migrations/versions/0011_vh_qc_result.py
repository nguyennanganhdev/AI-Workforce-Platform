"""Add immutable QC decisions and QC evidence links.

Revision ID: 0011_vh_qc_result
Revises: 0010_vh_evidence
Create Date: 2026-09-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_vh_qc_result"
down_revision: Union[str, None] = "0010_vh_evidence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vh_qc_result",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("work_order_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "outcome",
            sa.Enum(
                "PASS",
                "FAIL",
                "INCONCLUSIVE",
                name="ck_vh_qc_result_outcome",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "criteria",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "failed_criteria",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("redo_required", sa.Boolean(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("checked_by", sa.String(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_vh_qc_result"),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["vh_work_order.id"],
            name="fk_vh_qc_result_work_order_id_vh_work_order",
        ),
    )
    op.create_index(
        "ix_vh_qc_result_work_order_checked_at",
        "vh_qc_result",
        ["work_order_id", "checked_at"],
    )
    op.create_table(
        "vh_qc_result_evidence",
        sa.Column("qc_result_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("evidence_ref_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "qc_result_id", "evidence_ref_id", name="pk_vh_qc_result_evidence"
        ),
        sa.ForeignKeyConstraint(
            ["qc_result_id"],
            ["vh_qc_result.id"],
            name="fk_vh_qc_result_evidence_qc_result_id_vh_qc_result",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_ref_id"],
            ["vh_evidence_ref.id"],
            name="fk_vh_qc_result_evidence_evidence_ref_id_vh_evidence_ref",
        ),
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION vh_reject_qc_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'QC results and evidence links are immutable'
                    USING ERRCODE = '55000';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        for table_name, trigger_name in (
            ("vh_qc_result", "trg_vh_qc_result_immutable"),
            ("vh_qc_result_evidence", "trg_vh_qc_result_evidence_append_only"),
        ):
            op.execute(
                f"CREATE TRIGGER {trigger_name} BEFORE UPDATE OR DELETE ON {table_name} "
                "FOR EACH ROW EXECUTE FUNCTION vh_reject_qc_mutation()"
            )
    elif op.get_bind().dialect.name == "sqlite":
        for table_name, trigger_name in (
            ("vh_qc_result", "trg_vh_qc_result_immutable"),
            ("vh_qc_result_evidence", "trg_vh_qc_result_evidence_append_only"),
        ):
            for action in ("UPDATE", "DELETE"):
                op.execute(
                    f"""
                    CREATE TRIGGER {trigger_name}_{action.lower()}
                    BEFORE {action} ON {table_name}
                    BEGIN
                        SELECT RAISE(ABORT, 'QC results and evidence links are immutable');
                    END
                    """
                )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER trg_vh_qc_result_evidence_append_only ON vh_qc_result_evidence")
        op.execute("DROP TRIGGER trg_vh_qc_result_immutable ON vh_qc_result")
        op.execute("DROP FUNCTION vh_reject_qc_mutation()")
    elif op.get_bind().dialect.name == "sqlite":
        for trigger_name in (
            "trg_vh_qc_result_evidence_append_only_delete",
            "trg_vh_qc_result_evidence_append_only_update",
            "trg_vh_qc_result_immutable_delete",
            "trg_vh_qc_result_immutable_update",
        ):
            op.execute(f"DROP TRIGGER {trigger_name}")
    op.drop_table("vh_qc_result_evidence")
    op.drop_index("ix_vh_qc_result_work_order_checked_at", table_name="vh_qc_result")
    op.drop_table("vh_qc_result")
