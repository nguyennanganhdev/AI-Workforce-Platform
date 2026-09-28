/** Physical model for platform/agents. See docs/erd/README.md. */
import { sql } from "drizzle-orm";
import {
  check,
  foreignKey,
  index,
  integer,
  pgPolicy,
  pgTable,
  text,
  timestamp,
  unique,
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, jsonb, mutableColumns } from "../columns";
import { platformTenant, users } from "./identity";

export const platformAgent = pgTable(
  "platform_agent",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    name: text("name").notNull(),
    slug: text("slug").notNull(),
    description: text("description"),
    ownerType: text("owner_type", {
      enum: ["USER", "TEAM", "SYSTEM"],
    }).notNull(),
    ownerId: text("owner_id").notNull(),
    domainNamespace: text("domain_namespace"),
    status: text("status", {
      enum: ["ACTIVE", "SUSPENDED", "RETIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_agent_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_agent_uq_0").on(t.tenantId, t.slug),
    unique("platform_agent_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_agent_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    allowedValues("platform_agent_owner_type_ck", t.ownerType, [
      "USER",
      "TEAM",
      "SYSTEM",
    ]),
    allowedValues("platform_agent_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "RETIRED",
    ]),
    check("platform_agent_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const platformAgentVersion = pgTable(
  "platform_agent_version",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    agentId: uuid("agent_id").notNull(),
    versionNo: integer("version_no").notNull(),
    status: text("status", {
      enum: [
        "DRAFT",
        "NEEDS_INPUT",
        "READY_FOR_EVAL",
        "EVALUATING",
        "READY_FOR_REVIEW",
        "READY_FOR_PUBLISH",
        "PUBLISHED",
        "SUSPENDED",
        "RETIRED",
      ],
    }).notNull(),
    specHash: text("spec_hash").notNull(),
    createdBy: text("created_by").notNull(),
    publishedAt: timestamp("published_at", { withTimezone: true }),
    suspendedAt: timestamp("suspended_at", { withTimezone: true }),
    retiredAt: timestamp("retired_at", { withTimezone: true }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_agent_version_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_agent_version_uq_0").on(
      t.tenantId,
      t.agentId,
      t.versionNo,
    ),
    unique("platform_agent_version_uq_1").on(t.tenantId, t.id),
    unique("platform_agent_version_uq_2").on(t.tenantId, t.agentId, t.id),
    foreignKey({
      name: "platform_agent_version_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_version_fk_1",
      columns: [t.tenantId, t.agentId],
      foreignColumns: [platformAgent.tenantId, platformAgent.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_version_fk_2",
      columns: [t.createdBy],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("platform_agent_version_ix_0").on(t.createdBy),
    index("platform_agent_version_ix_1").on(t.tenantId, t.agentId),
    allowedValues("platform_agent_version_status_ck", t.status, [
      "DRAFT",
      "NEEDS_INPUT",
      "READY_FOR_EVAL",
      "EVALUATING",
      "READY_FOR_REVIEW",
      "READY_FOR_PUBLISH",
      "PUBLISHED",
      "SUSPENDED",
      "RETIRED",
    ]),
    check("platform_agent_version_ck_0", sql`version_no > 0`),
    check("platform_agent_version_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const platformAgentSpec = pgTable(
  "platform_agent_spec",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    agentVersionId: uuid("agent_version_id").notNull(),
    schemaVersion: integer("schema_version").notNull(),
    goal: text("goal").notNull(),
    instructions: text("instructions").notNull(),
    inputSchema: jsonb("input_schema").notNull(),
    outputSchema: jsonb("output_schema").notNull(),
    runtimeProfile: text("runtime_profile").notNull(),
    riskLevel: text("risk_level", {
      enum: ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
    }).notNull(),
    specJson: jsonb("spec_json").notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_agent_spec_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_agent_spec_uq_0").on(t.tenantId, t.agentVersionId),
    unique("platform_agent_spec_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_agent_spec_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_spec_fk_1",
      columns: [t.tenantId, t.agentVersionId],
      foreignColumns: [platformAgentVersion.tenantId, platformAgentVersion.id],
    }).onDelete("restrict"),
    allowedValues("platform_agent_spec_risk_level_ck", t.riskLevel, [
      "LOW",
      "MEDIUM",
      "HIGH",
      "CRITICAL",
    ]),
    check("platform_agent_spec_ck_0", sql`schema_version > 0`),
    check("platform_agent_spec_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const platformAgentChangeRequest = pgTable(
  "platform_agent_change_request",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    agentId: uuid("agent_id").notNull(),
    requestedBy: text("requested_by").notNull(),
    requestType: text("request_type").notNull(),
    description: text("description").notNull(),
    status: text("status", {
      enum: ["OPEN", "ACCEPTED", "REJECTED", "IMPLEMENTED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_agent_change_request_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_agent_change_request_uq_0").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_agent_change_request_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_change_request_fk_1",
      columns: [t.tenantId, t.agentId],
      foreignColumns: [platformAgent.tenantId, platformAgent.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_change_request_fk_2",
      columns: [t.requestedBy],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("platform_agent_change_request_ix_0").on(t.tenantId, t.agentId),
    index("platform_agent_change_request_ix_1").on(t.requestedBy),
    allowedValues("platform_agent_change_request_status_ck", t.status, [
      "OPEN",
      "ACCEPTED",
      "REJECTED",
      "IMPLEMENTED",
    ]),
    check("platform_agent_change_request_ck_0", sql`version > 0`),
  ],
).enableRLS();
