"""Additive D4 metadata, to be migrated by Foundation; no runtime create_all."""

from typing import List

from sqlalchemy import Boolean, Column, Integer, JSON, MetaData, String, Table

metadata = MetaData()


def _scope() -> List[Column]:
    return [
        Column(name, String(200), primary_key=True)
        for name in ("tenant_id", "domain_id", "area_id", "manager_account_id")
    ]


candidates = Table(
    "wf_release_candidates",
    metadata,
    *_scope(),
    Column("draft_id", String(200), primary_key=True),
    Column("agent_id", String(200), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("frozen", JSON, nullable=False),
    Column("content_hash", String(64), nullable=False),
)
versions = Table(
    "wf_published_versions",
    metadata,
    *_scope(),
    Column("version_id", String(200), primary_key=True),
    Column("agent_id", String(200), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("content_hash", String(64), nullable=False),
)
deployments = Table(
    "wf_agent_deployments",
    metadata,
    *_scope(),
    Column("deployment_id", String(200), primary_key=True),
    Column("active_version_id", String(200)),
    Column("revision", Integer, nullable=False),
    Column("archived", Boolean, nullable=False),
    Column("enabled", Boolean, nullable=False),
)
commands = Table(
    "wf_release_commands",
    metadata,
    *_scope(),
    Column("command_id", String(200), primary_key=True),
    Column("request_hash", String(64), nullable=False),
    Column("result", JSON),
)


def get_release_metadata() -> MetaData:
    return metadata
