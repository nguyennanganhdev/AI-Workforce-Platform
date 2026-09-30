import { describe, expect, test } from "bun:test";
import { responseEnvelopeSchema } from "../../src/technical-tools";
import {
  maintenanceHistoryReadInputSchema,
  maintenanceHistoryReadOutputSchema,
} from "../../src/technical-tools/contracts/maintenance";
import {
  sensorReadInputSchema,
  sensorReadOutputSchema,
} from "../../src/technical-tools/contracts/sensor";
import { BUILDING, TENANT } from "./fixtures/world";
import historyGolden from "./golden/maintenance_history.read.json";
import sensorGolden from "./golden/sensor.read.json";

/**
 * Whether the shapes these two tools accept and return are the shapes docs/teams/quang/tools.md
 * specifies. The golden files are that document's own worked examples, copied rather than
 * paraphrased.
 */
describe("the specification's own examples", () => {
  test("tools.md §3.3's example is a valid sensor.read exchange", () => {
    expect(sensorReadInputSchema.safeParse(sensorGolden.request).success).toBe(
      true,
    );
    expect(
      responseEnvelopeSchema.safeParse(sensorGolden.response).success,
    ).toBe(true);
    expect(
      sensorReadOutputSchema.safeParse(sensorGolden.response.data).success,
    ).toBe(true);
  });

  test("tools.md §3.4's example is a valid maintenance_history.read exchange", () => {
    expect(
      maintenanceHistoryReadInputSchema.safeParse(historyGolden.request)
        .success,
    ).toBe(true);
    expect(
      responseEnvelopeSchema.safeParse(historyGolden.response).success,
    ).toBe(true);
    expect(
      maintenanceHistoryReadOutputSchema.safeParse(historyGolden.response.data)
        .success,
    ).toBe(true);
  });
});

const window = {
  from: "2026-09-30T08:00:00Z",
  to: "2026-09-30T09:00:00Z",
};

describe("what sensor.read accepts", () => {
  const byAsset = {
    building_id: BUILDING.a1,
    asset_id: "AC-A1-1205-01",
    metric: "condensate_level",
    time_range: window,
  };

  test("a lookup by asset, and one by sensor", () => {
    expect(sensorReadInputSchema.safeParse(byAsset).success).toBe(true);
    const { asset_id: _asset, ...rest } = byAsset;
    expect(
      sensorReadInputSchema.safeParse({ ...rest, sensor_id: "SNS-AC1-COND" })
        .success,
    ).toBe(true);
  });

  test("fills in fifteen minutes as the age past which a reading is stale", () => {
    expect(sensorReadInputSchema.parse(byAsset).max_age_seconds).toBe(900);
  });

  /*
   * tools.md writes `oneOf`, which is exactly one. Given both, it would be unclear which decides
   * when they name different equipment; given neither, the call would ask for every sensor in the
   * building.
   */
  test("refuses both a sensor and an asset", () => {
    const result = sensorReadInputSchema.safeParse({
      ...byAsset,
      sensor_id: "SNS-AC1-COND",
    });
    expect(result.success).toBe(false);
    expect(result.error?.issues[0]?.path).toEqual(["sensor_id"]);
  });

  test("refuses neither a sensor nor an asset", () => {
    const { asset_id: _asset, ...rest } = byAsset;
    expect(sensorReadInputSchema.safeParse(rest).success).toBe(false);
  });

  test("refuses a window that runs backwards, on time_range", () => {
    const result = sensorReadInputSchema.safeParse({
      ...byAsset,
      time_range: { from: window.to, to: window.from },
    });
    expect(result.success).toBe(false);
    expect(result.error?.issues[0]?.path).toEqual(["time_range"]);
    expect(result.error?.issues[0]?.message).toBe(
      "time_range.from must be earlier than time_range.to.",
    );
  });

  test.each([
    ["no metric", { metric: "" }],
    ["a metric past a hundred characters", { metric: "x".repeat(101) }],
    ["a maximum age of zero", { max_age_seconds: 0 }],
    ["a maximum age past a day", { max_age_seconds: 86_401 }],
    ["a fractional maximum age", { max_age_seconds: 1.5 }],
    ["a window with no end", { time_range: { from: window.from } }],
    [
      "a time with no timezone",
      { time_range: { from: "2026-09-30T08:00:00", to: window.to } },
    ],
    ["a tenant_id of the agent's choosing", { tenant_id: TENANT.other }],
  ])("refuses %s", (_label, change) => {
    expect(
      sensorReadInputSchema.safeParse({ ...byAsset, ...change }).success,
    ).toBe(false);
  });
});

describe("what maintenance_history.read accepts", () => {
  const valid = {
    building_id: BUILDING.a1,
    asset_id: "AC-A1-1205-01",
    time_range: { from: "2026-01-01T00:00:00Z", to: window.to },
  };

  test("the valid call, with twenty events a page by default", () => {
    const parsed = maintenanceHistoryReadInputSchema.parse(valid);
    expect(parsed.limit).toBe(20);
  });

  test.each([
    ["no asset", { asset_id: "" }],
    ["a limit of zero", { limit: 0 }],
    ["a limit past a hundred", { limit: 101 }],
    [
      "a window that runs backwards",
      { time_range: { from: window.to, to: "2026-01-01T00:00:00Z" } },
    ],
    ["a location instead of an asset", { location: "A1-1205/phòng khách" }],
    ["a tenant_id of the agent's choosing", { tenant_id: TENANT.other }],
  ])("refuses %s", (_label, change) => {
    expect(
      maintenanceHistoryReadInputSchema.safeParse({ ...valid, ...change })
        .success,
    ).toBe(false);
  });

  test("refuses a call with no asset at all", () => {
    const { asset_id: _asset, ...rest } = valid;
    expect(maintenanceHistoryReadInputSchema.safeParse(rest).success).toBe(
      false,
    );
  });
});

/*
 * The host checks output before it leaves, including the data a STALE_DATA answer carries, so a
 * reading missing its unit or quality becomes an INTERNAL_ERROR rather than a number an agent
 * believes.
 */
describe("what the output schemas require", () => {
  test("a reading carries its unit, its time and its quality", () => {
    for (const missing of ["unit", "observed_at", "quality"]) {
      const reading: Record<string, unknown> = {
        sensor_id: "SNS-AC1-COND",
        asset_id: "AC-A1-1205-01",
        metric: "condensate_level",
        value: 12.4,
        unit: "mm",
        observed_at: "2026-09-30T08:58:00Z",
        quality: "good",
      };
      delete reading[missing];
      expect(
        sensorReadOutputSchema.safeParse({
          readings: [reading],
          freshness: "fresh",
        }).success,
      ).toBe(false);
    }
  });

  test("a quality or a freshness the specification does not define is refused", () => {
    const reading = {
      sensor_id: "SNS-AC1-COND",
      asset_id: null,
      metric: "condensate_level",
      value: 1,
      unit: "mm",
      observed_at: "2026-09-30T08:58:00Z",
      quality: "excellent",
    };
    expect(
      sensorReadOutputSchema.safeParse({
        readings: [reading],
        freshness: "fresh",
      }).success,
    ).toBe(false);
    expect(
      sensorReadOutputSchema.safeParse({ readings: [], freshness: "recent" })
        .success,
    ).toBe(false);
  });

  test("a repeat count is a whole number, never negative", () => {
    for (const repeat_count of [-1, 1.5]) {
      expect(
        maintenanceHistoryReadOutputSchema.safeParse({
          events: [],
          last_maintenance_at: null,
          repeat_count,
        }).success,
      ).toBe(false);
    }
  });
});
