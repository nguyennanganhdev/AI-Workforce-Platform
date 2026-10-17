"""Frozen Vin authority schema; feature flags provide non-destructive rollback."""

import sqlalchemy as sa
from alembic import op

revision = "0021_vin_platform_authority"
down_revision = "0020_unified_operation_owner"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('vin_accounts',
        sa.Column('user_id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('tenant_id', sa.String(length=255), nullable=False),
        sa.Column('eligible', sa.Boolean(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
    )
    op.create_table('vin_attempts',
        sa.Column('id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('tenant_id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('state', sa.String(length=255), nullable=False),
        sa.Column('purpose', sa.String(length=255), nullable=False),
        sa.Column('budget', sa.BigInteger(), nullable=False),
        sa.Column('actual', sa.BigInteger(), nullable=True),
        sa.Column('scopes', sa.JSON(), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_vin_attempts_owner', 'vin_attempts', ['tenant_id', 'user_id', 'state'], unique=False)
    op.create_table('vin_audit',
        sa.Column('id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('tenant_id', sa.String(length=255), nullable=False),
        sa.Column('actor_id', sa.String(length=255), nullable=False),
        sa.Column('action', sa.String(length=255), nullable=False),
        sa.Column('resource_id', sa.String(length=255), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table('vin_automation',
        sa.Column('id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('tenant_id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('kind', sa.String(length=255), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('claim_token', sa.String(length=255), nullable=True),
        sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_vin_automation_owner', 'vin_automation', ['tenant_id', 'user_id', 'kind'], unique=False)
    op.create_table('vin_case_events',
        sa.Column('tenant_id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('case_id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('sequence', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('event_id', sa.String(length=255), nullable=False),
        sa.Column('audience', sa.String(length=255), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'event_id', name='uq_vin_case_event'),
    )
    op.create_table('vin_cases',
        sa.Column('id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('tenant_id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('link_id', sa.String(length=255), nullable=False),
        sa.Column('idempotency_key', sa.String(length=128), nullable=False),
        sa.Column('payload_hash', sa.String(length=64), nullable=False),
        sa.Column('state', sa.String(length=255), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'user_id', 'idempotency_key', name='uq_vin_case_idempotency'),
    )
    op.create_index('ix_vin_cases_owner', 'vin_cases', ['tenant_id', 'user_id'], unique=False)
    op.create_table('vin_catalog',
        sa.Column('id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('tenant_id', sa.String(length=255), nullable=False),
        sa.Column('kind', sa.String(length=255), nullable=False),
        sa.Column('resource_id', sa.String(length=255), nullable=False),
        sa.Column('owner_id', sa.String(length=255), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'kind', 'resource_id', name='uq_vin_catalog_resource'),
    )
    op.create_index('ix_vin_catalog_tenant', 'vin_catalog', ['tenant_id', 'kind'], unique=False)
    op.create_table('vin_commands',
        sa.Column('id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('tenant_id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('case_id', sa.String(length=255), nullable=False),
        sa.Column('idempotency_key', sa.String(length=128), nullable=False),
        sa.Column('payload_hash', sa.String(length=64), nullable=False),
        sa.Column('state', sa.String(length=255), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'user_id', 'case_id', 'idempotency_key', name='uq_vin_command_key'),
    )
    op.create_table('vin_domain_links',
        sa.Column('id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('tenant_id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('provider_id', sa.String(length=255), nullable=False),
        sa.Column('issuer', sa.String(length=255), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=255), nullable=False),
        sa.Column('secret_ref', sa.String(length=255), nullable=False),
        sa.Column('scopes', sa.JSON(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'provider_id', 'issuer', 'subject', name='uq_vin_link_subject'),
    )
    op.create_table('vin_domain_providers',
        sa.Column('tenant_id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('data', sa.JSON(), nullable=False),
    )
    op.create_table('vin_grants',
        sa.Column('id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('tenant_id', sa.String(length=255), nullable=False),
        sa.Column('catalog_id', sa.String(length=255), nullable=False),
        sa.Column('subject_kind', sa.String(length=255), nullable=False),
        sa.Column('subject_id', sa.String(length=255), nullable=False),
        sa.Column('permissions', sa.JSON(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_vin_grants_subject', 'vin_grants', ['tenant_id', 'subject_kind', 'subject_id'], unique=False)
    op.create_table('vin_link_transactions',
        sa.Column('id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('tenant_id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('provider_id', sa.String(length=255), nullable=False),
        sa.Column('state_hash', sa.String(length=64), nullable=False),
        sa.Column('verifier', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table('vin_memberships',
        sa.Column('id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('tenant_id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('group_id', sa.String(length=255), nullable=False),
        sa.Column('domain_id', sa.String(length=255), nullable=True),
        sa.Column('area_id', sa.String(length=255), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_vin_memberships_user', 'vin_memberships', ['tenant_id', 'user_id'], unique=False)
    op.create_table('vin_quota_policies',
        sa.Column('tenant_id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('subject', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
    )
    op.create_table('vin_secrets',
        sa.Column('id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('tenant_id', sa.String(length=255), nullable=False),
        sa.Column('purpose', sa.String(length=255), nullable=False),
        sa.Column('ciphertext', sa.Text(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
    )
    op.create_table('vin_subject_usage',
        sa.Column('tenant_id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('subject', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('active_calls', sa.Integer(), nullable=False),
        sa.Column('stored_bytes', sa.BigInteger(), nullable=False),
        sa.Column('reserved_bytes', sa.BigInteger(), nullable=False),
    )
    op.create_table('vin_usage_buckets',
        sa.Column('tenant_id', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('subject', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('window', sa.String(length=255), nullable=False, primary_key=True),
        sa.Column('used', sa.BigInteger(), nullable=False),
        sa.Column('reserved', sa.BigInteger(), nullable=False),
    )


def downgrade():
    raise RuntimeError("Keep Vin authority data; disable feature flags when rolling back")
