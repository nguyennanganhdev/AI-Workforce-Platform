/**
 * Bring an existing database up to this release: the migrations, then the grants of the three
 * restricted roles the services connect with.
 *
 * A release that adds a table or a column also adds a line to the grant scripts, so the grants
 * are applied again every time. Role names are read from the services' own connection settings.
 * Creating the roles and the first organisation is not done here.
 *
 * Last, the technical tool host's catalogue is registered for the tenant, so an agent's
 * configuration can name the tools this release serves. The API's own tools are registered by the
 * `catalogue` job, from the API image.
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
const routinesRole = roleOf("ROUTINES_DATABASE_URL");
const connectionsRole = roleOf("OPENBOT_DATABASE_URL");

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
  const routines = (
    await readFile("server/scripts/grant_routines_role.sql", "utf8")
  ).replaceAll("vinhomes_routines", routinesRole);
  await sql.unsafe(api);
  await sql.unsafe(tools);
  await sql.unsafe(routines);
  const connections = (await readFile("server/scripts/grant_business_connections_role.sql", "utf8"))
    .replaceAll("vinhomes_business_connections", connectionsRole);
  await sql.unsafe(connections);
  console.log(
    JSON.stringify({
      type: "grants-applied",
      roles: [apiRole, toolsRole, routinesRole, connectionsRole],
    }),
  );
  const tenant = process.env.VINHOMES_TENANT_ID;
  if (!tenant) throw new Error("VINHOMES_TENANT_ID is required");
  // The catalogue comes from the tools themselves, so what is registered is what the host runs.
  const { describeTechnicalTools } = await import(
    `${process.cwd()}/server/src/technical-tools`
  );
  const described = describeTechnicalTools();
  await sql.begin(async (tx) => {
    await tx`select set_config('app.tenant_id', ${tenant}, true)`;
    await tx`
      insert into mcp_servers(id,title,vendor,url,provenance,tenant_id)
      values('technical-tools','Công cụ kỹ thuật','Team Quang','internal:/internal/technical/v1','first-party',${tenant})
      on conflict (id) do update set title=excluded.title,updated_at=now()`;
    for (const tool of described)
      await tx`
        insert into mcp_tools(server_id,name,description,input_schema,effect,destructive,version,tenant_id)
        values('technical-tools',${tool.name},${tool.description},${tx.json(tool.input_schema)},${tool.side_effect},false,${tool.version},${tenant})
        on conflict (server_id,name) do update set description=excluded.description,
          input_schema=excluded.input_schema,effect=excluded.effect,version=excluded.version`;
  });
  console.log(
    JSON.stringify({ type: "technical-tools-registered", count: described.length }),
  );
} finally {
  await sql.end();
}
