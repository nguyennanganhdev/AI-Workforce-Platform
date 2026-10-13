# -*- coding: utf-8 -*-
"""Area-scoped accounts, partner API clients, reviewed memory and tickets.

Revision ID: 0008_area_platform
Revises: 0007_auth
Create Date: 2026-10-09 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_area_platform"
down_revision: Union[str, None] = "0007_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the first area-platform business schema."""
    op.create_table(
        "business_domains",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "name",
            name="uq_business_domains_tenant_name",
        ),
    )
    op.create_index(
        "ix_business_domains_tenant_status",
        "business_domains",
        ["tenant_id", "status"],
    )
    op.create_table(
        "areas",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("domain_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(
            ["domain_id"],
            ["business_domains.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "domain_id",
            "name",
            name="uq_areas_domain_name",
        ),
    )
    op.create_index("ix_areas_domain_status", "areas", ["domain_id", "status"])

    # These seed rows let the local deployment register immediately. Future
    # administration can replace them with managed directory APIs.
    domains = sa.table(
        "business_domains",
        sa.column("id", sa.String),
        sa.column("tenant_id", sa.String),
        sa.column("name", sa.String),
        sa.column("status", sa.String),
    )
    op.bulk_insert(
        domains,
        [
            {
                "id": "vinhomes",
                "tenant_id": "default",
                "name": "Vinhomes",
                "status": "active",
            },
            {
                "id": "vinpearl",
                "tenant_id": "default",
                "name": "Vinpearl",
                "status": "active",
            },
            {
                "id": "vinwonders",
                "tenant_id": "default",
                "name": "VinWonders",
                "status": "active",
            },
        ],
    )
    areas = sa.table(
        "areas",
        sa.column("id", sa.String),
        sa.column("domain_id", sa.String),
        sa.column("name", sa.String),
        sa.column("status", sa.String),
    )
    op.bulk_insert(
        areas,
        [
            {
                "id": "ocean-park-1",
                "domain_id": "vinhomes",
                "name": "Ocean Park 1",
                "status": "active",
            },
            {
                "id": "ocean-park-2",
                "domain_id": "vinhomes",
                "name": "Ocean Park 2",
                "status": "active",
            },
        ],
    )

    op.add_column(
        "auth_users",
        sa.Column(
            "role",
            sa.String(length=32),
            nullable=False,
            server_default="AREA_MANAGER",
        ),
    )
    op.add_column(
        "auth_users",
        sa.Column("domain_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "auth_users",
        sa.Column("area_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_auth_users_area_role_status",
        "auth_users",
        ["tenant_id", "domain_id", "area_id", "role", "status"],
    )

    op.create_table(
        "partner_api_clients",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("domain_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["domain_id"], ["business_domains.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_partner_api_clients_domain_status",
        "partner_api_clients",
        ["tenant_id", "domain_id", "status"],
    )
    op.create_table(
        "partner_api_credentials",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=36), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["partner_api_clients.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_partner_api_credentials_client",
        "partner_api_credentials",
        ["client_id", "revoked_at"],
    )
    op.create_table(
        "partner_residences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("partner_client_id", sa.String(length=36), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column("residence_id", sa.String(length=255), nullable=False),
        sa.Column("domain_id", sa.String(length=64), nullable=False),
        sa.Column("area_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["partner_client_id"],
            ["partner_api_clients.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["domain_id"], ["business_domains.id"]),
        sa.ForeignKeyConstraint(["area_id"], ["areas.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "partner_client_id",
            "residence_id",
            name="uq_partner_residences_client_residence",
        ),
    )
    op.create_index(
        "ix_partner_residences_user_status",
        "partner_residences",
        ["partner_client_id", "external_user_id", "status"],
    )

    op.create_table(
        "memory_candidates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("domain_id", sa.String(length=64), nullable=False),
        sa.Column("area_id", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.String(length=255)),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=255)),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("reviewed_by", sa.String(length=36)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["domain_id"], ["business_domains.id"]),
        sa.ForeignKeyConstraint(["area_id"], ["areas.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_memory_candidates_review_queue",
        "memory_candidates",
        ["tenant_id", "domain_id", "area_id", "status", "created_at"],
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("domain_id", sa.String(length=64), nullable=False),
        sa.Column("area_id", sa.String(length=64), nullable=False),
        sa.Column("partner_client_id", sa.String(length=36), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column("residence_id", sa.String(length=255)),
        sa.Column("conversation_id", sa.String(length=255)),
        sa.Column("external_ticket_id", sa.String(length=255)),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["domain_id"], ["business_domains.id"]),
        sa.ForeignKeyConstraint(["area_id"], ["areas.id"]),
        sa.ForeignKeyConstraint(
            ["partner_client_id"],
            ["partner_api_clients.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "partner_client_id",
            "external_ticket_id",
            name="uq_tickets_client_external_id",
        ),
    )
    op.create_index(
        "ix_tickets_area_status_updated",
        "tickets",
        ["tenant_id", "domain_id", "area_id", "status", "updated_at"],
    )
    op.create_table(
        "ticket_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("actor_type", sa.String(length=24), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ticket_events_ticket_created",
        "ticket_events",
        ["ticket_id", "created_at"],
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.add_column(
            "reme_memories",
            sa.Column("domain_id", sa.String(length=64), nullable=True),
        )
        op.add_column(
            "reme_memories",
            sa.Column("area_id", sa.String(length=64), nullable=True),
        )
        op.add_column(
            "reme_memories",
            sa.Column("approved_by", sa.String(length=36), nullable=True),
        )
        op.add_column(
            "reme_memories",
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.add_column(
            "reme_memories",
            sa.Column("source_candidate_id", sa.String(length=36), nullable=True),
        )
        # Legacy active rows were never reviewed. They must not be retrieved
        # after review-gating becomes effective.
        op.execute(
            "UPDATE reme_memories SET status = 'archived' WHERE status = 'active'"
        )
        op.create_index(
            "ix_reme_memories_area_active",
            "reme_memories",
            ["tenant_id", "domain_id", "area_id", "agent_id", "status"],
        )
        op.create_unique_constraint(
            "uq_reme_memories_source_candidate",
            "reme_memories",
            ["source_candidate_id"],
        )
        op.create_foreign_key(
            "fk_reme_memories_source_candidate",
            "reme_memories",
            "memory_candidates",
            ["source_candidate_id"],
            ["id"],
        )
        op.create_check_constraint(
            "ck_reme_memories_active_is_reviewed",
            "reme_memories",
            "status <> 'active' OR ("
            "domain_id IS NOT NULL AND area_id IS NOT NULL "
            "AND approved_by IS NOT NULL AND approved_at IS NOT NULL "
            "AND source_candidate_id IS NOT NULL)",
        )


def downgrade() -> None:
    """Remove the area-platform business schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint(
            "ck_reme_memories_active_is_reviewed",
            "reme_memories",
            type_="check",
        )
        op.drop_constraint(
            "fk_reme_memories_source_candidate",
            "reme_memories",
            type_="foreignkey",
        )
        op.drop_constraint(
            "uq_reme_memories_source_candidate",
            "reme_memories",
            type_="unique",
        )
        op.drop_index("ix_reme_memories_area_active", table_name="reme_memories")
        op.drop_column("reme_memories", "source_candidate_id")
        op.drop_column("reme_memories", "approved_at")
        op.drop_column("reme_memories", "approved_by")
        op.drop_column("reme_memories", "area_id")
        op.drop_column("reme_memories", "domain_id")

    op.drop_index("ix_ticket_events_ticket_created", table_name="ticket_events")
    op.drop_table("ticket_events")
    op.drop_index("ix_tickets_area_status_updated", table_name="tickets")
    op.drop_table("tickets")
    op.drop_index(
        "ix_memory_candidates_review_queue",
        table_name="memory_candidates",
    )
    op.drop_table("memory_candidates")
    op.drop_index(
        "ix_partner_residences_user_status",
        table_name="partner_residences",
    )
    op.drop_table("partner_residences")
    op.drop_index(
        "ix_partner_api_credentials_client",
        table_name="partner_api_credentials",
    )
    op.drop_table("partner_api_credentials")
    op.drop_index(
        "ix_partner_api_clients_domain_status",
        table_name="partner_api_clients",
    )
    op.drop_table("partner_api_clients")
    op.drop_index("ix_auth_users_area_role_status", table_name="auth_users")
    op.drop_column("auth_users", "area_id")
    op.drop_column("auth_users", "domain_id")
    op.drop_column("auth_users", "role")
    op.drop_index("ix_areas_domain_status", table_name="areas")
    op.drop_table("areas")
    op.drop_index(
        "ix_business_domains_tenant_status",
        table_name="business_domains",
    )
    op.drop_table("business_domains")
