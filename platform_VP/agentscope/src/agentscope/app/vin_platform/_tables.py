"""SQL authority; separate from Redis session/resource serialization."""

import sqlalchemy as sa

metadata = sa.MetaData()


def table(name, *columns, constraints=()):
    return sa.Table("vin_" + name, metadata, *columns, *constraints)


def string(name, length=255, **kw):
    return sa.Column(name, sa.String(length), **kw)


accounts = table("accounts", string("user_id", primary_key=True), string("tenant_id", nullable=False),
    sa.Column("eligible", sa.Boolean, nullable=False), sa.Column("revision", sa.Integer, nullable=False))
memberships = table("memberships", string("id", primary_key=True), string("tenant_id", nullable=False),
    string("user_id", nullable=False), string("group_id", nullable=False), string("domain_id"), string("area_id"),
    sa.Column("active", sa.Boolean, nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True)))
catalog = table("catalog", string("id", primary_key=True), string("tenant_id", nullable=False),
    string("kind", nullable=False), string("resource_id", nullable=False), string("owner_id", nullable=False),
    sa.Column("version", sa.Integer, nullable=False), sa.Column("data", sa.JSON, nullable=False),
    sa.Column("active", sa.Boolean, nullable=False),
    constraints=(sa.UniqueConstraint("tenant_id", "kind", "resource_id", name="uq_vin_catalog_resource"),))
grants = table("grants", string("id", primary_key=True), string("tenant_id", nullable=False),
    string("catalog_id", nullable=False), string("subject_kind", nullable=False), string("subject_id", nullable=False),
    sa.Column("permissions", sa.JSON, nullable=False), sa.Column("active", sa.Boolean, nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True)))
policies = table("quota_policies", string("tenant_id", primary_key=True), string("subject", primary_key=True),
    sa.Column("data", sa.JSON, nullable=False), sa.Column("revision", sa.Integer, nullable=False))
subjects = table("subject_usage", string("tenant_id", primary_key=True), string("subject", primary_key=True),
    sa.Column("active_calls", sa.Integer, nullable=False), sa.Column("stored_bytes", sa.BigInteger, nullable=False),
    sa.Column("reserved_bytes", sa.BigInteger, nullable=False))
buckets = table("usage_buckets", string("tenant_id", primary_key=True), string("subject", primary_key=True),
    string("window", primary_key=True), sa.Column("used", sa.BigInteger, nullable=False),
    sa.Column("reserved", sa.BigInteger, nullable=False))
attempts = table("attempts", string("id", primary_key=True), string("tenant_id", nullable=False),
    string("user_id", nullable=False), string("state", nullable=False), string("purpose", nullable=False),
    sa.Column("budget", sa.BigInteger, nullable=False), sa.Column("actual", sa.BigInteger),
    sa.Column("scopes", sa.JSON, nullable=False), sa.Column("data", sa.JSON, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
secrets = table("secrets", string("id", primary_key=True), string("tenant_id", nullable=False),
    string("purpose", nullable=False), sa.Column("ciphertext", sa.Text, nullable=False),
    sa.Column("active", sa.Boolean, nullable=False))
providers = table("domain_providers", string("tenant_id", primary_key=True), string("id", primary_key=True),
    sa.Column("data", sa.JSON, nullable=False))
link_transactions = table("link_transactions", string("id", primary_key=True), string("tenant_id", nullable=False),
    string("user_id", nullable=False), string("provider_id", nullable=False), string("state_hash", 64, nullable=False),
    sa.Column("verifier", sa.Text, nullable=False), string("status", nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
links = table("domain_links", string("id", primary_key=True), string("tenant_id", nullable=False),
    string("user_id", nullable=False), string("provider_id", nullable=False), string("issuer", nullable=False),
    string("subject", nullable=False), string("status", nullable=False), string("secret_ref", nullable=False),
    sa.Column("scopes", sa.JSON, nullable=False), sa.Column("revision", sa.Integer, nullable=False),
    sa.Column("data", sa.JSON, nullable=False),
    constraints=(sa.UniqueConstraint("tenant_id", "provider_id", "issuer", "subject", name="uq_vin_link_subject"),))
cases = table("cases", string("id", primary_key=True), string("tenant_id", nullable=False),
    string("user_id", nullable=False), string("link_id", nullable=False), string("idempotency_key", 128, nullable=False),
    string("payload_hash", 64, nullable=False), string("state", nullable=False),
    sa.Column("data", sa.JSON, nullable=False), sa.Column("revision", sa.Integer, nullable=False),
    constraints=(sa.UniqueConstraint("tenant_id", "user_id", "idempotency_key", name="uq_vin_case_idempotency"),))
events = table("case_events", string("tenant_id", primary_key=True), string("case_id", primary_key=True),
    sa.Column("sequence", sa.Integer, primary_key=True), string("event_id", nullable=False),
    string("audience", nullable=False), sa.Column("data", sa.JSON, nullable=False),
    constraints=(sa.UniqueConstraint("tenant_id", "event_id", name="uq_vin_case_event"),))
commands = table("commands", string("id", primary_key=True), string("tenant_id", nullable=False),
    string("user_id", nullable=False), string("case_id", nullable=False), string("idempotency_key", 128, nullable=False),
    string("payload_hash", 64, nullable=False), string("state", nullable=False),
    sa.Column("data", sa.JSON, nullable=False),
    constraints=(sa.UniqueConstraint("tenant_id", "user_id", "case_id", "idempotency_key", name="uq_vin_command_key"),))
automation = table("automation", string("id", primary_key=True), string("tenant_id", nullable=False),
    string("user_id", nullable=False), string("kind", nullable=False), sa.Column("data", sa.JSON, nullable=False),
    sa.Column("revision", sa.Integer, nullable=False), string("claim_token"),
    sa.Column("lease_until", sa.DateTime(timezone=True)))
audit = table("audit", string("id", primary_key=True), string("tenant_id", nullable=False),
    string("actor_id", nullable=False), string("action", nullable=False), string("resource_id", nullable=False),
    sa.Column("data", sa.JSON, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))

for name, columns in [("catalog_tenant", (catalog.c.tenant_id, catalog.c.kind)),
                      ("grants_subject", (grants.c.tenant_id, grants.c.subject_kind, grants.c.subject_id)),
                      ("memberships_user", (memberships.c.tenant_id, memberships.c.user_id)),
                      ("attempts_owner", (attempts.c.tenant_id, attempts.c.user_id, attempts.c.state)),
                      ("cases_owner", (cases.c.tenant_id, cases.c.user_id)),
                      ("automation_owner", (automation.c.tenant_id, automation.c.user_id, automation.c.kind))]:
    sa.Index("ix_vin_" + name, *columns)
