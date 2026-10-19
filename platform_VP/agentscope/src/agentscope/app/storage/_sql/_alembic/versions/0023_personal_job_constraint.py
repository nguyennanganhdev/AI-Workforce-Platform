"""Expand the original queue owner CHECK for personal jobs without data loss."""

from alembic import op

revision = "0023_personal_job_constraint"
down_revision = "0022_personal_job_owner"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("wf_durable_jobs") as batch:
        batch.drop_constraint("ck_wf_job_owner_shape", type_="check")
        batch.create_check_constraint("ck_wf_job_owner_shape",
            "(owner_kind = 'scope' AND domain_id IS NOT NULL AND area_id IS NOT NULL "
            "AND manager_account_id IS NOT NULL AND provider_integration_id IS NULL AND personal_user_id IS NULL) OR "
            "(owner_kind = 'provider' AND domain_id IS NULL AND area_id IS NULL AND manager_account_id IS NULL "
            "AND provider_integration_id IS NOT NULL AND personal_user_id IS NULL) OR "
            "(owner_kind = 'personal' AND domain_id IS NULL AND area_id IS NULL AND manager_account_id IS NULL "
            "AND provider_integration_id IS NULL AND personal_user_id IS NOT NULL)")


def downgrade():
    raise RuntimeError("Retain personal job evidence; disable Vin features instead of removing its owner constraint")
