"""Tables of the partner case runtime of unified mode (migration 0017).

They hold what unified mode adds on top of the shared workflow engine: the
route's leader and tools, the provider event schema, the operations a tool
call started, the receipts of provider events, the evidence/say log of a
ticket, its session, and the approvals a partner decides.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
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

routes = Table(
    "wf_unified_routes",
    metadata,
    Column("route_id", String(255), primary_key=True),
    Column("tenant_id", String(255), nullable=False),
    Column("partner_client_id", String(255), nullable=False),
    Column("manager_account_id", String(255), nullable=False),
    Column("leader_agent_id", String(255), nullable=False),
    Column("integration_id", String(255), nullable=True),
    Column("config", JSON, nullable=False),
    Column("tools", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

integrations = Table(
    "wf_unified_integrations",
    metadata,
    Column("integration_id", String(255), primary_key=True),
    Column("tenant_id", String(255), nullable=False),
    Column("partner_client_id", String(255), nullable=False),
    Column("event_schema", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

case_sessions = Table(
    "wf_unified_case_sessions",
    metadata,
    Column("session_id", String(255), primary_key=True),
    Column("workflow_id", String(255), nullable=False, unique=True),
    Column("route_id", String(255), nullable=False),
    Column("manager_account_id", String(255), nullable=False),
    Column("scope", JSON, nullable=False),
    Column("agent_id", String(255), nullable=False),
    Column("agent_version", Integer, nullable=False),
    Column("trigger_id", String(255), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

operations = Table(
    "wf_unified_operations",
    metadata,
    Column("operation_id", String(255), primary_key=True),
    Column("workflow_id", String(255), nullable=False),
    Column("integration_id", String(255), nullable=True),
    Column("tool_name", String(255), nullable=False),
    Column("client_reference", String(255), nullable=False, unique=True),
    Column("external_job_id", String(255), nullable=True),
    Column("status", String(64), nullable=False),
    Column("rank", Integer, nullable=False),
    Column("terminal", Boolean, nullable=False),
    Column("outcome", String(64), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
Index("ix_wf_unified_operations_workflow", operations.c.workflow_id)

receipts = Table(
    "wf_unified_receipts",
    metadata,
    Column("receipt_id", String(255), primary_key=True),
    Column("integration_id", String(255), nullable=False),
    Column("external_event_id", String(255), nullable=False),
    Column("payload_hash", String(128), nullable=False),
    Column("ingestion_status", String(32), nullable=False),
    Column("normalized_status", String(64), nullable=True),
    Column("error_code", String(64), nullable=True),
    Column("operation_id", String(255), nullable=True),
    Column("received_at", DateTime(timezone=True), nullable=False),
    Column("applied_at", DateTime(timezone=True), nullable=True),
    UniqueConstraint(
        "integration_id",
        "external_event_id",
        name="uq_wf_unified_receipt_event",
    ),
)

case_entries = Table(
    "wf_unified_case_entries",
    metadata,
    Column("id", String(255), primary_key=True),
    Column("workflow_id", String(255), nullable=False),
    Column("seq", Integer, nullable=False),
    # evidence | say | event
    Column("kind", String(32), nullable=False),
    Column("trigger_id", String(255), nullable=True),
    Column("text", Text, nullable=False),
    Column("expects", String(32), nullable=True),
    Column("outcome", String(64), nullable=True),
    # An event the leader must hear about in its next turn.
    Column("pending", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("workflow_id", "seq", name="uq_wf_unified_case_entry_seq"),
)

approvals = Table(
    "wf_unified_approvals",
    metadata,
    Column("approval_id", String(255), primary_key=True),
    Column("workflow_id", String(255), nullable=False),
    Column("session_id", String(255), nullable=False),
    Column("agent_id", String(255), nullable=False),
    Column("tool_call_id", String(255), nullable=False),
    Column("tool_name", String(255), nullable=False),
    Column("arguments", JSON, nullable=False),
    Column("arguments_hash", String(128), nullable=False),
    Column("expected_revision", Integer, nullable=False),
    Column("summary", JSON, nullable=False),
    # pending | approved | rejected | expired
    Column("status", String(32), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("decided_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
Index("ix_wf_unified_approvals_workflow", approvals.c.workflow_id)


def get_metadata() -> MetaData:
    return metadata
