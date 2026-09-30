"""Persist deterministic rule decisions for ActionRequests.

Revision ID: 0012_vh_rule_evaluation
Revises: 0011_vh_qc_result
Create Date: 2026-09-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_vh_rule_evaluation"
down_revision: Union[str, None] = "0011_vh_qc_result"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vh_rule_evaluation",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("action_request_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "decision",
            sa.Enum(
                "ALLOW",
                "REQUIRE_APPROVAL",
                "DENY",
                name="ck_vh_rule_evaluation_decision",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("reason_code", sa.String(), nullable=False),
        sa.Column("rule_version", sa.String(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_vh_rule_evaluation"),
        sa.ForeignKeyConstraint(
            ["action_request_id"],
            ["vh_action_request.id"],
            name="fk_vh_rule_evaluation_action_request_id_vh_action_request",
        ),
    )
    op.create_index(
        "ix_vh_rule_evaluation_action_evaluated",
        "vh_rule_evaluation",
        ["action_request_id", "evaluated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_vh_rule_evaluation_action_evaluated",
        table_name="vh_rule_evaluation",
    )
    op.drop_table("vh_rule_evaluation")
