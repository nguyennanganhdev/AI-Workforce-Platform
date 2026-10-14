"""Partner case runtime of unified mode.

Revision ID: 0017_unified_partner_case
Revises: 0016_agent_memories
Create Date: 2026-10-14 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_unified_partner_case"
down_revision: str | None = "0016_agent_memories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _at(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _id(name: str, nullable: bool = False, **kw) -> sa.Column:
    return sa.Column(name, sa.String(length=255), nullable=nullable, **kw)


def upgrade() -> None:
    op.create_table(
        "wf_unified_routes",
        _id("route_id", primary_key=True),
        _id("tenant_id"),
        _id("partner_client_id"),
        _id("manager_account_id"),
        _id("leader_agent_id"),
        _id("integration_id", nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("tools", sa.JSON(), nullable=False),
        _at("created_at"),
        _at("updated_at"),
    )
    op.create_table(
        "wf_unified_integrations",
        _id("integration_id", primary_key=True),
        _id("tenant_id"),
        _id("partner_client_id"),
        sa.Column("event_schema", sa.JSON(), nullable=False),
        _at("created_at"),
        _at("updated_at"),
    )
    op.create_table(
        "wf_unified_case_sessions",
        _id("session_id", primary_key=True),
        _id("workflow_id", unique=True),
        _id("route_id"),
        _id("manager_account_id"),
        sa.Column("scope", sa.JSON(), nullable=False),
        _id("agent_id"),
        sa.Column("agent_version", sa.Integer(), nullable=False),
        _id("trigger_id", nullable=True),
        _at("created_at"),
    )
    op.create_table(
        "wf_unified_operations",
        _id("operation_id", primary_key=True),
        _id("workflow_id"),
        _id("integration_id", nullable=True),
        _id("tool_name"),
        _id("client_reference", unique=True),
        _id("external_job_id", nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("terminal", sa.Boolean(), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=True),
        _at("created_at"),
        _at("updated_at"),
    )
    op.create_index(
        "ix_wf_unified_operations_workflow",
        "wf_unified_operations",
        ["workflow_id"],
    )
    op.create_table(
        "wf_unified_receipts",
        _id("receipt_id", primary_key=True),
        _id("integration_id"),
        _id("external_event_id"),
        sa.Column("payload_hash", sa.String(length=128), nullable=False),
        sa.Column("ingestion_status", sa.String(length=32), nullable=False),
        sa.Column("normalized_status", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        _id("operation_id", nullable=True),
        _at("received_at"),
        _at("applied_at", nullable=True),
        sa.UniqueConstraint(
            "integration_id",
            "external_event_id",
            name="uq_wf_unified_receipt_event",
        ),
    )
    op.create_table(
        "wf_unified_case_entries",
        _id("id", primary_key=True),
        _id("workflow_id"),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        _id("trigger_id", nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("expects", sa.String(length=32), nullable=True),
        sa.Column("outcome", sa.String(length=64), nullable=True),
        sa.Column("pending", sa.Boolean(), nullable=False),
        _at("created_at"),
        sa.UniqueConstraint("workflow_id", "seq", name="uq_wf_unified_case_entry_seq"),
    )
    op.create_table(
        "wf_unified_approvals",
        _id("approval_id", primary_key=True),
        _id("workflow_id"),
        _id("session_id"),
        _id("agent_id"),
        _id("tool_call_id"),
        _id("tool_name"),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("arguments_hash", sa.String(length=128), nullable=False),
        sa.Column("expected_revision", sa.Integer(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        _at("expires_at"),
        _at("decided_at", nullable=True),
        _at("created_at"),
    )
    op.create_index(
        "ix_wf_unified_approvals_workflow",
        "wf_unified_approvals",
        ["workflow_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_wf_unified_approvals_workflow", table_name="wf_unified_approvals")
    op.drop_table("wf_unified_approvals")
    op.drop_table("wf_unified_case_entries")
    op.drop_table("wf_unified_receipts")
    op.drop_index("ix_wf_unified_operations_workflow", table_name="wf_unified_operations")
    op.drop_table("wf_unified_operations")
    op.drop_table("wf_unified_case_sessions")
    op.drop_table("wf_unified_integrations")
    op.drop_table("wf_unified_routes")
