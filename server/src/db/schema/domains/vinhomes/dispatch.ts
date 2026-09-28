/** Persistence for coordination and field operations. See docs/erd/SYSTEM_FLOW.md. */
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
  uniqueIndex,
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, mutableColumns } from "../../columns";
import { platformTenant, users } from "../../platform/identity";
import { vhBusinessEvent } from "./communication";
import { vhResidentReport } from "./intake";
import { vhIncident, vhTask, vhWorkOrder } from "./operations";
import { vhProject } from "./property";
import { vhTeam, vhTeamMember } from "./workforce";

export const vhWorkAssignment = pgTable(
  "vh_work_assignment",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    incidentId: uuid("incident_id").notNull(),
    taskId: uuid("task_id").notNull(),
    workOrderId: uuid("work_order_id").notNull(),
    teamId: uuid("team_id").notNull(),
    teamMemberId: uuid("team_member_id"),
    assignedByUserId: text("assigned_by_user_id").notNull(),
    offeredAt: timestamp("offered_at", { withTimezone: true }).notNull(),
    respondBy: timestamp("respond_by", { withTimezone: true }),
    acceptedAt: timestamp("accepted_at", { withTimezone: true }),
    endedAt: timestamp("ended_at", { withTimezone: true }),
    status: text("status", {
      enum: ["OFFERED", "ACCEPTED", "REJECTED", "RELEASED", "COMPLETED"],
    }).notNull(),
    reason: text("reason"),
    idempotencyKey: text("idempotency_key").notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_work_assignment_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_work_assignment_uq_0").on(t.tenantId, t.idempotencyKey),
    unique("vh_work_assignment_uq_1").on(t.tenantId, t.id),
    unique("vh_work_assignment_uq_2").on(t.tenantId, t.projectId, t.id),
    unique("vh_work_assignment_uq_3").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
      t.workOrderId,
      t.id,
    ),
    foreignKey({
      name: "vh_work_assignment_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_assignment_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_assignment_fk_2",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_assignment_fk_3",
      columns: [t.tenantId, t.projectId, t.incidentId, t.taskId],
      foreignColumns: [
        vhTask.tenantId,
        vhTask.projectId,
        vhTask.incidentId,
        vhTask.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_assignment_fk_4",
      columns: [t.tenantId, t.projectId, t.incidentId, t.taskId, t.workOrderId],
      foreignColumns: [
        vhWorkOrder.tenantId,
        vhWorkOrder.projectId,
        vhWorkOrder.incidentId,
        vhWorkOrder.taskId,
        vhWorkOrder.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_assignment_fk_5",
      columns: [t.tenantId, t.projectId, t.teamId],
      foreignColumns: [vhTeam.tenantId, vhTeam.projectId, vhTeam.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_assignment_fk_6",
      columns: [t.tenantId, t.projectId, t.teamId, t.teamMemberId],
      foreignColumns: [
        vhTeamMember.tenantId,
        vhTeamMember.projectId,
        vhTeamMember.teamId,
        vhTeamMember.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_assignment_fk_7",
      columns: [t.assignedByUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("vh_work_assignment_ix_0").on(t.assignedByUserId),
    index("vh_work_assignment_ix_2").on(t.tenantId, t.projectId),
    index("vh_work_assignment_ix_3").on(t.tenantId, t.projectId, t.incidentId),
    index("vh_work_assignment_ix_4").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
    ),
    index("vh_work_assignment_ix_5").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
      t.workOrderId,
    ),
    index("vh_work_assignment_ix_6").on(t.tenantId, t.projectId, t.teamId),
    index("vh_work_assignment_ix_7").on(
      t.tenantId,
      t.projectId,
      t.teamId,
      t.teamMemberId,
    ),
    allowedValues("vh_work_assignment_status_ck", t.status, [
      "OFFERED",
      "ACCEPTED",
      "REJECTED",
      "RELEASED",
      "COMPLETED",
    ]),
    check(
      "vh_work_assignment_ck_0",
      sql`respond_by IS NULL OR respond_by > offered_at`,
    ),
    check(
      "vh_work_assignment_ck_1",
      sql`status<>'ACCEPTED' OR accepted_at IS NOT NULL`,
    ),
    check(
      "vh_work_assignment_ck_2",
      sql`status NOT IN ('REJECTED','RELEASED','COMPLETED') OR ended_at IS NOT NULL`,
    ),
    check("vh_work_assignment_ck_3", sql`version > 0`),
    uniqueIndex("vh_work_assignment_live_0")
      .on(t.tenantId, t.workOrderId)
      .where(sql`status IN ('OFFERED','ACCEPTED')`),
  ],
).enableRLS();

export const vhWorkAppointment = pgTable(
  "vh_work_appointment",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    incidentId: uuid("incident_id").notNull(),
    taskId: uuid("task_id").notNull(),
    workOrderId: uuid("work_order_id").notNull(),
    residentReportId: uuid("resident_report_id"),
    requestedByUserId: text("requested_by_user_id").notNull(),
    startsAt: timestamp("starts_at", { withTimezone: true }).notNull(),
    endsAt: timestamp("ends_at", { withTimezone: true }).notNull(),
    timezone: text("timezone").notNull(),
    status: text("status", {
      enum: ["PROPOSED", "CONFIRMED", "COMPLETED", "CANCELLED"],
    }).notNull(),
    confirmedByUserId: text("confirmed_by_user_id"),
    confirmedAt: timestamp("confirmed_at", { withTimezone: true }),
    cancellationReason: text("cancellation_reason"),
    idempotencyKey: text("idempotency_key").notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_work_appointment_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_work_appointment_uq_0").on(t.tenantId, t.idempotencyKey),
    unique("vh_work_appointment_uq_1").on(t.tenantId, t.id),
    unique("vh_work_appointment_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_work_appointment_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_appointment_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_appointment_fk_2",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_appointment_fk_3",
      columns: [t.tenantId, t.projectId, t.incidentId, t.taskId],
      foreignColumns: [
        vhTask.tenantId,
        vhTask.projectId,
        vhTask.incidentId,
        vhTask.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_appointment_fk_4",
      columns: [t.tenantId, t.projectId, t.incidentId, t.taskId, t.workOrderId],
      foreignColumns: [
        vhWorkOrder.tenantId,
        vhWorkOrder.projectId,
        vhWorkOrder.incidentId,
        vhWorkOrder.taskId,
        vhWorkOrder.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_appointment_fk_5",
      columns: [t.tenantId, t.projectId, t.residentReportId],
      foreignColumns: [
        vhResidentReport.tenantId,
        vhResidentReport.projectId,
        vhResidentReport.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_appointment_fk_6",
      columns: [t.requestedByUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_appointment_fk_7",
      columns: [t.confirmedByUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("vh_work_appointment_ix_0").on(t.confirmedByUserId),
    index("vh_work_appointment_ix_1").on(t.requestedByUserId),
    index("vh_work_appointment_ix_3").on(t.tenantId, t.projectId),
    index("vh_work_appointment_ix_4").on(t.tenantId, t.projectId, t.incidentId),
    index("vh_work_appointment_ix_5").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
    ),
    index("vh_work_appointment_ix_6").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
      t.workOrderId,
    ),
    index("vh_work_appointment_ix_7").on(
      t.tenantId,
      t.projectId,
      t.residentReportId,
    ),
    allowedValues("vh_work_appointment_status_ck", t.status, [
      "PROPOSED",
      "CONFIRMED",
      "COMPLETED",
      "CANCELLED",
    ]),
    check("vh_work_appointment_ck_0", sql`ends_at > starts_at`),
    check(
      "vh_work_appointment_ck_1",
      sql`status NOT IN ('CONFIRMED','COMPLETED') OR (confirmed_by_user_id IS NOT NULL AND confirmed_at IS NOT NULL)`,
    ),
    check("vh_work_appointment_ck_2", sql`version > 0`),
  ],
).enableRLS();

export const vhWorkProgress = pgTable(
  "vh_work_progress",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    incidentId: uuid("incident_id").notNull(),
    taskId: uuid("task_id").notNull(),
    workOrderId: uuid("work_order_id").notNull(),
    assignmentId: uuid("assignment_id"),
    businessEventId: uuid("business_event_id").notNull(),
    actorUserId: text("actor_user_id").notNull(),
    stage: text("stage", {
      enum: [
        "ACKNOWLEDGED",
        "EN_ROUTE",
        "ON_SITE",
        "DIAGNOSING",
        "WAITING_PARTS",
        "WAITING_ACCESS",
        "REPAIRING",
        "READY_FOR_QC",
        "COMPLETED",
      ],
    }).notNull(),
    percentComplete: integer("percent_complete"),
    expectedCompletionAt: timestamp("expected_completion_at", {
      withTimezone: true,
    }),
    estimatedByUserId: text("estimated_by_user_id"),
    estimateReason: text("estimate_reason"),
    note: text("note").notNull(),
    occurredAt: timestamp("occurred_at", { withTimezone: true }).notNull(),
    idempotencyKey: text("idempotency_key").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_work_progress_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_work_progress_uq_0").on(t.tenantId, t.idempotencyKey),
    unique("vh_work_progress_uq_1").on(t.tenantId, t.businessEventId),
    unique("vh_work_progress_uq_2").on(t.tenantId, t.id),
    unique("vh_work_progress_uq_3").on(t.tenantId, t.projectId, t.id),
    unique("vh_work_progress_uq_4").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.id,
    ),
    foreignKey({
      name: "vh_work_progress_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_progress_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_progress_fk_2",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_progress_fk_3",
      columns: [t.tenantId, t.projectId, t.incidentId, t.taskId],
      foreignColumns: [
        vhTask.tenantId,
        vhTask.projectId,
        vhTask.incidentId,
        vhTask.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_progress_fk_4",
      columns: [t.tenantId, t.projectId, t.incidentId, t.taskId, t.workOrderId],
      foreignColumns: [
        vhWorkOrder.tenantId,
        vhWorkOrder.projectId,
        vhWorkOrder.incidentId,
        vhWorkOrder.taskId,
        vhWorkOrder.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_progress_fk_5",
      columns: [
        t.tenantId,
        t.projectId,
        t.incidentId,
        t.taskId,
        t.workOrderId,
        t.assignmentId,
      ],
      foreignColumns: [
        vhWorkAssignment.tenantId,
        vhWorkAssignment.projectId,
        vhWorkAssignment.incidentId,
        vhWorkAssignment.taskId,
        vhWorkAssignment.workOrderId,
        vhWorkAssignment.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_progress_fk_6",
      columns: [t.tenantId, t.projectId, t.businessEventId],
      foreignColumns: [
        vhBusinessEvent.tenantId,
        vhBusinessEvent.projectId,
        vhBusinessEvent.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_progress_fk_7",
      columns: [t.actorUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_work_progress_fk_8",
      columns: [t.estimatedByUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("vh_work_progress_ix_0").on(t.actorUserId),
    index("vh_work_progress_ix_1").on(t.estimatedByUserId),
    index("vh_work_progress_ix_3").on(t.tenantId, t.projectId),
    index("vh_work_progress_ix_4").on(
      t.tenantId,
      t.projectId,
      t.businessEventId,
    ),
    index("vh_work_progress_ix_5").on(t.tenantId, t.projectId, t.incidentId),
    index("vh_work_progress_ix_6").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
    ),
    index("vh_work_progress_ix_7").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
      t.workOrderId,
    ),
    index("vh_work_progress_ix_8").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
      t.workOrderId,
      t.assignmentId,
    ),
    allowedValues("vh_work_progress_stage_ck", t.stage, [
      "ACKNOWLEDGED",
      "EN_ROUTE",
      "ON_SITE",
      "DIAGNOSING",
      "WAITING_PARTS",
      "WAITING_ACCESS",
      "REPAIRING",
      "READY_FOR_QC",
      "COMPLETED",
    ]),
    check(
      "vh_work_progress_ck_0",
      sql`percent_complete IS NULL OR percent_complete BETWEEN 0 AND 100`,
    ),
    check(
      "vh_work_progress_ck_1",
      sql`expected_completion_at IS NULL OR (estimated_by_user_id IS NOT NULL AND estimate_reason IS NOT NULL)`,
    ),
  ],
).enableRLS();
