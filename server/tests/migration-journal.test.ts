import { expect, test } from "bun:test";
import { readdir, readFile } from "node:fs/promises";
test("migration reset is clean or the new journal owns every SQL file", async () => {
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
    expect(
      await Bun.file(
        new URL(
          `meta/${String(entry.idx).padStart(4, "0")}_snapshot.json`,
          dir,
        ),
      ).exists(),
    ).toBe(true);
  }
  const baseline = await readFile(new URL(sql[0]!, dir), "utf8");
  expect(baseline).toContain("CREATE EXTENSION IF NOT EXISTS vector");
  expect(baseline).toContain("CREATE TRIGGER triage_decision_source");
  expect(baseline).toContain("FORCE ROW LEVEL SECURITY");
});
