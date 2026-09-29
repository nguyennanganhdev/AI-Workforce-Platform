import { generateDrizzleJson, generateMigration } from "drizzle-kit/api";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import * as schema from "../src/db/schema";

const directory = resolve(
  import.meta.dir,
  "../../.codex-artifacts/schema-check",
);
await mkdir(directory, { recursive: true });
const empty = generateDrizzleJson({});
const snapshot = generateDrizzleJson(schema, empty.id);
const statements = await generateMigration(empty, snapshot);
await writeFile(
  resolve(directory, "schema.sql"),
  statements.join(";\n") + ";\n",
);
await writeFile(
  resolve(directory, "snapshot.json"),
  JSON.stringify(snapshot, null, 2),
);
console.log(
  `Validated generation: ${Object.keys(snapshot.tables).length} tables, ${statements.length} statements. No project migration was created.`,
);
