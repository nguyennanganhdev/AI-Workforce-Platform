import { describe, expect, test } from "bun:test";
import {
  createMockReadPorts,
  createTechnicalReadTools,
  type ExecutionContext,
  type MockReadSeed,
} from "../../src/technical-tools";

const building = "11111111-1111-4111-8111-111111111111";
const otherBuilding = "22222222-2222-4222-8222-222222222222";
const tenant = "33333333-3333-4333-8333-333333333333";
const context: ExecutionContext = {
  tenant_id: tenant,
  principal_id: "technician-1",
  source_run_id: "44444444-4444-4444-8444-444444444444",
  trace_id: "trace-poc",
  agent_version: "a2-1",
  received_at: "2026-09-30T09:00:00Z",
  grants: [
    { tool: "asset.read", capability: "asset:read", scopeIds: [building] },
    { tool: "sensor.read", capability: "sensor:read", scopeIds: [building] },
    {
      tool: "maintenance_history.read",
      capability: "maintenance:read",
      scopeIds: [building],
    },
  ],
};
const period = { from: "2026-09-30T08:00:00Z", to: "2026-09-30T09:00:00Z" };
const baseAsset = {
  tenantId: tenant,
  buildingId: building,
  type: "air_conditioner",
  location: "A1-1205/living room",
  status: "active",
  updated_at: "2026-09-20T02:00:00Z",
};
const seed: MockReadSeed = {
  assets: [
    { ...baseAsset, asset_id: "AC-1" },
    { ...baseAsset, asset_id: "AC-2" },
    { ...baseAsset, buildingId: otherBuilding, asset_id: "AC-OTHER" },
    { ...baseAsset, tenantId: otherBuilding, asset_id: "AC-OTHER-TENANT" },
  ],
  readings: [
    {
      tenantId: tenant,
      buildingId: building,
      sensor_id: "S-1",
      asset_id: "AC-1",
      metric: "temperature",
      value: 24,
      unit: "C",
      observed_at: "2026-09-30T08:58:00Z",
      quality: "good",
    },
    {
      tenantId: tenant,
      buildingId: building,
      sensor_id: "S-2",
      asset_id: "AC-2",
      metric: "temperature",
      value: 28,
      unit: "C",
      observed_at: "2026-09-30T08:10:00Z",
      quality: "bad",
    },
    {
      tenantId: tenant,
      buildingId: otherBuilding,
      sensor_id: "S-FOREIGN",
      asset_id: "AC-OTHER",
      metric: "temperature",
      value: 99,
      unit: "C",
      observed_at: "2026-09-30T08:59:00Z",
      quality: "good",
    },
  ],
  events: [
    {
      tenantId: tenant,
      buildingId: building,
      event_id: "ME-1",
      asset_id: "AC-1",
      occurred_at: "2026-09-30T08:30:00Z",
      outcome: "cleaned",
      source_refs: ["workorder:1"],
    },
    {
      tenantId: tenant,
      buildingId: otherBuilding,
      event_id: "ME-FOREIGN",
      asset_id: "AC-OTHER",
      occurred_at: "2026-09-30T08:40:00Z",
      outcome: "private",
      source_refs: ["workorder:2"],
    },
  ],
};
const access = {
  canAccessBuilding: async (_context: ExecutionContext, id: string) =>
    id === building,
};
const tools = createTechnicalReadTools(access, createMockReadPorts(seed));

describe("POC read tool adapters", () => {
  test("asset ID and ambiguous location follow the contract", async () => {
    const exact = await tools.assetRead(
      { building_id: building, asset_id: "AC-1" },
      context,
    );
    expect(exact.status).toBe("OK");
    expect(exact.data).toMatchObject({ assets: [{ asset_id: "AC-1" }] });
    const ambiguous = await tools.assetRead(
      { building_id: building, location: "A1-1205" },
      context,
    );
    expect(ambiguous.status).toBe("NEEDS_INPUT");
    expect(ambiguous.missing_fields).toEqual(["asset_id"]);
    expect((ambiguous.data as { assets: unknown[] }).assets).toHaveLength(2);
  });

  test("denied building never reaches fixture data", async () => {
    const denied = await tools.assetRead(
      { building_id: otherBuilding, asset_id: "AC-OTHER" },
      context,
    );
    expect(denied.status).toBe("FORBIDDEN");
    expect(denied.data).toBeNull();
    const filtered = await tools.assetRead(
      { building_id: building, location: "OTHER" },
      context,
    );
    expect(filtered.status).toBe("NOT_FOUND");
  });

  test("sensor returns stale readings with status and quality intact", async () => {
    const fresh = await tools.sensorRead(
      {
        building_id: building,
        sensor_id: "S-1",
        metric: "temperature",
        time_range: period,
      },
      context,
    );
    expect(fresh.status).toBe("OK");
    expect(fresh.data).toMatchObject({
      freshness: "fresh",
      readings: [{ quality: "good" }],
    });
    const stale = await tools.sensorRead(
      {
        building_id: building,
        sensor_id: "S-2",
        metric: "temperature",
        time_range: period,
      },
      context,
    );
    expect(stale.status).toBe("STALE_DATA");
    expect(stale.data).toMatchObject({
      freshness: "stale",
      readings: [{ quality: "bad" }],
    });
    expect(stale.errors[0]?.code).toBe("STALE_DATA");
  });

  test("maintenance history distinguishes empty history from missing asset", async () => {
    const history = await tools.maintenanceRead(
      { building_id: building, asset_id: "AC-1", time_range: period },
      context,
    );
    expect(history.data).toMatchObject({
      repeat_count: 1,
      events: [{ event_id: "ME-1" }],
    });
    const empty = await tools.maintenanceRead(
      { building_id: building, asset_id: "AC-2", time_range: period },
      context,
    );
    expect(empty).toMatchObject({
      status: "OK",
      data: { events: [], repeat_count: 0, last_maintenance_at: null },
    });
    const missing = await tools.maintenanceRead(
      { building_id: building, asset_id: "MISSING", time_range: period },
      context,
    );
    expect(missing.status).toBe("NOT_FOUND");
  });
});
