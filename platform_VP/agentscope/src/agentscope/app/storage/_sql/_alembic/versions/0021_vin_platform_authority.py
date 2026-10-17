"""Vin personal users, entitlements, quotas, domain links and durable jobs."""

from alembic import op

revision = "0021_vin_platform_authority"
down_revision = "0020_unified_operation_owner"
branch_labels = None
depends_on = None

# Frozen list: later authority tables must receive their own migration.
TABLES = (
    "vin_accounts", "vin_memberships", "vin_catalog", "vin_grants", "vin_quota_policies",
    "vin_subject_usage", "vin_usage_buckets", "vin_attempts", "vin_secrets", "vin_domain_providers",
    "vin_link_transactions", "vin_domain_links", "vin_cases", "vin_case_events", "vin_commands",
    "vin_automation", "vin_audit",
)


def upgrade():
    from agentscope.app.vin_platform._tables import metadata
    for name in TABLES:
        metadata.tables[name].create(op.get_bind(), checkfirst=False)


def downgrade():
    raise RuntimeError("Vin authority contains live links/quota/case data; roll back application flags, not data tables")
