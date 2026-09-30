import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import {
  createDbSopReadPort,
  createInMemoryAssetReadPort,
  createInMemorySopProfilePort,
  type SopReadPort,
  type ToolDependencies,
} from "../../src/technical-tools";
import { ASSETS } from "./fixtures/assets";
import { SOP_PROFILES, sopByKey } from "./fixtures/sop";
import { AGENT_VERSION, BUILDING, CALLER, NOW, TENANT } from "./fixtures/world";
import { technicalToolHarness } from "./support/harness";
import {
  DATABASE_SETUP_TIMEOUT_MS,
  type TestDatabase,
  technicalToolsTestDatabase,
} from "./support/database";

/**
 * `sop_kb.retrieve` and `asset.read` end to end, the way a Bot's call reaches them: through the
 * function `/api/agent-tools/call` is handed, down through the host's checks, into the adapters,
 * and back out as the envelope the agent reads.
 *
 * The SOP side runs against the real schema. The asset side runs against the in-memory adapter,
 * because no table holds equipment yet; the catalogue it is given is the test's, so nothing
 * invented ships in the module.
 */
let db: TestDatabase;
let ports: Partial<ToolDependencies>;

beforeAll(async () => {
  db = await technicalToolsTestDatabase();
  const sop: SopReadPort = createDbSopReadPort(db.database);
  ports = {
    sop,
    sopProfiles: createInMemorySopProfilePort(SOP_PROFILES),
    assets: createInMemoryAssetReadPort(ASSETS),
  };
}, DATABASE_SETUP_TIMEOUT_MS);

afterAll(() => db?.close());

const SOP = "sop_kb/retrieve";
const ASSET = "asset/read";

const sopArgs = (
  building_id: string,
  issue_code: string,
  query: string,
  rest: Record<string, unknown> = {},
) => ({ building_id, issue_code, query, ...rest });

/** The fixture keys of the documents an answer reported, in the order reported. */
function reportedSops(data: unknown): string[] {
  const { documents } = data as { documents: { code: string }[] };
  return documents.map(
    (document) =>
      SOP_PROFILES.find((profile) => profile.code === document.code)?.code ??
      document.code,
  );
}

function reportedAssets(data: unknown): string[] {
  const { assets } = data as { assets: { asset_id: string }[] };
  return assets.map((asset) => asset.asset_id);
}

/*
 * Level 3 is a routine fault: the agent looks up the approved procedure and the equipment behind
 * it before anybody is sent out (general.md §6).
 */
describe("level 3: a routine fault", () => {
  test("L3-5: cầu dao căn A1-1205 nhảy khi bật bếp từ — the SOP and its acceptance criteria", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope, isError } = await harness.call(
      SOP,
      sopArgs(
        BUILDING.a1,
        "TECH.ELEC.BREAKER_TRIP",
        "cầu dao nhảy khi bật bếp từ, cần tiêu chí nghiệm thu",
      ),
    );

    expect(envelope.status).toBe("OK");
    expect(isError).toBe(false);
    expect(reportedSops(envelope.data)).toEqual(["SOP-ELEC-001"]);

    const { documents } = envelope.data as {
      documents: {
        version_no: number;
        acceptance_criteria: string[];
        source_refs: string[];
        effective_to: string | null;
      }[];
    };
    expect(documents[0]).toMatchObject({
      version_no: 3,
      effective_to: null,
      // Pinned to the version, so a later revision cannot be mistaken for what was followed.
      source_refs: ["doc:SOP-ELEC-001:v3"],
    });
    expect(documents[0]?.acceptance_criteria).toEqual([
      "Dòng rò của nhánh dưới 30 mA sau xử lý",
      "Cầu dao giữ tải định mức trong 15 phút liên tục",
      "Có ảnh tủ điện sau khi hoàn tất",
    ]);
  });

  test("L3-6: which air conditioner in A1-1205 — identified by room", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(ASSET, {
      building_id: BUILDING.a1,
      location: "A1-1205/phòng ngủ",
    });

    expect(envelope.status).toBe("OK");
    expect(reportedAssets(envelope.data)).toEqual(["AC-A1-1205-02"]);
    const { assets } = envelope.data as {
      assets: { model: string; ownership: string; warranty_until: string }[];
    };
    expect(assets[0]).toMatchObject({
      model: "ACME-X2",
      ownership: "resident",
      warranty_until: "2027-03-31",
    });
  });

  test("L3-7: a resident typing without accents finds the same unit", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(ASSET, {
      building_id: BUILDING.a1,
      location: "A1-1205/phong khach",
    });

    expect(envelope.status).toBe("OK");
    expect(reportedAssets(envelope.data)).toEqual(["AC-A1-1205-01"]);
  });

  /*
   * general.md §11: no SOP means stop guiding and hand the case to somebody qualified. The cracked
   * ceiling has a document, but its version lapsed on 1 September, so following it now would be
   * following guidance that has been withdrawn.
   */
  test("L3-8: nứt trần — the only SOP lapsed, so the agent is told there is none", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope, isError } = await harness.call(
      SOP,
      sopArgs(BUILDING.a1, "TECH.ARCH.CRACK", "vết nứt chân chim trên trần"),
    );

    expect(envelope.status).toBe("NOT_FOUND");
    expect(isError).toBe(true);
    expect(envelope.data).toBeNull();
    expect(envelope.errors[0]).toMatchObject({
      code: "NOT_FOUND",
      field: "issue_code",
      retryable: false,
    });
  });

  test("L3-9: and the same SOP is found for an incident that happened while it was in force", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      SOP,
      sopArgs(BUILDING.a1, "TECH.ARCH.CRACK", "vết nứt chân chim trên trần", {
        effective_at: "2026-06-01T00:00:00Z",
      }),
    );

    expect(envelope.status).toBe("OK");
    expect(reportedSops(envelope.data)).toEqual(["SOP-ARCH-005"]);
  });

  test("L3-10: a draft is not guidance, so a fault with only a draft has none", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope, text } = await harness.call(
      SOP,
      sopArgs(
        BUILDING.a1,
        "TECH.ELEC.FIXTURE_FAILURE",
        "ổ cắm phòng khách không có điện",
      ),
    );

    expect(envelope.status).toBe("NOT_FOUND");
    // Neither the draft nor the English edition may stand in for approved Vietnamese guidance.
    expect(text).not.toContain("SOP-ELEC-009");
    expect(text).not.toContain("SOP-ELEC-030");
  });
});

/*
 * Level 2 is spreading or significant: the agent reads more, and the case usually reaches a
 * technician rather than being closed on guidance alone.
 */
describe("level 2: a fault that is spreading", () => {
  test("L2-5: thấm trần từ căn trên — both procedures, the closer one first", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      SOP,
      sopArgs(
        BUILDING.a1,
        "TECH.PLUMB.CONCEALED_LEAK",
        "vết thấm trần lan ở căn phía dưới",
      ),
    );

    expect(envelope.status).toBe("OK");
    // SOP-PLUMB-021 is about ceiling stains; SOP-PLUMB-020 is about locating the leak in the wall.
    expect(reportedSops(envelope.data)).toEqual([
      "SOP-PLUMB-021",
      "SOP-PLUMB-020",
    ]);
  });

  test("L2-6: the same fault asked about the wall puts the other procedure first", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      SOP,
      sopArgs(
        BUILDING.a1,
        "TECH.PLUMB.CONCEALED_LEAK",
        "dò rò ống nước âm tường bằng máy dò ẩm",
      ),
    );

    expect(reportedSops(envelope.data)).toEqual([
      "SOP-PLUMB-020",
      "SOP-PLUMB-021",
    ]);
  });

  test("L2-7: a limit of one returns only the best match", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      SOP,
      sopArgs(
        BUILDING.a1,
        "TECH.PLUMB.CONCEALED_LEAK",
        "vết thấm trần lan ở căn phía dưới",
        { limit: 1 },
      ),
    );

    expect(reportedSops(envelope.data)).toEqual(["SOP-PLUMB-021"]);
  });

  test("L2-8: nước ngưng điều hòa tòa A2 — the zone's procedure reaches it", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      SOP,
      sopArgs(
        BUILDING.a2,
        "TECH.HVAC.CONDENSATION",
        "điều hòa chảy nước ra sàn phòng khách",
      ),
    );

    expect(envelope.status).toBe("OK");
    expect(reportedSops(envelope.data)).toEqual(["SOP-HVAC-012"]);
    // The other zone's edition is for different equipment and must not be offered here.
    expect(JSON.stringify(envelope.data)).not.toContain("SOP-HVAC-020");
  });

  test("L2-9: nước thải trào ngược — one document serves two issue codes", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      SOP,
      sopArgs(
        BUILDING.a1,
        "TECH.PLUMB.SEWAGE_BACKFLOW",
        "nước thải trào ngược ở phễu thu sàn",
      ),
    );

    expect(reportedSops(envelope.data)).toEqual(["SOP-PLUMB-020"]);
  });

  test("L2-10: ẩm mốc bong sơn — the tenant-wide procedure reaches every building", async () => {
    const harness = technicalToolHarness(ports);
    for (const building of [BUILDING.a1, BUILDING.a2]) {
      const { envelope } = await harness.call(
        SOP,
        sopArgs(
          building,
          "TECH.ARCH.PAINT_MOISTURE",
          "tường bong sơn và có vết ẩm mốc",
        ),
      );
      expect(reportedSops(envelope.data)).toEqual(["SOP-TEN-001"]);
    }
  });
});

/*
 * Level 1 is immediate danger. What these two tools contribute is identification, and the failure
 * to avoid is confident identification of the wrong thing: an agent that reads the history of the
 * wrong breaker panel proposes work on the wrong circuit while a socket is arcing.
 */
describe("level 1: immediate danger", () => {
  test("L1-4: ổ cắm tóe lửa — the panel is named exactly, not guessed", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(ASSET, {
      building_id: BUILDING.a1,
      asset_id: "BP-A1-1205-01",
    });

    expect(envelope.status).toBe("OK");
    expect(reportedAssets(envelope.data)).toEqual(["BP-A1-1205-01"]);
    const { assets } = envelope.data as { assets: { ownership: string }[] };
    // Management's equipment, so entering the apartment is not what this needs.
    expect(assets[0]?.ownership).toBe("management");
  });

  test("L1-5: nước ngập phòng tắm — three assets share the room, so the tool refuses to choose", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope, isError } = await harness.call(ASSET, {
      building_id: BUILDING.a1,
      location: "A1-1205/phòng tắm",
    });

    expect(envelope.status).toBe("NEEDS_INPUT");
    // An answer, not a failure: the agent can act on it by asking which one.
    expect(isError).toBe(false);
    expect(envelope.missing_fields).toEqual(["asset_id"]);
    expect(reportedAssets(envelope.data).sort()).toEqual([
      "TL-A1-1205-01",
      "TL-A1-1205-02",
      "WH-A1-1205-01",
    ]);
  });

  test("L1-6: naming the type settles it where the room did not", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(ASSET, {
      building_id: BUILDING.a1,
      location: "A1-1205/phòng tắm",
      asset_type: "water_heater",
    });

    expect(envelope.status).toBe("OK");
    expect(reportedAssets(envelope.data)).toEqual(["WH-A1-1205-01"]);
  });

  test("L1-7: and where two of one type share the room, it still refuses", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(ASSET, {
      building_id: BUILDING.a1,
      location: "A1-1205/phòng tắm",
      asset_type: "toilet",
    });

    expect(envelope.status).toBe("NEEDS_INPUT");
    expect(reportedAssets(envelope.data).sort()).toEqual([
      "TL-A1-1205-01",
      "TL-A1-1205-02",
    ]);
  });

  /*
   * A room name is not an address. Asked for "the living room air conditioner" in a tower, the
   * tool must not answer with one of two apartments' units.
   */
  test("L1-8: a room name alone matches two apartments and is refused", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(ASSET, {
      building_id: BUILDING.a1,
      location: "phòng khách",
      asset_type: "air_conditioner",
    });

    expect(envelope.status).toBe("NEEDS_INPUT");
    expect(reportedAssets(envelope.data).sort()).toEqual([
      "AC-A1-1105-01",
      "AC-A1-1205-01",
    ]);
  });

  test("L1-9: a retired asset is reported with its status rather than hidden", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(ASSET, {
      building_id: BUILDING.a1,
      asset_id: "TL-A1-1205-02",
    });

    expect(envelope.status).toBe("OK");
    const { assets } = envelope.data as { assets: { status: string }[] };
    expect(assets[0]?.status).toBe("retired");
  });

  test("L1-10: an asset id the agent made up finds nothing", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(ASSET, {
      building_id: BUILDING.a1,
      asset_id: "AC-A1-9999-99",
    });

    expect(envelope.status).toBe("NOT_FOUND");
    expect(envelope.data).toBeNull();
    expect(envelope.errors[0]?.field).toBe("asset_id");
  });
});

describe("guidance the caller may not read", () => {
  /*
   * tools.md §3.1 answers FORBIDDEN here rather than NOT_FOUND, and the difference is
   * actionable: one says no procedure exists, the other that a grant is missing.
   */
  test("a document denied to the caller's role is a refusal", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope, isError, text } = await harness.call(
      SOP,
      sopArgs(BUILDING.a1, "TECH.PLUMB.TOILET_LEAK", "bồn cầu rỉ nước ở chân"),
    );

    expect(envelope.status).toBe("FORBIDDEN");
    expect(isError).toBe(true);
    expect(envelope.data).toBeNull();
    expect(envelope.provenance).toEqual([]);
    // Not a word of the document it refused.
    expect(text).not.toContain("SOP-PLUMB-031");
    expect(text).not.toContain("gioăng");
  });

  test("and the manager the document was granted to reads it", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      SOP,
      sopArgs(BUILDING.a1, "TECH.PLUMB.TOILET_LEAK", "bồn cầu rỉ nước ở chân"),
      CALLER.managementAgent,
    );

    expect(envelope.status).toBe("OK");
    expect(reportedSops(envelope.data)).toEqual(["SOP-PLUMB-031"]);
  });

  test("a document with no access row is refused too, not shared by default", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      SOP,
      sopArgs(BUILDING.a1, "TECH.PLUMB.TRAP_ODOR", "mùi cống ở phễu thu sàn"),
    );

    expect(envelope.status).toBe("FORBIDDEN");
  });

  test("a document in a retired collection is absent rather than refused", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      SOP,
      sopArgs(
        BUILDING.a1,
        "TECH.PLUMB.WATER_HEATER",
        "máy nước nóng không lên nhiệt",
      ),
    );

    // Nothing usable exists, so there is no grant to fix and nothing to hint at.
    expect(envelope.status).toBe("NOT_FOUND");
  });

  test("a document whose active version was never set is absent", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      SOP,
      sopArgs(BUILDING.a1, "TECH.ARCH.CABINET_SAG", "cánh tủ bếp bị xệ"),
    );

    expect(envelope.status).toBe("NOT_FOUND");
  });
});

describe("a building or a tenant the caller may not ask about", () => {
  test.each([
    ["in the same tenant but outside the grant", BUILDING.b1],
    ["in another tenant", BUILDING.x1],
    ["nowhere at all", BUILDING.missing],
  ])("a SOP lookup for a building %s is refused alike", async (_label, id) => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      SOP,
      sopArgs(id, "TECH.ELEC.BREAKER_TRIP", "cầu dao nhảy liên tục"),
    );

    expect(envelope.status).toBe("FORBIDDEN");
    expect(envelope.data).toBeNull();
  });

  test("no SOP of another tenant's library can be reached", async () => {
    const harness = technicalToolHarness(ports);
    const { text } = await harness.call(
      SOP,
      sopArgs(BUILDING.x1, "TECH.ELEC.BREAKER_TRIP", "cầu dao nhảy liên tục"),
    );
    expect(text).not.toContain("SOP-X-001");
  });

  test("an asset lookup outside the grant is refused before the adapter is asked", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope, text } = await harness.call(ASSET, {
      building_id: BUILDING.b1,
      asset_id: "AC-B1-0501-01",
    });

    expect(envelope.status).toBe("FORBIDDEN");
    expect(text).not.toContain("AC-B1-0501-01");
  });

  test("and another tenant's equipment is unreachable even by exact id", async () => {
    const harness = technicalToolHarness(ports);
    const { text } = await harness.call(ASSET, {
      building_id: BUILDING.x1,
      asset_id: "AC-X1-0101-01",
    });
    expect(text).not.toContain("ACME-X1");
  });

  test.each([
    ["sop_kb.retrieve", SOP],
    ["asset.read", ASSET],
  ])(
    "%s refuses a Bot that was never granted its capability",
    async (_n, tool) => {
      const harness = technicalToolHarness(ports);
      const { envelope } = await harness.call(
        tool,
        tool === SOP
          ? sopArgs(BUILDING.a1, "TECH.ELEC.BREAKER_TRIP", "cầu dao nhảy")
          : { building_id: BUILDING.a1, asset_id: "BP-A1-1205-01" },
        CALLER.ungrantedAgent,
      );

      expect(envelope.status).toBe("FORBIDDEN");
      expect(harness.auditEntries[0]?.detail).toMatch(/sop:read|asset:read/);
    },
  );
});

describe("a question with nothing to search on", () => {
  test("is answered NEEDS_INPUT rather than with an arbitrary document", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope, isError } = await harness.call(
      SOP,
      sopArgs(BUILDING.a1, "TECH.ELEC.BREAKER_TRIP", "và với của"),
    );

    expect(envelope.status).toBe("NEEDS_INPUT");
    expect(isError).toBe(false);
    expect(envelope.missing_fields).toEqual(["query"]);
    expect(envelope.data).toBeNull();
  });

  test("and the database is never asked", async () => {
    // The port would throw if reached, so an answer at all proves the check came first.
    const harness = technicalToolHarness({
      sopProfiles: createInMemorySopProfilePort(SOP_PROFILES),
    });
    const { envelope } = await harness.call(
      SOP,
      sopArgs(BUILDING.a1, "TECH.ELEC.BREAKER_TRIP", "???"),
    );

    expect(envelope.status).toBe("NEEDS_INPUT");
  });
});

describe("what an answer carries back", () => {
  test("the document and the revision each result came from", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      SOP,
      sopArgs(BUILDING.a1, "TECH.ELEC.BREAKER_TRIP", "cầu dao nhảy liên tục"),
    );

    expect(envelope.provenance).toEqual([
      {
        source_system: "application_db",
        source_record_id: sopByKey("S1").documentId,
        source_version: 3,
        retrieved_at: NOW.toISOString(),
      },
    ]);
  });

  /*
   * The asset adapter names itself rather than the database, so an answer built from sample data
   * cannot be mistaken for one read out of the deployment's own tables.
   */
  test("the asset source names itself as an adapter, not as the database", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(ASSET, {
      building_id: BUILDING.a1,
      asset_id: "AC-A1-1205-01",
    });

    expect(envelope.provenance).toEqual([
      {
        source_system: "asset_adapter",
        source_record_id: "AC-A1-1205-01",
        source_version: "etag-17",
        retrieved_at: NOW.toISOString(),
      },
    ]);
  });

  test("an empty asset catalogue is an honest NOT_FOUND, not an invented asset", async () => {
    const harness = technicalToolHarness({
      assets: createInMemoryAssetReadPort(),
    });
    const { envelope } = await harness.call(ASSET, {
      building_id: BUILDING.a1,
      asset_id: "AC-A1-1205-01",
    });

    expect(envelope.status).toBe("NOT_FOUND");
    expect(envelope.data).toBeNull();
  });

  test("a refused NEEDS_INPUT still says where its candidates came from", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(ASSET, {
      building_id: BUILDING.a1,
      location: "A1-1205/phòng tắm",
    });

    expect(envelope.provenance).toHaveLength(3);
    expect(envelope.provenance[0]?.source_system).toBe("asset_adapter");
  });
});

describe("what the audit trail records", () => {
  test("one entry per call, traceable to the run and the release", async () => {
    const harness = technicalToolHarness(ports);
    await harness.call(
      SOP,
      sopArgs(BUILDING.a1, "TECH.ELEC.BREAKER_TRIP", "cầu dao nhảy liên tục"),
    );
    await harness.call(ASSET, {
      building_id: BUILDING.a1,
      asset_id: "BP-A1-1205-01",
    });

    expect(harness.auditEntries).toHaveLength(2);
    expect(harness.auditEntries.map((entry) => entry.tool)).toEqual([
      "sop_kb.retrieve",
      "asset.read",
    ]);
    for (const entry of harness.auditEntries) {
      expect(entry).toMatchObject({
        status: "OK",
        agent_version: AGENT_VERSION,
        tenant_id: TENANT.vinhomes,
        building_id: BUILDING.a1,
        result_count: 1,
        occurred_at: NOW.toISOString(),
      });
    }
  });

  /*
   * A refusal is the entry that matters most. A document read is visible in the transcript; a
   * document withheld is invisible everywhere else.
   */
  test("a refusal records which document family and why, where the caller is told neither", async () => {
    const harness = technicalToolHarness(ports);
    await harness.call(
      SOP,
      sopArgs(BUILDING.a1, "TECH.PLUMB.TOILET_LEAK", "bồn cầu rỉ nước"),
    );

    expect(harness.auditEntries[0]).toMatchObject({
      tool: "sop_kb.retrieve",
      status: "FORBIDDEN",
      building_id: BUILDING.a1,
      result_count: null,
    });
  });

  test("the documents themselves are not copied into the trail", async () => {
    const harness = technicalToolHarness(ports);
    await harness.call(
      SOP,
      sopArgs(BUILDING.a1, "TECH.ELEC.BREAKER_TRIP", "cầu dao nhảy liên tục"),
    );

    const recorded = JSON.stringify(harness.auditEntries);
    expect(recorded).not.toContain("SOP-ELEC-001");
    expect(recorded).not.toContain("Dòng rò");
  });
});

describe("the door the server opens to these tools", () => {
  test.each([
    ["the name in tools.md", "sop_kb.retrieve"],
    ["the name a model is offered", "sop_kb__retrieve"],
    ["the ref the route derives from it", "sop_kb/retrieve"],
  ])("sop_kb.retrieve answers to %s", async (_label, name) => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      name,
      sopArgs(BUILDING.a1, "TECH.ELEC.BREAKER_TRIP", "cầu dao nhảy liên tục"),
    );

    expect(envelope.status).toBe("OK");
  });

  test.each([
    ["the name in tools.md", "asset.read"],
    ["the name a model is offered", "asset__read"],
    ["the ref the route derives from it", "asset/read"],
  ])("asset.read answers to %s", async (_label, name) => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(name, {
      building_id: BUILDING.a1,
      asset_id: "AC-A1-1205-01",
    });

    expect(envelope.status).toBe("OK");
  });
});
