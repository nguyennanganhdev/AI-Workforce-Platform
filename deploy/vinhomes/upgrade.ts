/**
 * Bring an existing database up to this release: the migrations, then the grants of the two
 * restricted roles the services connect with.
 *
 * A release that adds a table or a column also adds a line to the grant scripts, so the grants
 * are applied again every time. Role names are read from the services' own connection settings.
 * Creating the roles and the first organisation is not done here.
 */
import { readFile } from "node:fs/promises";
import postgres from "postgres";

const owner = process.env.DATABASE_URL;
if (!owner)
  throw new Error(
    "MIGRATION_DATABASE_URL (the database owner) is required for an upgrade",
  );

function roleOf(setting: string): string {
  const url = process.env[setting];
  if (!url) throw new Error(`${setting} is required`);
  const role = decodeURIComponent(
    new URL(url.replace(/^postgresql\+asyncpg:/, "postgresql:")).username,
  );
  if (!/^[a-z_][a-z0-9_]*$/.test(role))
    throw new Error(`${setting} names an unexpected role`);
  return role;
}
const apiRole = roleOf("VINHOMES_API_DATABASE_URL");
const toolsRole = roleOf("TECHNICAL_API_DATABASE_URL");

const migrated = Bun.spawnSync(["bun", "server/scripts/migrate.ts"], {
  stdout: "inherit",
  stderr: "inherit",
});
if (migrated.exitCode !== 0) process.exit(migrated.exitCode ?? 1);

const sql = postgres(owner, { max: 1 });
try {
  const [{ name }] = await sql`select current_database() as name`;
  const api = (
    await readFile(
      "services/vinhomes-api/scripts/grant_v3_api_role.sql",
      "utf8",
    )
  )
    .replaceAll("DATABASE vinhomes_v3 TO", `DATABASE "${name}" TO`)
    .replaceAll("vinhomes_v3_api", apiRole);
  const tools = (
    await readFile("server/scripts/grant_technical_api_role.sql", "utf8")
  ).replaceAll("vinhomes_technical_api", toolsRole);
  await sql.unsafe(api);
  await sql.unsafe(tools);
  console.log(
    JSON.stringify({ type: "grants-applied", roles: [apiRole, toolsRole] }),
  );
} finally {
  await sql.end();
}
