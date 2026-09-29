/** Persistence for coordination and field operations. See docs/erd/02_BUSINESS_ANALYSIS_IMPLEMENTATION.md. */
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
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, mutableColumns } from "../../columns";
import { platformTenant, users } from "../../platform/identity";
import { vhBusinessEvent, vhNotification } from "./communication";
import { vhWorkProgress } from "./dispatch";
import { vhResidentReport } from "./intake";
import { vhIncident } from "./operations";
import { vhProject } from "./property";

export const vhReportUpdate = pgTable(
  "vh_report_update",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    incidentId: uuid("incident_id").notNull(),
    reportId: uuid("report_id").notNull(),
    recipientUserId: text("recipient_user_id").notNull(),
    businessEventId: uuid("business_event_id").notNull(),
    workProgressId: uuid("work_progress_id"),
    sequenceNo: bigint("sequence_no", { mode: "bigint" }).notNull(),
    incidentVersion: bigint("incident_version", { mode: "bigint" }).notNull(),
    headline: text("headline").notNull(),
    publicSummary: text("public_summary").notNull(),
    publicStatus: text("public_status", {
      enum: [
        "RECEIVED",
        "ASSIGNED",
        "IN_PROGRESS",
        "WAITING",
        "RESOLVED",
        "CLOSED",
      ],
    }).notNull(),
    expectedCompletionAt: timestamp("expected_completion_at", {
      withTimezone: true,
    }),
    sourceOccurredAt: timestamp("source_occurred_at", {
      withTimezone: true,
    }).notNull(),
    preparedByType: text("prepared_by_type", {
      enum: ["HUMAN", "SYSTEM", "AGENT"],
    }).notNull(),
    preparedById: text("prepared_by_id").notNull(),
    idempotencyKey: text("idempotency_key").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_report_update_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_report_update_uq_0").on(t.tenantId, t.reportId, t.sequenceNo),
    unique("vh_report_update_uq_1").on(
      t.tenantId,
      t.reportId,
      t.businessEventId,
    ),
    unique("vh_report_update_uq_2").on(t.tenantId, t.idempotencyKey),
    unique("vh_report_update_uq_3").on(t.tenantId, t.id),
    unique("vh_report_update_uq_4").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_report_update_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_report_update_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_report_update_fk_2",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_report_update_fk_3",
      columns: [t.tenantId, t.projectId, t.reportId],
      foreignColumns: [
        vhResidentReport.tenantId,
        vhResidentReport.projectId,
        vhResidentReport.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_report_update_fk_4",
      columns: [t.recipientUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_report_update_fk_5",
      columns: [t.tenantId, t.projectId, t.businessEventId],
      foreignColumns: [
        vhBusinessEvent.tenantId,
        vhBusinessEvent.projectId,
        vhBusinessEvent.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_report_update_fk_6",
      columns: [t.tenantId, t.projectId, t.incidentId, t.workProgressId],
      foreignColumns: [
        vhWorkProgress.tenantId,
        vhWorkProgress.projectId,
        vhWorkProgress.incidentId,
        vhWorkProgress.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_report_update_fk_7",
      columns: [t.tenantId, t.incidentId, t.recipientUserId, t.reportId],
      foreignColumns: [
        vhResidentReport.tenantId,
        vhResidentReport.incidentId,
        vhResidentReport.reporterId,
        vhResidentReport.id,
      ],
    }).onDelete("restrict"),
    index("vh_report_update_ix_0").on(t.recipientUserId),
    index("vh_report_update_ix_2").on(
      t.tenantId,
      t.incidentId,
      t.recipientUserId,
      t.reportId,
    ),
    index("vh_report_update_ix_3").on(t.tenantId, t.projectId),
    index("vh_report_update_ix_4").on(
      t.tenantId,
      t.projectId,
      t.businessEventId,
    ),
    index("vh_report_update_ix_5").on(t.tenantId, t.projectId, t.incidentId),
    index("vh_report_update_ix_6").on(
      t.tenantId,
      t.projectId,
      t.incidentId,
      t.workProgressId,
    ),
    index("vh_report_update_ix_7").on(t.tenantId, t.projectId, t.reportId),
    allowedValues("vh_report_update_public_status_ck", t.publicStatus, [
      "RECEIVED",
      "ASSIGNED",
      "IN_PROGRESS",
      "WAITING",
      "RESOLVED",
      "CLOSED",
    ]),
    allowedValues("vh_report_update_prepared_by_type_ck", t.preparedByType, [
      "HUMAN",
      "SYSTEM",
      "AGENT",
    ]),
    check("vh_report_update_ck_0", sql`sequence_no > 0`),
    check("vh_report_update_ck_1", sql`incident_version > 0`),
  ],
).enableRLS();

export const vhNotificationDelivery = pgTable(
  "vh_notification_delivery",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    notificationId: uuid("notification_id").notNull(),
    reportUpdateId: uuid("report_update_id"),
    channel: text("channel", {
      enum: ["IN_APP", "EMAIL", "SMS", "PUSH", "CHAT"],
    }).notNull(),
    provider: text("provider").notNull(),
    destinationRef: text("destination_ref").notNull(),
    providerMessageRef: text("provider_message_ref"),
    attemptNo: integer("attempt_no").notNull(),
    idempotencyKey: text("idempotency_key").notNull(),
    status: text("status", {
      enum: ["QUEUED", "SENDING", "DELIVERED", "FAILED"],
    }).notNull(),
    availableAt: timestamp("available_at", { withTimezone: true }).notNull(),
    sentAt: timestamp("sent_at", { withTimezone: true }),
    deliveredAt: timestamp("delivered_at", { withTimezone: true }),
    lastErrorCode: text("last_error_code"),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_notification_delivery_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_notification_delivery_uq_0").on(
      t.tenantId,
      t.notificationId,
      t.channel,
      t.attemptNo,
    ),
    unique("vh_notification_delivery_uq_1").on(t.tenantId, t.idempotencyKey),
    unique("vh_notification_delivery_uq_2").on(
      t.provider,
      t.providerMessageRef,
    ),
    unique("vh_notification_delivery_uq_3").on(t.tenantId, t.id),
    unique("vh_notification_delivery_uq_4").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_notification_delivery_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_notification_delivery_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_notification_delivery_fk_2",
      columns: [t.tenantId, t.projectId, t.notificationId],
      foreignColumns: [
        vhNotification.tenantId,
        vhNotification.projectId,
        vhNotification.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_notification_delivery_fk_3",
      columns: [t.tenantId, t.projectId, t.reportUpdateId],
      foreignColumns: [
        vhReportUpdate.tenantId,
        vhReportUpdate.projectId,
        vhReportUpdate.id,
      ],
    }).onDelete("restrict"),
    index("vh_notification_delivery_ix_1").on(t.tenantId, t.projectId),
    index("vh_notification_delivery_ready_ix").on(
      t.tenantId,
      t.status,
      t.availableAt,
    ),
    index("vh_notification_delivery_ix_2").on(
      t.tenantId,
      t.projectId,
      t.notificationId,
    ),
    index("vh_notification_delivery_ix_3").on(
      t.tenantId,
      t.projectId,
      t.reportUpdateId,
    ),
    allowedValues("vh_notification_delivery_channel_ck", t.channel, [
      "IN_APP",
      "EMAIL",
      "SMS",
      "PUSH",
      "CHAT",
    ]),
    allowedValues("vh_notification_delivery_status_ck", t.status, [
      "QUEUED",
      "SENDING",
      "DELIVERED",
      "FAILED",
    ]),
    check("vh_notification_delivery_ck_0", sql`attempt_no > 0`),
    check(
      "vh_notification_delivery_ck_1",
      sql`status<>'DELIVERED' OR (delivered_at IS NOT NULL AND provider_message_ref IS NOT NULL)`,
    ),
    check("vh_notification_delivery_ck_2", sql`version > 0`),
  ],
).enableRLS();
