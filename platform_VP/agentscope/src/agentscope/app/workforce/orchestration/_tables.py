"""Orchestration-owned SQLAlchemy metadata. Foundation owns Alembic revisions.

The repository persists internal aggregates as JSON, plus indexed identity,
scope and revisions. PostgreSQL gets JSONB; SQLite is only a test dialect.
"""

from sqlalchemy import Column, ForeignKeyConstraint, Integer, JSON, MetaData, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()
SCOPE_COLUMNS = ("tenant_id", "domain_id", "area_id", "manager_account_id")


def _scope_columns():
    return [Column(name, String(128), nullable=False) for name in SCOPE_COLUMNS]


conversations = Table(
    "wf_conversations", metadata,
    Column("conversation_id", String(36), primary_key=True), *_scope_columns(),
    Column("revision", Integer, nullable=False),
    Column("payload", JSON().with_variant(JSONB(), "postgresql"), nullable=False),
    UniqueConstraint("conversation_id", *SCOPE_COLUMNS),
)
runs = Table(
    "wf_runs", metadata,
    Column("run_id", String(36), primary_key=True), *_scope_columns(),
    Column("conversation_id", String(36), nullable=False),
    Column("group_id", String(36), nullable=False, unique=True),
    Column("revision", Integer, nullable=False),
    Column("payload", JSON().with_variant(JSONB(), "postgresql"), nullable=False),
    ForeignKeyConstraint(["conversation_id", *SCOPE_COLUMNS],
                         [f"wf_conversations.{name}" for name in ("conversation_id", *SCOPE_COLUMNS)]),
)
workflows = Table(
    "wf_workflows", metadata,
    Column("workflow_id", String(36), primary_key=True), *_scope_columns(),
    Column("conversation_id", String(36), nullable=False, unique=True),
    Column("group_id", String(36), nullable=False, unique=True),
    Column("partner_client_id", String(128), nullable=False),
    Column("external_user_id", String(128), nullable=False),
    Column("external_ticket_id", String(128), nullable=False),
    Column("external_conversation_id", String(128), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("payload", JSON().with_variant(JSONB(), "postgresql"), nullable=False),
    UniqueConstraint("tenant_id", "partner_client_id", "external_user_id", "external_ticket_id"),
    UniqueConstraint("tenant_id", "partner_client_id", "external_user_id", "external_conversation_id"),
    UniqueConstraint("workflow_id", *SCOPE_COLUMNS),
    ForeignKeyConstraint(["conversation_id", *SCOPE_COLUMNS],
                         [f"wf_conversations.{name}" for name in ("conversation_id", *SCOPE_COLUMNS)]),
)
commands = Table(
    "wf_inbound_requests", metadata,
    Column("request_id", String(36), primary_key=True), *_scope_columns(),
    Column("partner_client_id", String(128), nullable=False),
    Column("external_request_id", String(128), nullable=False),
    Column("workflow_id", String(36), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("payload", JSON().with_variant(JSONB(), "postgresql"), nullable=False),
    UniqueConstraint("tenant_id", "partner_client_id", "external_request_id"),
    ForeignKeyConstraint(["workflow_id", *SCOPE_COLUMNS],
                         [f"wf_workflows.{name}" for name in ("workflow_id", *SCOPE_COLUMNS)]),
)
