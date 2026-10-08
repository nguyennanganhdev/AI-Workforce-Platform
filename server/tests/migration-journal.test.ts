import { expect, test } from "bun:test";
import { readdir, readFile } from "node:fs/promises";
test("migration journal owns every SQL file and validates available generation snapshots", async () => {
  const dir = new URL("../drizzle/", import.meta.url);
  const sql = (await readdir(dir)).filter((f) => f.endsWith(".sql")).sort();
  if (!sql.length) {
    expect(await Bun.file(new URL("meta/_journal.json", dir)).exists()).toBe(
      false,
    );
    return;
  }
  const journal = JSON.parse(
    await readFile(new URL("meta/_journal.json", dir), "utf8"),
  );
  expect(
    journal.entries.map((e: { tag: string }) => e.tag + ".sql").sort(),
  ).toEqual(sql);
  let last = 0;
  for (const entry of journal.entries) {
    expect(entry.when).toBeGreaterThan(last);
    last = entry.when;
    expect(entry.when).toBeLessThanOrEqual(Date.now() + 60_000);
    // Handwritten SQL migrations need a journal entry, not a drizzle-kit snapshot.
    // Snapshots describe generated ORM state; they are not read by the runtime migrator.
    const snapshot = Bun.file(new URL(`meta/${String(entry.idx).padStart(4, "0")}_snapshot.json`, dir));
    if (entry.idx === 0) expect(await snapshot.exists()).toBe(true);
    if (await snapshot.exists()) {
      const state = await snapshot.json();
      expect(state.version).toBe("7");
      expect(state.dialect).toBe("postgresql");
      expect(typeof state.id).toBe("string");
      expect(typeof state.tables).toBe("object");
    }
  }
  const baseline = await readFile(new URL(sql[0]!, dir), "utf8");
  expect(baseline).toContain("CREATE EXTENSION IF NOT EXISTS vector");
  expect(baseline).toContain("CREATE TRIGGER triage_decision_source");
  expect(baseline).toContain("FORCE ROW LEVEL SECURITY");
});
