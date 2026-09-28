/** Physical model for domains/vinhomes/files. See docs/erd/README.md. */
import { sql } from "drizzle-orm";
import {
  bigint,
  check,
  foreignKey,
  index,
  pgPolicy,
  pgTable,
  text,
  timestamp,
  unique,
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, mutableColumns } from "../../columns";
import { platformTenant, users } from "../../platform/identity";

export const vhFileObject = pgTable(
  "vh_file_object",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    storageProvider: text("storage_provider").notNull(),
    storageKey: text("storage_key").notNull(),
    mimeType: text("mime_type").notNull(),
    sizeBytes: bigint("size_bytes", { mode: "bigint" }).notNull(),
    checksum: text("checksum").notNull(),
    uploadedByUserId: text("uploaded_by_user_id").notNull(),
    uploadStatus: text("upload_status", {
      enum: ["PENDING", "UPLOADED", "QUARANTINED", "AVAILABLE", "REJECTED"],
    }).notNull(),
    visibility: text("visibility", {
      enum: ["PRIVATE", "RESIDENT_VISIBLE", "INTERNAL"],
    }).notNull(),
    originalFilename: text("original_filename").notNull(),
    uploadedAt: timestamp("uploaded_at", { withTimezone: true }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_file_object_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_file_object_uq_0").on(t.storageProvider, t.storageKey),
    unique("vh_file_object_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "vh_file_object_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_file_object_fk_1",
      columns: [t.uploadedByUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("vh_file_object_ix_0").on(t.uploadedByUserId),
    allowedValues("vh_file_object_upload_status_ck", t.uploadStatus, [
      "PENDING",
      "UPLOADED",
      "QUARANTINED",
      "AVAILABLE",
      "REJECTED",
    ]),
    allowedValues("vh_file_object_visibility_ck", t.visibility, [
      "PRIVATE",
      "RESIDENT_VISIBLE",
      "INTERNAL",
    ]),
    check("vh_file_object_ck_0", sql`size_bytes >= 0`),
    check("vh_file_object_ck_1", sql`version > 0`),
  ],
).enableRLS();
