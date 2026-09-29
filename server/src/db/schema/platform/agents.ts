import { agents } from "../core";
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

export const platformAgentVersion = pgTable(
  "platform_agent_version",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    agentId: text("agent_id").notNull(),
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
    specJson: jsonb("spec_json").notNull().default({}),
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
      foreignColumns: [agents.tenantId, agents.id],
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
    check("platform_agent_version_spec_ck", sql`jsonb_typeof(spec_json) = 'object'`),
    check("platform_agent_version_ck_0", sql`version_no > 0`),
    check("platform_agent_version_ck_1", sql`version > 0`),
  ],
).enableRLS();

