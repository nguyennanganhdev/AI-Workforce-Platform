import { describe, expect, test } from "bun:test";
import { responseEnvelopeSchema } from "../../src/technical-tools";
import {
  assetReadInputSchema,
  assetReadOutputSchema,
} from "../../src/technical-tools/contracts/asset";
import {
  sopRetrieveInputSchema,
  sopRetrieveOutputSchema,
} from "../../src/technical-tools/contracts/sop";
import { BUILDING, TENANT } from "./fixtures/world";
import assetGolden from "./golden/asset.read.json";
import sopGolden from "./golden/sop_kb.retrieve.json";

/**
 * Whether the shapes these two tools accept and return are the shapes docs/teams/quang/tools.md
 * specifies.
 *
 * The golden files are that document's own worked examples, copied rather than paraphrased. A
 * schema that rejects the specification's example of a valid call has drifted from it, however
 * reasonable the schema looks on its own.
 */
describe("the specification's own examples", () => {
  test("tools.md §3.1's example is a valid sop_kb.retrieve exchange", () => {
    expect(sopRetrieveInputSchema.safeParse(sopGolden.request).success).toBe(
      true,
    );
    expect(responseEnvelopeSchema.safeParse(sopGolden.response).success).toBe(
      true,
    );
    expect(
      sopRetrieveOutputSchema.safeParse(sopGolden.response.data).success,
    ).toBe(true);
  });

  test("tools.md §3.2's example is a valid asset.read exchange", () => {
    expect(assetReadInputSchema.safeParse(assetGolden.request).success).toBe(
      true,
    );
    expect(responseEnvelopeSchema.safeParse(assetGolden.response).success).toBe(
      true,
    );
    expect(
      assetReadOutputSchema.safeParse(assetGolden.response.data).success,
    ).toBe(true);
  });
});

describe("what sop_kb.retrieve accepts", () => {
  const valid = {
    building_id: BUILDING.a1,
    issue_code: "TECH.ELEC.BREAKER_TRIP",
    query: "cầu dao nhảy khi bật bếp từ",
  };

  test("the valid call it is compared against is accepted", () => {
    expect(sopRetrieveInputSchema.safeParse(valid).success).toBe(true);
  });

  /*
   * Defaults rather than required fields, so a model that asks the simple question gets the
   * ordinary answer: Vietnamese, and few enough documents to read.
   */
  test("fills in the language and the limit when they are left out", () => {
    const parsed = sopRetrieveInputSchema.parse(valid);
    expect(parsed.language).toBe("vi");
    expect(parsed.limit).toBe(5);
    expect(parsed.effective_at).toBeUndefined();
  });

  test.each([
    ["an issue code in the wrong shape", { issue_code: "breaker_trip" }],
    ["an issue code of another domain", { issue_code: "VH.ELEC.BREAKER" }],
    ["a lower-case issue code", { issue_code: "tech.elec.breaker_trip" }],
    ["a query too short to search on", { query: "ab" }],
    ["a limit of zero", { limit: 0 }],
    ["a limit past twenty", { limit: 21 }],
    ["a fractional limit", { limit: 2.5 }],
    ["a time with no timezone", { effective_at: "2026-09-30T09:00:00" }],
    ["a tenant_id of the agent's choosing", { tenant_id: TENANT.other }],
    ["a role the agent claims to hold", { role_code: "management" }],
  ])("refuses %s", (_label, change) => {
    expect(
      sopRetrieveInputSchema.safeParse({ ...valid, ...change }).success,
    ).toBe(false);
  });

  test.each(["building_id", "issue_code", "query"])(
    "refuses a call missing %s",
    (field) => {
      const { [field]: _removed, ...rest } = valid as Record<string, unknown>;
      expect(sopRetrieveInputSchema.safeParse(rest).success).toBe(false);
    },
  );
});

describe("what asset.read accepts", () => {
  test("a lookup by id, and a search by location", () => {
    expect(
      assetReadInputSchema.safeParse({
        building_id: BUILDING.a1,
        asset_id: "AC-A1-1205-01",
      }).success,
    ).toBe(true);
    expect(
      assetReadInputSchema.safeParse({
        building_id: BUILDING.a1,
        location: "A1-1205/phòng tắm",
        asset_type: "toilet",
      }).success,
    ).toBe(true);
  });

  /*
   * A call naming only the building would ask for every asset in it. That is a listing rather than
   * a lookup, and the tool would then have to pick one or hand back a whole tower's equipment.
   */
  test("refuses a call that names neither an id nor a location", () => {
    const result = assetReadInputSchema.safeParse({
      building_id: BUILDING.a1,
      asset_type: "air_conditioner",
    });
    expect(result.success).toBe(false);
    expect(result.error?.issues[0]?.path).toEqual(["asset_id"]);
  });

  test.each([
    ["an empty asset id", { asset_id: "" }],
    ["a location of one character", { location: "A" }],
    ["a building id that is not a UUID", { building_id: "A1", asset_id: "x" }],
    ["a tenant_id of the agent's choosing", { tenant_id: TENANT.other }],
    ["a made-up filter", { room: "phòng tắm" }],
  ])("refuses %s", (_label, change) => {
    expect(
      assetReadInputSchema.safeParse({
        building_id: BUILDING.a1,
        asset_id: "AC-A1-1205-01",
        ...change,
      }).success,
    ).toBe(false);
  });
});

/*
 * The output schemas are checked by the host before an answer leaves, so a field the tool forgets
 * becomes an INTERNAL_ERROR rather than a half-filled answer the agent believes.
 */
describe("what the output schemas require", () => {
  test("a reported SOP carries its version and where it came from", () => {
    const missingVersion = {
      documents: [
        {
          document_id: BUILDING.a1,
          code: "SOP-ELEC-001",
          title: "Xử lý cầu dao nhảy",
          effective_from: "2026-01-01T00:00:00Z",
          effective_to: null,
          excerpt: "…",
          acceptance_criteria: [],
          source_refs: [],
        },
      ],
    };
    expect(sopRetrieveOutputSchema.safeParse(missingVersion).success).toBe(
      false,
    );
  });

  test("a reported asset states its status and when it was last updated", () => {
    const missingStatus = {
      assets: [
        {
          asset_id: "AC-A1-1205-01",
          type: "air_conditioner",
          model: null,
          location: "A1-1205/phòng khách",
          ownership: null,
          warranty_until: null,
          updated_at: "2026-09-20T02:00:00Z",
        },
      ],
    };
    expect(assetReadOutputSchema.safeParse(missingStatus).success).toBe(false);
  });
});
