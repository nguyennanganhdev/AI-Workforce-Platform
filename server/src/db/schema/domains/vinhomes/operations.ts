/** Physical model for domains/vinhomes/operations. See docs/erd/README.md. */
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
import { allowedValues, createdAt, jsonb, mutableColumns } from "../../columns";
import { platformTenant, users } from "../../platform/identity";
import { vhProject, vhTower } from "./property";

export const vhIncident = pgTable(
  "vh_incident",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    towerId: uuid("tower_id"),
    category: text("category").notNull(),
    title: text("title").notNull(),
    locationJson: jsonb("location_json").notNull(),
    severity: text("severity", {
      enum: ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
    }).notNull(),
    status: text("status", {
      enum: ["NEW", "OPEN", "RESOLVED", "CLOSED"],
    }).notNull(),
    stage: text("stage", {
      enum: [
        "INTAKE",
        "TRIAGE",
        "PLANNING",
        "EXECUTION",
        "QC",
        "RESIDENT_CONFIRMATION",
      ],
    }).notNull(),
    ownerUserId: text("owner_user_id"),
    slaDueAt: timestamp("sla_due_at", { withTimezone: true }),
    resolvedAt: timestamp("resolved_at", { withTimezone: true }),
    resolutionVersion: bigint("resolution_version", { mode: "bigint" }),
    closedAt: timestamp("closed_at", { withTimezone: true }),
    closedByUserId: text("closed_by_user_id"),
    closureReason: text("closure_reason"),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_incident_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_incident_uq_0").on(t.tenantId, t.id),
    unique("vh_incident_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_incident_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_incident_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_incident_fk_2",
      columns: [t.tenantId, t.projectId, t.towerId],
      foreignColumns: [vhTower.tenantId, vhTower.projectId, vhTower.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_incident_fk_3",
      columns: [t.ownerUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_incident_fk_4",
      columns: [t.closedByUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("vh_incident_ix_0").on(t.tenantId, t.projectId, t.towerId),
    index("vh_incident_ix_1").on(t.tenantId, t.projectId),
    index("vh_incident_ix_2").on(t.closedByUserId),
    index("vh_incident_ix_3").on(t.tenantId, t.projectId, t.status, t.severity),
    index("vh_incident_ix_4").on(t.ownerUserId),
    index("vh_incident_ix_5").on(t.tenantId, t.towerId, t.status),
    allowedValues("vh_incident_severity_ck", t.severity, [
      "LOW",
      "MEDIUM",
      "HIGH",
      "CRITICAL",
    ]),
    allowedValues("vh_incident_status_ck", t.status, [
      "NEW",
      "OPEN",
      "RESOLVED",
      "CLOSED",
    ]),
    allowedValues("vh_incident_stage_ck", t.stage, [
      "INTAKE",
      "TRIAGE",
      "PLANNING",
      "EXECUTION",
      "QC",
      "RESIDENT_CONFIRMATION",
    ]),
    check(
      "vh_incident_ck_0",
      sql`status NOT IN ('RESOLVED','CLOSED') OR (resolved_at IS NOT NULL AND resolution_version IS NOT NULL)`,
    ),
    check(
      "vh_incident_ck_1",
      sql`status <> 'CLOSED' OR (closed_at IS NOT NULL AND closed_by_user_id IS NOT NULL AND closure_reason IS NOT NULL)`,
    ),
    check("vh_incident_ck_2", sql`version > 0`),
  ],
).enableRLS();

export const vhIncidentRelation = pgTable(
  "vh_incident_relation",
  {
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    sourceIncidentId: uuid("source_incident_id").notNull(),
    targetIncidentId: uuid("target_incident_id").notNull(),
    relationType: text("relation_type", {
      enum: ["RELATED", "DUPLICATE", "CAUSED_BY", "BLOCKS", "RECURRING_WITH"],
    }).notNull(),
    reason: text("reason").notNull(),
    createdBy: text("created_by").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_incident_relation_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({
      columns: [
        t.tenantId,
        t.sourceIncidentId,
        t.targetIncidentId,
        t.relationType,
      ],
    }),
    foreignKey({
      name: "vh_incident_relation_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_incident_relation_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_incident_relation_fk_2",
      columns: [t.tenantId, t.projectId, t.sourceIncidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_incident_relation_fk_3",
      columns: [t.tenantId, t.projectId, t.targetIncidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_incident_relation_fk_4",
      columns: [t.createdBy],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("vh_incident_relation_ix_0").on(
      t.tenantId,
      t.projectId,
      t.targetIncidentId,
    ),
    index("vh_incident_relation_ix_1").on(
      t.tenantId,
      t.projectId,
      t.sourceIncidentId,
    ),
    index("vh_incident_relation_ix_2").on(t.createdBy),
    index("vh_incident_relation_ix_3").on(t.tenantId, t.projectId),
    allowedValues("vh_incident_relation_relation_type_ck", t.relationType, [
      "RELATED",
      "DUPLICATE",
      "CAUSED_BY",
      "BLOCKS",
      "RECURRING_WITH",
    ]),
    check(
      "vh_incident_relation_ck_0",
      sql`source_incident_id <> target_incident_id`,
    ),
  ],
).enableRLS();

export const vhTask = pgTable(
  "vh_task",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    incidentId: uuid("incident_id").notNull(),
    title: text("title").notNull(),
    domainType: text("domain_type").notNull(),
    domainData: jsonb("domain_data").notNull(),
    domainSchemaVersion: integer("domain_schema_version").notNull(),
    assigneeType: text("assignee_type", {
      enum: ["HUMAN", "SYSTEM", "AUTOMATION", "EXTERNAL_SERVICE"],
    }).notNull(),
    assigneeId: text("assignee_id"),
    status: text("status", {
      enum: ["OPEN", "ASSIGNED", "IN_PROGRESS", "BLOCKED", "DONE", "CANCELLED"],
    }).notNull(),
    priority: integer("priority").notNull(),
    required: boolean("required").notNull(),
    dueAt: timestamp("due_at", { withTimezone: true }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_task_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_task_uq_0").on(t.tenantId, t.id),
    unique("vh_task_uq_1").on(t.tenantId, t.projectId, t.id),
    unique("vh_task_uq_2").on(t.tenantId, t.projectId, t.incidentId, t.id),
    foreignKey({
      name: "vh_task_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_task_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_task_fk_2",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    index("vh_task_ix_0").on(t.tenantId, t.incidentId, t.status),
    index("vh_task_ix_1").on(t.tenantId, t.projectId),
    index("vh_task_ix_2").on(t.tenantId, t.projectId, t.incidentId),
    allowedValues("vh_task_assignee_type_ck", t.assigneeType, [
      "HUMAN",
      "SYSTEM",
      "AUTOMATION",
      "EXTERNAL_SERVICE",
    ]),
    allowedValues("vh_task_status_ck", t.status, [
      "OPEN",
      "ASSIGNED",
      "IN_PROGRESS",
      "BLOCKED",
      "DONE",
      "CANCELLED",
    ]),
    check("vh_task_ck_0", sql`domain_schema_version > 0`),
    check("vh_task_ck_1", sql`priority >= 0`),
    check("vh_task_ck_2", sql`version > 0`),
  ],
).enableRLS();

export const vhTaskDependency = pgTable(
  "vh_task_dependency",
  {
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    incidentId: uuid("incident_id").notNull(),
    taskId: uuid("task_id").notNull(),
    dependsOnTaskId: uuid("depends_on_task_id").notNull(),
    dependencyType: text("dependency_type", {
      enum: ["FINISH_TO_START", "FINISH_TO_FINISH"],
    }).notNull(),
    required: boolean("required").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_task_dependency_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({ columns: [t.tenantId, t.taskId, t.dependsOnTaskId] }),
    foreignKey({
      name: "vh_task_dependency_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_task_dependency_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_task_dependency_fk_2",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_task_dependency_fk_3",
      columns: [t.tenantId, t.projectId, t.incidentId, t.taskId],
      foreignColumns: [
        vhTask.tenantId,
        vhTask.projectId,
        vhTask.incidentId,
        vhTask.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_task_dependency_fk_4",
      columns: [t.tenantId, t.projectId, t.incidentId, t.dependsOnTaskId],
      foreignColumns: [
        vhTask.tenantId,
        vhTask.projectId,
        vhTask.incidentId,
        vhTask.id,
      ],
    }).onDelete("restrict"),
    index("vh_task_dependency_ix_0").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
    ),
    index("vh_task_dependency_ix_1").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.dependsOnTaskId,
    ),
    index("vh_task_dependency_ix_2").on(t.tenantId, t.projectId),
    index("vh_task_dependency_ix_3").on(t.tenantId, t.projectId, t.incidentId),
    allowedValues("vh_task_dependency_dependency_type_ck", t.dependencyType, [
      "FINISH_TO_START",
      "FINISH_TO_FINISH",
    ]),
    check("vh_task_dependency_ck_0", sql`task_id <> depends_on_task_id`),
  ],
).enableRLS();

export const vhActionRequest = pgTable(
  "vh_action_request",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    incidentId: uuid("incident_id").notNull(),
    taskId: uuid("task_id").notNull(),
    requestedByType: text("requested_by_type", {
      enum: ["HUMAN", "SYSTEM", "AUTOMATION", "AGENT", "EXTERNAL_SERVICE"],
    }).notNull(),
    requestedById: text("requested_by_id").notNull(),
    requestedByVersion: text("requested_by_version"),
    actionType: text("action_type").notNull(),
    targetType: text("target_type").notNull(),
    targetId: text("target_id"),
    payload: jsonb("payload").notNull(),
    payloadHash: text("payload_hash").notNull(),
    policyVersion: text("policy_version").notNull(),
    expectedSubjectVersion: bigint("expected_subject_version", {
      mode: "bigint",
    }).notNull(),
    idempotencyKey: text("idempotency_key").notNull(),
    status: text("status", {
      enum: [
        "PROPOSED",
        "DENIED",
        "AWAITING_APPROVAL",
        "AUTHORIZED",
        "REJECTED",
        "EXPIRED",
        "EXECUTING",
        "SUCCEEDED",
        "FAILED",
      ],
    }).notNull(),
    correlationId: text("correlation_id").notNull(),
    traceId: text("trace_id").notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_action_request_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_action_request_uq_0").on(t.tenantId, t.idempotencyKey),
    unique("vh_action_request_uq_1").on(t.tenantId, t.id),
    unique("vh_action_request_uq_2").on(t.tenantId, t.projectId, t.id),
    unique("vh_action_request_uq_3").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
      t.id,
    ),
    unique("vh_action_request_uq_4").on(t.tenantId, t.id, t.payloadHash),
    unique("vh_action_request_uq_5").on(t.tenantId, t.id, t.policyVersion),
    foreignKey({
      name: "vh_action_request_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_action_request_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_action_request_fk_2",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_action_request_fk_3",
      columns: [t.tenantId, t.projectId, t.incidentId, t.taskId],
      foreignColumns: [
        vhTask.tenantId,
        vhTask.projectId,
        vhTask.incidentId,
        vhTask.id,
      ],
    }).onDelete("restrict"),
    index("vh_action_request_ix_0").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
    ),
    index("vh_action_request_ix_1").on(t.tenantId, t.incidentId, t.status),
    index("vh_action_request_ix_2").on(t.tenantId, t.projectId),
    index("vh_action_request_ix_3").on(t.tenantId, t.projectId, t.incidentId),
    allowedValues("vh_action_request_requested_by_type_ck", t.requestedByType, [
      "HUMAN",
      "SYSTEM",
      "AUTOMATION",
      "AGENT",
      "EXTERNAL_SERVICE",
    ]),
    allowedValues("vh_action_request_status_ck", t.status, [
      "PROPOSED",
      "DENIED",
      "AWAITING_APPROVAL",
      "AUTHORIZED",
      "REJECTED",
      "EXPIRED",
      "EXECUTING",
      "SUCCEEDED",
      "FAILED",
    ]),
    check("vh_action_request_ck_0", sql`expected_subject_version > 0`),
    check("vh_action_request_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const vhRuleEvaluation = pgTable(
  "vh_rule_evaluation",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    actionRequestId: uuid("action_request_id").notNull(),
    actionPayloadHash: text("action_payload_hash").notNull(),
    decision: text("decision", {
      enum: ["ALLOW", "REQUIRE_APPROVAL", "DENY"],
    }).notNull(),
    reasonCode: text("reason_code").notNull(),
    ruleVersion: text("rule_version").notNull(),
    evaluatedAt: timestamp("evaluated_at", { withTimezone: true }).notNull(),
    correlationId: text("correlation_id").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_rule_evaluation_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_rule_evaluation_uq_0").on(t.tenantId, t.id),
    unique("vh_rule_evaluation_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_rule_evaluation_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_rule_evaluation_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_rule_evaluation_fk_2",
      columns: [t.tenantId, t.projectId, t.actionRequestId],
      foreignColumns: [
        vhActionRequest.tenantId,
        vhActionRequest.projectId,
        vhActionRequest.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_rule_evaluation_fk_3",
      columns: [t.tenantId, t.actionRequestId, t.actionPayloadHash],
      foreignColumns: [
        vhActionRequest.tenantId,
        vhActionRequest.id,
        vhActionRequest.payloadHash,
      ],
    }).onDelete("restrict"),
    index("vh_rule_evaluation_ix_0").on(
      t.tenantId,
      t.projectId,
      t.actionRequestId,
    ),
    index("vh_rule_evaluation_ix_1").on(t.tenantId, t.projectId),
    allowedValues("vh_rule_evaluation_decision_ck", t.decision, [
      "ALLOW",
      "REQUIRE_APPROVAL",
      "DENY",
    ]),
  ],
).enableRLS();

export const vhActionApproval = pgTable(
  "vh_action_approval",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    actionRequestId: uuid("action_request_id").notNull(),
    actionPayloadHash: text("action_payload_hash").notNull(),
    policyVersion: text("policy_version").notNull(),
    status: text("status", {
      enum: ["PENDING", "APPROVED", "REJECTED", "EXPIRED"],
    }).notNull(),
    requestedById: text("requested_by_id").notNull(),
    reviewerId: text("reviewer_id"),
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
    decidedAt: timestamp("decided_at", { withTimezone: true }),
    reason: text("reason"),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_action_approval_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_action_approval_uq_0").on(t.tenantId, t.id),
    unique("vh_action_approval_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_action_approval_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_action_approval_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_action_approval_fk_2",
      columns: [t.tenantId, t.projectId, t.actionRequestId],
      foreignColumns: [
        vhActionRequest.tenantId,
        vhActionRequest.projectId,
        vhActionRequest.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_action_approval_fk_3",
      columns: [t.reviewerId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_action_approval_fk_4",
      columns: [t.tenantId, t.actionRequestId, t.actionPayloadHash],
      foreignColumns: [
        vhActionRequest.tenantId,
        vhActionRequest.id,
        vhActionRequest.payloadHash,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_action_approval_fk_5",
      columns: [t.tenantId, t.actionRequestId, t.policyVersion],
      foreignColumns: [
        vhActionRequest.tenantId,
        vhActionRequest.id,
        vhActionRequest.policyVersion,
      ],
    }).onDelete("restrict"),
    index("vh_action_approval_ix_0").on(
      t.tenantId,
      t.projectId,
      t.actionRequestId,
    ),
    index("vh_action_approval_ix_1").on(t.reviewerId),
    index("vh_action_approval_ix_2").on(t.tenantId, t.status, t.expiresAt),
    index("vh_action_approval_ix_3").on(t.tenantId, t.projectId),
    allowedValues("vh_action_approval_status_ck", t.status, [
      "PENDING",
      "APPROVED",
      "REJECTED",
      "EXPIRED",
    ]),
    check(
      "vh_action_approval_ck_0",
      sql`status NOT IN ('APPROVED','REJECTED') OR (reviewer_id IS NOT NULL AND decided_at IS NOT NULL)`,
    ),
    check("vh_action_approval_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const vhExecutionGrant = pgTable(
  "vh_execution_grant",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    actionRequestId: uuid("action_request_id").notNull(),
    actionPayloadHash: text("action_payload_hash").notNull(),
    policyVersion: text("policy_version").notNull(),
    tokenHash: text("token_hash").notNull(),
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
    consumedAt: timestamp("consumed_at", { withTimezone: true }),
    status: text("status", {
      enum: ["ACTIVE", "CONSUMED", "EXPIRED", "REVOKED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_execution_grant_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_execution_grant_uq_0").on(t.tenantId, t.tokenHash),
    unique("vh_execution_grant_uq_1").on(t.tenantId, t.id),
    unique("vh_execution_grant_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_execution_grant_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_execution_grant_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_execution_grant_fk_2",
      columns: [t.tenantId, t.projectId, t.actionRequestId],
      foreignColumns: [
        vhActionRequest.tenantId,
        vhActionRequest.projectId,
        vhActionRequest.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_execution_grant_fk_3",
      columns: [t.tenantId, t.actionRequestId, t.actionPayloadHash],
      foreignColumns: [
        vhActionRequest.tenantId,
        vhActionRequest.id,
        vhActionRequest.payloadHash,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_execution_grant_fk_4",
      columns: [t.tenantId, t.actionRequestId, t.policyVersion],
      foreignColumns: [
        vhActionRequest.tenantId,
        vhActionRequest.id,
        vhActionRequest.policyVersion,
      ],
    }).onDelete("restrict"),
    index("vh_execution_grant_ix_0").on(
      t.tenantId,
      t.projectId,
      t.actionRequestId,
    ),
    index("vh_execution_grant_ix_1").on(t.tenantId, t.projectId),
    allowedValues("vh_execution_grant_status_ck", t.status, [
      "ACTIVE",
      "CONSUMED",
      "EXPIRED",
      "REVOKED",
    ]),
    check(
      "vh_execution_grant_ck_0",
      sql`status <> 'CONSUMED' OR consumed_at IS NOT NULL`,
    ),
    check("vh_execution_grant_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const vhChecklist = pgTable(
  "vh_checklist",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    code: text("code").notNull(),
    name: text("name").notNull(),
    category: text("category").notNull(),
    status: text("status", { enum: ["ACTIVE", "RETIRED"] }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_checklist_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_checklist_uq_0").on(t.tenantId, t.code),
    unique("vh_checklist_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "vh_checklist_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    allowedValues("vh_checklist_status_ck", t.status, ["ACTIVE", "RETIRED"]),
    check("vh_checklist_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const vhChecklistVersion = pgTable(
  "vh_checklist_version",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    checklistId: uuid("checklist_id").notNull(),
    versionNo: integer("version_no").notNull(),
    criteriaJson: jsonb("criteria_json").notNull(),
    status: text("status", {
      enum: ["DRAFT", "PUBLISHED", "RETIRED"],
    }).notNull(),
    publishedAt: timestamp("published_at", { withTimezone: true }),
    createdBy: text("created_by").notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_checklist_version_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_checklist_version_uq_0").on(
      t.tenantId,
      t.checklistId,
      t.versionNo,
    ),
    unique("vh_checklist_version_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "vh_checklist_version_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_checklist_version_fk_1",
      columns: [t.tenantId, t.checklistId],
      foreignColumns: [vhChecklist.tenantId, vhChecklist.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_checklist_version_fk_2",
      columns: [t.createdBy],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("vh_checklist_version_ix_0").on(t.createdBy),
    index("vh_checklist_version_ix_1").on(t.tenantId, t.checklistId),
    allowedValues("vh_checklist_version_status_ck", t.status, [
      "DRAFT",
      "PUBLISHED",
      "RETIRED",
    ]),
    check("vh_checklist_version_ck_0", sql`version_no > 0`),
    check("vh_checklist_version_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const vhWorkOrder = pgTable(
  "vh_work_order",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    incidentId: uuid("incident_id").notNull(),
    taskId: uuid("task_id").notNull(),
    actionRequestId: uuid("action_request_id").notNull(),
    executorType: text("executor_type", {
      enum: ["HUMAN", "SYSTEM", "AUTOMATION", "EXTERNAL_SERVICE"],
    }).notNull(),
    executorId: text("executor_id"),
    status: text("status", {
      enum: [
        "OPEN",
        "ASSIGNED",
        "IN_PROGRESS",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
      ],
    }).notNull(),
    attemptNo: integer("attempt_no").notNull(),
    redoOfWorkOrderId: uuid("redo_of_work_order_id"),
    checklistVersionId: uuid("checklist_version_id"),
    executionStartedAt: timestamp("execution_started_at", {
      withTimezone: true,
    }),
    executionCompletedAt: timestamp("execution_completed_at", {
      withTimezone: true,
    }),
    result: jsonb("result").notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_work_order_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_work_order_uq_0").on(t.tenantId, t.taskId, t.attemptNo),
    unique("vh_work_order_uq_1").on(t.tenantId, t.redoOfWorkOrderId),
    unique("vh_work_order_uq_2").on(t.tenantId, t.id),
    unique("vh_work_order_uq_3").on(t.tenantId, t.projectId, t.id),
    unique("vh_work_order_uq_4").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
      t.id,
    ),
    foreignKey({
      name: "vh_work_order_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_order_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_order_fk_2",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_order_fk_3",
      columns: [t.tenantId, t.projectId, t.incidentId, t.taskId],
      foreignColumns: [
        vhTask.tenantId,
        vhTask.projectId,
        vhTask.incidentId,
        vhTask.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_order_fk_4",
      columns: [
        t.tenantId,
        t.projectId,
        t.incidentId,
        t.taskId,
        t.actionRequestId,
      ],
      foreignColumns: [
        vhActionRequest.tenantId,
        vhActionRequest.projectId,
        vhActionRequest.incidentId,
        vhActionRequest.taskId,
        vhActionRequest.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_order_fk_5",
      columns: [
        t.tenantId,
        t.projectId,
        t.incidentId,
        t.taskId,
        t.redoOfWorkOrderId,
      ],
      foreignColumns: [t.tenantId, t.projectId, t.incidentId, t.taskId, t.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_order_fk_6",
      columns: [t.tenantId, t.checklistVersionId],
      foreignColumns: [vhChecklistVersion.tenantId, vhChecklistVersion.id],
    }).onDelete("restrict"),
    index("vh_work_order_ix_0").on(t.tenantId, t.checklistVersionId),
    index("vh_work_order_ix_1").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
      t.redoOfWorkOrderId,
    ),
    index("vh_work_order_ix_2").on(t.tenantId, t.projectId),
    index("vh_work_order_ix_3").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
    ),
    index("vh_work_order_ix_4").on(t.tenantId, t.projectId, t.incidentId),
    index("vh_work_order_ix_5").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
      t.actionRequestId,
    ),
    allowedValues("vh_work_order_executor_type_ck", t.executorType, [
      "HUMAN",
      "SYSTEM",
      "AUTOMATION",
      "EXTERNAL_SERVICE",
    ]),
    allowedValues("vh_work_order_status_ck", t.status, [
      "OPEN",
      "ASSIGNED",
      "IN_PROGRESS",
      "COMPLETED",
      "FAILED",
      "CANCELLED",
    ]),
    check("vh_work_order_ck_0", sql`attempt_no > 0`),
    check(
      "vh_work_order_ck_1",
      sql`redo_of_work_order_id IS NULL OR redo_of_work_order_id <> id`,
    ),
    check(
      "vh_work_order_ck_2",
      sql`execution_completed_at IS NULL OR execution_completed_at >= execution_started_at`,
    ),
    check("vh_work_order_ck_3", sql`version > 0`),
  ],
).enableRLS();
