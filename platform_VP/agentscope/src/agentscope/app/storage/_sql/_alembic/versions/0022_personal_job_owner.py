"""Add personal owners to the existing fenced durable-job queue."""

import sqlalchemy as sa
from alembic import op

revision = "0022_personal_job_owner"
down_revision = "0021_vin_platform_authority"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("wf_durable_jobs", sa.Column("personal_user_id", sa.String(255), nullable=True))
    op.create_index("ix_wf_job_personal", "wf_durable_jobs", ["tenant_id", "personal_user_id", "status"])


def downgrade():
    raise RuntimeError("Keep personal job evidence; disable feature flags when rolling back")
