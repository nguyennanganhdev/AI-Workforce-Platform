import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import {
  type BuildingAccessPort,
  type ContextResolver,
  createDbInterruptionReadPort,
  createDbScopeReadPort,
  createScopeBuildingAccess,
} from "../../src/technical-tools";
import { BUILDING, SCOPE, TENANT } from "./fixtures/world";
import {
  DATABASE_SETUP_TIMEOUT_MS,
  type TestDatabase,
  technicalToolsTestDatabase,
} from "./support/database";
import {
  fixtureBuildingAccess,
  fixtureContextResolver,
  technicalToolHarness,
} from "./support/harness";

/**
 * Grants made on access scopes (the scoped grant of dev_TeamQuang, 17e5826): which buildings a
 * granted scope reaches, and the host refusing a call whose building the grant for that very
 * capability does not reach.
 *
 * The same questions are asked of the fixture scopes and of the real `access_scopes`, so the
 * in-memory answer cannot drift from the database's.
 */
let db: TestDatabase;
let fromDatabase: BuildingAccessPort;

beforeAll(async () => {
  db = await technicalToolsTestDatabase();
  fromDatabase = createScopeBuildingAccess(createDbScopeReadPort(db.database));
}, DATABASE_SETUP_TIMEOUT_MS);

afterAll(() => db?.close());

const CASES: [string, string[], string, boolean][] = [
  ["a building's own scope reaches it", [SCOPE.buildingA1], BUILDING.a1, true],
  ["and not its neighbour", [SCOPE.buildingA1], BUILDING.a2, false],
  ["a zone reaches the buildings in it", [SCOPE.zoneS1], BUILDING.a2, true],
  ["and not a building in another zone", [SCOPE.zoneS1], BUILDING.b1, false],
  [
    "a site reaches every building on it",
    [SCOPE.siteOceanPark],
    BUILDING.b1,
    true,
  ],
  [
    "the whole tenant reaches every building it has",
    [SCOPE.tenantWide],
    BUILDING.b1,
    true,
  ],
  [
    "another tenant's scope grants nothing here",
    [SCOPE.buildingX1],
    BUILDING.a1,
    false,
  ],
  [
    "a scope that does not exist grants nothing",
    ["30000000-0000-4000-8000-000000000099"],
    BUILDING.a1,
    false,
  ],
  ["no scopes grant nothing", [], BUILDING.a1, false],
  [
    "a building the tenant does not have is reached by nothing",
    [SCOPE.tenantWide],
    BUILDING.x1,
    false,
  ],
  [
    "one scope in a list reaching it is enough",
    [SCOPE.buildingB1, SCOPE.zoneS1],
    BUILDING.a1,
    true,
  ],
];

describe.each([
  ["the fixture scopes", () => fixtureBuildingAccess],
  ["the real access_scopes", () => fromDatabase],
] as const)("which buildings a grant reaches, from %s", (_source, access) => {
  test.each(CASES)("%s", async (_label, scopeIds, buildingId, expected) => {
    expect(
      await access().canAccessBuilding({
        tenantId: TENANT.vinhomes,
        buildingId,
        scopeIds,
      }),
    ).toBe(expected);
  });
});

const OUTAGE = "technical/get_active_outage";
const outage = (building_id: string) => ({
  building_id,
  service_type: "water",
  occurred_at: "2026-09-30T08:30:00Z",
});

/** The technical agent, holding one capability over one set of scopes. */
const grantedOnly =
  (capability: string, scope_ids: string[]): ContextResolver =>
  async (caller) => {
    const identity = await fixtureContextResolver(caller);
    return identity && { ...identity, grants: [{ capability, scope_ids }] };
  };

describe("the host, asking for the grant of the capability the tool needs", () => {
  const ports = () => ({
    interruptions: createDbInterruptionReadPort(db.database),
  });

  test("a zone-wide grant opens every building in the zone and nothing else", async () => {
    const harness = technicalToolHarness(ports(), {
      contextResolver: grantedOnly("interruption:read", [SCOPE.zoneS1]),
    });
    const inZone = await harness.call(OUTAGE, outage(BUILDING.a2));
    const outside = await harness.call(OUTAGE, outage(BUILDING.b1));

    expect(inZone.envelope.status).toBe("OK");
    expect(outside.envelope.status).toBe("FORBIDDEN");
    expect(harness.auditEntries[1]?.detail).toBe(
      "The building is outside the caller's grant.",
    );
  });

  /*
   * Where a caller holds one capability says nothing about another. A grant to read SOPs across
   * the whole site must not let the same caller read outages there.
   */
  test("a grant for one capability does not lend its scopes to another", async () => {
    const harness = technicalToolHarness(ports(), {
      contextResolver: async (caller) => {
        const identity = await fixtureContextResolver(caller);
        return (
          identity && {
            ...identity,
            grants: [
              { capability: "sop:read", scope_ids: [SCOPE.siteOceanPark] },
              {
                capability: "interruption:read",
                scope_ids: [SCOPE.buildingA1],
              },
            ],
          }
        );
      },
    });
    expect(
      (await harness.call(OUTAGE, outage(BUILDING.a1))).envelope.status,
    ).toBe("OK");
    expect(
      (await harness.call(OUTAGE, outage(BUILDING.b1))).envelope.status,
    ).toBe("FORBIDDEN");
  });

  test("holding a capability over no scope at all is holding it nowhere", async () => {
    const harness = technicalToolHarness(ports(), {
      contextResolver: grantedOnly("interruption:read", []),
    });
    const { envelope } = await harness.call(OUTAGE, outage(BUILDING.a1));
    expect(envelope.status).toBe("FORBIDDEN");
    expect(harness.auditEntries[0]?.detail).toBe(
      "The building is outside the caller's grant.",
    );
  });

  test("a building access check that fails refuses nothing silently: the call fails", async () => {
    const harness = technicalToolHarness(ports(), {
      buildingAccess: {
        canAccessBuilding: async () => {
          throw new Error("scope service down");
        },
      },
    });
    const { envelope } = await harness.call(OUTAGE, outage(BUILDING.a1));
    expect(envelope.status).toBe("INTERNAL_ERROR");
    expect(harness.auditEntries[0]?.detail).toBe(
      "The caller's building access could not be checked.",
    );
    expect(JSON.stringify(envelope)).not.toContain("scope service down");
  });

  test("the refusal reads the same whether the building is outside the grant or nowhere", async () => {
    const harness = technicalToolHarness(ports());
    const outside = await harness.call(OUTAGE, outage(BUILDING.b1));
    const nowhere = await harness.call(OUTAGE, outage(BUILDING.missing));
    expect(outside.envelope.errors).toEqual(nowhere.envelope.errors);
  });
});
