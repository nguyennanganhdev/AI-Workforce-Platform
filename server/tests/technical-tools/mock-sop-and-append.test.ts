import { describe, expect, test } from "bun:test";
import {
  createMockMaintenancePort,
  createMockSopPort,
  createTechnicalReadTools,
  createTechnicalWriteTools,
  type ExecutionContext,
  type MockSopDocument,
} from "../../src/technical-tools";

const tenant = "11111111-1111-4111-8111-111111111111";
const building = "22222222-2222-4222-8222-222222222222";
const documentId = "33333333-3333-4333-8333-333333333333";
const workorderId = "44444444-4444-4444-8444-444444444444";
const context: ExecutionContext = {
  tenant_id: tenant,
  principal_id: "staff-1",
  source_run_id: "55555555-5555-4555-8555-555555555555",
  trace_id: "trace-sop-write",
  agent_version: "a2-1",
  received_at: "2026-09-30T09:00:00Z",
  grants: [
    { tool: "sop_kb.retrieve", capability: "sop:read", scopeIds: [building] },
    {
      tool: "maintenance_history.append",
      capability: "maintenance:append",
      scopeIds: [building],
    },
  ],
};
const access = { canAccessBuilding: async () => true };
const sopBase: MockSopDocument = {
  tenantId: tenant,
  buildingIds: [building],
  issueCodes: ["TECH.HVAC.CONDENSATION"],
  language: "vi",
  status: "published",
  activeVersion: true,
  reviewed: true,
  ingested: true,
  allowedPrincipalIds: ["staff-1"],
  document_id: documentId,
  code: "SOP-HVAC-012",
  title: "Xử lý nước ngưng điều hòa",
  version_no: 3,
  effective_from: "2026-01-01T00:00:00Z",
  effective_to: null,
  excerpt: "Kiểm tra đường thoát nước ngưng.",
  acceptance_criteria: ["Không còn rò nước"],
  source_refs: ["doc:SOP-HVAC-012:v3"],
};

describe("SOP POC retrieval", () => {
  test("filters draft, expired, denied and unreviewed SOP before ranking", async () => {
    const docs: MockSopDocument[] = [
      sopBase,
      {
        ...sopBase,
        document_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        status: "draft",
        title: "nước ngưng draft",
      },
      {
        ...sopBase,
        document_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        effective_to: "2026-08-01T00:00:00Z",
      },
      {
        ...sopBase,
        document_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        deniedPrincipalIds: ["staff-1"],
      },
      {
        ...sopBase,
        document_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        reviewed: false,
      },
      {
        ...sopBase,
        document_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        activeVersion: false,
      },
    ];
    const tool = createTechnicalReadTools(access, {
      sop: createMockSopPort(docs),
      asset: {
        read: async () => {
          throw new Error("unused");
        },
      },
      sensor: {
        read: async () => {
          throw new Error("unused");
        },
      },
      maintenance: {
        read: async () => {
          throw new Error("unused");
        },
      },
    });
    const answer = await tool.sopRetrieve(
      {
        building_id: building,
        issue_code: "TECH.HVAC.CONDENSATION",
        query: "nước ngưng",
      },
      context,
    );
    expect(answer.status).toBe("OK");
    expect(
      (answer.data as { documents: { document_id: string }[] }).documents.map(
        (doc) => doc.document_id,
      ),
    ).toEqual([documentId]);
    const denied = await tool.sopRetrieve(
      {
        building_id: building,
        issue_code: "TECH.HVAC.CONDENSATION",
        query: "nước ngưng",
      },
      { ...context, principal_id: "stranger" },
    );
    expect(denied.status).toBe("NOT_FOUND");
  });
});

describe("maintenance append POC", () => {
  const asset = {
    tenantId: tenant,
    buildingId: building,
    asset_id: "AC-1",
    type: "air_conditioner",
    location: "A1-1205",
    status: "active",
    updated_at: "2026-09-20T02:00:00Z",
  };
  const baseInput = {
    building_id: building,
    asset_id: "AC-1",
    workorder_id: workorderId,
    verified_result_id: "result-1",
    outcome: "Drain cleaned",
    source_refs: ["workorder:1"],
    idempotency_key: "append-001",
  };

  test("requires VERIFIED result and keeps idempotent append-only history", async () => {
    const maintenance = createMockMaintenancePort(
      {
        assets: [asset],
        verifiedResults: [
          {
            id: "result-1",
            tenantId: tenant,
            buildingId: building,
            assetId: "AC-1",
            workorderId,
            status: "VERIFIED",
            allowedPrincipalIds: ["staff-1"],
          },
          {
            id: "result-2",
            tenantId: tenant,
            buildingId: building,
            assetId: "AC-1",
            workorderId,
            status: "PENDING",
            allowedPrincipalIds: ["staff-1"],
          },
        ],
      },
      () => new Date("2026-09-30T09:01:00Z"),
    );
    const tool = createTechnicalWriteTools(access, maintenance);
    const first = await tool.maintenanceAppend(baseInput, context);
    expect(first.status).toBe("OK");
    const retry = await tool.maintenanceAppend(baseInput, context);
    expect(retry.data).toEqual(first.data);
    const conflict = await tool.maintenanceAppend(
      { ...baseInput, outcome: "Different repair" },
      context,
    );
    expect(conflict.status).toBe("CONFLICT");
    const pending = await tool.maintenanceAppend(
      {
        ...baseInput,
        verified_result_id: "result-2",
        idempotency_key: "append-002",
      },
      context,
    );
    expect(pending.status).toBe("CONFLICT");
    const history = await maintenance.read(context, {
      building_id: building,
      asset_id: "AC-1",
      time_range: {
        from: "2026-09-30T08:00:00Z",
        to: "2026-09-30T10:00:00Z",
      },
      limit: 20,
    });
    expect(history.data.events).toHaveLength(1);
    const revision = await tool.maintenanceAppend(
      {
        ...baseInput,
        outcome: "Corrected result",
        idempotency_key: "append-003",
        supersedes_event_id: (first.data as { maintenance_event_id: string })
          .maintenance_event_id,
      },
      context,
    );
    expect(revision.data).toMatchObject({ revision: 2 });
  });
});
