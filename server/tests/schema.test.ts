import { describe, expect, test } from "bun:test";
import { getTableName, is } from "drizzle-orm";
import { getTableConfig, PgTable } from "drizzle-orm/pg-core";
import * as schema from "../src/db/schema";
import design from "../src/db/design/merged.json";
describe("Reviewed V2 + V3 application schema", () => {
  const tables = Object.values(schema).filter((v): v is PgTable =>
    is(v, PgTable),
  );
  const configs = new Map(tables.map((t) => [t, getTableConfig(t)]));
  test("exports exactly 148 application tables and excludes framework state", () => {
    expect(tables.map(getTableName).sort()).toEqual(Object.keys(design).sort());
    expect(tables).toHaveLength(148);
    expect(tables.map(getTableName)).not.toContain("checkpoints");
  });
  test("preserves all specified columns and nullability", () => {
    for (const table of tables) {
      const name = getTableName(table) as keyof typeof design;
      const config = configs.get(table)!;
      expect(config.columns.map((c) => c.name).sort()).toEqual(
        design[name].rows.map((r) => r[0]).sort(),
      );
      for (const row of design[name].rows) {
        const column = config.columns.find((c) => c.name === row[0])!;
        expect(column.notNull).toBe(row[2]!.includes("NOT NULL"));
      }
    }
  });
  test("uses type-compatible tenant-composite references", () => {
    for (const table of tables) {
      const config = configs.get(table)!;
      for (const key of config.foreignKeys) {
        expect(key.getName().length).toBeLessThanOrEqual(63);
        const ref = key.reference();
        const parent = configs.get(ref.foreignTable)!;
        expect(
          ref.columns.map((c) =>
            config.columns
              .find((actual) => actual.name === c.name)!
              .getSQLType(),
          ),
        ).toEqual(
          ref.foreignColumns.map((c) =>
            parent.columns
              .find((actual) => actual.name === c.name)!
              .getSQLType(),
          ),
        );
        const childTenant = config.columns.find((c) => c.name === "tenant_id");
        const parentTenant = parent.columns.find((c) => c.name === "tenant_id");
        if (
          childTenant &&
          parentTenant?.notNull &&
          !ref.columns.some((c) => c.name === "tenant_id")
        )
          throw new Error(`Unscoped reference ${key.getName()}`);
      }
    }
  });
  test("separates severity and priority, supports phone identities and RAG", () => {
    expect(schema.users.email.notNull).toBe(false);
    expect(schema.users.phoneE164.getSQLType()).toBe("text");
    expect(schema.tickets.priority.notNull).toBe(false);
    expect(schema.dispatchQueue.priorityRank.getSQLType()).toBe("integer");
    expect(schema.knowledgeEmbeddings.embedding.getSQLType()).toBe(
      "vector(1536)",
    );
  });
});
