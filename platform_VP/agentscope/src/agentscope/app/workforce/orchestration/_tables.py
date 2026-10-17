"""Orchestration-owned additive SQL metadata for Phase C4.

Foundation owns the Alembic chain.  This module only publishes tables so C7
can copy them into the next additive migration without making orchestration
create schema at runtime.
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


def _scope_columns() -> list[Column]:
    return [
        Column(name, String(255), nullable=False)
        for name in (
            "tenant_id",
            "domain_id",
            "area_id",
            "manager_account_id",
        )
    ]


workflows = Table(
    "wf_workflows",
    metadata,
    Column("id", String(255), primary_key=True),
    *_scope_columns(),
    Column("conversation_id", String(255), nullable=False),
    Column("group_id", String(255), nullable=False),
    Column("state", String(64), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("lease_owner", String(255), nullable=True),
    Column("lease_expires_at", DateTime(timezone=True), nullable=True),
    Column("fencing_token", Integer, nullable=False, default=0),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "conversation_id", name="uq_wf_workflow_conversation"
    ),
    UniqueConstraint("group_id", name="uq_wf_workflow_group"),
)
Index(
    "ix_wf_workflow_owner_state",
    workflows.c.tenant_id,
    workflows.c.domain_id,
    workflows.c.area_id,
    workflows.c.manager_account_id,
    workflows.c.state,
)


workflow_bindings = Table(
    "wf_workflow_bindings",
    metadata,
    Column("workflow_id", String(255), primary_key=True),
    *_scope_columns(),
    Column("partner_client_id", String(255), nullable=False),
    Column("external_user_id", String(255), nullable=False),
    Column("external_ticket_id", String(255), nullable=True),
    Column("external_conversation_id", String(255), nullable=False),
    Column("residence_id", String(255), nullable=True),
    Column("conversation_id", String(255), nullable=False),
    Column("group_id", String(255), nullable=False),
    Column("route_id", String(255), nullable=False),
    Column("route_revision", Integer, nullable=False),
    Column("status", String(32), nullable=False, default="active"),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "tenant_id",
        "partner_client_id",
        "external_user_id",
        "external_conversation_id",
        name="uq_wf_binding_external_conversation",
    ),
    UniqueConstraint(
        "tenant_id",
        "partner_client_id",
        "external_user_id",
        "external_ticket_id",
        name="uq_wf_binding_external_ticket",
    ),
    UniqueConstraint(
        "conversation_id", name="uq_wf_binding_conversation"
    ),
    UniqueConstraint("group_id", name="uq_wf_binding_group"),
)
Index(
    "ix_wf_binding_owner",
    workflow_bindings.c.tenant_id,
    workflow_bindings.c.domain_id,
    workflow_bindings.c.area_id,
    workflow_bindings.c.manager_account_id,
)


workflow_inputs = Table(
    "wf_workflow_inputs",
    metadata,
    Column("id", String(255), primary_key=True),
    Column("workflow_id", String(255), nullable=False),
    Column("cause_kind", String(64), nullable=False),
    Column("cause_id", String(255), nullable=False),
    Column("text", Text, nullable=False),
    Column("payload_hash", String(64), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "workflow_id",
        "cause_kind",
        "cause_id",
        name="uq_wf_workflow_input_cause",
    ),
)
Index("ix_wf_workflow_input_workflow", workflow_inputs.c.workflow_id)


workflow_checkpoints = Table(
    "wf_workflow_checkpoints",
    metadata,
    Column("id", String(255), primary_key=True),
    *_scope_columns(),
    Column("workflow_id", String(255), nullable=False),
    Column("state_revision", Integer, nullable=False),
    Column("payload_hash", String(64), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "workflow_id",
        "state_revision",
        name="uq_wf_checkpoint_workflow_revision",
    ),
)
Index(
    "ix_wf_checkpoint_owner_workflow",
    workflow_checkpoints.c.tenant_id,
    workflow_checkpoints.c.domain_id,
    workflow_checkpoints.c.area_id,
    workflow_checkpoints.c.manager_account_id,
    workflow_checkpoints.c.workflow_id,
)


partner_commands = Table(
    "wf_partner_commands",
    metadata,
    Column("id", String(255), primary_key=True),
    Column("tenant_id", String(255), nullable=False),
    Column("partner_client_id", String(255), nullable=False),
    Column("external_user_id", String(255), nullable=False),
    Column("external_request_id", String(255), nullable=False),
    Column("command_kind", String(100), nullable=False),
    Column("target_ref", String(255), nullable=True),
    Column("payload_hash", String(200), nullable=False),
    Column("status", String(32), nullable=False),
    Column("result", JSON, nullable=True),
    Column("error", JSON, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    UniqueConstraint(
        "tenant_id",
        "partner_client_id",
        "external_request_id",
        name="uq_wf_partner_command_request",
    ),
)
Index(
    "ix_wf_partner_command_user",
    partner_commands.c.tenant_id,
    partner_commands.c.partner_client_id,
    partner_commands.c.external_user_id,
)


partner_requests = Table(
    "wf_partner_requests",
    metadata,
    Column("id", String(255), primary_key=True),
    *_scope_columns(),
    Column("partner_client_id", String(255), nullable=False),
    Column("external_user_id", String(255), nullable=False),
    Column("workflow_id", String(255), nullable=False),
    Column("conversation_id", String(255), nullable=False),
    Column("status", String(32), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("accepted_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
)
Index(
    "ix_wf_partner_request_audience",
    partner_requests.c.partner_client_id,
    partner_requests.c.external_user_id,
    partner_requests.c.workflow_id,
)


public_events = Table(
    "wf_public_events",
    metadata,
    Column("id", String(255), primary_key=True),
    *_scope_columns(),
    Column("conversation_id", String(255), nullable=False),
    Column("workflow_id", String(255), nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("event_type", String(128), nullable=False),
    Column("causation_id", String(255), nullable=True),
    Column("payload", JSON, nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "conversation_id",
        "sequence",
        name="uq_wf_public_event_sequence",
    ),
)
Index(
    "ix_wf_public_event_replay",
    public_events.c.conversation_id,
    public_events.c.sequence,
)


__all__ = [
    "metadata",
    "partner_commands",
    "partner_requests",
    "public_events",
    "workflow_bindings",
    "workflow_checkpoints",
    "workflow_inputs",
    "workflows",
]
