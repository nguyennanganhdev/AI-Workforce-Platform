/** Persistence for coordination and field operations. See docs/erd/SYSTEM_FLOW.md. */
import { sql } from "drizzle-orm";
import {
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
import { platformTenant } from "../../platform/identity";
import { vhIncident } from "./operations";
import { vhApartment, vhProject, vhTower } from "./property";

export const vhAsset = pgTable(
  "vh_asset",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    towerId: uuid("tower_id"),
    apartmentId: uuid("apartment_id"),
    code: text("code").notNull(),
    name: text("name").notNull(),
    category: text("category").notNull(),
    manufacturer: text("manufacturer"),
    model: text("model"),
    serialNumber: text("serial_number"),
    installedAt: timestamp("installed_at", { withTimezone: true }),
    warrantyUntil: timestamp("warranty_until", { withTimezone: true }),
    status: text("status", {
      enum: ["ACTIVE", "OUT_OF_SERVICE", "RETIRED"],
    }).notNull(),
    metadataJson: jsonb("metadata_json").notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_asset_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_asset_uq_0").on(t.tenantId, t.projectId, t.code),
    unique("vh_asset_uq_1").on(t.tenantId, t.id),
    unique("vh_asset_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_asset_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_asset_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_asset_fk_2",
      columns: [t.tenantId, t.projectId, t.towerId],
      foreignColumns: [vhTower.tenantId, vhTower.projectId, vhTower.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_asset_fk_3",
      columns: [t.tenantId, t.projectId, t.apartmentId],
      foreignColumns: [
        vhApartment.tenantId,
        vhApartment.projectId,
        vhApartment.id,
      ],
    }).onDelete("restrict"),
    index("vh_asset_ix_1").on(t.tenantId, t.projectId),
    index("vh_asset_ix_2").on(t.tenantId, t.projectId, t.apartmentId),
    index("vh_asset_ix_3").on(t.tenantId, t.projectId, t.towerId),
    allowedValues("vh_asset_status_ck", t.status, [
      "ACTIVE",
      "OUT_OF_SERVICE",
      "RETIRED",
    ]),
    check("vh_asset_ck_0", sql`apartment_id IS NULL OR tower_id IS NOT NULL`),
    check("vh_asset_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const vhIncidentAsset = pgTable(
  "vh_incident_asset",
  {
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    incidentId: uuid("incident_id").notNull(),
    assetId: uuid("asset_id").notNull(),
    relationship: text("relationship", {
      enum: ["AFFECTED", "SUSPECTED", "CAUSAL"],
    }).notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_incident_asset_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({
      name: "vh_incident_asset_pk",
      columns: [t.tenantId, t.incidentId, t.assetId],
    }),
    foreignKey({
      name: "vh_incident_asset_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_incident_asset_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_incident_asset_fk_2",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_incident_asset_fk_3",
      columns: [t.tenantId, t.projectId, t.assetId],
      foreignColumns: [vhAsset.tenantId, vhAsset.projectId, vhAsset.id],
    }).onDelete("restrict"),
    index("vh_incident_asset_ix_1").on(t.tenantId, t.projectId),
    index("vh_incident_asset_ix_2").on(t.tenantId, t.projectId, t.assetId),
    index("vh_incident_asset_ix_3").on(t.tenantId, t.projectId, t.incidentId),
    allowedValues("vh_incident_asset_relationship_ck", t.relationship, [
      "AFFECTED",
      "SUSPECTED",
      "CAUSAL",
    ]),
  ],
).enableRLS();
