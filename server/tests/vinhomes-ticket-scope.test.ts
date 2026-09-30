import { afterAll, describe, expect, test } from "bun:test";
import { PGlite } from "@electric-sql/pglite";
import { drizzle } from "drizzle-orm/pglite";
import type { Database } from "../src/db/client";
import { createTicketReader } from "../src/business/tickets";

const tenantA = "00000000-0000-4000-8000-000000000001";
const tenantB = "00000000-0000-4000-8000-000000000002";
const unitA = "00000000-0000-4000-8000-000000000011";
const unitB = "00000000-0000-4000-8000-000000000012";
const db = new PGlite();
afterAll(() => db.close());

async function seed() {
  await db.exec(`
    CREATE TABLE tenant_memberships (id uuid PRIMARY KEY, tenant_id uuid NOT NULL, user_id text NOT NULL, status text NOT NULL);
    CREATE TABLE access_scopes (id uuid PRIMARY KEY, tenant_id uuid NOT NULL, kind text NOT NULL, management_unit_id uuid, site_id uuid, zone_id uuid, building_id uuid);
    CREATE TABLE scoped_user_roles (id uuid PRIMARY KEY, tenant_id uuid NOT NULL, membership_id uuid NOT NULL, scope_id uuid NOT NULL, role_code text NOT NULL, valid_from timestamptz NOT NULL, valid_to timestamptz);
    CREATE TABLE tickets (id uuid PRIMARY KEY, tenant_id uuid NOT NULL, code text NOT NULL, title text NOT NULL, status text NOT NULL, priority text, severity text NOT NULL, triage_status text NOT NULL, created_at timestamptz NOT NULL, management_unit_id uuid, site_id uuid, zone_id uuid, building_id uuid);
  `);
  await db.query(
    "INSERT INTO tenant_memberships VALUES ($1,$2,'manager','active')",
    ["00000000-0000-4000-8000-000000000021", tenantA],
  );
  await db.query(
    "INSERT INTO access_scopes (id,tenant_id,kind,management_unit_id) VALUES ($1,$2,'management',$3)",
    ["00000000-0000-4000-8000-000000000031", tenantA, unitA],
  );
  await db.query(
    "INSERT INTO scoped_user_roles VALUES ($1,$2,$3,$4,'management',now() - interval '1 day',null)",
    [
      "00000000-0000-4000-8000-000000000041",
      tenantA,
      "00000000-0000-4000-8000-000000000021",
      "00000000-0000-4000-8000-000000000031",
    ],
  );
  for (const [id, tenant, unit, code] of [
    ["00000000-0000-4000-8000-000000000051", tenantA, unitA, "VISIBLE"],
    ["00000000-0000-4000-8000-000000000052", tenantA, unitB, "OTHER-UNIT"],
    ["00000000-0000-4000-8000-000000000053", tenantB, unitA, "OTHER-TENANT"],
  ]) {
    await db.query(
      "INSERT INTO tickets (id,tenant_id,management_unit_id,code,title,status,severity,triage_status,created_at) VALUES ($1,$2,$3,$4,'Test','new','unknown','pending',now())",
      [id, tenant, unit, code],
    );
  }
}

describe("Vinhomes ticket scope", () => {
  test("limits management to active grants and never crosses tenants", async () => {
    await seed();
    const reader = createTicketReader(
      drizzle(db) as unknown as Database,
      tenantA,
    );
    expect(
      (await reader.listForManagement("manager", false)).map(
        (ticket) => ticket.code,
      ),
    ).toEqual(["VISIBLE"]);
    expect(await reader.listForManagement("outsider", false)).toEqual([]);
    expect(
      new Set(
        (await reader.listForManagement("admin", true)).map(
          (ticket) => ticket.code,
        ),
      ),
    ).toEqual(new Set(["VISIBLE", "OTHER-UNIT"]));

    await db.query(
      "UPDATE scoped_user_roles SET valid_to = now() - interval '1 hour'",
    );
    expect(await reader.listForManagement("manager", false)).toEqual([]);

    await db.query("UPDATE scoped_user_roles SET valid_to = null");
    await db.query("UPDATE tenant_memberships SET status = 'suspended'");
    expect(await reader.listForManagement("manager", false)).toEqual([]);
  });
});
