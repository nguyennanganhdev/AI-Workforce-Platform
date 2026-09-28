import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import {
  copyFile,
  mkdir,
  mkdtemp,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { drizzle } from "drizzle-orm/postgres-js";
import { migrate } from "drizzle-orm/postgres-js/migrator";
import postgres from "postgres";
import { testDatabaseUrl } from "./support/database";

async function removeTestDirectory(directory: string) {
  if (
    dirname(resolve(directory)) !== resolve(tmpdir()) ||
    !basename(directory).startsWith("wf-upgrade-")
  ) {
    throw new Error(
      "Refusing to remove a directory outside this test's temporary root",
    );
  }
  await rm(directory, { recursive: true, force: true });
}

test("upgrades 0045 without losing OpenBot identity and replays the ledger safely", async () => {
  const name = `wf_upgrade_${randomUUID().replaceAll("-", "")}`;
  const url = new URL(testDatabaseUrl());
  const control = postgres(url.toString(), { max: 1, onnotice: () => {} });
  url.pathname = `/${name}`;
  const client = postgres(url.toString(), { max: 1, onnotice: () => {} });
  const directory = await mkdtemp(join(tmpdir(), "wf-upgrade-"));
  let created = false;
  try {
    await control`create database ${control(name)}`;
    created = true;
    const migrations = join(import.meta.dir, "..", "drizzle");
    const journal = JSON.parse(
      await readFile(join(migrations, "meta", "_journal.json"), "utf8"),
    );
    const baseline = journal.entries.filter(
      (entry: { idx: number }) => entry.idx <= 45,
    );
    await mkdir(join(directory, "meta"));
    await writeFile(
      join(directory, "meta", "_journal.json"),
      JSON.stringify({ ...journal, entries: baseline }),
    );
    for (const entry of baseline)
      await copyFile(
        join(migrations, `${entry.tag}.sql`),
        join(directory, `${entry.tag}.sql`),
      );
    await migrate(drizzle(client), { migrationsFolder: directory });
    const userId = "existing-auth-text-identifier";
    await client`insert into users(id,email,name) values (${userId},'existing@workforce.test','Existing user')`;
    await migrate(drizzle(client), { migrationsFolder: migrations });
    await migrate(drizzle(client), { migrationsFolder: migrations });
    expect(
      (
        await client`select id from users where email='existing@workforce.test'`
      )[0]?.id,
    ).toBe(userId);
    expect(
      (
        await client`select count(*)::int as n from information_schema.tables where table_schema='public' and table_type='BASE TABLE'`
      )[0]?.n,
    ).toBe(190);
    expect(
      (
        await client`select count(*)::int as n from drizzle.__drizzle_migrations`
      )[0]?.n,
    ).toBe(journal.entries.length);
    expect(
      (
        await client`select count(*)::int as n from pg_class where relnamespace='public'::regnamespace and relkind='r' and relforcerowsecurity`
      )[0]?.n,
    ).toBe(151);
  } finally {
    await client.end();
    if (created) await control`drop database ${control(name)}`;
    await control.end();
    await removeTestDirectory(directory);
  }
}, 60_000);
