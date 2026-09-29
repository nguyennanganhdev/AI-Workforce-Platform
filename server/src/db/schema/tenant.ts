/** Shared tenant root. No dependency on user, agent or domain tables. */
import { sql } from "drizzle-orm";
import {
  pgTable,
  pgPolicy,
  uuid,
  text,
  unique,
  check,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, mutableColumns } from "./columns";

export const platformTenant = pgTable(
  "platform_tenant",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    code: text("code").notNull(),
    name: text("name").notNull(),
    status: text("status", {
      enum: ["ACTIVE", "SUSPENDED", "RETIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_tenant_tenant_policy", {
      for: "all",
      using: sql`${t.id} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.id} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_tenant_uq_0").on(t.code),
    allowedValues("platform_tenant_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "RETIRED",
    ]),
    check("platform_tenant_ck_0", sql`version > 0`),
  ],
).enableRLS();
