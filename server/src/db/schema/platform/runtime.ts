import { agents } from "../core";
/** Physical model for platform/runtime. See docs/erd/README.md. */
import { sql } from "drizzle-orm";
import {
  bigint,
  boolean,
  check,
  foreignKey,
  index,
  integer,
  pgPolicy,
  pgTable,
  primaryKey,
  text,
  timestamp,
  unique,
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, jsonb, mutableColumns } from "../columns";
import { platformAgentVersion } from "./agents";
import { platformCapability } from "./capabilities";
import { platformTenant } from "./identity";

export const platformWorkflowSession = pgTable(
  "platform_workflow_session",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    domainNamespace: text("domain_namespace").notNull(),
    subjectType: text("subject_type").notNull(),
    subjectRef: text("subject_ref").notNull(),
    subjectVersion: bigint("subject_version", { mode: "bigint" }),
    runtimeProvider: text("runtime_provider").notNull(),
    environment: text("environment", {
      enum: ["DEVELOPMENT", "STAGING", "PRODUCTION"],
    }).notNull(),
    status: text("status", {
      enum: [
        "PENDING",
        "RUNNING",
        "WAITING",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
      ],
    }).notNull(),
    planJson: jsonb("plan_json").notNull(),
    contextSnapshotJson: jsonb("context_snapshot_json").notNull().default({}),
    startedAt: timestamp("started_at", { withTimezone: true }),
    completedAt: timestamp("completed_at", { withTimezone: true }),
    traceId: text("trace_id").notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_workflow_session_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_workflow_session_uq_0").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_workflow_session_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    index("platform_workflow_session_ix_0").on(
      t.tenantId,
      t.domainNamespace,
      t.subjectRef,
    ),
    index("platform_workflow_session_ix_1").on(
      t.tenantId,
      t.status,
      t.createdAt,
    ),
    allowedValues("platform_workflow_session_status_ck", t.status, [
      "PENDING",
      "RUNNING",
      "WAITING",
      "COMPLETED",
      "FAILED",
      "CANCELLED",
    ]),
    check("platform_workflow_session_plan_ck", sql`(jsonb_typeof(plan_json)='object' AND jsonb_typeof(plan_json->'steps')='array') IS TRUE AND jsonb_typeof(context_snapshot_json)='object'`),
    check("platform_workflow_session_ck_0", sql`version > 0`),
    allowedValues("platform_workflow_session_environment_ck", t.environment, [
      "DEVELOPMENT",
      "STAGING",
      "PRODUCTION",
    ]),
  ],
).enableRLS();

export const platformAgentRun = pgTable(
  "platform_agent_run",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    workflowSessionId: uuid("workflow_session_id").notNull(),
    stepKey: text("step_key").notNull(),
    role: text("role").notNull().default("SPECIALIST"),
    attemptNo: integer("attempt_no").notNull().default(1),
    errorType: text("error_type"),
    errorJson: jsonb("error_json"),
    agentId: text("agent_id").notNull(),
    agentVersionId: uuid("agent_version_id").notNull(),
    status: text("status", {
      enum: ["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"],
    }).notNull(),
    inputJson: jsonb("input_json").notNull(),
    outputJson: jsonb("output_json").notNull(),
    traceId: text("trace_id").notNull(),
    startedAt: timestamp("started_at", { withTimezone: true }),
    completedAt: timestamp("completed_at", { withTimezone: true }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_agent_run_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_agent_run_uq_0").on(t.tenantId, t.id),
    unique("platform_agent_run_uq_1").on(t.tenantId, t.workflowSessionId, t.id),
    foreignKey({
      name: "platform_agent_run_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_run_fk_1",
      columns: [t.tenantId, t.workflowSessionId],
      foreignColumns: [
        platformWorkflowSession.tenantId,
        platformWorkflowSession.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_run_fk_3",
      columns: [t.tenantId, t.agentId],
      foreignColumns: [agents.tenantId, agents.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_run_fk_4",
      columns: [t.tenantId, t.agentId, t.agentVersionId],
      foreignColumns: [
        platformAgentVersion.tenantId,
        platformAgentVersion.agentId,
        platformAgentVersion.id,
      ],
    }).onDelete("restrict"),
    index("platform_agent_run_ix_0").on(
      t.tenantId,
      t.agentId,
      t.agentVersionId,
    ),
    index("platform_agent_run_ix_1").on(t.tenantId, t.workflowSessionId),
    index("platform_agent_run_ix_2").on(
      t.tenantId,
      t.workflowSessionId,
      t.stepKey,
    ),
    index("platform_agent_run_ix_3").on(t.tenantId, t.agentId),
    allowedValues("platform_agent_run_status_ck", t.status, [
      "PENDING",
      "RUNNING",
      "COMPLETED",
      "FAILED",
      "CANCELLED",
    ]),
    unique("platform_agent_run_attempt_uq").on(t.tenantId, t.workflowSessionId, t.stepKey, t.agentId, t.attemptNo),
    check("platform_agent_run_attempt_ck", sql`attempt_no > 0`),
    check("platform_agent_run_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const platformToolCall = pgTable(
  "platform_tool_call",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    agentRunId: uuid("agent_run_id").notNull(),
    capabilityId: uuid("capability_id").notNull(),
    requestJson: jsonb("request_json").notNull(),
    responseJson: jsonb("response_json").notNull(),
    decision: text("decision", {
      enum: ["ALLOW", "DENY", "REQUIRE_APPROVAL"],
    }).notNull(),
    status: text("status", {
      enum: ["PENDING", "RUNNING", "SUCCEEDED", "FAILED", "DENIED"],
    }).notNull(),
    startedAt: timestamp("started_at", { withTimezone: true }),
    completedAt: timestamp("completed_at", { withTimezone: true }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_tool_call_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_tool_call_uq_0").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_tool_call_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_tool_call_fk_1",
      columns: [t.tenantId, t.agentRunId],
      foreignColumns: [platformAgentRun.tenantId, platformAgentRun.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_tool_call_fk_2",
      columns: [t.tenantId, t.capabilityId],
      foreignColumns: [platformCapability.tenantId, platformCapability.id],
    }).onDelete("restrict"),
    index("platform_tool_call_ix_0").on(t.tenantId, t.agentRunId),
    index("platform_tool_call_ix_1").on(t.tenantId, t.capabilityId),
    allowedValues("platform_tool_call_decision_ck", t.decision, [
      "ALLOW",
      "DENY",
      "REQUIRE_APPROVAL",
    ]),
    allowedValues("platform_tool_call_status_ck", t.status, [
      "PENDING",
      "RUNNING",
      "SUCCEEDED",
      "FAILED",
      "DENIED",
    ]),
    check("platform_tool_call_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const platformRuntimeArtifact = pgTable(
  "platform_runtime_artifact",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    agentRunId: uuid("agent_run_id").notNull(),
    artifactType: text("artifact_type").notNull(),
    payloadJson: jsonb("payload_json").notNull(),
    storageRef: text("storage_ref"),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_runtime_artifact_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_runtime_artifact_uq_0").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_runtime_artifact_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_runtime_artifact_fk_1",
      columns: [t.tenantId, t.agentRunId],
      foreignColumns: [platformAgentRun.tenantId, platformAgentRun.id],
    }).onDelete("restrict"),
    index("platform_runtime_artifact_ix_0").on(t.tenantId, t.agentRunId),
  ],
).enableRLS();

export const platformRuntimeDecision = pgTable(
  "platform_runtime_decision",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    workflowSessionId: uuid("workflow_session_id").notNull(),
    decisionType: text("decision_type").notNull(),
    payloadJson: jsonb("payload_json").notNull(),
    createdByRunId: uuid("created_by_run_id"),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_runtime_decision_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_runtime_decision_uq_0").on(t.tenantId, t.id),
    unique("platform_runtime_decision_uq_1").on(
      t.tenantId,
      t.workflowSessionId,
      t.id,
    ),
    foreignKey({
      name: "platform_runtime_decision_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_runtime_decision_fk_1",
      columns: [t.tenantId, t.workflowSessionId],
      foreignColumns: [
        platformWorkflowSession.tenantId,
        platformWorkflowSession.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_runtime_decision_fk_2",
      columns: [t.tenantId, t.workflowSessionId, t.createdByRunId],
      foreignColumns: [
        platformAgentRun.tenantId,
        platformAgentRun.workflowSessionId,
        platformAgentRun.id,
      ],
    }).onDelete("restrict"),
    index("platform_runtime_decision_ix_0").on(
      t.tenantId,
      t.workflowSessionId,
      t.createdByRunId,
    ),
    index("platform_runtime_decision_ix_1").on(t.tenantId, t.workflowSessionId),
  ],
).enableRLS();

export const platformActionProposal = pgTable(
  "platform_action_proposal",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    runtimeDecisionId: uuid("runtime_decision_id").notNull(),
    workflowSessionId: uuid("workflow_session_id").notNull(),
    producerAgentRunId: uuid("producer_agent_run_id"),
    actionType: text("action_type").notNull(),
    targetJson: jsonb("target_json").notNull(),
    payloadJson: jsonb("payload_json").notNull(),
    payloadHash: text("payload_hash").notNull(),
    idempotencyKey: text("idempotency_key").notNull(),
    status: text("status", {
      enum: ["PROPOSED", "ACCEPTED", "REJECTED"],
    }).notNull(),
    correlationId: text("correlation_id").notNull(),
    traceId: text("trace_id").notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_action_proposal_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_action_proposal_uq_0").on(t.tenantId, t.idempotencyKey),
    unique("platform_action_proposal_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_action_proposal_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_action_proposal_fk_1",
      columns: [t.tenantId, t.workflowSessionId, t.runtimeDecisionId],
      foreignColumns: [
        platformRuntimeDecision.tenantId,
        platformRuntimeDecision.workflowSessionId,
        platformRuntimeDecision.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_action_proposal_fk_2",
      columns: [t.tenantId, t.workflowSessionId],
      foreignColumns: [
        platformWorkflowSession.tenantId,
        platformWorkflowSession.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_action_proposal_fk_3",
      columns: [t.tenantId, t.workflowSessionId, t.producerAgentRunId],
      foreignColumns: [
        platformAgentRun.tenantId,
        platformAgentRun.workflowSessionId,
        platformAgentRun.id,
      ],
    }).onDelete("restrict"),
    index("platform_action_proposal_ix_0").on(
      t.tenantId,
      t.workflowSessionId,
      t.runtimeDecisionId,
    ),
    index("platform_action_proposal_ix_1").on(
      t.tenantId,
      t.workflowSessionId,
      t.producerAgentRunId,
    ),
    index("platform_action_proposal_ix_2").on(t.tenantId, t.workflowSessionId),
    allowedValues("platform_action_proposal_status_ck", t.status, [
      "PROPOSED",
      "ACCEPTED",
      "REJECTED",
    ]),
    check("platform_action_proposal_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const platformExecutionGrantRef = pgTable(
  "platform_execution_grant_ref",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    actionProposalId: uuid("action_proposal_id").notNull(),
    domainNamespace: text("domain_namespace").notNull(),
    domainActionRef: text("domain_action_ref").notNull(),
    grantRef: text("grant_ref").notNull(),
    payloadHash: text("payload_hash").notNull(),
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
    status: text("status", {
      enum: ["ACTIVE", "CONSUMED", "REVOKED", "EXPIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_execution_grant_ref_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_execution_grant_ref_uq_0").on(
      t.tenantId,
      t.domainNamespace,
      t.grantRef,
    ),
    unique("platform_execution_grant_ref_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_execution_grant_ref_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_execution_grant_ref_fk_1",
      columns: [t.tenantId, t.actionProposalId],
      foreignColumns: [
        platformActionProposal.tenantId,
        platformActionProposal.id,
      ],
    }).onDelete("restrict"),
    index("platform_execution_grant_ref_ix_0").on(
      t.tenantId,
      t.actionProposalId,
    ),
    allowedValues("platform_execution_grant_ref_status_ck", t.status, [
      "ACTIVE",
      "CONSUMED",
      "REVOKED",
      "EXPIRED",
    ]),
    check("platform_execution_grant_ref_ck_0", sql`version > 0`),
  ],
).enableRLS();
