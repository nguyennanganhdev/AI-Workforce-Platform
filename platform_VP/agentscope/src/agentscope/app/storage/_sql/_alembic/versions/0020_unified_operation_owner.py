"""Persist the agent responsible for tracking a partner operation."""

import sqlalchemy as sa
from alembic import op

revision = "0020_unified_operation_owner"
down_revision = "0019_model_call_ledger"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "wf_unified_operations",
        sa.Column("owner_agent_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "wf_unified_operations",
        sa.Column("owner_session_id", sa.String(255), nullable=True),
    )


def downgrade():
    op.drop_column("wf_unified_operations", "owner_session_id")
    op.drop_column("wf_unified_operations", "owner_agent_id")
