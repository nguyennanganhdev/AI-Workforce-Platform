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
import { platformAgent, platformAgentVersion } from "./agents";
import { platformTenant, users } from "./identity";

export const platformEvalSuite = pgTable(
  "platform_eval_suite",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    name: text("name").notNull(),
    versionNo: integer("version_no").notNull(),
    type: text("type").notNull(),
    ownerId: text("owner_id").notNull(),
    status: text("status", { enum: ["DRAFT", "ACTIVE", "RETIRED"] }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_eval_suite_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_eval_suite_uq_0").on(t.tenantId, t.name, t.versionNo),
    unique("platform_eval_suite_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_eval_suite_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_eval_suite_fk_1",
      columns: [t.ownerId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("platform_eval_suite_ix_0").on(t.ownerId),
    allowedValues("platform_eval_suite_status_ck", t.status, [
      "DRAFT",
      "ACTIVE",
      "RETIRED",
    ]),
    check("platform_eval_suite_ck_0", sql`version_no > 0`),
    check("platform_eval_suite_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const platformEvalCase = pgTable(
  "platform_eval_case",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    evalSuiteId: uuid("eval_suite_id").notNull(),
    caseCode: text("case_code").notNull(),
    inputJson: jsonb("input_json").notNull(),
    expectedJson: jsonb("expected_json").notNull(),
    severity: text("severity", {
      enum: ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
    }).notNull(),
    tags: text("tags").array().notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_eval_case_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_eval_case_uq_0").on(t.tenantId, t.evalSuiteId, t.caseCode),
    unique("platform_eval_case_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_eval_case_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_eval_case_fk_1",
      columns: [t.tenantId, t.evalSuiteId],
      foreignColumns: [platformEvalSuite.tenantId, platformEvalSuite.id],
    }).onDelete("restrict"),
    index("platform_eval_case_ix_0").on(t.tenantId, t.evalSuiteId),
    allowedValues("platform_eval_case_severity_ck", t.severity, [
      "LOW",
      "MEDIUM",
      "HIGH",
      "CRITICAL",
    ]),
    check("platform_eval_case_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const platformEvalRun = pgTable(
  "platform_eval_run",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    agentVersionId: uuid("agent_version_id").notNull(),
    evalSuiteId: uuid("eval_suite_id").notNull(),
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
    foreignKey({
      name: "platform_eval_run_fk_2",
      columns: [t.tenantId, t.evalSuiteId],
      foreignColumns: [platformEvalSuite.tenantId, platformEvalSuite.id],
    }).onDelete("restrict"),
    index("platform_eval_run_ix_0").on(t.tenantId, t.agentVersionId),
    index("platform_eval_run_ix_1").on(t.tenantId, t.evalSuiteId),
    allowedValues("platform_eval_run_status_ck", t.status, [
      "PENDING",
      "RUNNING",
      "PASSED",
      "FAILED",
      "CANCELLED",
    ]),
    check(
      "platform_eval_run_ck_0",
      sql`completed_at IS NULL OR completed_at >= started_at`,
    ),
    check("platform_eval_run_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const platformEvalAssertion = pgTable(
  "platform_eval_assertion",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    evalRunId: uuid("eval_run_id").notNull(),
    evalCaseId: uuid("eval_case_id").notNull(),
    assertionType: text("assertion_type").notNull(),
    status: text("status", {
      enum: ["PASS", "FAIL", "ERROR", "SKIPPED"],
    }).notNull(),
    score: numeric("score"),
    expectedJson: jsonb("expected_json").notNull(),
    actualJson: jsonb("actual_json").notNull(),
    failureReason: text("failure_reason"),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_eval_assertion_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_eval_assertion_uq_0").on(t.tenantId, t.id),
    unique("platform_eval_assertion_uq_1").on(t.tenantId, t.evalRunId, t.id),
    foreignKey({
      name: "platform_eval_assertion_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_eval_assertion_fk_1",
      columns: [t.tenantId, t.evalRunId],
      foreignColumns: [platformEvalRun.tenantId, platformEvalRun.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_eval_assertion_fk_2",
      columns: [t.tenantId, t.evalCaseId],
      foreignColumns: [platformEvalCase.tenantId, platformEvalCase.id],
    }).onDelete("restrict"),
    index("platform_eval_assertion_ix_0").on(t.tenantId, t.evalCaseId),
    index("platform_eval_assertion_ix_1").on(t.tenantId, t.evalRunId),
    allowedValues("platform_eval_assertion_status_ck", t.status, [
      "PASS",
      "FAIL",
      "ERROR",
      "SKIPPED",
    ]),
  ],
).enableRLS();

export const platformEvalEvidence = pgTable(
  "platform_eval_evidence",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    evalRunId: uuid("eval_run_id").notNull(),
    evalAssertionId: uuid("eval_assertion_id"),
    evidenceType: text("evidence_type").notNull(),
    artifactRef: text("artifact_ref").notNull(),
    traceId: text("trace_id").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_eval_evidence_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_eval_evidence_uq_0").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_eval_evidence_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_eval_evidence_fk_1",
      columns: [t.tenantId, t.evalRunId],
      foreignColumns: [platformEvalRun.tenantId, platformEvalRun.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_eval_evidence_fk_2",
      columns: [t.tenantId, t.evalRunId, t.evalAssertionId],
      foreignColumns: [
        platformEvalAssertion.tenantId,
        platformEvalAssertion.evalRunId,
        platformEvalAssertion.id,
      ],
    }).onDelete("restrict"),
    index("platform_eval_evidence_ix_0").on(t.tenantId, t.evalRunId),
    index("platform_eval_evidence_ix_1").on(
      t.tenantId,
      t.evalRunId,
      t.evalAssertionId,
    ),
  ],
).enableRLS();

export const platformRegressionBaseline = pgTable(
  "platform_regression_baseline",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    agentId: uuid("agent_id").notNull(),
    baselineAgentVersionId: uuid("baseline_agent_version_id").notNull(),
    evalSuiteId: uuid("eval_suite_id").notNull(),
    acceptedBy: text("accepted_by").notNull(),
    acceptedAt: timestamp("accepted_at", { withTimezone: true }).notNull(),
    status: text("status", { enum: ["ACTIVE", "RETIRED"] }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_regression_baseline_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_regression_baseline_uq_0").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_regression_baseline_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_regression_baseline_fk_1",
      columns: [t.tenantId, t.agentId],
      foreignColumns: [platformAgent.tenantId, platformAgent.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_regression_baseline_fk_2",
      columns: [t.tenantId, t.agentId, t.baselineAgentVersionId],
      foreignColumns: [
        platformAgentVersion.tenantId,
        platformAgentVersion.agentId,
        platformAgentVersion.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_regression_baseline_fk_3",
      columns: [t.tenantId, t.evalSuiteId],
      foreignColumns: [platformEvalSuite.tenantId, platformEvalSuite.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_regression_baseline_fk_4",
      columns: [t.acceptedBy],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_regression_baseline_fk_5",
      columns: [t.tenantId, t.agentId, t.baselineAgentVersionId],
      foreignColumns: [
        platformAgentVersion.tenantId,
        platformAgentVersion.agentId,
        platformAgentVersion.id,
      ],
    }).onDelete("restrict"),
    index("platform_regression_baseline_ix_0").on(t.acceptedBy),
    index("platform_regression_baseline_ix_1").on(
      t.tenantId,
      t.agentId,
      t.baselineAgentVersionId,
    ),
    index("platform_regression_baseline_ix_2").on(t.tenantId, t.evalSuiteId),
    index("platform_regression_baseline_ix_3").on(t.tenantId, t.agentId),
    allowedValues("platform_regression_baseline_status_ck", t.status, [
      "ACTIVE",
      "RETIRED",
    ]),
    check("platform_regression_baseline_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const platformPublishGate = pgTable(
  "platform_publish_gate",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    agentVersionId: uuid("agent_version_id").notNull(),
    status: text("status", { enum: ["PENDING", "PASSED", "FAILED"] }).notNull(),
    completedAt: timestamp("completed_at", { withTimezone: true }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_publish_gate_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_publish_gate_uq_0").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_publish_gate_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_publish_gate_fk_1",
      columns: [t.tenantId, t.agentVersionId],
      foreignColumns: [platformAgentVersion.tenantId, platformAgentVersion.id],
    }).onDelete("restrict"),
    index("platform_publish_gate_ix_0").on(t.tenantId, t.agentVersionId),
    allowedValues("platform_publish_gate_status_ck", t.status, [
      "PENDING",
      "PASSED",
      "FAILED",
    ]),
    check("platform_publish_gate_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const platformPublishGateResult = pgTable(
  "platform_publish_gate_result",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    publishGateId: uuid("publish_gate_id").notNull(),
    gateType: text("gate_type", {
      enum: ["CONTRACT", "QUALITY", "SAFETY", "REGRESSION"],
    }).notNull(),
    status: text("status", { enum: ["PASS", "FAIL"] }).notNull(),
    evidenceRef: text("evidence_ref").notNull(),
    detailsJson: jsonb("details_json").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_publish_gate_result_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_publish_gate_result_uq_0").on(
      t.tenantId,
      t.publishGateId,
      t.gateType,
    ),
    unique("platform_publish_gate_result_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_publish_gate_result_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_publish_gate_result_fk_1",
      columns: [t.tenantId, t.publishGateId],
      foreignColumns: [platformPublishGate.tenantId, platformPublishGate.id],
    }).onDelete("restrict"),
    index("platform_publish_gate_result_ix_0").on(t.tenantId, t.publishGateId),
    allowedValues("platform_publish_gate_result_gate_type_ck", t.gateType, [
      "CONTRACT",
      "QUALITY",
      "SAFETY",
      "REGRESSION",
    ]),
    allowedValues("platform_publish_gate_result_status_ck", t.status, [
      "PASS",
      "FAIL",
    ]),
  ],
).enableRLS();

export const platformPublishApproval = pgTable(
  "platform_publish_approval",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    publishGateId: uuid("publish_gate_id").notNull(),
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
      t.publishGateId,
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
      columns: [t.tenantId, t.publishGateId],
      foreignColumns: [platformPublishGate.tenantId, platformPublishGate.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_publish_approval_fk_2",
      columns: [t.reviewerId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("platform_publish_approval_ix_0").on(t.tenantId, t.publishGateId),
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
