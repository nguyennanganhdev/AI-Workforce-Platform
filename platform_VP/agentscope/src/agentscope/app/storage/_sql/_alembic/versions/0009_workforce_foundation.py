# -*- coding: utf-8 -*-
"""Workforce Phase-C foundation persistence.

Revision ID: 0009_workforce_foundation
Revises: 0008_area_platform
Create Date: 2026-10-11 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0009_workforce_foundation"
down_revision: Union[str, None] = "0008_area_platform"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the secure identity, route, provider and job baseline."""
    op.create_table(
        "wf_manager_memberships",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("domain_id", sa.String(length=64), nullable=False),
        sa.Column("area_id", sa.String(length=64), nullable=False),
        sa.Column("manager_account_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("verified_by", sa.String(length=255), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending_verification', 'verified', 'revoked')",
            name="ck_wf_manager_membership_status",
        ),
        sa.ForeignKeyConstraint(
            ["manager_account_id"],
            ["auth_users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["domain_id"], ["business_domains.id"]),
        sa.ForeignKeyConstraint(["area_id"], ["areas.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "manager_account_id",
            name="uq_wf_manager_membership_account",
        ),
    )
    op.create_index(
        "ix_wf_manager_membership_scope_status",
        "wf_manager_memberships",
        ["tenant_id", "domain_id", "area_id", "status"],
    )

    # Existing accounts need an explicit verification decision. They are not
    # silently activated merely because legacy rows contain domain/area.
    op.execute(
        """
        INSERT INTO wf_manager_memberships (
            id, tenant_id, domain_id, area_id, manager_account_id,
            status, revision, verified_by, verified_at,
            created_at, updated_at
        )
        SELECT
            'legacy-' || id, tenant_id, domain_id, area_id, id,
            'pending_verification', 1, NULL, NULL,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM auth_users
        WHERE role = 'AREA_MANAGER'
          AND domain_id IS NOT NULL
          AND area_id IS NOT NULL
        """,
    )

    op.create_table(
        "wf_partner_manager_routes",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("domain_id", sa.String(length=64), nullable=False),
        sa.Column("area_id", sa.String(length=64), nullable=False),
        sa.Column("manager_account_id", sa.String(length=255), nullable=False),
        sa.Column("partner_client_id", sa.String(length=255), nullable=False),
        sa.Column(
            "external_management_ref",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("membership_revision", sa.Integer(), nullable=False),
        sa.Column("allowed_operations", sa.JSON(), nullable=False),
        sa.Column("granted_by", sa.String(length=255), nullable=False),
        sa.Column("confirmed_by_client_id", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["manager_account_id"],
            ["auth_users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["partner_client_id"],
            ["partner_api_clients.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "partner_client_id",
            "external_management_ref",
            name="uq_wf_route_client_management_ref",
        ),
    )
    op.create_index(
        "ix_wf_route_owner_status",
        "wf_partner_manager_routes",
        [
            "tenant_id",
            "domain_id",
            "area_id",
            "manager_account_id",
            "status",
        ],
    )

    op.create_table(
        "wf_provider_integrations",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("partner_client_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["partner_client_id"],
            ["partner_api_clients.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "partner_client_id",
            "name",
            name="uq_wf_provider_integration_name",
        ),
    )
    op.create_table(
        "wf_provider_credentials",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column(
            "provider_integration_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column("api_credential_id", sa.String(length=255), nullable=False),
        sa.Column("signing_key_id", sa.String(length=255), nullable=False),
        sa.Column("secret_ref", sa.Text(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("allowed_operations", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "purpose = 'provider_events'",
            name="ck_wf_provider_credential_purpose",
        ),
        sa.ForeignKeyConstraint(
            ["api_credential_id"],
            ["partner_api_credentials.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["provider_integration_id"],
            ["wf_provider_integrations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "api_credential_id",
            "signing_key_id",
            name="uq_wf_provider_credential_keys",
        ),
    )
    op.create_index(
        "ix_wf_provider_credential_integration_status",
        "wf_provider_credentials",
        ["provider_integration_id", "status"],
    )

    op.create_table(
        "wf_durable_jobs",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("owner_kind", sa.String(length=32), nullable=False),
        sa.Column("owner_namespace", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("domain_id", sa.String(length=64)),
        sa.Column("area_id", sa.String(length=64)),
        sa.Column("manager_account_id", sa.String(length=255)),
        sa.Column("provider_integration_id", sa.String(length=255)),
        sa.Column("job_type", sa.String(length=200), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String(length=200)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("fencing_token", sa.Integer(), nullable=False),
        sa.Column("result", sa.JSON()),
        sa.Column("error", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(owner_kind = 'scope' AND domain_id IS NOT NULL "
            "AND area_id IS NOT NULL AND manager_account_id IS NOT NULL "
            "AND provider_integration_id IS NULL) OR "
            "(owner_kind = 'provider' AND domain_id IS NULL "
            "AND area_id IS NULL AND manager_account_id IS NULL "
            "AND provider_integration_id IS NOT NULL)",
            name="ck_wf_job_owner_shape",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_namespace",
            "idempotency_key",
            name="uq_wf_job_owner_idempotency",
        ),
    )
    op.create_index(
        "ix_wf_job_claim",
        "wf_durable_jobs",
        ["status", "not_before", "lease_expires_at"],
    )
    op.create_index(
        "ix_wf_job_scope",
        "wf_durable_jobs",
        ["tenant_id", "domain_id", "area_id", "manager_account_id"],
    )


def downgrade() -> None:
    """Drop only the Phase-C foundation additions."""
    op.drop_index("ix_wf_job_scope", table_name="wf_durable_jobs")
    op.drop_index("ix_wf_job_claim", table_name="wf_durable_jobs")
    op.drop_table("wf_durable_jobs")
    op.drop_index(
        "ix_wf_provider_credential_integration_status",
        table_name="wf_provider_credentials",
    )
    op.drop_table("wf_provider_credentials")
    op.drop_table("wf_provider_integrations")
    op.drop_index(
        "ix_wf_route_owner_status",
        table_name="wf_partner_manager_routes",
    )
    op.drop_table("wf_partner_manager_routes")
    op.drop_index(
        "ix_wf_manager_membership_scope_status",
        table_name="wf_manager_memberships",
    )
    op.drop_table("wf_manager_memberships")
