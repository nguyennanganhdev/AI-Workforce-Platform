import { describe, expect, test } from "bun:test";
import {
  type ApprovalRequest,
  createInMemoryApprovalRequestStore,
} from "../../src/technical-tools";
import { BUILDING, NOW, SOURCE_RUN_ID, TENANT, USER } from "./fixtures/world";

/**
 * The shared approval adapter, in memory: where a power isolation and an area restriction wait for
 * a person.
 */
const request = (
  requestId: string,
  change: Partial<ApprovalRequest> = {},
): ApprovalRequest => ({
  requestId,
  kind: "area_restriction",
  tenantId: TENANT.vinhomes,
  buildingId: BUILDING.a1,
  incidentId: "incident-1",
  workOrderId: null,
  status: "pending",
  requiredApproverScope: "building_management",
  detail: { area: "Hành lang tầng 12" },
  requestHash: "hash",
  requestedBy: USER.technician,
  sourceRunId: SOURCE_RUN_ID,
  createdAt: NOW,
  ...change,
});

describe("the approval adapter", () => {
  test("starts empty", () => {
    expect(createInMemoryApprovalRequestStore().all()).toEqual([]);
  });

  test("lists what is waiting, by tenant, kind and incident", async () => {
    const store = createInMemoryApprovalRequestStore();
    await store.create(request("AR-1"));
    await store.create(request("AR-2", { incidentId: "incident-2" }));
    await store.create(request("PI-1", { kind: "power_isolation" }));
    await store.create(request("AR-X", { tenantId: TENANT.other }));

    const open = await store.listOpen({
      tenantId: TENANT.vinhomes,
      kind: "area_restriction",
      incidentId: "incident-1",
    });
    expect(open.map((r) => r.requestId)).toEqual(["AR-1"]);
  });

  /*
   * The adapter is the agent's only way to the approval workflow. Had it a method to approve,
   * reject or carry out a request, a tool could call it, and every request would be one the agent
   * could approve itself.
   */
  test("has no way to approve, reject or carry out a request", () => {
    const store = createInMemoryApprovalRequestStore();
    expect(Object.keys(store).sort()).toEqual(["all", "create", "listOpen"]);
  });

  test("what it hands back cannot be used to change what it holds", async () => {
    const store = createInMemoryApprovalRequestStore();
    await store.create(request("AR-1"));
    (store.all() as ApprovalRequest[]).pop();
    expect(store.all()).toHaveLength(1);
  });
});
