"""Durable unified reconciliation and replayable provider receipts.

Revision ID: 0018_unified_recovery
Revises: 0017_unified_partner_case
"""

import sqlalchemy as sa
from alembic import op

revision = "0018_unified_recovery"
down_revision = "0017_unified_partner_case"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("wf_unified_operations", sa.Column("provider_version", sa.Integer(), nullable=True))
    op.add_column("wf_unified_operations", sa.Column("call_result", sa.JSON(), nullable=True))
    op.add_column("wf_unified_receipts", sa.Column("envelope", sa.JSON(), nullable=True))
    op.add_column("wf_unified_receipts", sa.Column("schema_entry", sa.JSON(), nullable=True))
    op.add_column("wf_unified_receipts", sa.Column("projection_text", sa.Text(), nullable=True))
    op.add_column("wf_unified_receipts", sa.Column("projected_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for name in ("projected_at", "projection_text", "schema_entry", "envelope"):
        op.drop_column("wf_unified_receipts", name)
    op.drop_column("wf_unified_operations", "call_result")
    op.drop_column("wf_unified_operations", "provider_version")
