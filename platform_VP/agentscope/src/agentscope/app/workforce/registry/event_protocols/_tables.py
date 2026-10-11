# -*- coding: utf-8 -*-
"""Registry-owned SQL metadata for immutable async protocol snapshots."""

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)


metadata = MetaData()


async_protocol_versions = Table(
    "wf_async_protocol_versions",
    metadata,
    Column("id", String(255), primary_key=True),
    Column("tenant_id", String(255), nullable=False),
    Column("domain_id", String(64), nullable=False),
    Column("area_id", String(64), nullable=False),
    Column("manager_account_id", String(255), nullable=False),
    Column("tool_version_id", String(255), nullable=False),
    Column("protocol_id", String(255), nullable=False),
    Column("protocol_version", String(100), nullable=False),
    Column("schema_hash", String(64), nullable=False),
    Column("configuration", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "tenant_id",
        "domain_id",
        "area_id",
        "manager_account_id",
        "tool_version_id",
        "protocol_id",
        "protocol_version",
        name="uq_wf_proto_version_identity",
    ),
)
Index(
    "ix_wf_proto_version_hash",
    async_protocol_versions.c.tenant_id,
    async_protocol_versions.c.domain_id,
    async_protocol_versions.c.area_id,
    async_protocol_versions.c.manager_account_id,
    async_protocol_versions.c.schema_hash,
)


async_protocol_heads = Table(
    "wf_async_protocol_heads",
    metadata,
    Column("id", String(255), primary_key=True),
    Column("tenant_id", String(255), nullable=False),
    Column("domain_id", String(64), nullable=False),
    Column("area_id", String(64), nullable=False),
    Column("manager_account_id", String(255), nullable=False),
    Column("tool_version_id", String(255), nullable=False),
    Column("current_protocol_id", String(255), nullable=False),
    Column("current_protocol_version", String(100), nullable=False),
    Column("current_schema_hash", String(64), nullable=False),
    Column("current_provider_integration_id", String(255), nullable=True),
    Column("current_capabilities", JSON, nullable=False),
    Column("enabled", Boolean, nullable=False),
    Column("revision", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("revision >= 1", name="ck_wf_proto_head_revision"),
    ForeignKeyConstraint(
        [
            "tenant_id",
            "domain_id",
            "area_id",
            "manager_account_id",
            "tool_version_id",
            "current_protocol_id",
            "current_protocol_version",
        ],
        [
            "wf_async_protocol_versions.tenant_id",
            "wf_async_protocol_versions.domain_id",
            "wf_async_protocol_versions.area_id",
            "wf_async_protocol_versions.manager_account_id",
            "wf_async_protocol_versions.tool_version_id",
            "wf_async_protocol_versions.protocol_id",
            "wf_async_protocol_versions.protocol_version",
        ],
        name="fk_wf_proto_head_current_version",
    ),
    UniqueConstraint(
        "tenant_id",
        "domain_id",
        "area_id",
        "manager_account_id",
        "tool_version_id",
        name="uq_wf_proto_head_scope_tool",
    ),
)
Index(
    "ix_wf_proto_head_enabled",
    async_protocol_heads.c.tenant_id,
    async_protocol_heads.c.domain_id,
    async_protocol_heads.c.area_id,
    async_protocol_heads.c.manager_account_id,
    async_protocol_heads.c.enabled,
)


__all__ = [
    "async_protocol_heads",
    "async_protocol_versions",
    "metadata",
]
