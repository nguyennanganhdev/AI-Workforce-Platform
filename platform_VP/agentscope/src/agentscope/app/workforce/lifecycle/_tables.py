"""Exported Lifecycle metadata for Foundation's existing Alembic chain.

No schema is created at import or service startup. Foundation must include this
metadata in its additive migration before enabling the router/worker.
"""

from typing import Dict

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKeyConstraint,
    Integer,
    JSON,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

metadata = MetaData()
SCOPE_COLUMNS = ("tenant_id", "domain_id", "area_id", "manager_account_id")


def record_table(
    name: str, business: bool = False, agent_reference: bool = False
) -> Table:
    columns = [Column("id", String(200), primary_key=True)]
    columns.extend(
        Column(key, String(200), nullable=False) for key in SCOPE_COLUMNS
    )
    columns.extend(
        [
            Column("revision", Integer, nullable=False),
            Column("payload", JSON, nullable=False),
            CheckConstraint("revision >= 1", name=f"ck_{name}_revision"),
            UniqueConstraint(*SCOPE_COLUMNS, "id", name=f"uq_{name}_owner_id"),
        ]
    )
    if agent_reference:
        columns.append(Column("agent_id", String(200), nullable=False))
        columns.append(
            ForeignKeyConstraint(
                [*SCOPE_COLUMNS, "agent_id"],
                [
                    f"wf_agent_definitions.{key}"
                    for key in (*SCOPE_COLUMNS, "id")
                ],
                name=f"fk_{name}_agent_owner",
                ondelete="RESTRICT",
            )
        )
    if business:
        columns.append(Column("legacy_agent_id", String(200), nullable=True))
        columns.append(Column("business_key", String(200), nullable=False))
        columns.append(
            UniqueConstraint(
                *SCOPE_COLUMNS,
                "business_key",
                name="uq_wf_agent_business_scope",
            )
        )
        columns.append(
            UniqueConstraint(
                *SCOPE_COLUMNS,
                "legacy_agent_id",
                name="uq_wf_agent_legacy_scope",
            )
        )
    return Table(name, metadata, *columns)


agents = record_table("wf_agent_definitions", business=True)
drafts = record_table("wf_drafts", agent_reference=True)
versions = record_table("wf_versions", agent_reference=True)
deployments = record_table("wf_deployments", agent_reference=True)
evaluations = record_table("wf_evaluations", agent_reference=True)
snapshots = record_table("wf_evaluation_snapshots", agent_reference=True)
suites = record_table("wf_evaluation_suites")
cases = record_table("wf_evaluation_cases", agent_reference=True)
release_events = record_table("wf_release_events", agent_reference=True)
batches = record_table("wf_build_batches")
batch_items = record_table("wf_build_batch_items")
reuse_checks = record_table("wf_agent_reuse_checks")
receipts = record_table("wf_lifecycle_idempotency")
catalogs = Table(
    "wf_agent_catalog_revisions",
    metadata,
    *(Column(key, String(200), primary_key=True) for key in SCOPE_COLUMNS),
    Column("revision", Integer, nullable=False),
)
TABLES: Dict[str, Table] = {
    "agents": agents,
    "drafts": drafts,
    "versions": versions,
    "deployments": deployments,
    "evaluations": evaluations,
    "batches": batches,
    "reuse_checks": reuse_checks,
    "receipts": receipts,
    "snapshots": snapshots,
    "suites": suites,
    "cases": cases,
    "release_events": release_events,
    "batch_items": batch_items,
}
