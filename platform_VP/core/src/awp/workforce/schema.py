"""Workforce control state. Public events commit with their aggregate changes."""
from sqlalchemy import (
    JSON,
    Column,
    Float,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)

from ..db import metadata


def table(name, *columns, unique=()):
    return Table("awp_wf_" + name, metadata, *columns,
                 *[UniqueConstraint(*keys, name=f"uq_wf_{name}_{i}") for i, keys in enumerate(unique)])


def ident(name="id", primary=False):
    return Column(name, String(200), primary_key=primary, nullable=False)


clients = table("clients", ident(primary=True), ident("tenant"), ident("purpose"),
                ident("key_hash"), ident("status"), Column("expires", Float),
                Column("operations", JSON, nullable=False), Column("settings", JSON, nullable=False))
routes = table("routes", ident(primary=True), ident("client_id"), ident("external_ref"),
               ident("status"), Column("revision", Integer, nullable=False),
               Column("config", JSON, nullable=False), unique=[("client_id", "external_ref")])
residences = table("residences", ident("client_id", True), ident("residence_id", True),
                   ident("user_id", True), ident("route_id"), ident("status"),
                   Column("revision", Integer, nullable=False), Column("updated", Float, nullable=False))
conversations = table("conversations", ident(primary=True), ident("client_id"), ident("route_id"),
                      ident("user_id"), ident("external_ticket_id"), ident("external_conversation_id"),
                      Column("sequence", Integer, nullable=False, default=0),
                      Column("purged_through", Integer, nullable=False, default=0),
                      Column("latest_event_id", String(200)),
                      unique=[("client_id", "external_conversation_id"), ("client_id", "external_ticket_id")])
workflows = table("workflows", ident(primary=True), ident("conversation_id"), ident("state"),
                  Column("revision", Integer, nullable=False), Column("snapshot", JSON, nullable=False),
                  Column("case_id", String(200), unique=True), Column("closed_at", Float),
                  Column("created", Float, nullable=False), Column("updated", Float, nullable=False))
requests = table("requests", ident(primary=True), ident("client_id"), ident("external_id"),
                 ident("payload_hash"), ident("command"), ident("workflow_id"), ident("status"),
                 Column("body", JSON, nullable=False), Column("result", JSON), Column("error", JSON),
                 Column("created", Float, nullable=False), Column("completed", Float),
                 unique=[("client_id", "external_id")])
jobs = table("jobs", ident(primary=True), ident("workflow_id"), ident("request_id"), ident("kind"),
             ident("status"), Column("payload", JSON, nullable=False), Column("owner", String(200)),
             Column("lease_until", Float, nullable=False, default=0),
             Column("generation", Integer, nullable=False, default=0),
             Column("attempts", Integer, nullable=False, default=0), Column("available", Float, nullable=False))
events = table("events", ident(primary=True), ident("conversation_id"), ident("workflow_id"),
               Column("sequence", Integer, nullable=False), ident("event_type"),
               Column("payload", JSON, nullable=False), Column("occurred", Float, nullable=False),
               Column("recorded", Float, nullable=False), unique=[("conversation_id", "sequence")])
messages = table("messages", ident(primary=True), ident("conversation_id"), ident("workflow_id"),
                 Column("sequence", Integer, nullable=False), Column("payload", JSON, nullable=False))
operations = table("operations", ident(primary=True), ident("workflow_id"), ident("integration_id"),
                   ident("client_reference"), Column("external_job_id", String(200)), ident("status"),
                   Column("provider_version", Integer, nullable=False, default=0),
                   Column("data", JSON, nullable=False), Column("created", Float, nullable=False),
                   unique=[("integration_id", "client_reference"), ("integration_id", "external_job_id")])
approvals = table("approvals", ident(primary=True), ident("workflow_id"), ident("operation_id"),
                  ident("status"), ident("arguments_hash"), ident("quote_ref"),
                  Column("revision", Integer, nullable=False), Column("expires", Float, nullable=False),
                  Column("summary", String(4000), nullable=False))
receipts = table("receipts", ident(primary=True), ident("integration_id"), ident("external_id"),
                 ident("payload_hash"), ident("status"), Column("body", JSON, nullable=False),
                 Column("policy", JSON, nullable=False),
                 Column("received", Float, nullable=False), Column("applied", Float), Column("error", JSON),
                 unique=[("integration_id", "external_id")])
assets = table("assets", ident(primary=True), ident("client_id"), ident("route_id"), ident("user_id"),
               ident("external_ticket_id"), ident("external_conversation_id"), ident("object_key"),
               ident("status"), Column("workflow_id", String(200)), Column("metadata", JSON, nullable=False),
               Column("created", Float, nullable=False), Column("expires", Float, nullable=False))
reservations = table("reservations", ident(primary=True), ident("workflow_id"), ident("status"),
                     Column("micros", Integer, nullable=False), Column("tokens", Integer, nullable=False),
                     Column("actual_micros", Integer), Column("actual_tokens", Integer),
                     Column("created", Float, nullable=False))
versions = table("schema_versions", ident(primary=True), ident("checksum"), Column("applied", Float, nullable=False))
integrations = table("integrations", ident(primary=True), ident("tenant"), ident("status"),
                     Column("revision", Integer, nullable=False), Column("config", JSON, nullable=False))
rate_limits = table("rate_limits", ident(primary=True), Column("window", Integer, nullable=False),
                    Column("count", Integer, nullable=False))
audit = table("audit", ident(primary=True), ident("tenant"), ident("actor"), ident("action"),
              ident("resource"), Column("data", JSON, nullable=False), Column("created", Float, nullable=False))
knowledge = table("knowledge", ident(primary=True), ident("tenant"), ident("knowledge_base_id"),
                  ident("document_key"), Column("version", Integer, nullable=False), ident("status"),
                  ident("sha256"), Column("title", String(300), nullable=False), Column("text", Text, nullable=False),
                  Column("source", String(2000), nullable=False), Column("created", Float, nullable=False),
                  unique=[("tenant", "knowledge_base_id", "document_key", "version")])
memory = table("memory", ident("workflow_id", True), ident("profile_key", True), ident("key", True),
               Column("text", String(8000), nullable=False), Column("updated", Float, nullable=False))
session_fences = table("session_fences", ident(primary=True), ident("job_id"), ident("owner"),
                       Column("generation", Integer, nullable=False), ident("role"))
Index("ix_wf_jobs_claim", jobs.c.status, jobs.c.available, jobs.c.lease_until)
Index("ix_wf_jobs_workflow", jobs.c.workflow_id, jobs.c.status)
Index("ix_wf_workflows_conversation", workflows.c.conversation_id)
Index("ix_wf_requests_workflow", requests.c.workflow_id, requests.c.status)
Index("ix_wf_operations_workflow", operations.c.workflow_id, operations.c.status)
Index("ix_wf_events_retention", events.c.workflow_id, events.c.recorded)
Index("ix_wf_messages_conversation", messages.c.conversation_id, messages.c.sequence)
Index("ix_wf_knowledge_scope", knowledge.c.tenant, knowledge.c.knowledge_base_id, knowledge.c.status)
