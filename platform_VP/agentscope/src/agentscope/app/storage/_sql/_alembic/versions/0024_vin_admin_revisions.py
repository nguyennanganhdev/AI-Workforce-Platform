"""Backfill revisions for administrative grant and membership edits."""

from alembic import op
import sqlalchemy as sa

revision = "0024_vin_admin_revisions"
down_revision = "0023_personal_job_constraint"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("vin_grants", "vin_memberships"):
        op.add_column(name, sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("vin_quota_policies", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade():
    raise RuntimeError("Keep administrative revisions; disable Vin instead of discarding audit concurrency")
