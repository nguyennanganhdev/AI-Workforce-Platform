/** Physical model for platform/domains. See docs/erd/README.md. */
import { sql } from "drizzle-orm";
import {
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
import { allowedValues, createdAt, jsonb, mutableColumns } from "../columns";
import { platformTenant } from "./identity";

export const platformDomainInstallation = pgTable(
  "platform_domain_installation",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    domainNamespace: text("domain_namespace").notNull(),
    domainVersion: text("domain_version").notNull(),
    environment: text("environment").notNull(),
    configJson: jsonb("config_json").notNull(),
    status: text("status", { enum: ["ENABLED", "DISABLED"] }).notNull(),
    installedAt: timestamp("installed_at", { withTimezone: true }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_domain_installation_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_domain_installation_uq_0").on(
      t.tenantId,
      t.domainNamespace,
      t.environment,
    ),
    unique("platform_domain_installation_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_domain_installation_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    index("platform_domain_installation_ix_0").on(t.domainNamespace),
    allowedValues("platform_domain_installation_status_ck", t.status, [
      "ENABLED",
      "DISABLED",
    ]),
    check("platform_domain_installation_ck_0", sql`version > 0`),
  ],
).enableRLS();
