import { describe, expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { getTableName, is } from "drizzle-orm";
import { getTableConfig, PgTable } from "drizzle-orm/pg-core";
import * as schema from "../src/db/schema";

const tables = Object.values(schema).filter(
  (v): v is PgTable =>
    is(v, PgTable) && /^(platform_|vh_)/.test(getTableName(v)),
);

describe("workforce physical model", () => {
  test("covers the complete documented domain inventory", async () => {
    const source = await readFile(
      new URL("../../docx/02_VINHOMES_DOMAIN_ERD.md", import.meta.url),
      "utf8",
    );
    const names = new Set(tables.map(getTableName));
    const documented = new Set(
      [...source.matchAll(/`(vh_[a-z_]+)`/g)].map((m) => m[1]),
    );
    expect([...documented].filter((name) => !names.has(name))).toEqual([]);
    expect(tables).toHaveLength(152);
  });

  test("every domain relationship is tenant scoped and never references runtime", () => {
    for (const table of tables.filter((t) =>
      getTableName(t).startsWith("vh_"),
    )) {
      const config = getTableConfig(table);
      expect(config.columns.find((c) => c.name === "tenant_id")?.notNull).toBe(
        true,
      );
      for (const fk of config.foreignKeys) {
        const ref = fk.reference();
        const target = getTableName(ref.foreignTable);
        expect(
          target.startsWith("vh_") ||
            ["users", "platform_tenant", "platform_tenant_membership"].includes(
              target,
            ),
        ).toBe(true);
        if (target !== "users" && target !== "platform_tenant") {
          expect(ref.columns.map((c) => c.name)).toContain("tenant_id");
          expect(ref.foreignColumns.map((c) => c.name)).toContain("tenant_id");
        }
        expect(fk.onDelete).toBe("restrict");
      }
    }
  });

  test("tenant policies, bigint money and existing text user IDs are present", () => {
    for (const table of tables) {
      const config = getTableConfig(table);
      if (config.name !== "platform_domain_package") {
        expect(config.enableRLS).toBe(true);
        expect(config.policies).toHaveLength(1);
      }
      for (const col of config.columns) {
        if (col.name.endsWith("_minor"))
          expect(col.getSQLType()).toBe("bigint");
        if (col.name === "version") expect(col.getSQLType()).toBe("bigint");
      }
      for (const key of config.foreignKeys) {
        const ref = key.reference();
        if (getTableName(ref.foreignTable) === "users")
          // FK source columns are Drizzle ExtraConfigColumn objects; inspect the
          // actual table column (ExtraConfigColumn.getSQLType recurses in 0.45).
          expect(
            config.columns
              .find((c) => c.name === ref.columns[0]?.name)
              ?.getSQLType(),
          ).toBe("text");
        expect(key.getName().length).toBeLessThanOrEqual(63);
      }
      for (const constraint of config.checks)
        expect(constraint.name.length).toBeLessThanOrEqual(63);
    }
  });

  test("the migration generator sees every exported table", async () => {
    const snapshot = await Bun.file(
      new URL("../drizzle/meta/0050_snapshot.json", import.meta.url),
    ).json();
    for (const table of tables)
      expect(snapshot.tables[`public.${getTableName(table)}`]).toBeDefined();
  });

  test("every project table has a documented purpose", async () => {
    const purposes = await Bun.file(
      new URL("../scripts/table-purposes.json", import.meta.url),
    ).json();
    const allNames = Object.values(schema)
      .filter((v): v is PgTable => is(v, PgTable))
      .map(getTableName)
      .sort();
    expect(Object.keys(purposes).sort()).toEqual(allNames);
    expect(allNames).toHaveLength(190);
    for (const purpose of Object.values(purposes))
      expect(String(purpose).length).toBeGreaterThan(20);
  });
});
