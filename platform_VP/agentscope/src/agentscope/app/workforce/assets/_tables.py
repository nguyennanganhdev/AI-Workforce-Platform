"""SQL metadata for private Workforce assets."""

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

metadata = MetaData()

assets = Table(
    "wf_assets",
    metadata,
    Column("id", String(255), primary_key=True),
    Column("tenant_id", String(255), nullable=False),
    Column("domain_id", String(255), nullable=False),
    Column("area_id", String(255), nullable=False),
    Column("manager_account_id", String(255), nullable=False),
    Column("origin", String(32), nullable=False),
    Column("status", String(32), nullable=False),
    Column("partner_client_id", String(255), nullable=False),
    Column("external_user_id", String(255), nullable=False),
    Column("external_ticket_id", String(255), nullable=True),
    Column("external_conversation_id", String(255), nullable=False),
    Column("workflow_id", String(255), nullable=True),
    Column("operation_id", String(255), nullable=True),
    Column("provider_integration_id", String(255), nullable=True),
    Column("object_uri", String(2048), nullable=False),
    Column("filename", String(512), nullable=False),
    Column("content_type", String(100), nullable=False),
    Column("expected_size", Integer, nullable=False),
    Column("actual_size", Integer, nullable=True),
    Column("upload_expires_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("object_uri", name="uq_wf_asset_object_uri"),
)
Index(
    "ix_wf_asset_customer_audience",
    assets.c.tenant_id,
    assets.c.partner_client_id,
    assets.c.external_user_id,
    assets.c.external_conversation_id,
)
Index(
    "ix_wf_asset_workflow",
    assets.c.tenant_id,
    assets.c.workflow_id,
    assets.c.status,
)
Index(
    "ix_wf_asset_provider_operation",
    assets.c.tenant_id,
    assets.c.provider_integration_id,
    assets.c.operation_id,
)

__all__ = ["assets", "metadata"]
