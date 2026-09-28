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
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, mutableColumns } from "../../columns";
import { platformTenant, users } from "../../platform/identity";
import { vhIncident } from "./operations";
import { vhProject } from "./property";
import { vhTeam } from "./workforce";

export const vhSlaPolicy = pgTable(
  "vh_sla_policy",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    code: text("code").notNull(),
    versionNo: integer("version_no").notNull(),
    category: text("category").notNull(),
    severity: text("severity", {
      enum: ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
    }).notNull(),
    responseMinutes: integer("response_minutes").notNull(),
    resolutionMinutes: integer("resolution_minutes").notNull(),
    clockType: text("clock_type").notNull(),
    calendarRef: text("calendar_ref"),
    effectiveFrom: timestamp("effective_from", {
      withTimezone: true,
    }).notNull(),
    effectiveUntil: timestamp("effective_until", { withTimezone: true }),
    status: text("status", {
      enum: ["DRAFT", "PUBLISHED", "RETIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_sla_policy_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_sla_policy_uq_0").on(
      t.tenantId,
      t.projectId,
      t.code,
      t.versionNo,
    ),
    unique("vh_sla_policy_uq_1").on(t.tenantId, t.id),
    unique("vh_sla_policy_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_sla_policy_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_sla_policy_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    index("vh_sla_policy_ix_1").on(t.tenantId, t.projectId),
    allowedValues("vh_sla_policy_severity_ck", t.severity, [
      "LOW",
      "MEDIUM",
      "HIGH",
      "CRITICAL",
    ]),
    allowedValues("vh_sla_policy_status_ck", t.status, [
      "DRAFT",
      "PUBLISHED",
      "RETIRED",
    ]),
    check("vh_sla_policy_ck_0", sql`version_no > 0`),
    check("vh_sla_policy_ck_1", sql`clock_type = 'ELAPSED'`),
    check("vh_sla_policy_ck_2", sql`response_minutes > 0`),
    check("vh_sla_policy_ck_3", sql`resolution_minutes >= response_minutes`),
    check(
      "vh_sla_policy_ck_4",
      sql`effective_until IS NULL OR effective_until > effective_from`,
    ),
    check("vh_sla_policy_ck_5", sql`version > 0`),
  ],
).enableRLS();

export const vhIncidentSla = pgTable(
  "vh_incident_sla",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    incidentId: uuid("incident_id").notNull(),
    policyId: uuid("policy_id").notNull(),
    startedAt: timestamp("started_at", { withTimezone: true }).notNull(),
    responseDueAt: timestamp("response_due_at", {
      withTimezone: true,
    }).notNull(),
    resolutionDueAt: timestamp("resolution_due_at", {
      withTimezone: true,
    }).notNull(),
    respondedAt: timestamp("responded_at", { withTimezone: true }),
    resolvedAt: timestamp("resolved_at", { withTimezone: true }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_incident_sla_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_incident_sla_uq_0").on(t.tenantId, t.incidentId),
    unique("vh_incident_sla_uq_1").on(t.tenantId, t.id),
    unique("vh_incident_sla_uq_2").on(t.tenantId, t.projectId, t.id),
    unique("vh_incident_sla_uq_3").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.id,
    ),
    foreignKey({
      name: "vh_incident_sla_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_incident_sla_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_incident_sla_fk_2",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_incident_sla_fk_3",
      columns: [t.tenantId, t.projectId, t.policyId],
      foreignColumns: [
        vhSlaPolicy.tenantId,
        vhSlaPolicy.projectId,
        vhSlaPolicy.id,
      ],
    }).onDelete("restrict"),
    index("vh_incident_sla_ix_1").on(t.tenantId, t.projectId),
    index("vh_incident_sla_response_ix")
      .on(t.tenantId, t.responseDueAt)
      .where(sql`${t.respondedAt} is null`),
    index("vh_incident_sla_resolution_ix")
      .on(t.tenantId, t.resolutionDueAt)
      .where(sql`${t.resolvedAt} is null`),
    index("vh_incident_sla_ix_2").on(t.tenantId, t.projectId, t.incidentId),
    index("vh_incident_sla_ix_3").on(t.tenantId, t.projectId, t.policyId),
    check("vh_incident_sla_ck_0", sql`response_due_at >= started_at`),
    check("vh_incident_sla_ck_1", sql`resolution_due_at >= response_due_at`),
    check(
      "vh_incident_sla_ck_2",
      sql`responded_at IS NULL OR responded_at >= started_at`,
    ),
    check(
      "vh_incident_sla_ck_3",
      sql`resolved_at IS NULL OR resolved_at >= started_at`,
    ),
    check("vh_incident_sla_ck_4", sql`version > 0`),
  ],
).enableRLS();

export const vhEscalation = pgTable(
  "vh_escalation",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    incidentId: uuid("incident_id").notNull(),
    incidentSlaId: uuid("incident_sla_id"),
    assignedTeamId: uuid("assigned_team_id"),
    reason: text("reason", {
      enum: ["RESPONSE_BREACH", "RESOLUTION_BREACH", "SAFETY", "MANUAL"],
    }).notNull(),
    level: integer("level").notNull(),
    raisedByType: text("raised_by_type", {
      enum: ["HUMAN", "SYSTEM", "AGENT"],
    }).notNull(),
    raisedById: text("raised_by_id").notNull(),
    raisedAt: timestamp("raised_at", { withTimezone: true }).notNull(),
    status: text("status", {
      enum: ["OPEN", "ACKNOWLEDGED", "RESOLVED"],
    }).notNull(),
    acknowledgedByUserId: text("acknowledged_by_user_id"),
    acknowledgedAt: timestamp("acknowledged_at", { withTimezone: true }),
    resolvedAt: timestamp("resolved_at", { withTimezone: true }),
    resolutionNote: text("resolution_note"),
    idempotencyKey: text("idempotency_key").notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_escalation_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_escalation_uq_0").on(t.tenantId, t.idempotencyKey),
    unique("vh_escalation_uq_1").on(t.tenantId, t.id),
    unique("vh_escalation_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_escalation_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_escalation_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_escalation_fk_2",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_escalation_fk_3",
      columns: [t.tenantId, t.projectId, t.incidentId, t.incidentSlaId],
      foreignColumns: [
        vhIncidentSla.tenantId,
        vhIncidentSla.projectId,
        vhIncidentSla.incidentId,
        vhIncidentSla.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_escalation_fk_4",
      columns: [t.tenantId, t.projectId, t.assignedTeamId],
      foreignColumns: [vhTeam.tenantId, vhTeam.projectId, vhTeam.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_escalation_fk_5",
      columns: [t.acknowledgedByUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("vh_escalation_ix_0").on(t.acknowledgedByUserId),
    index("vh_escalation_ix_2").on(t.tenantId, t.projectId),
    index("vh_escalation_ix_3").on(t.tenantId, t.projectId, t.assignedTeamId),
    index("vh_escalation_ix_4").on(t.tenantId, t.projectId, t.incidentId),
    index("vh_escalation_ix_5").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.incidentSlaId,
    ),
    allowedValues("vh_escalation_reason_ck", t.reason, [
      "RESPONSE_BREACH",
      "RESOLUTION_BREACH",
      "SAFETY",
      "MANUAL",
    ]),
    allowedValues("vh_escalation_raised_by_type_ck", t.raisedByType, [
      "HUMAN",
      "SYSTEM",
      "AGENT",
    ]),
    allowedValues("vh_escalation_status_ck", t.status, [
      "OPEN",
      "ACKNOWLEDGED",
      "RESOLVED",
    ]),
    check("vh_escalation_ck_0", sql`level > 0`),
    check(
      "vh_escalation_ck_1",
      sql`status NOT IN ('ACKNOWLEDGED','RESOLVED') OR (acknowledged_by_user_id IS NOT NULL AND acknowledged_at IS NOT NULL)`,
    ),
    check(
      "vh_escalation_ck_2",
      sql`status<>'RESOLVED' OR (resolved_at IS NOT NULL AND resolution_note IS NOT NULL)`,
    ),
    check("vh_escalation_ck_3", sql`version > 0`),
  ],
).enableRLS();
