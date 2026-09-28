/** Persistence for coordination and field operations. See docs/erd/SYSTEM_FLOW.md. */
import { sql } from "drizzle-orm";
import {
  bigint,
  check,
  foreignKey,
  index,
  integer,
  pgPolicy,
  pgTable,
  text,
  timestamp,
  unique,
  uniqueIndex,
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, jsonb, mutableColumns } from "../columns";
import { platformAgentVersion } from "./agents";
import { platformConversation } from "./conversations";
import { platformTenant } from "./identity";
import {
  platformAgentRun,
  platformRunStep,
  platformWorkflowSession,
} from "./runtime";

export const platformSessionParticipant = pgTable(
  "platform_session_participant",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    workflowSessionId: uuid("workflow_session_id").notNull(),
    agentVersionId: uuid("agent_version_id").notNull(),
    role: text("role", {
      enum: ["COORDINATOR", "SPECIALIST", "REVIEWER"],
    }).notNull(),
    capabilityScopeJson: jsonb("capability_scope_json").notNull(),
    status: text("status", {
      enum: ["INVITED", "ACTIVE", "LEFT", "FAILED"],
    }).notNull(),
    joinedAt: timestamp("joined_at", { withTimezone: true }),
    leftAt: timestamp("left_at", { withTimezone: true }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_session_participant_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_session_participant_uq_0").on(
      t.tenantId,
      t.workflowSessionId,
      t.agentVersionId,
    ),
    unique("platform_session_participant_uq_1").on(t.tenantId, t.id),
    unique("platform_session_participant_uq_2").on(
      t.tenantId,
      t.workflowSessionId,
      t.id,
    ),
    foreignKey({
      name: "platform_session_participant_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_session_participant_fk_1",
      columns: [t.tenantId, t.workflowSessionId],
      foreignColumns: [
        platformWorkflowSession.tenantId,
        platformWorkflowSession.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_session_participant_fk_2",
      columns: [t.tenantId, t.agentVersionId],
      foreignColumns: [platformAgentVersion.tenantId, platformAgentVersion.id],
    }).onDelete("restrict"),
    index("platform_session_participant_ix_1").on(t.tenantId, t.agentVersionId),
    index("platform_session_participant_ix_2").on(
      t.tenantId,
      t.workflowSessionId,
    ),
    allowedValues("platform_session_participant_role_ck", t.role, [
      "COORDINATOR",
      "SPECIALIST",
      "REVIEWER",
    ]),
    allowedValues("platform_session_participant_status_ck", t.status, [
      "INVITED",
      "ACTIVE",
      "LEFT",
      "FAILED",
    ]),
    check(
      "platform_session_participant_ck_0",
      sql`left_at IS NULL OR (joined_at IS NOT NULL AND left_at >= joined_at)`,
    ),
    check("platform_session_participant_ck_1", sql`version > 0`),
    uniqueIndex("platform_session_participant_live_0")
      .on(t.tenantId, t.workflowSessionId)
      .where(sql`role='COORDINATOR' AND status IN ('INVITED','ACTIVE')`),
  ],
).enableRLS();

export const platformSessionControl = pgTable(
  "platform_session_control",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    workflowSessionId: uuid("workflow_session_id").notNull(),
    parentWorkflowSessionId: uuid("parent_workflow_session_id"),
    coordinatorParticipantId: uuid("coordinator_participant_id"),
    purpose: text("purpose", {
      enum: ["TRIAGE", "PLAN", "FOLLOW_UP", "QC", "REPLAN"],
    }).notNull(),
    initiationKey: text("initiation_key").notNull(),
    requestHash: text("request_hash").notNull(),
    leaseOwner: text("lease_owner"),
    leaseExpiresAt: timestamp("lease_expires_at", { withTimezone: true }),
    fencingToken: bigint("fencing_token", { mode: "bigint" }).notNull(),
    heartbeatAt: timestamp("heartbeat_at", { withTimezone: true }),
    deadlineAt: timestamp("deadline_at", { withTimezone: true }),
    maxTurns: integer("max_turns").notNull(),
    maxToolCalls: integer("max_tool_calls").notNull(),
    stopReason: text("stop_reason"),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_session_control_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_session_control_uq_0").on(t.tenantId, t.workflowSessionId),
    unique("platform_session_control_uq_1").on(t.tenantId, t.initiationKey),
    unique("platform_session_control_uq_2").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_session_control_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_session_control_fk_1",
      columns: [t.tenantId, t.workflowSessionId],
      foreignColumns: [
        platformWorkflowSession.tenantId,
        platformWorkflowSession.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_session_control_fk_2",
      columns: [t.tenantId, t.parentWorkflowSessionId],
      foreignColumns: [
        platformWorkflowSession.tenantId,
        platformWorkflowSession.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_session_control_fk_3",
      columns: [t.tenantId, t.workflowSessionId, t.coordinatorParticipantId],
      foreignColumns: [
        platformSessionParticipant.tenantId,
        platformSessionParticipant.workflowSessionId,
        platformSessionParticipant.id,
      ],
    }).onDelete("restrict"),
    index("platform_session_control_ix_1").on(
      t.tenantId,
      t.parentWorkflowSessionId,
    ),
    index("platform_session_control_ix_2").on(t.tenantId, t.workflowSessionId),
    index("platform_session_control_lease_ix").on(t.tenantId, t.leaseExpiresAt),
    index("platform_session_control_ix_3").on(
      t.tenantId,
      t.workflowSessionId,
      t.coordinatorParticipantId,
    ),
    allowedValues("platform_session_control_purpose_ck", t.purpose, [
      "TRIAGE",
      "PLAN",
      "FOLLOW_UP",
      "QC",
      "REPLAN",
    ]),
    check("platform_session_control_ck_0", sql`fencing_token >= 0`),
    check("platform_session_control_ck_1", sql`max_turns > 0`),
    check("platform_session_control_ck_2", sql`max_tool_calls >= 0`),
    check(
      "platform_session_control_ck_3",
      sql`(lease_owner IS NULL) = (lease_expires_at IS NULL)`,
    ),
    check(
      "platform_session_control_ck_4",
      sql`parent_workflow_session_id IS NULL OR parent_workflow_session_id <> workflow_session_id`,
    ),
    check("platform_session_control_ck_5", sql`version > 0`),
  ],
).enableRLS();

export const platformRuntimeMessage = pgTable(
  "platform_runtime_message",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    workflowSessionId: uuid("workflow_session_id").notNull(),
    sequenceNo: bigint("sequence_no", { mode: "bigint" }).notNull(),
    senderParticipantId: uuid("sender_participant_id"),
    recipientParticipantId: uuid("recipient_participant_id"),
    agentRunId: uuid("agent_run_id"),
    replyToMessageId: uuid("reply_to_message_id"),
    kind: text("kind", {
      enum: ["REQUEST", "FINDING", "PROPOSAL", "DECISION", "SYSTEM"],
    }).notNull(),
    body: text("body").notNull(),
    payloadJson: jsonb("payload_json").notNull(),
    schemaVersion: integer("schema_version").notNull(),
    idempotencyKey: text("idempotency_key").notNull(),
    correlationId: text("correlation_id").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_runtime_message_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_runtime_message_uq_0").on(
      t.tenantId,
      t.workflowSessionId,
      t.sequenceNo,
    ),
    unique("platform_runtime_message_uq_1").on(
      t.tenantId,
      t.workflowSessionId,
      t.idempotencyKey,
    ),
    unique("platform_runtime_message_uq_2").on(t.tenantId, t.id),
    unique("platform_runtime_message_uq_3").on(
      t.tenantId,
      t.workflowSessionId,
      t.id,
    ),
    foreignKey({
      name: "platform_runtime_message_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_runtime_message_fk_1",
      columns: [t.tenantId, t.workflowSessionId],
      foreignColumns: [
        platformWorkflowSession.tenantId,
        platformWorkflowSession.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_runtime_message_fk_2",
      columns: [t.tenantId, t.workflowSessionId, t.senderParticipantId],
      foreignColumns: [
        platformSessionParticipant.tenantId,
        platformSessionParticipant.workflowSessionId,
        platformSessionParticipant.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_runtime_message_fk_3",
      columns: [t.tenantId, t.workflowSessionId, t.recipientParticipantId],
      foreignColumns: [
        platformSessionParticipant.tenantId,
        platformSessionParticipant.workflowSessionId,
        platformSessionParticipant.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_runtime_message_fk_4",
      columns: [t.tenantId, t.workflowSessionId, t.agentRunId],
      foreignColumns: [
        platformAgentRun.tenantId,
        platformAgentRun.workflowSessionId,
        platformAgentRun.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_runtime_message_fk_5",
      columns: [t.tenantId, t.workflowSessionId, t.replyToMessageId],
      foreignColumns: [t.tenantId, t.workflowSessionId, t.id],
    }).onDelete("restrict"),
    index("platform_runtime_message_ix_1").on(t.tenantId, t.workflowSessionId),
    index("platform_runtime_message_ix_2").on(
      t.tenantId,
      t.workflowSessionId,
      t.agentRunId,
    ),
    index("platform_runtime_message_ix_3").on(
      t.tenantId,
      t.workflowSessionId,
      t.recipientParticipantId,
    ),
    index("platform_runtime_message_ix_4").on(
      t.tenantId,
      t.workflowSessionId,
      t.replyToMessageId,
    ),
    index("platform_runtime_message_ix_5").on(
      t.tenantId,
      t.workflowSessionId,
      t.senderParticipantId,
    ),
    allowedValues("platform_runtime_message_kind_ck", t.kind, [
      "REQUEST",
      "FINDING",
      "PROPOSAL",
      "DECISION",
      "SYSTEM",
    ]),
    check("platform_runtime_message_ck_0", sql`sequence_no > 0`),
    check("platform_runtime_message_ck_1", sql`schema_version > 0`),
    check(
      "platform_runtime_message_ck_2",
      sql`(kind='SYSTEM' AND sender_participant_id IS NULL AND agent_run_id IS NULL) OR (kind<>'SYSTEM' AND sender_participant_id IS NOT NULL)`,
    ),
  ],
).enableRLS();

export const platformRuntimeCheckpoint = pgTable(
  "platform_runtime_checkpoint",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    workflowSessionId: uuid("workflow_session_id").notNull(),
    checkpointNo: bigint("checkpoint_no", { mode: "bigint" }).notNull(),
    runtimeProvider: text("runtime_provider").notNull(),
    runtimeVersion: text("runtime_version").notNull(),
    stateSchemaVersion: integer("state_schema_version").notNull(),
    storageRef: text("storage_ref").notNull(),
    contentHash: text("content_hash").notNull(),
    lastMessageSequence: bigint("last_message_sequence", {
      mode: "bigint",
    }).notNull(),
    fencingToken: bigint("fencing_token", { mode: "bigint" }).notNull(),
    createdByRunId: uuid("created_by_run_id"),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_runtime_checkpoint_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_runtime_checkpoint_uq_0").on(
      t.tenantId,
      t.workflowSessionId,
      t.checkpointNo,
    ),
    unique("platform_runtime_checkpoint_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_runtime_checkpoint_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_runtime_checkpoint_fk_1",
      columns: [t.tenantId, t.workflowSessionId],
      foreignColumns: [
        platformWorkflowSession.tenantId,
        platformWorkflowSession.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_runtime_checkpoint_fk_2",
      columns: [t.tenantId, t.workflowSessionId, t.createdByRunId],
      foreignColumns: [
        platformAgentRun.tenantId,
        platformAgentRun.workflowSessionId,
        platformAgentRun.id,
      ],
    }).onDelete("restrict"),
    index("platform_runtime_checkpoint_ix_1").on(
      t.tenantId,
      t.workflowSessionId,
    ),
    index("platform_runtime_checkpoint_ix_2").on(
      t.tenantId,
      t.workflowSessionId,
      t.createdByRunId,
    ),
    check("platform_runtime_checkpoint_ck_0", sql`checkpoint_no > 0`),
    check("platform_runtime_checkpoint_ck_1", sql`state_schema_version > 0`),
    check("platform_runtime_checkpoint_ck_2", sql`last_message_sequence >= 0`),
    check("platform_runtime_checkpoint_ck_3", sql`fencing_token >= 0`),
  ],
).enableRLS();

export const platformSessionWait = pgTable(
  "platform_session_wait",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    workflowSessionId: uuid("workflow_session_id").notNull(),
    runStepId: uuid("run_step_id"),
    participantId: uuid("participant_id"),
    waitKey: text("wait_key").notNull(),
    waitType: text("wait_type", {
      enum: ["AGENT", "HUMAN", "DOMAIN_EVENT", "TIMER"],
    }).notNull(),
    expectedEventType: text("expected_event_type"),
    expectedSubjectRef: text("expected_subject_ref"),
    status: text("status", {
      enum: ["WAITING", "SATISFIED", "TIMED_OUT", "CANCELLED"],
    }).notNull(),
    deadlineAt: timestamp("deadline_at", { withTimezone: true }),
    satisfiedAt: timestamp("satisfied_at", { withTimezone: true }),
    responseEventRef: text("response_event_ref"),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_session_wait_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_session_wait_uq_0").on(
      t.tenantId,
      t.workflowSessionId,
      t.waitKey,
    ),
    unique("platform_session_wait_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_session_wait_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_session_wait_fk_1",
      columns: [t.tenantId, t.workflowSessionId],
      foreignColumns: [
        platformWorkflowSession.tenantId,
        platformWorkflowSession.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_session_wait_fk_2",
      columns: [t.tenantId, t.workflowSessionId, t.runStepId],
      foreignColumns: [
        platformRunStep.tenantId,
        platformRunStep.workflowSessionId,
        platformRunStep.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_session_wait_fk_3",
      columns: [t.tenantId, t.workflowSessionId, t.participantId],
      foreignColumns: [
        platformSessionParticipant.tenantId,
        platformSessionParticipant.workflowSessionId,
        platformSessionParticipant.id,
      ],
    }).onDelete("restrict"),
    index("platform_session_wait_ix_1").on(t.tenantId, t.workflowSessionId),
    index("platform_session_wait_deadline_ix").on(
      t.tenantId,
      t.status,
      t.deadlineAt,
    ),
    index("platform_session_wait_ix_2").on(
      t.tenantId,
      t.workflowSessionId,
      t.participantId,
    ),
    index("platform_session_wait_ix_3").on(
      t.tenantId,
      t.workflowSessionId,
      t.runStepId,
    ),
    allowedValues("platform_session_wait_wait_type_ck", t.waitType, [
      "AGENT",
      "HUMAN",
      "DOMAIN_EVENT",
      "TIMER",
    ]),
    allowedValues("platform_session_wait_status_ck", t.status, [
      "WAITING",
      "SATISFIED",
      "TIMED_OUT",
      "CANCELLED",
    ]),
    check(
      "platform_session_wait_ck_0",
      sql`status<>'SATISFIED' OR satisfied_at IS NOT NULL`,
    ),
    check("platform_session_wait_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const platformHandoff = pgTable(
  "platform_handoff",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    sourceConversationId: uuid("source_conversation_id"),
    sourceWorkflowSessionId: uuid("source_workflow_session_id"),
    targetAgentVersionId: uuid("target_agent_version_id").notNull(),
    targetWorkflowSessionId: uuid("target_workflow_session_id"),
    domainNamespace: text("domain_namespace").notNull(),
    subjectType: text("subject_type").notNull(),
    subjectRef: text("subject_ref").notNull(),
    subjectVersion: bigint("subject_version", { mode: "bigint" }),
    reason: text("reason").notNull(),
    contextJson: jsonb("context_json").notNull(),
    requestHash: text("request_hash").notNull(),
    idempotencyKey: text("idempotency_key").notNull(),
    correlationId: text("correlation_id").notNull(),
    traceId: text("trace_id").notNull(),
    status: text("status", {
      enum: [
        "OFFERED",
        "ACCEPTED",
        "COMPLETED",
        "FAILED",
        "EXPIRED",
        "CANCELLED",
      ],
    }).notNull(),
    attemptCount: integer("attempt_count").notNull(),
    nextAttemptAt: timestamp("next_attempt_at", {
      withTimezone: true,
    }).notNull(),
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
    acceptedAt: timestamp("accepted_at", { withTimezone: true }),
    completedAt: timestamp("completed_at", { withTimezone: true }),
    lastErrorCode: text("last_error_code"),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_handoff_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_handoff_uq_0").on(t.tenantId, t.idempotencyKey),
    unique("platform_handoff_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_handoff_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_handoff_fk_1",
      columns: [t.tenantId, t.sourceConversationId],
      foreignColumns: [platformConversation.tenantId, platformConversation.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_handoff_fk_2",
      columns: [t.tenantId, t.sourceWorkflowSessionId],
      foreignColumns: [
        platformWorkflowSession.tenantId,
        platformWorkflowSession.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_handoff_fk_3",
      columns: [t.tenantId, t.targetAgentVersionId],
      foreignColumns: [platformAgentVersion.tenantId, platformAgentVersion.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_handoff_fk_4",
      columns: [t.tenantId, t.targetWorkflowSessionId],
      foreignColumns: [
        platformWorkflowSession.tenantId,
        platformWorkflowSession.id,
      ],
    }).onDelete("restrict"),
    index("platform_handoff_ix_1").on(t.tenantId, t.sourceConversationId),
    index("platform_handoff_ready_ix").on(
      t.tenantId,
      t.status,
      t.nextAttemptAt,
    ),
    index("platform_handoff_ix_2").on(t.tenantId, t.sourceWorkflowSessionId),
    index("platform_handoff_ix_3").on(t.tenantId, t.targetAgentVersionId),
    index("platform_handoff_ix_4").on(t.tenantId, t.targetWorkflowSessionId),
    allowedValues("platform_handoff_status_ck", t.status, [
      "OFFERED",
      "ACCEPTED",
      "COMPLETED",
      "FAILED",
      "EXPIRED",
      "CANCELLED",
    ]),
    check(
      "platform_handoff_ck_0",
      sql`num_nonnulls(source_conversation_id, source_workflow_session_id) = 1`,
    ),
    check("platform_handoff_ck_1", sql`attempt_count >= 0`),
    check("platform_handoff_ck_2", sql`expires_at > created_at`),
    check(
      "platform_handoff_ck_3",
      sql`status NOT IN ('ACCEPTED','COMPLETED') OR (target_workflow_session_id IS NOT NULL AND accepted_at IS NOT NULL)`,
    ),
    check(
      "platform_handoff_ck_4",
      sql`status<>'COMPLETED' OR completed_at IS NOT NULL`,
    ),
    check("platform_handoff_ck_5", sql`version > 0`),
  ],
).enableRLS();
