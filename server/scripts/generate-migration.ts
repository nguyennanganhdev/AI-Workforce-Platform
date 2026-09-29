import { readdir, readFile, writeFile, mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const root = resolve(import.meta.dir, "..");
const out = resolve(root, "drizzle");
await mkdir(out, { recursive: true });
const before = (await readdir(out)).filter((f) => f.endsWith(".sql"));
const child = Bun.spawn(
  [
    process.execPath,
    resolve(root, "node_modules/drizzle-kit/bin.cjs"),
    "generate",
    "--config=drizzle.config.ts",
    ...process.argv.slice(2),
  ],
  {
    cwd: root,
    stdout: "inherit",
    stderr: "inherit",
    env: {
      ...process.env,
      DATABASE_URL:
        process.env.DATABASE_URL ??
        "postgres://generate:generate@localhost/generate_only",
    },
  },
);
if ((await child.exited) !== 0) process.exit(1);
const added = (await readdir(out))
  .filter((f) => f.endsWith(".sql") && !before.includes(f))
  .sort();
if (!before.length && added.length === 1) {
  const path = resolve(out, added[0]!);
  const original = await readFile(path, "utf8");
  const invariant = await readFile(
    resolve(root, "src/db/invariants.sql"),
    "utf8",
  );
  const generated = await readFile(
    resolve(root, "src/db/generated-invariants.sql"),
    "utf8",
  );
  await writeFile(
    path,
    "CREATE EXTENSION IF NOT EXISTS vector;\n--> statement-breakpoint\n" +
      original +
      "\n--> statement-breakpoint\n" +
      invariant +
      "\n--> statement-breakpoint\n" +
      generated,
  );
  console.log(
    "Baseline includes pgvector, exclusion constraints, invariant triggers and FORCE RLS.",
  );
}
