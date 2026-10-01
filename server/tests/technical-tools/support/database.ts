import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { PGlite } from "@electric-sql/pglite";
import { btree_gist } from "@electric-sql/pglite/contrib/btree_gist";
import { vector } from "@electric-sql/pglite-pgvector";
import { drizzle as drizzlePglite } from "drizzle-orm/pglite";
import { drizzle as drizzlePostgres } from "drizzle-orm/postgres-js";
import { migrate } from "drizzle-orm/postgres-js/migrator";
import postgres from "postgres";
import { createDatabase } from "../../../src/db/client";
import * as schema from "../../../src/db/schema";
import type { TechnicalToolsDatabase } from "../../../src/technical-tools";
import { testDatabaseUrl } from "../../support/database";
import { seedWorld } from "./seed-db";

const MIGRATIONS = resolve(import.meta.dir, "../../../drizzle");
const BASELINE = resolve(MIGRATIONS, "0000_grey_blockbuster.sql");

/**
 * The role the tools' queries run as. It reads what the tools read, and may insert into the three
 * tables a water isolation request is written to: insert, never update or delete, so a request it
 * writes cannot be turned into an approval or an outage by anything running as it.
 */
const RUNTIME_ROLE = "technical_tools_runtime";

/** Everything that role is given, which is also the whole of what the tools need. */
const runtimeGrants = (role: string) => `
  GRANT USAGE ON SCHEMA public TO ${role};
  GRANT SELECT ON buildings, access_scopes, service_interruptions, interruption_scopes TO ${role};
  GRANT SELECT ON knowledge_bases, knowledge_documents, document_versions, document_scopes,
    document_acl TO ${role};
  GRANT SELECT ON tickets, work_orders, work_assignments, staff_profiles, evidence_items, files
    TO ${role};
  GRANT SELECT ON units, unit_residents TO ${role};
  GRANT SELECT, INSERT ON work_approvals TO ${role};
  GRANT INSERT ON service_interruptions, interruption_scopes TO ${role};
`;

export type TestDatabase = {
  engine: "pglite" | "postgres";
  /** Connected as the runtime role, so row-level security applies to everything read through it. */
  database: TechnicalToolsDatabase;
  /** A raw statement as the runtime role, for questions about the session itself. */
  rows<T>(statement: string): Promise<T[]>;
  close(): Promise<void>;
};

/**
 * A real PostgreSQL, in process, holding the real schema.
 *
 * PGlite is PostgreSQL compiled to WASM, and what is loaded into it is the published baseline
 * migration itself: all 148 tables with their foreign keys, checks, triggers and row-level security.
 * `scripts/verify-baseline.mjs` verifies the schema the same way. A fake repository could not show
 * that a query respects a policy, and a hand-written subset of the schema would show that it
 * respects the subset.
 *
 * The sample estate is seeded as the owner, then the session drops to a role that is not a
 * superuser. Row-level security does not apply to superusers at all, FORCE or not, so tests run as
 * the owner would pass whether or not a query set its tenant.
 */
async function openPglite(shared: boolean): Promise<TestDatabase> {
  const client = new PGlite({ extensions: { vector, btree_gist } });
  await client.exec(await readFile(BASELINE, "utf8"));
  const database = drizzlePglite({ client, schema });
  await seedWorld(database);
  await client.exec(`
    CREATE ROLE ${RUNTIME_ROLE} NOLOGIN;
    ${runtimeGrants(RUNTIME_ROLE)}
    SET ROLE ${RUNTIME_ROLE};
  `);
  return {
    engine: "pglite",
    database,
    rows: async <T>(statement: string) =>
      (await client.query<T>(statement)).rows,
    // The shared instance is gone with the process; a file's own instance is released with it.
    close: async () => {
      if (!shared) await client.close();
    },
  };
}

function withCredentials(
  url: string,
  change: { database: string; user?: string; password?: string },
) {
  const next = new URL(url);
  next.pathname = `/${change.database}`;
  if (change.user) next.username = change.user;
  if (change.password) next.password = change.password;
  return next.toString();
}

/**
 * The same thing on a PostgreSQL server, through the drivers the deployment uses.
 *
 * A database of its own, created beside the one `TEST_DATABASE_URL` names and dropped afterwards,
 * so nothing here depends on or disturbs what is already in the test database. The baseline goes in
 * through Drizzle's migrator, which is what `scripts/migrate.ts` runs at start-up, and the tools
 * read through `createDatabase`, which is the server's own Bun SQL client: the one driver PGlite
 * cannot stand in for.
 *
 * The runtime role is a real login here, since a pooled connection cannot be dropped to a role
 * with `SET ROLE` the way a single PGlite session can.
 */
async function openPostgres(adminUrl: string): Promise<TestDatabase> {
  const suffix = randomUUID().replaceAll("-", "").slice(0, 12);
  const databaseName = `technical_tools_test_${suffix}`;
  const role = `${RUNTIME_ROLE}_${suffix}`;
  const password = randomUUID().replaceAll("-", "");
  const ownerUrl = withCredentials(adminUrl, { database: databaseName });

  const admin = postgres(adminUrl, { max: 1, onnotice: () => {} });
  const drop = async () => {
    await admin.unsafe(`DROP DATABASE IF EXISTS ${databaseName} WITH (FORCE)`);
    await admin.unsafe(`DROP ROLE IF EXISTS ${role}`);
    await admin.end({ timeout: 5 });
  };

  try {
    await admin.unsafe(`CREATE DATABASE ${databaseName}`);

    const owner = postgres(ownerUrl, { max: 1, onnotice: () => {} });
    try {
      await migrate(drizzlePostgres(owner), { migrationsFolder: MIGRATIONS });
      await owner.unsafe(`
        CREATE ROLE ${role} LOGIN PASSWORD '${password}';
        GRANT CONNECT ON DATABASE ${databaseName} TO ${role};
        ${runtimeGrants(role)}
      `);
    } finally {
      await owner.end({ timeout: 5 });
    }

    // Seeded through the server's own client: the schema's `jsonb` type hands Bun's driver an
    // object to serialise, and another driver would store it differently.
    const seeding = createDatabase(ownerUrl, { max: 1 });
    try {
      await seedWorld(seeding);
    } finally {
      await seeding.$client.close({ timeout: 5 });
    }

    const database = createDatabase(
      withCredentials(adminUrl, {
        database: databaseName,
        user: role,
        password,
      }),
      { max: 2 },
    );
    return {
      engine: "postgres",
      database,
      rows: async <T>(statement: string) =>
        (await database.$client.unsafe(statement)) as T[],
      close: async () => {
        await database.$client.close({ timeout: 5 });
        await drop();
      },
    };
  } catch (error) {
    await drop().catch(() => {});
    throw error;
  }
}

let sharedPglite: Promise<TestDatabase> | undefined;

/**
 * The seeded schema the technical-tool tests read.
 *
 * In process by default, so the suite needs nothing installed and nothing running. With
 * `TEST_DATABASE_URL` set, as it is in CI, the same tests run against that PostgreSQL server
 * instead. The variable is read through the repository's own `testDatabaseUrl`, which refuses the
 * live `openbot` database.
 *
 * The in-process instance is shared by every file that only reads: loading the baseline takes
 * about ten seconds. A file whose tools write asks for `isolated`.
 */
export function technicalToolsTestDatabase(
  options: { isolated?: boolean } = {},
): Promise<TestDatabase> {
  if (process.env.TEST_DATABASE_URL?.trim()) {
    return openPostgres(testDatabaseUrl());
  }
  // A file that writes gets a database of its own, so the counts the read tests assert on stay
  // what the seed made them. On PostgreSQL every file already has its own.
  if (options.isolated) return openPglite(false);
  sharedPglite ??= openPglite(true);
  return sharedPglite;
}

/** Long enough to load the baseline on a slow machine; the default hook timeout is five seconds. */
export const DATABASE_SETUP_TIMEOUT_MS = 180_000;
