import { describe, expect, test } from "bun:test";
import {
  type ExecutionContext,
  errorEnvelope,
  parseToolInput,
  parseToolOutput,
  requireBuildingAccess,
  runTechnicalTool,
  successEnvelope,
  ToolError,
  technicalToolCatalog,
  toolSchemas,
} from "../../src/technical-tools";

const buildingId = "11111111-1111-4111-8111-111111111111";
const scopeId = "22222222-2222-4222-8222-222222222222";
const context: ExecutionContext = {
  tenant_id: "33333333-3333-4333-8333-333333333333",
  principal_id: "staff-1",
  source_run_id: "44444444-4444-4444-8444-444444444444",
  trace_id: "trace-1",
  agent_version: "a2-1",
  received_at: "2026-09-30T09:00:00Z",
  grants: [
    { tool: "asset.read", capability: "asset:read", scopeIds: [scopeId] },
  ],
};
const range = { from: "2026-09-30T08:00:00Z", to: "2026-09-30T09:00:00Z" };

describe("first seven technical tool contracts", () => {
  test("catalog and schemas have exactly the same seven names", () => {
    expect(Object.keys(technicalToolCatalog).sort()).toEqual(
      Object.keys(toolSchemas).sort(),
    );
    expect(Object.keys(technicalToolCatalog)).toHaveLength(7);
    expect(technicalToolCatalog["maintenance_history.append"].idempotency).toBe(
      "required",
    );
  });

  test("every input rejects model supplied identity fields", () => {
    const samples = {
      "sop_kb.retrieve": {
        building_id: buildingId,
        issue_code: "TECH.HVAC.CONDENSATION",
        query: "nghiệm thu",
      },
      "asset.read": { building_id: buildingId, asset_id: "AC-1" },
      "sensor.read": {
        building_id: buildingId,
        asset_id: "AC-1",
        metric: "temperature",
        time_range: range,
      },
      "maintenance_history.read": {
        building_id: buildingId,
        asset_id: "AC-1",
        time_range: range,
      },
      "technical.get_active_outage": {
        building_id: buildingId,
        service_type: "water",
        occurred_at: range.from,
      },
      "utility_schedule.read": {
        building_id: buildingId,
        utility_type: "power",
        time_range: range,
      },
      "maintenance_history.append": {
        building_id: buildingId,
        asset_id: "AC-1",
        workorder_id: buildingId,
        verified_result_id: "result-1",
        outcome: "Repaired",
        source_refs: ["workorder:1"],
        idempotency_key: "append-001",
      },
    } as const;
    for (const [name, sample] of Object.entries(samples)) {
      expect(() =>
        parseToolInput(name as keyof typeof samples, sample),
      ).not.toThrow();
      expect(() =>
        parseToolInput(name as keyof typeof samples, {
          ...sample,
          tenant_id: context.tenant_id,
        }),
      ).toThrow();
    }
  });

  test("applies defaults and rejects ambiguous lookup or reversed time", () => {
    expect(
      parseToolInput("sop_kb.retrieve", {
        building_id: buildingId,
        issue_code: "TECH.HVAC.CONDENSATION",
        query: "nghiệm thu",
      }),
    ).toMatchObject({ language: "vi", limit: 5 });
    expect(() =>
      parseToolInput("asset.read", {
        building_id: buildingId,
        asset_id: "AC-1",
        location: "A1",
      }),
    ).toThrow();
    expect(() =>
      parseToolInput("sensor.read", {
        building_id: buildingId,
        sensor_id: "S-1",
        asset_id: "AC-1",
        metric: "temperature",
        time_range: range,
      }),
    ).toThrow();
    expect(() =>
      parseToolInput("utility_schedule.read", {
        building_id: buildingId,
        utility_type: "water",
        time_range: { from: range.to, to: range.from },
      }),
    ).toThrow();
  });

  test("rejects duplicate source references and proposed outages", () => {
    expect(() =>
      parseToolInput("maintenance_history.append", {
        building_id: buildingId,
        asset_id: "AC-1",
        workorder_id: buildingId,
        verified_result_id: "result-1",
        outcome: "Repaired",
        source_refs: ["a", "a"],
        idempotency_key: "append-001",
      }),
    ).toThrow();
    expect(() =>
      parseToolOutput("technical.get_active_outage", {
        outages: [
          {
            outage_id: buildingId,
            service_type: "water",
            status: "proposed",
            scope_ids: [scopeId],
            started_at: range.from,
          },
        ],
      }),
    ).toThrow();
  });

  test("requires tool grant and backend scope check before access", async () => {
    const allowed = { canAccessBuilding: async () => true };
    await expect(
      requireBuildingAccess(
        context,
        "asset.read",
        "asset:read",
        buildingId,
        allowed,
      ),
    ).resolves.toBeUndefined();
    await expect(
      requireBuildingAccess(
        context,
        "sensor.read",
        "sensor:read",
        buildingId,
        allowed,
      ),
    ).rejects.toMatchObject({ code: "FORBIDDEN" });
    await expect(
      requireBuildingAccess(context, "asset.read", "asset:read", buildingId, {
        canAccessBuilding: async () => false,
      }),
    ).rejects.toMatchObject({ code: "FORBIDDEN" });
  });

  test("envelopes keep trace/provenance and hide unexpected errors", () => {
    const now = new Date("2026-09-30T09:00:00Z");
    expect(successEnvelope(context, { assets: [] }, [], now)).toMatchObject({
      status: "OK",
      trace_id: "trace-1",
      data: { assets: [] },
    });
    expect(
      errorEnvelope(
        context,
        new ToolError("INVALID_INPUT", "Invalid time range", {
          field: "time_range",
        }),
        now,
      ),
    ).toMatchObject({
      status: "NEEDS_INPUT",
      data: null,
      errors: [
        { code: "INVALID_INPUT", field: "time_range", retryable: false },
      ],
    });
    expect(
      JSON.stringify(
        errorEnvelope(context, new Error("DATABASE_URL=secret"), now),
      ),
    ).not.toContain("secret");
  });

  test("runner rejects invalid input and denied scope before calling adapter", async () => {
    let calls = 0;
    const invoke = async () => {
      calls++;
      return { data: { assets: [] }, provenance: [] };
    };
    const access = { canAccessBuilding: async () => false };
    const invalid = await runTechnicalTool(
      "asset.read",
      { building_id: buildingId },
      context,
      access,
      invoke,
    );
    expect(invalid.errors[0]?.code).toBe("INVALID_INPUT");
    const forbidden = await runTechnicalTool(
      "asset.read",
      { building_id: buildingId, asset_id: "AC-1" },
      context,
      access,
      invoke,
    );
    expect(forbidden.status).toBe("FORBIDDEN");
    expect(calls).toBe(0);
  });

  test("runner validates adapter output and records an OK response", async () => {
    const access = { canAccessBuilding: async () => true };
    const input = { building_id: buildingId, asset_id: "AC-1" };
    const good = await runTechnicalTool(
      "asset.read",
      input,
      context,
      access,
      async () => ({
        data: {
          assets: [
            {
              asset_id: "AC-1",
              type: "air_conditioner",
              location: "A1",
              status: "active",
              updated_at: range.to,
            },
          ],
        },
        provenance: [{ source_system: "asset_mock", retrieved_at: range.to }],
      }),
    );
    expect(good.status).toBe("OK");
    expect(good.provenance[0]?.source_system).toBe("asset_mock");
    const bad = await runTechnicalTool(
      "asset.read",
      input,
      context,
      access,
      async () => ({
        data: { assets: [{ asset_id: "AC-1" }] } as never,
        provenance: [],
      }),
    );
    expect(bad.status).toBe("INTERNAL_ERROR");
  });
});
