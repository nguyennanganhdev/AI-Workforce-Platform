# -*- coding: utf-8 -*-
"""Foundation-owned SQL tables for the Phase-C Workforce baseline.

Business modules own their payload tables.  This module contains only the
cross-cutting records needed before those modules can be composed: verified
manager memberships, partner routes, provider credentials and durable jobs.
Alembic remains the only component allowed to create these tables.
"""

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)


metadata = MetaData()


manager_memberships = Table(
    "wf_manager_memberships",
    metadata,
    Column("id", String(255), primary_key=True),
    Column("tenant_id", String(255), nullable=False),
    Column("domain_id", String(64), nullable=False),
    Column("area_id", String(64), nullable=False),
    Column("manager_account_id", String(255), nullable=False),
    Column("status", String(32), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("verified_by", String(255), nullable=True),
    Column("verified_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "manager_account_id",
        name="uq_wf_manager_membership_account",
    ),
)
Index(
    "ix_wf_manager_membership_scope_status",
    manager_memberships.c.tenant_id,
    manager_memberships.c.domain_id,
    manager_memberships.c.area_id,
    manager_memberships.c.status,
)


partner_manager_routes = Table(
    "wf_partner_manager_routes",
    metadata,
    Column("id", String(255), primary_key=True),
    Column("tenant_id", String(255), nullable=False),
    Column("domain_id", String(64), nullable=False),
    Column("area_id", String(64), nullable=False),
    Column("manager_account_id", String(255), nullable=False),
    Column("partner_client_id", String(255), nullable=False),
    Column("external_management_ref", String(128), nullable=False),
    Column("status", String(32), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("membership_revision", Integer, nullable=False),
    Column("allowed_operations", JSON, nullable=False),
    Column("granted_by", String(255), nullable=False),
    Column("confirmed_by_client_id", String(255), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "partner_client_id",
        "external_management_ref",
        name="uq_wf_route_client_management_ref",
    ),
)
Index(
    "ix_wf_route_owner_status",
    partner_manager_routes.c.tenant_id,
    partner_manager_routes.c.domain_id,
    partner_manager_routes.c.area_id,
    partner_manager_routes.c.manager_account_id,
    partner_manager_routes.c.status,
)


provider_integrations = Table(
    "wf_provider_integrations",
    metadata,
    Column("id", String(255), primary_key=True),
    Column("tenant_id", String(255), nullable=False),
    Column("partner_client_id", String(255), nullable=False),
    Column("name", String(255), nullable=False),
    Column("status", String(32), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "tenant_id",
        "partner_client_id",
        "name",
        name="uq_wf_provider_integration_name",
    ),
)


provider_credentials = Table(
    "wf_provider_credentials",
    metadata,
    Column("id", String(255), primary_key=True),
    Column("provider_integration_id", String(255), nullable=False),
    Column("api_credential_id", String(255), nullable=False),
    Column("signing_key_id", String(255), nullable=False),
    Column("secret_ref", Text, nullable=False),
    Column("purpose", String(32), nullable=False),
    Column("allowed_operations", JSON, nullable=False),
    Column("status", String(32), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=True),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "api_credential_id",
        "signing_key_id",
        name="uq_wf_provider_credential_keys",
    ),
)
Index(
    "ix_wf_provider_credential_integration_status",
    provider_credentials.c.provider_integration_id,
    provider_credentials.c.status,
)


durable_jobs = Table(
    "wf_durable_jobs",
    metadata,
    Column("id", String(255), primary_key=True),
    Column("owner_kind", String(32), nullable=False),
    Column("owner_namespace", String(64), nullable=False),
    Column("tenant_id", String(255), nullable=False),
    Column("domain_id", String(64), nullable=True),
    Column("area_id", String(64), nullable=True),
    Column("manager_account_id", String(255), nullable=True),
    Column("provider_integration_id", String(255), nullable=True),
    Column("personal_user_id", String(255), nullable=True),
    Column("job_type", String(200), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("payload_hash", String(64), nullable=False),
    Column("idempotency_key", String(500), nullable=False),
    Column("status", String(32), nullable=False),
    Column("attempt", Integer, nullable=False),
    Column("max_attempts", Integer, nullable=False),
    Column("not_before", DateTime(timezone=True), nullable=False),
    Column("lease_owner", String(200), nullable=True),
    Column("lease_expires_at", DateTime(timezone=True), nullable=True),
    Column("fencing_token", Integer, nullable=False),
    Column("result", JSON, nullable=True),
    Column("error", JSON, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "owner_namespace",
        "idempotency_key",
        name="uq_wf_job_owner_idempotency",
    ),
)
Index(
    "ix_wf_job_claim",
    durable_jobs.c.status,
    durable_jobs.c.not_before,
    durable_jobs.c.lease_expires_at,
)
Index(
    "ix_wf_job_scope",
    durable_jobs.c.tenant_id,
    durable_jobs.c.domain_id,
    durable_jobs.c.area_id,
    durable_jobs.c.manager_account_id,
)


__all__ = [
    "durable_jobs",
    "manager_memberships",
    "metadata",
    "partner_manager_routes",
    "provider_credentials",
    "provider_integrations",
]
