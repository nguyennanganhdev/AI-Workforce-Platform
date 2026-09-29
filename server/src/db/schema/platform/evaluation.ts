/** Physical model for platform/evaluation. See docs/erd/README.md. */
import { sql } from "drizzle-orm";
import {
  check,
  foreignKey,
  index,
  integer,
  numeric,
  pgPolicy,
  pgTable,
  text,
  timestamp,
  unique,
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, jsonb, mutableColumns } from "../columns";
import { platformAgentVersion } from "./agents";
import { platformTenant, users } from "./identity";

export const platformEvalRun = pgTable(
  "platform_eval_run",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    agentVersionId: uuid("agent_version_id").notNull(),
    result: text("result", { enum: ["PASS", "REVISE", "BLOCK", "INCONCLUSIVE"] }),
    testsJson: jsonb("tests_json").notNull(),
    resultsJson: jsonb("results_json").$type<unknown[]>().notNull().default([]),
    evidenceJson: jsonb("evidence_json").$type<unknown[]>().notNull().default([]),
    evaluatedBy: text("evaluated_by").notNull(),
    status: text("status", {
      enum: ["PENDING", "RUNNING", "PASSED", "FAILED", "CANCELLED"],
    }).notNull(),
    environmentSnapshot: jsonb("environment_snapshot").notNull(),
    modelSnapshot: jsonb("model_snapshot").notNull(),
    startedAt: timestamp("started_at", { withTimezone: true }),
    completedAt: timestamp("completed_at", { withTimezone: true }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_eval_run_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_eval_run_uq_0").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_eval_run_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_eval_run_fk_1",
      columns: [t.tenantId, t.agentVersionId],
      foreignColumns: [platformAgentVersion.tenantId, platformAgentVersion.id],
    }).onDelete("restrict"),
    index("platform_eval_run_ix_0").on(t.tenantId, t.agentVersionId),
    allowedValues("platform_eval_run_status_ck", t.status, [
      "PENDING",
      "RUNNING",
      "PASSED",
      "FAILED",
      "CANCELLED",
    ]),
    foreignKey({ name: "platform_eval_run_reviewer_fk", columns: [t.evaluatedBy], foreignColumns: [users.id] }).onDelete("restrict"),
    allowedValues("platform_eval_run_result_ck", t.result, ["PASS", "REVISE", "BLOCK", "INCONCLUSIVE"]),
    check("platform_eval_run_json_ck", sql`jsonb_typeof(tests_json)='array' AND jsonb_typeof(results_json)='array' AND jsonb_typeof(evidence_json)='array'`),
    check("platform_eval_run_outcome_ck", sql`((status='PASSED' AND result='PASS' AND completed_at IS NOT NULL) OR (status IN ('FAILED','CANCELLED') AND result IN ('REVISE','BLOCK','INCONCLUSIVE') AND completed_at IS NOT NULL) OR (status IN ('PENDING','RUNNING') AND result IS NULL AND completed_at IS NULL)) IS TRUE`),
    check(
      "platform_eval_run_ck_0",
      sql`completed_at IS NULL OR completed_at >= started_at`,
    ),
    check("platform_eval_run_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const platformPublishApproval = pgTable(
  "platform_publish_approval",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    agentVersionId: uuid("agent_version_id").notNull(),
    approvalType: text("approval_type", {
      enum: ["DOMAIN", "EVALUATION", "SECURITY", "PLATFORM"],
    }).notNull(),
    reviewerId: text("reviewer_id").notNull(),
    status: text("status", { enum: ["APPROVED", "REJECTED"] }).notNull(),
    reason: text("reason"),
    decidedAt: timestamp("decided_at", { withTimezone: true }).notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_publish_approval_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_publish_approval_uq_0").on(
      t.tenantId,
      t.agentVersionId,
      t.approvalType,
    ),
    unique("platform_publish_approval_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_publish_approval_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_publish_approval_fk_1",
      columns: [t.tenantId, t.agentVersionId],
      foreignColumns: [platformAgentVersion.tenantId, platformAgentVersion.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_publish_approval_fk_2",
      columns: [t.reviewerId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("platform_publish_approval_ix_0").on(t.tenantId, t.agentVersionId),
    index("platform_publish_approval_ix_1").on(t.reviewerId),
    allowedValues(
      "platform_publish_approval_approval_type_ck",
      t.approvalType,
      ["DOMAIN", "EVALUATION", "SECURITY", "PLATFORM"],
    ),
    allowedValues("platform_publish_approval_status_ck", t.status, [
      "APPROVED",
      "REJECTED",
    ]),
  ],
).enableRLS();
