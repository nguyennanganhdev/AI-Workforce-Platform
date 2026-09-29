import { sql } from "drizzle-orm";
import { pgPolicy, uuid, type AnyPgColumn } from "drizzle-orm/pg-core";
import { platformTenant } from "./tenant";

/** Set by an authenticated application transaction. No default tenant or client fallback. */
export const tenantId = () =>
  uuid("tenant_id")
    .notNull()
    .default(sql`nullif(current_setting('app.tenant_id', true), '')::uuid`)
    .references(() => platformTenant.id, { onDelete: "restrict" });
export const tenantPolicy = (name: string, column: AnyPgColumn) =>
  pgPolicy(name, {
    for: "all",
    using: sql`${column} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    withCheck: sql`${column} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
  });
