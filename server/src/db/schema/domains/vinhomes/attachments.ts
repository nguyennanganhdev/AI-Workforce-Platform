/** Physical model for domains/vinhomes/attachments. See docs/erd/README.md. */
import { sql } from "drizzle-orm";
import {
  foreignKey,
  index,
  pgPolicy,
  pgTable,
  primaryKey,
  text,
  uuid,
} from "drizzle-orm/pg-core";
import { createdAt } from "../../columns";
import { platformTenant } from "../../platform/identity";
import { vhFileObject } from "./files";
import { vhResidentReport, vhResidentRequest } from "./intake";
import { vhMembershipApplication, vhProject } from "./property";
import { vhPetProfile, vhServiceRequest } from "./services";

export const vhMembershipApplicationFile = pgTable(
  "vh_membership_application_file",
  {
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    applicationId: uuid("application_id").notNull(),
    fileId: uuid("file_id").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_membership_application_file_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({ columns: [t.tenantId, t.applicationId, t.fileId] }),
    foreignKey({
      name: "vh_membership_application_file_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_membership_application_file_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_membership_application_file_fk_2",
      columns: [t.tenantId, t.projectId, t.applicationId],
      foreignColumns: [
        vhMembershipApplication.tenantId,
        vhMembershipApplication.projectId,
        vhMembershipApplication.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_membership_application_file_fk_3",
      columns: [t.tenantId, t.fileId],
      foreignColumns: [vhFileObject.tenantId, vhFileObject.id],
    }).onDelete("restrict"),
    index("vh_membership_application_file_ix_0").on(
      t.tenantId,
      t.projectId,
      t.applicationId,
    ),
    index("vh_membership_application_file_ix_1").on(t.tenantId, t.projectId),
    index("vh_membership_application_file_ix_2").on(t.tenantId, t.fileId),
  ],
).enableRLS();

export const vhRequestAttachment = pgTable(
  "vh_request_attachment",
  {
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    requestId: uuid("request_id").notNull(),
    fileId: uuid("file_id").notNull(),
    caption: text("caption"),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_request_attachment_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({ columns: [t.tenantId, t.requestId, t.fileId] }),
    foreignKey({
      name: "vh_request_attachment_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_request_attachment_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_request_attachment_fk_2",
      columns: [t.tenantId, t.projectId, t.requestId],
      foreignColumns: [
        vhResidentRequest.tenantId,
        vhResidentRequest.projectId,
        vhResidentRequest.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_request_attachment_fk_3",
      columns: [t.tenantId, t.fileId],
      foreignColumns: [vhFileObject.tenantId, vhFileObject.id],
    }).onDelete("restrict"),
    index("vh_request_attachment_ix_0").on(
      t.tenantId,
      t.projectId,
      t.requestId,
    ),
    index("vh_request_attachment_ix_1").on(t.tenantId, t.projectId),
    index("vh_request_attachment_ix_2").on(t.tenantId, t.fileId),
  ],
).enableRLS();

export const vhReportAttachment = pgTable(
  "vh_report_attachment",
  {
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    reportId: uuid("report_id").notNull(),
    fileId: uuid("file_id").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_report_attachment_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({ columns: [t.tenantId, t.reportId, t.fileId] }),
    foreignKey({
      name: "vh_report_attachment_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_report_attachment_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_report_attachment_fk_2",
      columns: [t.tenantId, t.projectId, t.reportId],
      foreignColumns: [
        vhResidentReport.tenantId,
        vhResidentReport.projectId,
        vhResidentReport.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_report_attachment_fk_3",
      columns: [t.tenantId, t.fileId],
      foreignColumns: [vhFileObject.tenantId, vhFileObject.id],
    }).onDelete("restrict"),
    index("vh_report_attachment_ix_0").on(t.tenantId, t.projectId, t.reportId),
    index("vh_report_attachment_ix_1").on(t.tenantId, t.projectId),
    index("vh_report_attachment_ix_2").on(t.tenantId, t.fileId),
  ],
).enableRLS();

export const vhPetDocument = pgTable(
  "vh_pet_document",
  {
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    petId: uuid("pet_id").notNull(),
    fileId: uuid("file_id").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_pet_document_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({ columns: [t.tenantId, t.petId, t.fileId] }),
    foreignKey({
      name: "vh_pet_document_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_pet_document_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_pet_document_fk_2",
      columns: [t.tenantId, t.projectId, t.petId],
      foreignColumns: [
        vhPetProfile.tenantId,
        vhPetProfile.projectId,
        vhPetProfile.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_pet_document_fk_3",
      columns: [t.tenantId, t.fileId],
      foreignColumns: [vhFileObject.tenantId, vhFileObject.id],
    }).onDelete("restrict"),
    index("vh_pet_document_ix_0").on(t.tenantId, t.fileId),
    index("vh_pet_document_ix_1").on(t.tenantId, t.projectId),
    index("vh_pet_document_ix_2").on(t.tenantId, t.projectId, t.petId),
  ],
).enableRLS();

export const vhServiceRequestFile = pgTable(
  "vh_service_request_file",
  {
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    requestId: uuid("request_id").notNull(),
    fileId: uuid("file_id").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_service_request_file_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({ columns: [t.tenantId, t.requestId, t.fileId] }),
    foreignKey({
      name: "vh_service_request_file_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_service_request_file_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_service_request_file_fk_2",
      columns: [t.tenantId, t.projectId, t.requestId],
      foreignColumns: [
        vhServiceRequest.tenantId,
        vhServiceRequest.projectId,
        vhServiceRequest.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_service_request_file_fk_3",
      columns: [t.tenantId, t.fileId],
      foreignColumns: [vhFileObject.tenantId, vhFileObject.id],
    }).onDelete("restrict"),
    index("vh_service_request_file_ix_0").on(
      t.tenantId,
      t.projectId,
      t.requestId,
    ),
    index("vh_service_request_file_ix_1").on(t.tenantId, t.projectId),
    index("vh_service_request_file_ix_2").on(t.tenantId, t.fileId),
  ],
).enableRLS();
