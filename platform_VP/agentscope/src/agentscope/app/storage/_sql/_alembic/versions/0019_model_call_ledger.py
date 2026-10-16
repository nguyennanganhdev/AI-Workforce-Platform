"""Owner-scoped provider-call evidence for SQL primary storage."""
from alembic import op
import sqlalchemy as sa

revision = "0019_model_call_ledger"
down_revision = "0018_unified_recovery"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("model_call_ledger",
        sa.Column("user_id", sa.String(255), primary_key=True),
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("started_at", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False))
    op.create_index("ix_model_call_owner_started", "model_call_ledger", ["user_id", "started_at"])


def downgrade():
    op.drop_table("model_call_ledger")
