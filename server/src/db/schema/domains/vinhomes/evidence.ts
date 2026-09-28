/** Physical model for domains/vinhomes/evidence. See docs/erd/README.md. */
import { sql } from "drizzle-orm";
import {
  boolean,
  check,
  foreignKey,
  index,
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
import { vhFileObject } from "./files";
import { vhIncident, vhTask, vhWorkOrder } from "./operations";
import { vhProject } from "./property";

export const vhEvidenceRef = pgTable(
  "vh_evidence_ref",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    incidentId: uuid("incident_id").notNull(),
    taskId: uuid("task_id"),
    workOrderId: uuid("work_order_id"),
    fileId: uuid("file_id").notNull(),
    kind: text("kind").notNull(),
    capturePhase: text("capture_phase", {
      enum: ["BEFORE", "AFTER", "QC", "OTHER"],
    }).notNull(),
    metadata: jsonb("metadata").notNull(),
    uploadedBy: text("uploaded_by").notNull(),
    visibility: text("visibility", {
      enum: ["INTERNAL", "RESIDENT_VISIBLE"],
    }).notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_evidence_ref_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_evidence_ref_uq_0").on(t.tenantId, t.id),
    unique("vh_evidence_ref_uq_1").on(t.tenantId, t.projectId, t.id),
    unique("vh_evidence_ref_uq_2").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.id,
    ),
    foreignKey({
      name: "vh_evidence_ref_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_evidence_ref_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_evidence_ref_fk_2",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_evidence_ref_fk_3",
      columns: [t.tenantId, t.projectId, t.incidentId, t.taskId],
      foreignColumns: [
        vhTask.tenantId,
        vhTask.projectId,
        vhTask.incidentId,
        vhTask.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_evidence_ref_fk_4",
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
      name: "vh_evidence_ref_fk_5",
      columns: [t.tenantId, t.fileId],
      foreignColumns: [vhFileObject.tenantId, vhFileObject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_evidence_ref_fk_6",
      columns: [t.uploadedBy],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("vh_evidence_ref_ix_0").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
      t.workOrderId,
    ),
    index("vh_evidence_ref_ix_1").on(t.tenantId, t.projectId),
    index("vh_evidence_ref_ix_2").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
    ),
    index("vh_evidence_ref_ix_3").on(t.tenantId, t.projectId, t.incidentId),
    index("vh_evidence_ref_ix_4").on(t.uploadedBy),
    index("vh_evidence_ref_ix_5").on(t.tenantId, t.fileId),
    allowedValues("vh_evidence_ref_capture_phase_ck", t.capturePhase, [
      "BEFORE",
      "AFTER",
      "QC",
      "OTHER",
    ]),
    allowedValues("vh_evidence_ref_visibility_ck", t.visibility, [
      "INTERNAL",
      "RESIDENT_VISIBLE",
    ]),
    check(
      "vh_evidence_ref_ck_0",
      sql`work_order_id IS NULL OR task_id IS NOT NULL`,
    ),
  ],
).enableRLS();

export const vhQcResult = pgTable(
  "vh_qc_result",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    incidentId: uuid("incident_id").notNull(),
    taskId: uuid("task_id").notNull(),
    workOrderId: uuid("work_order_id").notNull(),
    outcome: text("outcome", {
      enum: ["PASS", "FAIL", "INCONCLUSIVE"],
    }).notNull(),
    criteria: jsonb("criteria").notNull(),
    failedCriteria: jsonb("failed_criteria").notNull(),
    redoRequired: boolean("redo_required").notNull(),
    note: text("note"),
    checkedBy: text("checked_by").notNull(),
    checkedAt: timestamp("checked_at", { withTimezone: true }).notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_qc_result_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_qc_result_uq_0").on(t.tenantId, t.id),
    unique("vh_qc_result_uq_1").on(t.tenantId, t.projectId, t.id),
    unique("vh_qc_result_uq_2").on(t.tenantId, t.projectId, t.incidentId, t.id),
    foreignKey({
      name: "vh_qc_result_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_qc_result_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_qc_result_fk_2",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_qc_result_fk_3",
      columns: [t.tenantId, t.projectId, t.incidentId, t.taskId],
      foreignColumns: [
        vhTask.tenantId,
        vhTask.projectId,
        vhTask.incidentId,
        vhTask.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_qc_result_fk_4",
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
      name: "vh_qc_result_fk_5",
      columns: [t.checkedBy],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("vh_qc_result_ix_0").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
      t.workOrderId,
    ),
    index("vh_qc_result_ix_1").on(t.tenantId, t.projectId),
    index("vh_qc_result_ix_2").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.taskId,
    ),
    index("vh_qc_result_ix_3").on(t.tenantId, t.projectId, t.incidentId),
    index("vh_qc_result_ix_4").on(t.checkedBy),
    allowedValues("vh_qc_result_outcome_ck", t.outcome, [
      "PASS",
      "FAIL",
      "INCONCLUSIVE",
    ]),
    check("vh_qc_result_ck_0", sql`NOT redo_required OR outcome = 'FAIL'`),
  ],
).enableRLS();

export const vhQcResultEvidence = pgTable(
  "vh_qc_result_evidence",
  {
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    incidentId: uuid("incident_id").notNull(),
    qcResultId: uuid("qc_result_id").notNull(),
    evidenceRefId: uuid("evidence_ref_id").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_qc_result_evidence_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({ columns: [t.tenantId, t.qcResultId, t.evidenceRefId] }),
    foreignKey({
      name: "vh_qc_result_evidence_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_qc_result_evidence_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_qc_result_evidence_fk_2",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_qc_result_evidence_fk_3",
      columns: [t.tenantId, t.projectId, t.incidentId, t.qcResultId],
      foreignColumns: [
        vhQcResult.tenantId,
        vhQcResult.projectId,
        vhQcResult.incidentId,
        vhQcResult.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_qc_result_evidence_fk_4",
      columns: [t.tenantId, t.projectId, t.incidentId, t.evidenceRefId],
      foreignColumns: [
        vhEvidenceRef.tenantId,
        vhEvidenceRef.projectId,
        vhEvidenceRef.incidentId,
        vhEvidenceRef.id,
      ],
    }).onDelete("restrict"),
    index("vh_qc_result_evidence_ix_0").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.evidenceRefId,
    ),
    index("vh_qc_result_evidence_ix_1").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.qcResultId,
    ),
    index("vh_qc_result_evidence_ix_2").on(t.tenantId, t.projectId),
    index("vh_qc_result_evidence_ix_3").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
    ),
  ],
).enableRLS();

export const vhRootCauseFinding = pgTable(
  "vh_root_cause_finding",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    incidentId: uuid("incident_id").notNull(),
    suspectedDomain: text("suspected_domain", {
      enum: ["TECHNICAL", "SECURITY", "PROCESS", "SANITATION", "UNKNOWN"],
    }).notNull(),
    description: text("description").notNull(),
    status: text("status", {
      enum: ["PROPOSED", "CONFIRMED", "REJECTED"],
    }).notNull(),
    createdByType: text("created_by_type", {
      enum: ["HUMAN", "SYSTEM", "AGENT"],
    }).notNull(),
    createdById: text("created_by_id").notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_root_cause_finding_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_root_cause_finding_uq_0").on(t.tenantId, t.id),
    unique("vh_root_cause_finding_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_root_cause_finding_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_root_cause_finding_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_root_cause_finding_fk_2",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    index("vh_root_cause_finding_ix_0").on(t.tenantId, t.projectId),
    index("vh_root_cause_finding_ix_1").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
    ),
    allowedValues(
      "vh_root_cause_finding_suspected_domain_ck",
      t.suspectedDomain,
      ["TECHNICAL", "SECURITY", "PROCESS", "SANITATION", "UNKNOWN"],
    ),
    allowedValues("vh_root_cause_finding_status_ck", t.status, [
      "PROPOSED",
      "CONFIRMED",
      "REJECTED",
    ]),
    allowedValues("vh_root_cause_finding_created_by_type_ck", t.createdByType, [
      "HUMAN",
      "SYSTEM",
      "AGENT",
    ]),
    check("vh_root_cause_finding_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const vhRootCauseIncident = pgTable(
  "vh_root_cause_incident",
  {
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    rootCauseFindingId: uuid("root_cause_finding_id").notNull(),
    relatedIncidentId: uuid("related_incident_id").notNull(),
    relationType: text("relation_type").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_root_cause_incident_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({
      columns: [t.tenantId, t.rootCauseFindingId, t.relatedIncidentId],
    }),
    foreignKey({
      name: "vh_root_cause_incident_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_root_cause_incident_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_root_cause_incident_fk_2",
      columns: [t.tenantId, t.projectId, t.rootCauseFindingId],
      foreignColumns: [
        vhRootCauseFinding.tenantId,
        vhRootCauseFinding.projectId,
        vhRootCauseFinding.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_root_cause_incident_fk_3",
      columns: [t.tenantId, t.projectId, t.relatedIncidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    index("vh_root_cause_incident_ix_0").on(
      t.tenantId,
      t.projectId,
      t.relatedIncidentId,
    ),
    index("vh_root_cause_incident_ix_1").on(t.tenantId, t.projectId),
    index("vh_root_cause_incident_ix_2").on(
      t.tenantId,
      t.projectId,
      t.rootCauseFindingId,
    ),
  ],
).enableRLS();

export const vhRootCauseEvidence = pgTable(
  "vh_root_cause_evidence",
  {
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    rootCauseFindingId: uuid("root_cause_finding_id").notNull(),
    evidenceRefId: uuid("evidence_ref_id").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_root_cause_evidence_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({
      columns: [t.tenantId, t.rootCauseFindingId, t.evidenceRefId],
    }),
    foreignKey({
      name: "vh_root_cause_evidence_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_root_cause_evidence_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_root_cause_evidence_fk_2",
      columns: [t.tenantId, t.projectId, t.rootCauseFindingId],
      foreignColumns: [
        vhRootCauseFinding.tenantId,
        vhRootCauseFinding.projectId,
        vhRootCauseFinding.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_root_cause_evidence_fk_3",
      columns: [t.tenantId, t.projectId, t.evidenceRefId],
      foreignColumns: [
        vhEvidenceRef.tenantId,
        vhEvidenceRef.projectId,
        vhEvidenceRef.id,
      ],
    }).onDelete("restrict"),
    index("vh_root_cause_evidence_ix_0").on(
      t.tenantId,
      t.projectId,
      t.evidenceRefId,
    ),
    index("vh_root_cause_evidence_ix_1").on(t.tenantId, t.projectId),
    index("vh_root_cause_evidence_ix_2").on(
      t.tenantId,
      t.projectId,
      t.rootCauseFindingId,
    ),
  ],
).enableRLS();
