import { describe, expect, test } from "bun:test";
import {
  createInMemoryMaintenanceReadPort,
  createInMemorySensorReadPort,
} from "../../src/technical-tools";
import { MAINTENANCE_EVENTS } from "./fixtures/maintenance";
import { READINGS, SENSORS } from "./fixtures/sensors";
import { BUILDING, TENANT } from "./fixtures/world";

/**
 * The two in-memory adapters, which stand in for tables that do not exist yet.
 *
 * They are the only thing between a tool and another tenant's data until those tables arrive, so
 * they are held to what row-level security would enforce: a tenant and a building must both match,
 * whatever id the caller already knows.
 */
const window = {
  from: new Date("2026-09-30T00:00:00Z"),
  to: new Date("2026-09-30T09:00:00Z"),
};

describe("the sensor adapter", () => {
  const port = createInMemorySensorReadPort(SENSORS, READINGS);

  /*
   * Given nothing, it has nothing. A deployment that shipped with sample readings would report a
   * leakage current it never measured.
   */
  test("holds no sensors of its own", async () => {
    const empty = createInMemorySensorReadPort();
    expect(
      await empty.find({
        tenantId: TENANT.vinhomes,
        buildingId: BUILDING.a1,
        assetId: "AC-A1-1205-01",
        metric: "condensate_level",
        window,
      }),
    ).toEqual({ sensors: [], readings: [] });
  });

  test("finds sensors by the asset they are fitted to", async () => {
    const { sensors } = await port.find({
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
      assetId: "BP-A1-1205-01",
      metric: "leakage_current",
      window,
    });
    expect(sensors.map((sensor) => sensor.sensorId).sort()).toEqual([
      "SNS-BP1-CUR-A",
      "SNS-BP1-CUR-B",
    ]);
  });

  test("finds a sensor by its own id, including one fitted to no asset", async () => {
    const { sensors } = await port.find({
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
      sensorId: "SNS-1205-HUM",
      metric: "surface_moisture",
      window,
    });
    expect(sensors).toHaveLength(1);
    expect(sensors[0]?.assetId).toBeNull();
  });

  test("a sensor measuring another metric is not a match", async () => {
    const { sensors } = await port.find({
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
      assetId: "AC-A1-1205-01",
      metric: "outlet_temperature",
      window,
    });
    expect(sensors).toEqual([]);
  });

  test("returns a sensor with no readings, so silence can be told from absence", async () => {
    const { sensors, readings } = await port.find({
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
      assetId: "WF-A1-1205-01",
      metric: "flow_rate",
      window,
    });
    expect(sensors).toHaveLength(1);
    // Yesterday's reading comes back; the rules, not the adapter, keep the window.
    expect(readings).toHaveLength(1);
  });

  test.each([
    [
      "another building's sensor, asked under building A1",
      TENANT.vinhomes,
      BUILDING.a1,
      "SNS-B1-COND",
    ],
    [
      "another tenant's sensor, asked under this tenant",
      TENANT.vinhomes,
      BUILDING.x1,
      "SNS-X1-COND",
    ],
    [
      "another tenant's sensor, asked under building A1",
      TENANT.vinhomes,
      BUILDING.a1,
      "SNS-X1-COND",
    ],
  ])(
    "never returns %s, even by its exact id",
    async (_label, tenantId, buildingId, sensorId) => {
      expect(
        await port.find({
          tenantId,
          buildingId,
          sensorId,
          metric: "condensate_level",
          window,
        }),
      ).toEqual({ sensors: [], readings: [] });
    },
  );

  test("returns that same sensor to the tenant that owns it", async () => {
    // The positive control: without it the test above would pass on an empty catalogue.
    const { sensors } = await port.find({
      tenantId: TENANT.other,
      buildingId: BUILDING.x1,
      sensorId: "SNS-X1-COND",
      metric: "condensate_level",
      window,
    });
    expect(sensors).toHaveLength(1);
  });
});

describe("the maintenance adapter", () => {
  const port = createInMemoryMaintenanceReadPort(MAINTENANCE_EVENTS);
  const until = window.to;

  test("holds no history of its own", async () => {
    expect(
      await createInMemoryMaintenanceReadPort().listForAsset({
        tenantId: TENANT.vinhomes,
        buildingId: BUILDING.a1,
        assetId: "AC-A1-1205-01",
        until,
      }),
    ).toEqual([]);
  });

  test("returns every event of the asset, the corrected one included", async () => {
    const events = await port.listForAsset({
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
      assetId: "AC-A1-1205-01",
      until,
    });
    // Which of them still stands is the rules' decision, not the adapter's.
    expect(events.map((event) => event.eventId).sort()).toEqual([
      "ME-101",
      "ME-102",
      "ME-103",
      "ME-104",
    ]);
  });

  test("reaches back as far as the record goes", async () => {
    const events = await port.listForAsset({
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
      assetId: "BP-A1-1205-01",
      until,
    });
    expect(events.map((event) => event.eventId)).toEqual(["ME-201"]);
  });

  test("stops before the end it was given", async () => {
    const events = await port.listForAsset({
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
      assetId: "AC-A1-1205-01",
      until: new Date("2026-08-15T03:00:00Z"),
    });
    expect(events.map((event) => event.eventId).sort()).toEqual([
      "ME-101",
      "ME-102",
    ]);
  });

  test.each([
    [
      "another building's history",
      TENANT.vinhomes,
      BUILDING.a1,
      "AC-B1-0501-01",
    ],
    ["another tenant's history", TENANT.vinhomes, BUILDING.x1, "AC-X1-0101-01"],
  ])("never returns %s", async (_label, tenantId, buildingId, assetId) => {
    expect(
      await port.listForAsset({ tenantId, buildingId, assetId, until }),
    ).toEqual([]);
  });
});
