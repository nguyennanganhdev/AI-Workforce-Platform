# -*- coding: utf-8 -*-
"""Workforce Phase-C runtime persistence.

Revision ID: 0010_workforce_runtime
Revises: 0009_workforce_foundation
Create Date: 2026-10-12 00:00:00.000000

The table definitions are deliberately frozen in this revision.  Runtime
modules publish SQLAlchemy metadata to their owners, but an already released
migration must never change when those modules evolve later.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0010_workforce_runtime"
down_revision: Union[str, None] = "0009_workforce_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


metadata = sa.MetaData()


def _scope(length: int = 255) -> list[sa.Column]:
    return [
        sa.Column(name, sa.String(length=length), nullable=False)
        for name in ("tenant_id", "domain_id", "area_id", "manager_account_id")
    ]


def _payload_table(
    name: str,
    *extra: sa.Column,
    constraints: tuple[sa.Constraint, ...] = (),
    scoped: bool = True,
) -> sa.Table:
    columns: list[sa.SchemaItem] = [
        sa.Column("id", sa.String(length=255), primary_key=True)
    ]
    if scoped:
        columns.extend(_scope())
    columns.extend(extra)
    columns.extend(
        (
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
        )
    )
    columns.extend(constraints)
    table = sa.Table(name, metadata, *columns)
    if scoped:
        sa.Index(
            name + "_owner",
            table.c.tenant_id,
            table.c.domain_id,
            table.c.area_id,
            table.c.manager_account_id,
        )
    return table


protocol_versions = sa.Table(
    "wf_async_protocol_versions",
    metadata,
    sa.Column("id", sa.String(length=255), primary_key=True),
    sa.Column("tenant_id", sa.String(length=255), nullable=False),
    sa.Column("domain_id", sa.String(length=64), nullable=False),
    sa.Column("area_id", sa.String(length=64), nullable=False),
    sa.Column("manager_account_id", sa.String(length=255), nullable=False),
    sa.Column("tool_version_id", sa.String(length=255), nullable=False),
    sa.Column("protocol_id", sa.String(length=255), nullable=False),
    sa.Column("protocol_version", sa.String(length=100), nullable=False),
    sa.Column("schema_hash", sa.String(length=64), nullable=False),
    sa.Column("configuration", sa.JSON(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint(
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
sa.Index(
    "ix_wf_proto_version_hash",
    protocol_versions.c.tenant_id,
    protocol_versions.c.domain_id,
    protocol_versions.c.area_id,
    protocol_versions.c.manager_account_id,
    protocol_versions.c.schema_hash,
)

protocol_heads = sa.Table(
    "wf_async_protocol_heads",
    metadata,
    sa.Column("id", sa.String(length=255), primary_key=True),
    sa.Column("tenant_id", sa.String(length=255), nullable=False),
    sa.Column("domain_id", sa.String(length=64), nullable=False),
    sa.Column("area_id", sa.String(length=64), nullable=False),
    sa.Column("manager_account_id", sa.String(length=255), nullable=False),
    sa.Column("tool_version_id", sa.String(length=255), nullable=False),
    sa.Column("current_protocol_id", sa.String(length=255), nullable=False),
    sa.Column(
        "current_protocol_version", sa.String(length=100), nullable=False
    ),
    sa.Column("current_schema_hash", sa.String(length=64), nullable=False),
    sa.Column("current_provider_integration_id", sa.String(length=255)),
    sa.Column("current_capabilities", sa.JSON(), nullable=False),
    sa.Column("enabled", sa.Boolean(), nullable=False),
    sa.Column("revision", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("revision >= 1", name="ck_wf_proto_head_revision"),
    sa.ForeignKeyConstraint(
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
    sa.UniqueConstraint(
        "tenant_id",
        "domain_id",
        "area_id",
        "manager_account_id",
        "tool_version_id",
        name="uq_wf_proto_head_scope_tool",
    ),
)
sa.Index(
    "ix_wf_proto_head_enabled",
    protocol_heads.c.tenant_id,
    protocol_heads.c.domain_id,
    protocol_heads.c.area_id,
    protocol_heads.c.manager_account_id,
    protocol_heads.c.enabled,
)

tool_calls = _payload_table(
    "wf_tool_calls",
    sa.Column("run_id", sa.String(length=255), nullable=False),
    sa.Column("idempotency_key", sa.String(length=255), nullable=False),
    constraints=(
        sa.UniqueConstraint(
            "tenant_id",
            "domain_id",
            "area_id",
            "manager_account_id",
            "run_id",
            "idempotency_key",
            name="uq_wf_call_key",
        ),
    ),
)
approvals = _payload_table(
    "wf_approvals",
    sa.Column("call_id", sa.String(length=255), nullable=False),
    constraints=(sa.UniqueConstraint("call_id", name="uq_wf_approval_call"),),
)
bookings = _payload_table(
    "wf_booking_operations",
    sa.Column("call_id", sa.String(length=255), nullable=False),
    constraints=(sa.UniqueConstraint("call_id", name="uq_wf_booking_call"),),
)
execution_events = _payload_table(
    "wf_execution_events",
    sa.Column("call_id", sa.String(length=255), nullable=False),
)
external_operations = _payload_table(
    "wf_external_operations",
    sa.Column("call_id", sa.String(length=255), nullable=False),
    sa.Column("workflow_id", sa.String(length=255), nullable=False),
    sa.Column(
        "provider_integration_id", sa.String(length=255), nullable=False
    ),
    sa.Column("correlation_id", sa.String(length=255), nullable=False),
    sa.Column("external_job_id", sa.String(length=255)),
    constraints=(
        sa.UniqueConstraint("call_id", name="uq_wf_operation_call"),
        sa.UniqueConstraint("correlation_id", name="uq_wf_correlation"),
        sa.UniqueConstraint(
            "tenant_id",
            "provider_integration_id",
            "external_job_id",
            name="uq_wf_provider_job",
        ),
    ),
)
provider_inbox = _payload_table(
    "wf_provider_event_inbox",
    sa.Column("tenant_id", sa.String(length=255), nullable=False),
    sa.Column(
        "provider_integration_id", sa.String(length=255), nullable=False
    ),
    sa.Column("external_event_id", sa.String(length=255), nullable=False),
    constraints=(
        sa.UniqueConstraint(
            "tenant_id",
            "provider_integration_id",
            "external_event_id",
            name="uq_wf_provider_event",
        ),
    ),
    scoped=False,
)

workflows = sa.Table(
    "wf_workflows",
    metadata,
    sa.Column("id", sa.String(length=255), primary_key=True),
    *_scope(),
    sa.Column("conversation_id", sa.String(length=255), nullable=False),
    sa.Column("group_id", sa.String(length=255), nullable=False),
    sa.Column("state", sa.String(length=64), nullable=False),
    sa.Column("revision", sa.Integer(), nullable=False),
    sa.Column("payload", sa.JSON(), nullable=False),
    sa.Column("lease_owner", sa.String(length=255)),
    sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
    sa.Column("fencing_token", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("conversation_id", name="uq_wf_workflow_conversation"),
    sa.UniqueConstraint("group_id", name="uq_wf_workflow_group"),
)
sa.Index(
    "ix_wf_workflow_owner_state",
    workflows.c.tenant_id,
    workflows.c.domain_id,
    workflows.c.area_id,
    workflows.c.manager_account_id,
    workflows.c.state,
)

bindings = sa.Table(
    "wf_workflow_bindings",
    metadata,
    sa.Column("workflow_id", sa.String(length=255), primary_key=True),
    *_scope(),
    sa.Column("partner_client_id", sa.String(length=255), nullable=False),
    sa.Column("external_user_id", sa.String(length=255), nullable=False),
    sa.Column("external_ticket_id", sa.String(length=255)),
    sa.Column(
        "external_conversation_id", sa.String(length=255), nullable=False
    ),
    sa.Column("residence_id", sa.String(length=255)),
    sa.Column("conversation_id", sa.String(length=255), nullable=False),
    sa.Column("group_id", sa.String(length=255), nullable=False),
    sa.Column("route_id", sa.String(length=255), nullable=False),
    sa.Column("route_revision", sa.Integer(), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint(
        "tenant_id",
        "partner_client_id",
        "external_user_id",
        "external_conversation_id",
        name="uq_wf_binding_external_conversation",
    ),
    sa.UniqueConstraint(
        "tenant_id",
        "partner_client_id",
        "external_user_id",
        "external_ticket_id",
        name="uq_wf_binding_external_ticket",
    ),
    sa.UniqueConstraint("conversation_id", name="uq_wf_binding_conversation"),
    sa.UniqueConstraint("group_id", name="uq_wf_binding_group"),
)
sa.Index(
    "ix_wf_binding_owner",
    bindings.c.tenant_id,
    bindings.c.domain_id,
    bindings.c.area_id,
    bindings.c.manager_account_id,
)

workflow_inputs = sa.Table(
    "wf_workflow_inputs",
    metadata,
    sa.Column("id", sa.String(length=255), primary_key=True),
    sa.Column("workflow_id", sa.String(length=255), nullable=False),
    sa.Column("cause_kind", sa.String(length=64), nullable=False),
    sa.Column("cause_id", sa.String(length=255), nullable=False),
    sa.Column("text", sa.Text(), nullable=False),
    sa.Column("payload_hash", sa.String(length=64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint(
        "workflow_id",
        "cause_kind",
        "cause_id",
        name="uq_wf_workflow_input_cause",
    ),
)
sa.Index("ix_wf_workflow_input_workflow", workflow_inputs.c.workflow_id)

checkpoints = sa.Table(
    "wf_workflow_checkpoints",
    metadata,
    sa.Column("id", sa.String(length=255), primary_key=True),
    *_scope(),
    sa.Column("workflow_id", sa.String(length=255), nullable=False),
    sa.Column("state_revision", sa.Integer(), nullable=False),
    sa.Column("payload_hash", sa.String(length=64), nullable=False),
    sa.Column("payload", sa.JSON(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint(
        "workflow_id",
        "state_revision",
        name="uq_wf_checkpoint_workflow_revision",
    ),
)
sa.Index(
    "ix_wf_checkpoint_owner_workflow",
    checkpoints.c.tenant_id,
    checkpoints.c.domain_id,
    checkpoints.c.area_id,
    checkpoints.c.manager_account_id,
    checkpoints.c.workflow_id,
)

commands = sa.Table(
    "wf_partner_commands",
    metadata,
    sa.Column("id", sa.String(length=255), primary_key=True),
    sa.Column("tenant_id", sa.String(length=255), nullable=False),
    sa.Column("partner_client_id", sa.String(length=255), nullable=False),
    sa.Column("external_user_id", sa.String(length=255), nullable=False),
    sa.Column("external_request_id", sa.String(length=255), nullable=False),
    sa.Column("command_kind", sa.String(length=100), nullable=False),
    sa.Column("target_ref", sa.String(length=255)),
    sa.Column("payload_hash", sa.String(length=200), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("result", sa.JSON()),
    sa.Column("error", sa.JSON()),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("completed_at", sa.DateTime(timezone=True)),
    sa.UniqueConstraint(
        "tenant_id",
        "partner_client_id",
        "external_request_id",
        name="uq_wf_partner_command_request",
    ),
)
sa.Index(
    "ix_wf_partner_command_user",
    commands.c.tenant_id,
    commands.c.partner_client_id,
    commands.c.external_user_id,
)

requests = sa.Table(
    "wf_partner_requests",
    metadata,
    sa.Column("id", sa.String(length=255), primary_key=True),
    *_scope(),
    sa.Column("partner_client_id", sa.String(length=255), nullable=False),
    sa.Column("external_user_id", sa.String(length=255), nullable=False),
    sa.Column("workflow_id", sa.String(length=255), nullable=False),
    sa.Column("conversation_id", sa.String(length=255), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("payload", sa.JSON(), nullable=False),
    sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("completed_at", sa.DateTime(timezone=True)),
)
sa.Index(
    "ix_wf_partner_request_audience",
    requests.c.partner_client_id,
    requests.c.external_user_id,
    requests.c.workflow_id,
)

public_events = sa.Table(
    "wf_public_events",
    metadata,
    sa.Column("id", sa.String(length=255), primary_key=True),
    *_scope(),
    sa.Column("conversation_id", sa.String(length=255), nullable=False),
    sa.Column("workflow_id", sa.String(length=255), nullable=False),
    sa.Column("sequence", sa.Integer(), nullable=False),
    sa.Column("event_type", sa.String(length=128), nullable=False),
    sa.Column("causation_id", sa.String(length=255)),
    sa.Column("payload", sa.JSON(), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint(
        "conversation_id",
        "sequence",
        name="uq_wf_public_event_sequence",
    ),
)
sa.Index(
    "ix_wf_public_event_replay",
    public_events.c.conversation_id,
    public_events.c.sequence,
)


def _evaluation_scope() -> list[sa.Column]:
    return [
        sa.Column(name, sa.String(length=200), primary_key=True)
        for name in ("tenant_id", "domain_id", "area_id", "manager_account_id")
    ]


evaluations = sa.Table(
    "wf_evaluations",
    metadata,
    *_evaluation_scope(),
    sa.Column("evaluation_id", sa.String(length=200), primary_key=True),
    sa.Column("snapshot_id", sa.String(length=200), nullable=False),
    sa.Column("content_hash", sa.String(length=64), nullable=False),
    sa.Column("frozen", sa.JSON(), nullable=False),
    sa.Column("record", sa.JSON()),
    sa.Column("record_hash", sa.String(length=64)),
)
evaluation_cases = sa.Table(
    "wf_evaluation_cases",
    metadata,
    *_evaluation_scope(),
    sa.Column("snapshot_id", sa.String(length=200), primary_key=True),
    sa.Column("case_id", sa.String(length=200), primary_key=True),
    sa.Column("workflow_id", sa.String(length=200), nullable=False),
    sa.Column("input_hash", sa.String(length=64), nullable=False),
    sa.Column(
        "cancelled", sa.Boolean(), nullable=False, server_default=sa.false()
    ),
    sa.Column("result", sa.JSON()),
    sa.Column("result_hash", sa.String(length=64)),
)
sa.Index(
    "uq_wf_eval_case_workflow",
    evaluation_cases.c.tenant_id,
    evaluation_cases.c.domain_id,
    evaluation_cases.c.area_id,
    evaluation_cases.c.manager_account_id,
    evaluation_cases.c.workflow_id,
    unique=True,
)
evaluation_evidence = sa.Table(
    "wf_evaluation_turn_evidence",
    metadata,
    *_evaluation_scope(),
    sa.Column("workflow_id", sa.String(length=200), primary_key=True),
    sa.Column("trigger_id", sa.String(length=200), primary_key=True),
    sa.Column("after_revision", sa.Integer(), nullable=False),
    sa.Column("payload", sa.JSON(), nullable=False),
    sa.Column("content_hash", sa.String(length=64), nullable=False),
)
sa.Index(
    "ix_wf_eval_evidence_revision",
    evaluation_evidence.c.tenant_id,
    evaluation_evidence.c.domain_id,
    evaluation_evidence.c.area_id,
    evaluation_evidence.c.manager_account_id,
    evaluation_evidence.c.workflow_id,
    evaluation_evidence.c.after_revision,
)
evaluation_steps = sa.Table(
    "wf_evaluation_steps",
    metadata,
    *_evaluation_scope(),
    sa.Column("snapshot_id", sa.String(length=200), primary_key=True),
    sa.Column("case_id", sa.String(length=200), primary_key=True),
    sa.Column("step_index", sa.Integer(), primary_key=True),
    sa.Column("observation", sa.JSON(), nullable=False),
    sa.Column("content_hash", sa.String(length=64), nullable=False),
)


def upgrade() -> None:
    """Create all owner-provided Phase-C runtime tables and indexes."""
    bind = op.get_bind()
    for table in metadata.sorted_tables:
        table.create(bind=bind)


def downgrade() -> None:
    """Drop only Phase-C runtime additions in dependency-safe order."""
    bind = op.get_bind()
    for table in reversed(metadata.sorted_tables):
        table.drop(bind=bind)
