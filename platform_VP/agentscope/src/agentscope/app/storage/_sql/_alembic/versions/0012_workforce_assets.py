"""Ticket-bound private Workforce assets.

Revision ID: 0012_workforce_assets
Revises: 0011_workforce_releases
Create Date: 2026-10-12 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_workforce_assets"
down_revision: str | None = "0011_workforce_releases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wf_assets",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("domain_id", sa.String(length=255), nullable=False),
        sa.Column("area_id", sa.String(length=255), nullable=False),
        sa.Column("manager_account_id", sa.String(length=255), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("partner_client_id", sa.String(length=255), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column("external_ticket_id", sa.String(length=255), nullable=True),
        sa.Column("external_conversation_id", sa.String(length=255), nullable=False),
        sa.Column("workflow_id", sa.String(length=255), nullable=True),
        sa.Column("operation_id", sa.String(length=255), nullable=True),
        sa.Column("provider_integration_id", sa.String(length=255), nullable=True),
        sa.Column("object_uri", sa.String(length=2048), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("expected_size", sa.Integer(), nullable=False),
        sa.Column("actual_size", sa.Integer(), nullable=True),
        sa.Column("upload_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("object_uri", name="uq_wf_asset_object_uri"),
    )
    op.create_index(
        "ix_wf_asset_customer_audience",
        "wf_assets",
        [
            "tenant_id",
            "partner_client_id",
            "external_user_id",
            "external_conversation_id",
        ],
    )
    op.create_index(
        "ix_wf_asset_workflow",
        "wf_assets",
        ["tenant_id", "workflow_id", "status"],
    )
    op.create_index(
        "ix_wf_asset_provider_operation",
        "wf_assets",
        ["tenant_id", "provider_integration_id", "operation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_wf_asset_provider_operation", table_name="wf_assets")
    op.drop_index("ix_wf_asset_workflow", table_name="wf_assets")
    op.drop_index("ix_wf_asset_customer_audience", table_name="wf_assets")
    op.drop_table("wf_assets")
