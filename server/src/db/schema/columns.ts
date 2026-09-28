import { sql } from "drizzle-orm";
import type { AnyPgColumn } from "drizzle-orm/pg-core";
import { bigint, check, timestamp } from "drizzle-orm/pg-core";

export { jsonb } from "./json";

export const createdAt = () =>
  timestamp("created_at", { withTimezone: true }).notNull().defaultNow();
export const mutableColumns = () => ({
  version: bigint("version", { mode: "bigint" }).notNull().default(sql`1`),
  updatedAt: timestamp("updated_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

/** Text checks keep lifecycle additions independent of PostgreSQL enum migrations. */
export function allowedValues(
  name: string,
  column: AnyPgColumn,
  values: readonly string[],
) {
  return check(
    name,
    sql`${column} in (${sql.join(
      values.map((value) => sql.raw(`'${value.replaceAll("'", "''")}'`)),
      sql`, `,
    )})`,
  );
}
