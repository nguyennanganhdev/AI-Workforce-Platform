"""Workforce v1 tables (spec section 4), on the same metadata as `awp.db`.

All of them exist from the first slice so later slices only add logic.
Times are epoch floats, like the rest of the core.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Float,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
    true,
)

from ..db import metadata


def new_id(prefix: str) -> str:
    """Platform ids: a short prefix and a uuid4 (`req_`, `wf_`, `route_`, ...)."""
    return f"{prefix}_{uuid.uuid4().hex}"


ID = String(48)
EXT = String(200)  # ids the partner chooses

_f = lambda name: Column(name, Float, nullable=False)  # noqa: E731

EVAL_ENV = "eval"  # the environment of a tenant's internal evaluation sandbox client (evals/sandbox.py): no API makes one

clients = Table(
    "wf_clients", metadata,
    Column("id", ID, primary_key=True),
    Column("tenant", String(80), nullable=False, index=True),
    Column("domain", String(80), nullable=False),
    Column("environment", String(16), nullable=False),
    Column("name", String(120), nullable=False),
    Column("status", String(12), nullable=False, default="active"),
    Column("capabilities", JSON, nullable=False, default=list),
    _f("created_at"),
)

integrations = Table(
    "wf_integrations", metadata,
    Column("id", ID, primary_key=True),
    Column("client_id", ID, nullable=False, index=True),
    Column("status", String(12), nullable=False, default="active"),
    Column("event_schema", JSON, nullable=False),
    _f("created_at"),
)

keys = Table(
    "wf_keys", metadata,
    Column("key_id", String(64), primary_key=True),
    Column("client_id", ID, index=True),
    Column("integration_id", ID, index=True),
    Column("kind", String(12), nullable=False),  # customer | provider
    Column("secret_hash", String(64), nullable=False),  # sha256 hex; the secret is never stored
    Column("operations", JSON, nullable=False),
    Column("routes", JSON, nullable=False),  # ["*"] or route ids
    Column("status", String(12), nullable=False, default="active"),  # active | revoked
    Column("expires_at", Float),
    _f("created_at"),
    Column("revoked_at", Float),
    CheckConstraint(
        "(kind = 'customer' AND client_id IS NOT NULL AND integration_id IS NULL) OR "
        "(kind = 'provider' AND integration_id IS NOT NULL AND client_id IS NULL)",
        name="ck_key_owner"),
)

signing_keys = Table(
    "wf_signing_keys", metadata,
    Column("key_id", String(64), primary_key=True),
    Column("integration_id", ID, nullable=False, index=True),
    Column("secret_enc", Text, nullable=False),  # Fernet token (A7)
    Column("status", String(12), nullable=False, default="active"),
    _f("created_at"),
)

routes = Table(
    "wf_routes", metadata,
    Column("id", ID, primary_key=True),
    Column("client_id", ID, nullable=False, index=True),
    Column("external_management_ref", String(128), nullable=False),
    Column("status", String(12), nullable=False, default="pending"),  # pending|active|suspended|replaced
    Column("revision", Integer, nullable=False, default=1),
    Column("leader_profile", String(80), nullable=False),
    Column("config", JSON, nullable=False, default=dict),
    # The management account the route belongs to (M6). Required for a route made through the API; null only on rows
    # older than managers, which no manager key can reach.
    Column("manager_id", ID, index=True),
    _f("created_at"),
    Index("uq_route_active_ref", "client_id", "external_management_ref", unique=True,
          sqlite_where=text("status = 'active'"), postgresql_where=text("status = 'active'")),
)

# A management account of a client (M6): several may share one client; each route, and so each
# external_management_ref, belongs to exactly one of them.
managers = Table(
    "wf_managers", metadata,
    Column("id", ID, primary_key=True),
    Column("tenant", String(80), nullable=False, index=True),
    Column("client_id", ID, nullable=False, index=True),
    Column("name", String(120), nullable=False),
    Column("status", String(12), nullable=False, default="active"),  # active | disabled
    _f("created_at"),
)

# Operator keys of a manager (`Bearer mk_<id>.<secret>`), stored hashed like a partner's key. A table of their own:
# they never authenticate on /workforce, and a partner key never on the admin API.
manager_keys = Table(
    "wf_manager_keys", metadata,
    Column("key_id", String(64), primary_key=True),
    Column("manager_id", ID, nullable=False, index=True),
    Column("secret_hash", String(64), nullable=False),
    Column("status", String(12), nullable=False, default="active"),  # active | revoked
    Column("expires_at", Float),
    _f("created_at"),
    Column("revoked_at", Float),
)

mcp_servers = Table(
    "wf_mcp_servers", metadata,
    Column("route_id", ID, primary_key=True),
    Column("name", String(80), primary_key=True),
    Column("url", Text, nullable=False),
    Column("transport", String(24), nullable=False, default="streamable_http"),
    Column("headers_enc", Text),  # Fernet token
    Column("timeout", Float, nullable=False, default=8.0),
    # Off: none of its tools reaches an agent (the rows stay). A server added to the tool store starts off until it is
    # enabled, which reads its tool list; one declared with the whole-set PUT is on, as before. The API always says
    # which; the database's own default (on) is for rows older than the store.
    Column("enabled", Boolean, nullable=False, server_default=true()),
    Column("last_discovered_at", Float),
    Column("last_error", String(300)),  # why the last discovery failed, in the platform's words (never the partner's)
    # Goes up with every change a person or a discovery makes to the row. A discovery reads the row, waits for the
    # partner's list, and only writes when the row is still the one it read.
    Column("revision", Integer, nullable=False, default=0, server_default="0"),
)

tools = Table(
    "wf_tools", metadata,
    Column("route_id", ID, primary_key=True),
    Column("name", String(80), primary_key=True),  # the name the model sees
    Column("server", String(80), nullable=False),
    Column("mcp_tool", String(120), nullable=False),
    Column("kind", String(12), nullable=False),  # lookup | action
    Column("read_only", Boolean, nullable=False, default=False),
    Column("requires_consent", Boolean, nullable=False, default=False),
    Column("tracking", String(16), nullable=False, default="none"),  # none | events | status_query
    Column("client_reference_arg", String(80)),
    Column("idempotency_arg", String(80)),
    Column("consent_summary", Text),
    Column("call_timeout", Float, nullable=False, default=8.0),
    Column("description_override", Text),
    # The MCP tool (same server) that answers "what became of client_reference X"; tracking=status_query only.
    Column("status_tool", String(120)),
    # The provider integration whose events follow this tool's operations (T2): events of another integration
    # never match them. Null: any integration of the same client.
    Column("integration_id", ID),
    # The tool store (M1). manual: an admin typed it; discovered: read from the server's tools/list.
    Column("source", String(12), nullable=False, default="manual", server_default="manual"),
    # proposed: seen, not usable until a person activates it; active; gone: the server no longer offers it.
    Column("status", String(12), nullable=False, default="active", server_default="active"),
    # The tool as the server described it at the last discovery (input schema, cleaned description, read-only hint):
    # what an agent is given when the server cannot be listed, so a restart with the partner down loses no tool.
    Column("schema", JSON),
    Column("discovered_at", Float),
    # Why this action runs without the resident's consent (M5): required to turn requires_consent off, kept as said.
    Column("consent_waiver", String(300)),
)

residences = Table(
    "wf_residences", metadata,
    Column("client_id", ID, primary_key=True),
    Column("residence_id", EXT, primary_key=True),
    Column("external_user_id", EXT, primary_key=True),
    Column("route_id", ID, nullable=False),
    Column("status", String(12), nullable=False),
    Column("revision", Integer, nullable=False, default=1),
    _f("updated_at"),
)

conversations = Table(
    "wf_conversations", metadata,
    Column("id", ID, primary_key=True),
    Column("client_id", ID, nullable=False),
    Column("route_id", ID, nullable=False),
    Column("external_user_id", EXT, nullable=False),
    Column("external_conversation_id", EXT, nullable=False),
    Column("external_ticket_id", EXT),
    Column("last_sequence", Integer, nullable=False, default=0),
    Column("purged_through", Integer, nullable=False, default=0),
    _f("created_at"),
    UniqueConstraint("client_id", "external_conversation_id", name="uq_conv_external"),
)

workflows = Table(
    "wf_workflows", metadata,
    Column("id", ID, primary_key=True),
    Column("conversation_id", ID, nullable=False, index=True),
    Column("client_id", ID, nullable=False),
    Column("route_id", ID, nullable=False),
    Column("case_id", String(40), index=True),
    Column("external_user_id", EXT, nullable=False),
    Column("external_ticket_id", EXT),
    Column("ticket_id", ID),
    Column("state", String(32), nullable=False, default="accepted", index=True),
    Column("revision", Integer, nullable=False, default=1),
    Column("expects", String(16)),  # reply | confirmation | null
    Column("current_request_id", ID),
    Column("close_reason", String(200)),  # the partner's own reason text (contract: an id-like string of up to 200)
    Column("attention_reason", String(40)),
    Column("last_activity_at", Float),
    _f("created_at"),
    Column("closed_at", Float),
    UniqueConstraint("client_id", "external_ticket_id", name="uq_workflow_ticket"),
)

requests = Table(
    "wf_requests", metadata,
    Column("id", ID, primary_key=True),
    Column("client_id", ID, nullable=False),
    Column("external_request_id", EXT, nullable=False),
    Column("command_type", String(24), nullable=False),
    Column("fingerprint", String(80), nullable=False),
    Column("route_id", ID),
    Column("conversation_id", ID),
    Column("workflow_id", ID, index=True),
    Column("status", String(12), nullable=False, default="accepted"),
    Column("response", JSON),  # the frozen result once completed
    Column("error", JSON),
    _f("accepted_at"),
    Column("completed_at", Float),
    UniqueConstraint("client_id", "external_request_id", name="uq_request_external"),
)

messages = Table(
    "wf_messages", metadata,
    Column("id", ID, primary_key=True),
    Column("conversation_id", ID, nullable=False),
    Column("workflow_id", ID, nullable=False),
    Column("request_id", ID, index=True),
    Column("sender", String(12), nullable=False),  # user | assistant | system
    Column("text", Text, nullable=False),
    Column("asset_ids", JSON, nullable=False, default=list),
    # What the leader said (CaseSay, CaseFinalize) and what it expects next, written with the message so
    # settle reads them from facts: none | reply | confirmation; null for text no leader chose (safe reply).
    Column("expects", String(16)),
    Column("outcome", String(16)),  # resolved | needs_human | cannot_resolve, on a CaseFinalize answer
    # Who wrote the words when it was not the leader: "provider" = a template of an event schema filled with a provider's
    # values (the leader's own context shows it as a quotation, not as something it said). Public output is unchanged.
    Column("source", String(12)),
    # The sequence of the event written with the message: a total order that survives equal clock ticks.
    Column("sequence", Integer, nullable=False),
    _f("created_at"),
    UniqueConstraint("conversation_id", "sequence", name="uq_msg_sequence"),
)

events = Table(
    "wf_events", metadata,
    Column("event_id", ID, primary_key=True),
    Column("conversation_id", ID, nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("event_type", String(48), nullable=False),
    Column("workflow_id", ID),
    Column("ticket_id", ID),
    Column("external_ticket_id", EXT),
    Column("payload", JSON, nullable=False, default=dict),
    _f("occurred_at"),
    _f("recorded_at"),
    UniqueConstraint("conversation_id", "sequence", name="uq_event_sequence"),
)

event_tombstones = Table(
    "wf_event_tombstones", metadata,
    Column("event_id", ID, primary_key=True),
    Column("conversation_id", ID, nullable=False, index=True),
    Column("sequence", Integer, nullable=False),
)

turns = Table(
    "wf_turns", metadata,
    Column("id", ID, primary_key=True),
    Column("workflow_id", ID, nullable=False, index=True),
    Column("job_id", ID),  # null for a turn a worker's report woke (13.12)
    Column("trigger", String(12)),  # message | continue
    Column("msg_id", String(80)),
    Column("status", String(12), nullable=False, default="running"),
    _f("started_at"),
    Column("ended_at", Float),
)

jobs = Table(
    "wf_jobs", metadata,
    Column("id", ID, primary_key=True),
    Column("workflow_id", ID, nullable=False),
    Column("kind", String(24), nullable=False),
    Column("request_id", ID),
    Column("payload", JSON, nullable=False, default=dict),
    Column("status", String(12), nullable=False, default="queued"),
    Column("lease_owner", String(80)),
    Column("lease_until", Float),
    Column("attempts", Integer, nullable=False, default=0),
    _f("created_at"),
    Index("ix_job_queue", "status", "created_at"),
    # one running job per workflow (spec 9)
    Index("uq_job_dispatched", "workflow_id", unique=True,
          sqlite_where=text("status = 'dispatched'"), postgresql_where=text("status = 'dispatched'")),
)

approvals = Table(
    "wf_approvals", metadata,
    Column("id", ID, primary_key=True),
    Column("workflow_id", ID, nullable=False, index=True),
    Column("conversation_id", ID, nullable=False),
    Column("client_id", ID, nullable=False),
    Column("external_user_id", EXT, nullable=False),
    Column("session_id", String(60), nullable=False),
    Column("agent_id", String(60), nullable=False),
    Column("tool_call_id", String(120), nullable=False),
    Column("tool_name", String(80), nullable=False),
    Column("arguments", Text, nullable=False),  # canonical JSON
    Column("arguments_hash", String(80), nullable=False),
    Column("quote_ref", String(80)),
    Column("summary", JSON, nullable=False, default=dict),
    Column("status", String(12), nullable=False, default="pending"),
    Column("workflow_revision", Integer, nullable=False),
    Column("expires_at", Float),
    Column("decided_at", Float),
    Column("decision_request_id", ID),
    # What the engine needs to wake the agent that asked: the parked reply (S4). `resumed_at` is the engine's
    # acknowledgement that the agent took the resume event; `used_at` that its tool call passed the gate once.
    Column("reply_id", String(80)),
    Column("resumed_at", Float),
    Column("used_at", Float),
    # The one operation whose provider evidence a cost consent cites (what it prices), when there is exactly one: an event
    # that ends that work or quotes it again withdraws the consent while it is pending (provider_effects.py).
    Column("operation_id", ID),
    _f("created_at"),
    UniqueConstraint("session_id", "reply_id", "tool_call_id", name="uq_approval_call"),
)

operations = Table(
    "wf_operations", metadata,
    Column("id", ID, primary_key=True),
    Column("workflow_id", ID, nullable=False, index=True),
    Column("route_id", ID, nullable=False),
    Column("integration_id", ID),
    Column("tool_name", String(80), nullable=False),
    Column("tool_call_id", String(120)),
    Column("args_hash", String(80), nullable=False),
    Column("client_reference", String(120), nullable=False),
    Column("external_job_id", EXT),
    Column("status", String(12), nullable=False, default="intent"),
    Column("normalized_status", String(40)),
    Column("last_rank", Integer),
    Column("provider_version", String(80)),
    Column("result", JSON),
    # What the model sent (its own arguments): a crash leaves an intent that is sent again from here.
    Column("arguments", JSON),
    # The process that holds the live call (nodes.py): while it lives, no other process takes the row for a leftover.
    Column("node", String(40)),
    _f("created_at"),
    _f("updated_at"),
    UniqueConstraint("client_reference", name="uq_operation_reference"),
    UniqueConstraint("workflow_id", "tool_name", "args_hash", name="uq_operation_dedupe"),
    Index("ix_operation_job", "integration_id", "external_job_id"),
)

provider_inbox = Table(
    "wf_provider_inbox", metadata,
    Column("receipt_id", ID, primary_key=True),
    Column("integration_id", ID, nullable=False),
    Column("external_event_id", EXT, nullable=False),
    Column("key_id", String(64)),  # the provider API key that sent it: its route scope limits which operations it may reach
    Column("sig_key_id", String(64)),  # the signing key it was signed with: a key revoked since no longer speaks for its provider
    Column("payload_hash", String(80), nullable=False),
    Column("event_type", String(64), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("operation_id", ID, index=True),
    Column("workflow_id", ID),
    # accepted (queued) | processing (a delta event held for its predecessor) | applied | duplicate | quarantined |
    # rejected | needs_attention
    Column("ingestion_status", String(16), nullable=False),
    Column("normalized_status", String(40)),
    Column("error", JSON),
    Column("provider_version", String(80)),
    # Why an event that was stored changed nothing: after_close | route_blocked (applied, audit only).
    Column("note", String(40)),
    _f("received_at"),
    Column("applied_at", Float),
    Column("checked_at", Float),  # when the sweep last tried to match a quarantined event (it looks less often as it ages)
    UniqueConstraint("integration_id", "external_event_id", name="uq_inbox_event"),
    Index("ix_inbox_pending", "ingestion_status", "received_at"),
)

# One row per scheduled job that exactly one process of a fleet may run (workforce/lease.py).
leases = Table(
    "wf_leases", metadata,
    Column("name", String(80), primary_key=True),
    Column("owner", String(80)),
    Column("lease_until", Float, nullable=False, default=0.0),
    Column("last_run_at", Float),
)

assets = Table(
    "wf_assets", metadata,
    Column("id", ID, primary_key=True),
    Column("client_id", ID, nullable=False),
    Column("conversation_id", ID),
    Column("object_key", Text, nullable=False),
    Column("content_type", String(64), nullable=False),
    Column("size", Integer, nullable=False),
    Column("sha256", String(64), nullable=False),
    _f("created_at"),
)
