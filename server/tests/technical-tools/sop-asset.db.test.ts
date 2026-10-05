import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { sql } from "drizzle-orm";
import { knowledgeDocuments } from "../../src/db/schema";
import {
  createDbSopReadPort,
  type SopReadPort,
} from "../../src/technical-tools";
import { SOPS, sopByKey } from "./fixtures/sop";
import { BUILDING, TENANT } from "./fixtures/world";
import {
  DATABASE_SETUP_TIMEOUT_MS,
  type TestDatabase,
  technicalToolsTestDatabase,
} from "./support/database";

/**
 * The SOP adapter against the real schema.
 *
 * Only what a database can get wrong is asked here: which documents a building's scope reaches,
 * whether the version pointer and the access rows come back intact, and whether another tenant's
 * library can leak. Which of them may be followed is the rules' question and is tested without a
 * database.
 */
let db: TestDatabase;
let port: SopReadPort;

beforeAll(async () => {
  db = await technicalToolsTestDatabase();
  port = createDbSopReadPort(db.database);
}, DATABASE_SETUP_TIMEOUT_MS);

afterAll(() => db?.close());

const keyOf = (documentId: string) =>
  SOPS.find((sop) => sop.documentId === documentId)?.key ?? documentId;

async function keysFor(buildingId: string, tenantId: string = TENANT.vinhomes) {
  const records = await port.listForBuilding({ tenantId, buildingId });
  return records?.map((record) => keyOf(record.documentId)).sort() ?? null;
}

describe("which documents reach a building", () => {
  /*
   * The scope rules, all four at once. S1 names building A1; S2 names zone S1; S3 names the site;
   * S15 names the whole tenant. S10 belongs to the other zone and S11 is a site document that does
   * not apply to descendants, so neither reaches an apartment.
   */
  test("its own scope, its zone, its site and the tenant", async () => {
    expect(await keysFor(BUILDING.a1)).toEqual([
      "S1",
      "S12",
      "S13",
      "S14",
      "S15",
      "S2",
      "S3",
      "S4",
      "S5",
      "S6",
      "S7",
      "S8",
      "S9",
    ]);
  });

  /*
   * Deliberately a superset. Drafts, archived documents, lapsed versions, the English edition and
   * the retired collection all come back from here, because deciding which of them is guidance is
   * `sop-rules`' job and keeping that decision in one place is what lets it be tested without a
   * database.
   */
  test("and everything in scope, whatever state it is in", async () => {
    const records = await port.listForBuilding({
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
    });
    expect(records?.map((record) => record.status)).toEqual(
      expect.arrayContaining(["published", "draft", "archived"]),
    );
    expect(records?.map((record) => record.language)).toContain("en");
  });

  test("a neighbour in the same zone shares the zone's, the site's and the tenant's", async () => {
    expect(await keysFor(BUILDING.a2)).toEqual(["S15", "S2", "S3"]);
  });

  test("a building in the other zone gets that zone's instead", async () => {
    expect(await keysFor(BUILDING.b1)).toEqual(["S10", "S15", "S3"]);
  });

  /*
   * `applies_to_descendants` is how guidance meant for one level is kept from being served at
   * every level below it. Without it, the whole-site instructions for the water plant would be
   * offered as the procedure for a tap in an apartment.
   */
  test("a site document that does not apply to descendants reaches no building", async () => {
    for (const building of [BUILDING.a1, BUILDING.a2, BUILDING.b1]) {
      expect(await keysFor(building)).not.toContain("S11");
    }
  });

  test("a zone's document does not reach a building in another zone", async () => {
    expect(await keysFor(BUILDING.a1)).not.toContain("S10");
    expect(await keysFor(BUILDING.b1)).not.toContain("S2");
  });
});

describe("what comes back with each document", () => {
  test("the state and the active version, as the tables hold them", async () => {
    const records = await port.listForBuilding({
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
    });
    const found = records?.find(
      (record) => record.documentId === sopByKey("S1").documentId,
    );

    expect(found).toMatchObject({
      code: "SOP-ELEC-001",
      status: "published",
      knowledgeBaseStatus: "active",
      language: "vi",
    });
    expect(found?.activeVersion).toMatchObject({
      versionNo: 3,
      effectiveFrom: new Date("2026-01-01T00:00:00Z"),
      effectiveTo: null,
    });
    expect(found?.activeVersion?.contentHash).toMatch(/^[0-9a-f]{64}$/);
  });

  test("a lapsed version keeps the date it lapsed on", async () => {
    const records = await port.listForBuilding({
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
    });
    const lapsed = records?.find(
      (record) => record.documentId === sopByKey("S5").documentId,
    );
    expect(lapsed?.activeVersion?.effectiveTo).toEqual(
      new Date("2026-09-01T00:00:00Z"),
    );
  });

  /*
   * A document whose version pointer was never set is a configuration mistake. Left out of the
   * answer it would look like a document that does not exist, and nobody would know to fix it.
   */
  test("a document with no active version comes back with none", async () => {
    const records = await port.listForBuilding({
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
    });
    const unversioned = records?.find(
      (record) => record.documentId === sopByKey("S14").documentId,
    );
    expect(unversioned).toBeDefined();
    expect(unversioned?.activeVersion).toBeNull();
  });

  test("the retired collection's own status, not the document's", async () => {
    const records = await port.listForBuilding({
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
    });
    const retired = records?.find(
      (record) => record.documentId === sopByKey("S13").documentId,
    );
    expect(retired).toMatchObject({
      status: "published",
      knowledgeBaseStatus: "archived",
    });
  });

  test("every access row of the document, and none of another's", async () => {
    const records = await port.listForBuilding({
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
    });
    const withDeny = records?.find(
      (record) => record.documentId === sopByKey("S7").documentId,
    );
    expect(withDeny?.acl).toHaveLength(2);
    expect(withDeny?.acl).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          principalKind: "role",
          roleCode: "management",
          effect: "allow",
        }),
        expect.objectContaining({
          principalKind: "role",
          roleCode: "staff",
          effect: "deny",
        }),
      ]),
    );

    const withNone = records?.find(
      (record) => record.documentId === sopByKey("S8").documentId,
    );
    expect(withNone?.acl).toEqual([]);
  });
});

describe("a building the tenant does not have", () => {
  test("no such building at all", async () => {
    expect(await keysFor(BUILDING.missing)).toBeNull();
  });

  test("another tenant's building, asked for under this tenant", async () => {
    expect(await keysFor(BUILDING.x1)).toBeNull();
  });

  test("which does have a library, for the tenant that owns it", async () => {
    // The positive control: without it the two above would pass on an empty table.
    expect(await keysFor(BUILDING.x1, TENANT.other)).toEqual(["S16"]);
  });

  test("and that library never appears for the managed tenant", async () => {
    expect(await keysFor(BUILDING.a1)).not.toContain("S16");
  });
});

/*
 * Tenant isolation that does not depend on the adapter remembering its `tenant_id` filter. This
 * query deliberately has none; what comes back is decided by the policy on the table alone.
 */
describe("row-level security, with the tenant filter left out", () => {
  const visibleTo = (tenantId: string | null) =>
    db.database.transaction(async (tx) => {
      if (tenantId) {
        await tx.execute(
          sql`select set_config('app.tenant_id', ${tenantId}, true)`,
        );
      }
      const rows = await tx
        .select({ code: knowledgeDocuments.code })
        .from(knowledgeDocuments);
      return rows.map((row) => row.code).sort();
    });

  test("one tenant sees its own fifteen documents and not the other's", async () => {
    const visible = await visibleTo(TENANT.vinhomes);
    expect(visible).toHaveLength(15);
    expect(visible).not.toContain("SOP-X-001");
  });

  test("the other tenant sees only its one", async () => {
    expect(await visibleTo(TENANT.other)).toEqual(["SOP-X-001"]);
  });

  test("a query that never says which tenant it is for sees nothing", async () => {
    expect(await visibleTo(null)).toEqual([]);
  });
});

describe("what the role the tools run as cannot do", () => {
  test.each([
    [
      "publish a draft",
      sql`update knowledge_documents set status = 'published' where status = 'draft'`,
    ],
    [
      "grant itself a document",
      sql`insert into document_acl (tenant_id, document_id, principal_kind, role_code, effect) values (gen_random_uuid(), gen_random_uuid(), 'role', 'staff', 'allow')`,
    ],
    ["read the files behind the documents", sql`select 1 from file_objects`],
  ])("%s", async (_label, statement) => {
    const failure: { cause?: unknown } | null = await Promise.resolve(
      db.database.execute(statement),
    ).then(
      () => null,
      (error) => error,
    );
    // Drizzle wraps the driver's error; the database's own reason is the cause.
    expect(String(failure?.cause)).toMatch(/permission denied/);
  });

  test("and every document is still there afterwards", async () => {
    expect(await keysFor(BUILDING.a1)).toHaveLength(13);
  });
});
