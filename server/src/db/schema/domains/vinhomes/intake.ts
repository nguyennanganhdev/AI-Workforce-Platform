/** Physical model for domains/vinhomes/intake. See docs/erd/README.md. */
import { sql } from "drizzle-orm";
import {
  bigint,
  check,
  foreignKey,
  index,
  integer,
  numeric,
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
import { vhIncident } from "./operations";
import { vhApartment, vhProject, vhPropertyMembership } from "./property";

export const vhCase = pgTable(
  "vh_case",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    residentUserId: text("resident_user_id").notNull(),
    apartmentId: uuid("apartment_id"),
    openedByMembershipId: uuid("opened_by_membership_id").notNull(),
    intakeStateJson: jsonb("intake_state_json")
      .notNull()
      .default({ issueCandidates: [] }),
    status: text("status", {
      enum: ["OPEN", "CLARIFYING", "READY", "TICKETED", "CLOSED", "CANCELLED"],
    }).notNull(),
    summary: text("summary").notNull(),
    openedAt: timestamp("opened_at", { withTimezone: true }).notNull(),
    closedAt: timestamp("closed_at", { withTimezone: true }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_case_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_case_uq_0").on(t.tenantId, t.id),
    unique("vh_case_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_case_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_case_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_case_fk_2",
      columns: [t.residentUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_case_fk_3",
      columns: [t.tenantId, t.projectId, t.apartmentId],
      foreignColumns: [
        vhApartment.tenantId,
        vhApartment.projectId,
        vhApartment.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_case_fk_4",
      columns: [t.tenantId, t.projectId, t.openedByMembershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_case_fk_5",
      columns: [
        t.tenantId,
        t.projectId,
        t.residentUserId,
        t.openedByMembershipId,
      ],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.userId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_case_fk_6",
      columns: [t.tenantId, t.projectId, t.apartmentId, t.openedByMembershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.apartmentId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    index("vh_case_ix_0").on(t.tenantId, t.projectId, t.openedByMembershipId),
    index("vh_case_ix_1").on(t.residentUserId),
    index("vh_case_ix_2").on(t.tenantId, t.projectId, t.apartmentId),
    index("vh_case_ix_3").on(t.tenantId, t.projectId),
    allowedValues("vh_case_status_ck", t.status, [
      "OPEN",
      "CLARIFYING",
      "READY",
      "TICKETED",
      "CLOSED",
      "CANCELLED",
    ]),
    check("vh_case_ck_0", sql`version > 0`),
    check(
      "vh_case_intake_state_ck",
      sql`(jsonb_typeof(${t.intakeStateJson}) = 'object' AND jsonb_typeof(${t.intakeStateJson}->'issueCandidates') = 'array') IS TRUE`,
    ),
  ],
).enableRLS();

export const vhResidentRequest = pgTable(
  "vh_resident_request",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    caseId: uuid("case_id").notNull(),
    channel: text("channel").notNull(),
    requestType: text("request_type").notNull(),
    rawContentRef: text("raw_content_ref"),
    sanitizedContent: text("sanitized_content").notNull(),
    idempotencyKey: text("idempotency_key").notNull(),
    submittedBy: text("submitted_by").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_resident_request_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_resident_request_uq_0").on(t.tenantId, t.idempotencyKey),
    unique("vh_resident_request_uq_1").on(t.tenantId, t.id),
    unique("vh_resident_request_uq_2").on(t.tenantId, t.projectId, t.id),
    unique("vh_resident_request_uq_3").on(
      t.tenantId,
      t.projectId,
      t.caseId,
      t.id,
    ),
    foreignKey({
      name: "vh_resident_request_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_resident_request_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_resident_request_fk_2",
      columns: [t.tenantId, t.projectId, t.caseId],
      foreignColumns: [vhCase.tenantId, vhCase.projectId, vhCase.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_resident_request_fk_3",
      columns: [t.submittedBy],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("vh_resident_request_ix_0").on(t.tenantId, t.projectId, t.caseId),
    index("vh_resident_request_ix_1").on(t.tenantId, t.caseId, t.createdAt),
    index("vh_resident_request_ix_2").on(t.tenantId, t.projectId),
    index("vh_resident_request_ix_3").on(t.submittedBy),
  ],
).enableRLS();

export const vhResidentReport = pgTable(
  "vh_resident_report",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    caseId: uuid("case_id").notNull(),
    incidentId: uuid("incident_id"),
    reporterId: text("reporter_id").notNull(),
    reporterMembershipId: uuid("reporter_membership_id").notNull(),
    apartmentId: uuid("apartment_id"),
    category: text("category").notNull(),
    description: text("description").notNull(),
    locationJson: jsonb("location_json").notNull(),
    status: text("status", {
      enum: ["SUBMITTED", "LINKED", "WITHDRAWN"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_resident_report_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_resident_report_uq_1").on(t.tenantId, t.id),
    unique("vh_resident_report_uq_2").on(t.tenantId, t.projectId, t.id),
    unique("vh_resident_report_uq_3").on(
      t.tenantId,
      t.incidentId,
      t.reporterId,
      t.id,
    ),
    unique("vh_resident_report_uq_4").on(t.tenantId, t.reporterId, t.id),
    unique("vh_resident_report_uq_5").on(t.tenantId, t.incidentId, t.id),
    foreignKey({
      name: "vh_resident_report_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_resident_report_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_resident_report_fk_2",
      columns: [t.tenantId, t.projectId, t.caseId],
      foreignColumns: [vhCase.tenantId, vhCase.projectId, vhCase.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_resident_report_fk_4",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_resident_report_fk_5",
      columns: [t.reporterId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_resident_report_fk_6",
      columns: [t.tenantId, t.projectId, t.reporterMembershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_resident_report_fk_7",
      columns: [t.tenantId, t.projectId, t.apartmentId],
      foreignColumns: [
        vhApartment.tenantId,
        vhApartment.projectId,
        vhApartment.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_resident_report_fk_8",
      columns: [t.tenantId, t.projectId, t.reporterId, t.reporterMembershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.userId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_resident_report_fk_9",
      columns: [t.tenantId, t.projectId, t.apartmentId, t.reporterMembershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.apartmentId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    index("vh_resident_report_ix_0").on(t.tenantId, t.reporterId, t.createdAt),
    index("vh_resident_report_ix_2").on(t.tenantId, t.projectId),
    index("vh_resident_report_ix_3").on(t.tenantId, t.projectId, t.incidentId),
    index("vh_resident_report_ix_4").on(t.reporterId),
    index("vh_resident_report_ix_5").on(t.tenantId, t.projectId, t.caseId),
    index("vh_resident_report_ix_6").on(t.tenantId, t.projectId, t.apartmentId),
    index("vh_resident_report_ix_7").on(
      t.tenantId,
      t.projectId,
      t.reporterMembershipId,
    ),
    allowedValues("vh_resident_report_status_ck", t.status, [
      "SUBMITTED",
      "LINKED",
      "WITHDRAWN",
    ]),
    check(
      "vh_resident_report_ck_0",
      sql`(status = 'LINKED') = (incident_id IS NOT NULL)`,
    ),
    check("vh_resident_report_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const vhResidentConfirmation = pgTable(
  "vh_resident_confirmation",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    reportId: uuid("report_id").notNull(),
    incidentId: uuid("incident_id").notNull(),
    resolutionVersion: bigint("resolution_version", {
      mode: "bigint",
    }).notNull(),
    response: text("response", {
      enum: ["ACCEPTED", "REOPEN_REQUESTED"],
    }).notNull(),
    note: text("note"),
    confirmedByUserId: text("confirmed_by_user_id").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_resident_confirmation_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_resident_confirmation_uq_0").on(
      t.tenantId,
      t.reportId,
      t.resolutionVersion,
    ),
    unique("vh_resident_confirmation_uq_1").on(t.tenantId, t.id),
    unique("vh_resident_confirmation_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_resident_confirmation_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_resident_confirmation_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_resident_confirmation_fk_2",
      columns: [t.tenantId, t.projectId, t.reportId],
      foreignColumns: [
        vhResidentReport.tenantId,
        vhResidentReport.projectId,
        vhResidentReport.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_resident_confirmation_fk_3",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_resident_confirmation_fk_4",
      columns: [t.confirmedByUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_resident_confirmation_fk_5",
      columns: [t.tenantId, t.incidentId, t.confirmedByUserId, t.reportId],
      foreignColumns: [
        vhResidentReport.tenantId,
        vhResidentReport.incidentId,
        vhResidentReport.reporterId,
        vhResidentReport.id,
      ],
    }).onDelete("restrict"),
    index("vh_resident_confirmation_ix_0").on(
      t.tenantId,
      t.incidentId,
      t.resolutionVersion,
    ),
    index("vh_resident_confirmation_ix_1").on(t.tenantId, t.projectId),
    index("vh_resident_confirmation_ix_2").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
    ),
    index("vh_resident_confirmation_ix_3").on(t.confirmedByUserId),
    index("vh_resident_confirmation_ix_4").on(
      t.tenantId,
      t.projectId,
      t.reportId,
    ),
    allowedValues("vh_resident_confirmation_response_ck", t.response, [
      "ACCEPTED",
      "REOPEN_REQUESTED",
    ]),
    check("vh_resident_confirmation_ck_0", sql`resolution_version > 0`),
  ],
).enableRLS();

export const vhFeedback = pgTable(
  "vh_feedback",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    reportId: uuid("report_id").notNull(),
    authorUserId: text("author_user_id").notNull(),
    rating: integer("rating").notNull(),
    comment: text("comment"),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_feedback_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_feedback_uq_0").on(t.tenantId, t.reportId, t.authorUserId),
    unique("vh_feedback_uq_1").on(t.tenantId, t.id),
    unique("vh_feedback_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_feedback_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_feedback_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_feedback_fk_2",
      columns: [t.tenantId, t.projectId, t.reportId],
      foreignColumns: [
        vhResidentReport.tenantId,
        vhResidentReport.projectId,
        vhResidentReport.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_feedback_fk_3",
      columns: [t.authorUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_feedback_fk_4",
      columns: [t.tenantId, t.authorUserId, t.reportId],
      foreignColumns: [
        vhResidentReport.tenantId,
        vhResidentReport.reporterId,
        vhResidentReport.id,
      ],
    }).onDelete("restrict"),
    index("vh_feedback_ix_0").on(t.authorUserId),
    index("vh_feedback_ix_1").on(t.tenantId, t.projectId, t.reportId),
    index("vh_feedback_ix_2").on(t.tenantId, t.projectId),
    check("vh_feedback_ck_0", sql`rating BETWEEN 1 AND 5`),
  ],
).enableRLS();
