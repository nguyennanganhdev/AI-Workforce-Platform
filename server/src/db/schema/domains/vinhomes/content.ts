/** Physical model for domains/vinhomes/content. See docs/erd/README.md. */
import { sql } from "drizzle-orm";
import {
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
import { platformTenant } from "../../platform/identity";
import { vhProject, vhPropertyMembership, vhTower } from "./property";

export const vhMapPlace = pgTable(
  "vh_map_place",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    towerId: uuid("tower_id"),
    name: text("name").notNull(),
    category: text("category").notNull(),
    address: text("address").notNull(),
    latitude: numeric("latitude"),
    longitude: numeric("longitude"),
    status: text("status", { enum: ["ACTIVE", "RETIRED"] }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_map_place_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_map_place_uq_0").on(t.tenantId, t.id),
    unique("vh_map_place_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_map_place_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_map_place_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_map_place_fk_2",
      columns: [t.tenantId, t.projectId, t.towerId],
      foreignColumns: [vhTower.tenantId, vhTower.projectId, vhTower.id],
    }).onDelete("restrict"),
    index("vh_map_place_ix_0").on(t.tenantId, t.projectId, t.towerId),
    index("vh_map_place_ix_1").on(t.tenantId, t.projectId),
    allowedValues("vh_map_place_status_ck", t.status, ["ACTIVE", "RETIRED"]),
    check("vh_map_place_ck_0", sql`(latitude IS NULL) = (longitude IS NULL)`),
    check(
      "vh_map_place_ck_1",
      sql`latitude IS NULL OR latitude BETWEEN -90 AND 90`,
    ),
    check(
      "vh_map_place_ck_2",
      sql`longitude IS NULL OR longitude BETWEEN -180 AND 180`,
    ),
    check("vh_map_place_ck_3", sql`version > 0`),
  ],
).enableRLS();

export const vhContentItem = pgTable(
  "vh_content_item",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    title: text("title").notNull(),
    kind: text("kind", { enum: ["NEWS", "HANDBOOK", "NOTICE"] }).notNull(),
    body: text("body").notNull(),
    status: text("status", {
      enum: ["DRAFT", "PUBLISHED", "ARCHIVED"],
    }).notNull(),
    publishedAt: timestamp("published_at", { withTimezone: true }),
    expiresAt: timestamp("expires_at", { withTimezone: true }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_content_item_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_content_item_uq_0").on(t.tenantId, t.id),
    unique("vh_content_item_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_content_item_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_content_item_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    index("vh_content_item_ix_0").on(t.tenantId, t.projectId),
    index("vh_content_item_ix_1").on(
      t.tenantId,
      t.projectId,
      t.status,
      t.publishedAt,
    ),
    allowedValues("vh_content_item_kind_ck", t.kind, [
      "NEWS",
      "HANDBOOK",
      "NOTICE",
    ]),
    allowedValues("vh_content_item_status_ck", t.status, [
      "DRAFT",
      "PUBLISHED",
      "ARCHIVED",
    ]),
    check(
      "vh_content_item_ck_0",
      sql`status <> 'PUBLISHED' OR published_at IS NOT NULL`,
    ),
    check(
      "vh_content_item_ck_1",
      sql`expires_at IS NULL OR expires_at > published_at`,
    ),
    check("vh_content_item_ck_2", sql`version > 0`),
  ],
).enableRLS();

export const vhCommunityEvent = pgTable(
  "vh_community_event",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    placeId: uuid("place_id"),
    title: text("title").notNull(),
    startsAt: timestamp("starts_at", { withTimezone: true }).notNull(),
    endsAt: timestamp("ends_at", { withTimezone: true }).notNull(),
    registrationClosesAt: timestamp("registration_closes_at", {
      withTimezone: true,
    }).notNull(),
    capacity: integer("capacity").notNull(),
    status: text("status", {
      enum: ["DRAFT", "PUBLISHED", "CANCELLED", "COMPLETED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_community_event_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_community_event_uq_0").on(t.tenantId, t.id),
    unique("vh_community_event_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_community_event_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_community_event_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_community_event_fk_2",
      columns: [t.tenantId, t.projectId, t.placeId],
      foreignColumns: [
        vhMapPlace.tenantId,
        vhMapPlace.projectId,
        vhMapPlace.id,
      ],
    }).onDelete("restrict"),
    index("vh_community_event_ix_0").on(t.tenantId, t.projectId, t.placeId),
    index("vh_community_event_ix_1").on(t.tenantId, t.projectId),
    allowedValues("vh_community_event_status_ck", t.status, [
      "DRAFT",
      "PUBLISHED",
      "CANCELLED",
      "COMPLETED",
    ]),
    check("vh_community_event_ck_0", sql`ends_at > starts_at`),
    check("vh_community_event_ck_1", sql`capacity > 0`),
    check("vh_community_event_ck_2", sql`registration_closes_at <= starts_at`),
    check("vh_community_event_ck_3", sql`version > 0`),
  ],
).enableRLS();

export const vhEventRegistration = pgTable(
  "vh_event_registration",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    eventId: uuid("event_id").notNull(),
    membershipId: uuid("membership_id").notNull(),
    guestCount: integer("guest_count").notNull(),
    status: text("status", {
      enum: ["REGISTERED", "CANCELLED", "ATTENDED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_event_registration_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_event_registration_uq_0").on(
      t.tenantId,
      t.eventId,
      t.membershipId,
    ),
    unique("vh_event_registration_uq_1").on(t.tenantId, t.id),
    unique("vh_event_registration_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_event_registration_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_event_registration_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_event_registration_fk_2",
      columns: [t.tenantId, t.projectId, t.eventId],
      foreignColumns: [
        vhCommunityEvent.tenantId,
        vhCommunityEvent.projectId,
        vhCommunityEvent.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_event_registration_fk_3",
      columns: [t.tenantId, t.projectId, t.membershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    index("vh_event_registration_ix_0").on(t.tenantId, t.projectId, t.eventId),
    index("vh_event_registration_ix_1").on(
      t.tenantId,
      t.projectId,
      t.membershipId,
    ),
    index("vh_event_registration_ix_2").on(t.tenantId, t.projectId),
    index("vh_event_registration_ix_3").on(t.tenantId, t.eventId, t.status),
    allowedValues("vh_event_registration_status_ck", t.status, [
      "REGISTERED",
      "CANCELLED",
      "ATTENDED",
    ]),
    check("vh_event_registration_ck_0", sql`guest_count >= 0`),
    check("vh_event_registration_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const vhOffer = pgTable(
  "vh_offer",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    merchantName: text("merchant_name").notNull(),
    title: text("title").notNull(),
    terms: text("terms").notNull(),
    startsAt: timestamp("starts_at", { withTimezone: true }).notNull(),
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
    destinationUrl: text("destination_url"),
    status: text("status", {
      enum: ["DRAFT", "PUBLISHED", "EXPIRED", "RETIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_offer_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_offer_uq_0").on(t.tenantId, t.id),
    unique("vh_offer_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_offer_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_offer_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    index("vh_offer_ix_0").on(t.tenantId, t.projectId),
    allowedValues("vh_offer_status_ck", t.status, [
      "DRAFT",
      "PUBLISHED",
      "EXPIRED",
      "RETIRED",
    ]),
    check("vh_offer_ck_0", sql`expires_at > starts_at`),
    check("vh_offer_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const vhSensorReading = pgTable(
  "vh_sensor_reading",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    placeId: uuid("place_id").notNull(),
    sensorCode: text("sensor_code").notNull(),
    metric: text("metric").notNull(),
    value: numeric("value").notNull(),
    unit: text("unit").notNull(),
    observedAt: timestamp("observed_at", { withTimezone: true }).notNull(),
    source: text("source").notNull(),
    quality: text("quality", { enum: ["VALID", "STALE", "INVALID"] }).notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_sensor_reading_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_sensor_reading_uq_0").on(
      t.tenantId,
      t.projectId,
      t.sensorCode,
      t.metric,
      t.observedAt,
    ),
    unique("vh_sensor_reading_uq_1").on(t.tenantId, t.id),
    unique("vh_sensor_reading_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_sensor_reading_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_sensor_reading_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_sensor_reading_fk_2",
      columns: [t.tenantId, t.projectId, t.placeId],
      foreignColumns: [
        vhMapPlace.tenantId,
        vhMapPlace.projectId,
        vhMapPlace.id,
      ],
    }).onDelete("restrict"),
    index("vh_sensor_reading_ix_0").on(t.tenantId, t.projectId, t.placeId),
    index("vh_sensor_reading_ix_1").on(t.tenantId, t.projectId),
    allowedValues("vh_sensor_reading_quality_ck", t.quality, [
      "VALID",
      "STALE",
      "INVALID",
    ]),
  ],
).enableRLS();

export const vhTransitRoute = pgTable(
  "vh_transit_route",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    code: text("code").notNull(),
    name: text("name").notNull(),
    operator: text("operator").notNull(),
    timetableJson: jsonb("timetable_json").notNull(),
    timetableVersion: integer("timetable_version").notNull(),
    effectiveFrom: timestamp("effective_from", {
      withTimezone: true,
    }).notNull(),
    status: text("status", {
      enum: ["ACTIVE", "SUSPENDED", "RETIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_transit_route_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_transit_route_uq_0").on(t.tenantId, t.projectId, t.code),
    unique("vh_transit_route_uq_1").on(t.tenantId, t.id),
    unique("vh_transit_route_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_transit_route_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_transit_route_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    index("vh_transit_route_ix_0").on(t.tenantId, t.projectId),
    allowedValues("vh_transit_route_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "RETIRED",
    ]),
    check("vh_transit_route_ck_0", sql`timetable_version > 0`),
    check("vh_transit_route_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const vhTransitStop = pgTable(
  "vh_transit_stop",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    name: text("name").notNull(),
    latitude: numeric("latitude").notNull(),
    longitude: numeric("longitude").notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_transit_stop_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_transit_stop_uq_0").on(t.tenantId, t.id),
    unique("vh_transit_stop_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_transit_stop_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_transit_stop_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    index("vh_transit_stop_ix_0").on(t.tenantId, t.projectId),
    check("vh_transit_stop_ck_0", sql`latitude BETWEEN -90 AND 90`),
    check("vh_transit_stop_ck_1", sql`longitude BETWEEN -180 AND 180`),
    check("vh_transit_stop_ck_2", sql`version > 0`),
  ],
).enableRLS();

export const vhTransitRouteStop = pgTable(
  "vh_transit_route_stop",
  {
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    routeId: uuid("route_id").notNull(),
    stopId: uuid("stop_id").notNull(),
    sequenceNo: integer("sequence_no").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_transit_route_stop_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({ columns: [t.tenantId, t.routeId, t.sequenceNo] }),
    foreignKey({
      name: "vh_transit_route_stop_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_transit_route_stop_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_transit_route_stop_fk_2",
      columns: [t.tenantId, t.projectId, t.routeId],
      foreignColumns: [
        vhTransitRoute.tenantId,
        vhTransitRoute.projectId,
        vhTransitRoute.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_transit_route_stop_fk_3",
      columns: [t.tenantId, t.projectId, t.stopId],
      foreignColumns: [
        vhTransitStop.tenantId,
        vhTransitStop.projectId,
        vhTransitStop.id,
      ],
    }).onDelete("restrict"),
    index("vh_transit_route_stop_ix_0").on(t.tenantId, t.projectId),
    index("vh_transit_route_stop_ix_1").on(t.tenantId, t.projectId, t.stopId),
    index("vh_transit_route_stop_ix_2").on(t.tenantId, t.projectId, t.routeId),
    check("vh_transit_route_stop_ck_0", sql`sequence_no > 0`),
  ],
).enableRLS();

export const vhMiniappCatalog = pgTable(
  "vh_miniapp_catalog",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    code: text("code").notNull(),
    name: text("name").notNull(),
    description: text("description").notNull(),
    destinationUrl: text("destination_url").notNull(),
    status: text("status", { enum: ["ACTIVE", "DISABLED"] }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_miniapp_catalog_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_miniapp_catalog_uq_0").on(t.tenantId, t.projectId, t.code),
    unique("vh_miniapp_catalog_uq_1").on(t.tenantId, t.id),
    unique("vh_miniapp_catalog_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_miniapp_catalog_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_miniapp_catalog_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    index("vh_miniapp_catalog_ix_0").on(t.tenantId, t.projectId),
    allowedValues("vh_miniapp_catalog_status_ck", t.status, [
      "ACTIVE",
      "DISABLED",
    ]),
    check("vh_miniapp_catalog_ck_0", sql`version > 0`),
  ],
).enableRLS();
