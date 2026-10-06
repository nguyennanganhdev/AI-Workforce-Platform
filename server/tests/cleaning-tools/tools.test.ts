import { describe, expect, test } from "bun:test";
import {
  describeCleaningTools,
  findCleaningTool,
} from "../../src/cleaning-tools/catalog";
import { fixture, I, submission } from "./support";
import { createV3CleaningOperations } from "../../src/cleaning-tools/adapters/v3-operations";
import { technicalTools } from "../../src/technical-tools/catalog";
import {
  cleaningNames,
  reuseTechnicalTool,
} from "../../src/cleaning-tools/tools/technical-counterparts";
import { z } from "zod";
import { NOW } from "./support";
import { cleaningTechnicalDependencies } from "../../src/cleaning-tools/adapters/technical-dependencies";
import type { ToolContext } from "../../src/technical-tools/contracts/context";

describe("cleaning tools and the shared specialist boundary", () => {
  test("exports all fourteen technical counterparts plus five V3 coordination tools", () => {
    const tools = describeCleaningTools();
    expect(tools).toHaveLength(19);
    for (const t of tools) {
      expect(t.name.startsWith("cleaning.")).toBe(true);
      expect(findCleaningTool(t.model_name)?.name).toBe(t.name);
      expect(findCleaningTool(t.name.replace(".", "/"))?.name).toBe(t.name);
      expect(t.input_schema.additionalProperties).toBe(false);
      if (t.side_effect === "write")
        expect(t.input_schema.required).toContain("idempotency_key");
    }
    expect(
      findCleaningTool("technical.submit_executor_result"),
    ).toBeUndefined();
  });
  test("refuses a missing capability before querying the backend and records the denial", async () => {
    const f = fixture();
    f.identity.grants = [];
    expect(
      (
        await f.call("cleaning.read_work_order", {
          building_id: I.building,
          work_order_id: I.work,
        })
      ).status,
    ).toBe("FORBIDDEN");
    expect(f.requests).toHaveLength(0);
    expect(f.audit[0]?.status).toBe("FORBIDDEN");
  });
  test("refuses another building and model-supplied authority", async () => {
    const f = fixture();
    expect(
      (
        await f.call("cleaning.read_work_order", {
          building_id: I.otherBuilding,
          work_order_id: I.work,
        })
      ).status,
    ).toBe("FORBIDDEN");
    expect(
      (
        await f.call("cleaning.read_work_order", {
          building_id: I.building,
          work_order_id: I.work,
          role: "admin",
        })
      ).status,
    ).toBe("INVALID_INPUT");
    expect(f.requests).toHaveLength(0);
  });
  test("rejects ambiguous selectors", async () => {
    const f = fixture();
    expect(
      (
        await f.call("cleaning.read_work_order", {
          building_id: I.building,
          work_order_id: I.work,
          ticket_id: I.ticket,
        })
      ).status,
    ).toBe("INVALID_INPUT");
  });
  test("reads current work and isolates its timeline", async () => {
    const f = fixture();
    const r = await f.call("cleaning.read_work_order", {
      building_id: I.building,
      work_order_id: I.work,
      include_history: true,
    });
    expect(r.status).toBe("OK");
    expect((r.data as any).work_orders[0].version).toBe(4);
    expect((r.data as any).history).toHaveLength(1);
    expect((r.data as any).history[0].event_type).toBe(
      "work_order.status_changed",
    );
  });
  test("does not expose technical work when reading by ticket", async () => {
    const f = fixture();
    f.setCategory(I.technical);
    const r = await f.call("cleaning.read_work_order", {
      building_id: I.building,
      ticket_id: I.ticket,
    });
    expect(r.status).toBe("OK");
    expect((r.data as any).work_orders).toEqual([]);
    expect(
      (
        await f.call("cleaning.read_work_order", {
          building_id: I.building,
          work_order_id: I.work,
        })
      ).status,
    ).toBe("FORBIDDEN");
  });
  test("reads only the cleaning timeline when selecting by ticket", async () => {
    const f = fixture();
    const r = await f.call("cleaning.read_work_order", {
      building_id: I.building,
      ticket_id: I.ticket,
      include_history: true,
    });
    expect(r.status).toBe("OK");
    expect((r.data as any).history.map((e: any) => e.event_type)).toEqual([
      "work_order.status_changed",
    ]);
  });
  test("narrows available cleaning staff to the work's required specialty", async () => {
    const f = fixture();
    f.deps.operations = createV3CleaningOperations({
      async request(_context, r) {
        if (r.path === "/catalogs")
          return {
            serviceCategories: [
              { id: I.cleaning, code: "cleaning", parent_id: null },
            ],
            buildings: [{ id: I.building, site_id: I.site }],
            sites: [{ id: I.site, domain_id: I.domain }],
          };
        if (r.path === "/management-units/resolve")
          return { managementUnitId: I.unit };
        if (r.path === `/tickets/${I.ticket}`)
          return {
            ticket: {
              id: I.ticket,
              building_id: I.building,
              management_unit_id: I.unit,
              version: 2,
            },
            workOrders: [],
            events: [],
          };
        if (r.path === `/work-orders/${I.work}`)
          return {
            workOrder: {
              id: I.work,
              ticket_id: I.ticket,
              category_id: I.cleaning,
              required_specialty_id: I.scope,
              description: "Vệ sinh sàn",
              status: "queued",
              version: 4,
            },
            assignments: [],
          };
        if (r.path === "/staff/available")
          return {
            items:
              r.query?.categoryId === I.scope
                ? []
                : [
                    {
                      id: I.staff,
                      employee_code: "VS-001",
                      management_unit_id: I.unit,
                      active_jobs: 0,
                      max_concurrent_jobs: 2,
                    },
                  ],
          };
        throw new Error("Unexpected request");
      },
    });
    const r = await f.call("cleaning.list_available_staff", {
      building_id: I.building,
      work_order_id: I.work,
    });
    expect(r.status).toBe("OK");
    expect(r.data).toMatchObject({ staff: [] });
  });
  test("lists only eligible cleaning staff and reports no available staff truthfully", async () => {
    const f = fixture();
    const input = { building_id: I.building };
    expect(
      (await f.call("cleaning.list_available_staff", input)).data,
    ).toMatchObject({ staff: [{ staff_id: I.staff }] });
    f.setUnavailable();
    expect(
      (await f.call("cleaning.list_available_staff", input)).data,
    ).toMatchObject({ staff: [] });
  });
  test("technical-only staff cannot be dispatched", async () => {
    const f = fixture();
    f.setWork("queued");
    expect(
      (
        await f.call("cleaning.dispatch_staff", {
          building_id: I.building,
          work_order_id: I.work,
          staff_id: I.techStaff,
          expected_version: 4,
          offer_expires_at: "2026-10-06T11:00:00Z",
          idempotency_key: "dispatch-tech",
        })
      ).status,
    ).toBe("FORBIDDEN");
    expect(f.requests.filter((r) => r.method === "POST")).toHaveLength(0);
  });
  test("offers work once across retries and concurrent calls", async () => {
    const f = fixture();
    f.setWork("queued");
    const input = {
      building_id: I.building,
      work_order_id: I.work,
      staff_id: I.staff,
      expected_version: 4,
      offer_expires_at: "2026-10-06T11:00:00Z",
      idempotency_key: "dispatch-once",
    };
    const replies = await Promise.all([
      f.call("cleaning.dispatch_staff", input),
      f.call("cleaning.dispatch_staff", input),
    ]);
    expect(replies.some((r) => r.status === "OK")).toBe(true);
    const replay = await f.call("cleaning.dispatch_staff", input);
    expect(replay.data).toMatchObject({
      assignment_status: "offered",
      work_order_status: "offered",
      version: 5,
    });
    expect(f.requests.filter((r) => r.method === "POST")).toHaveLength(1);
    expect(
      (
        await f.call("cleaning.dispatch_staff", {
          ...input,
          staff_id: I.techStaff,
        })
      ).status,
    ).toBe("CONFLICT");
  });
  test("expired offers and stale versions do not call the mutation", async () => {
    const f = fixture();
    f.setWork("queued");
    const input = {
      building_id: I.building,
      work_order_id: I.work,
      staff_id: I.staff,
      expected_version: 3,
      offer_expires_at: "2026-10-06T11:00:00Z",
      idempotency_key: "bad-offer-1",
    };
    expect((await f.call("cleaning.dispatch_staff", input)).status).toBe(
      "CONFLICT",
    );
    expect(
      (
        await f.call("cleaning.dispatch_staff", {
          ...input,
          expected_version: 4,
          offer_expires_at: "2026-10-06T09:00:00Z",
        })
      ).status,
    ).toBe("CONFLICT");
    expect(f.requests.filter((r) => r.method === "POST")).toHaveLength(0);
  });
  test("cannot accept work through the progress tool", async () => {
    const f = fixture();
    expect(
      (
        await f.call("cleaning.update_work_status", {
          building_id: I.building,
          work_order_id: I.work,
          assignment_id: I.assignment,
          expected_version: 4,
          status: "accepted",
          note: "Nhận việc",
          idempotency_key: "no-accept",
        })
      ).status,
    ).toBe("INVALID_INPUT");
  });
  test("backend worker authority remains mandatory for progress", async () => {
    const f = fixture();
    const input = {
      building_id: I.building,
      work_order_id: I.work,
      assignment_id: I.assignment,
      expected_version: 4,
      status: "in_progress",
      note: "Nhân viên báo đang làm",
      idempotency_key: "progress-1",
    };
    expect((await f.call("cleaning.update_work_status", input)).status).toBe(
      "FORBIDDEN",
    );
    f.identity.role_code = "staff";
    f.identity.user_id = "cleaner";
    expect((await f.call("cleaning.update_work_status", input)).status).toBe(
      "OK",
    );
    expect(f.requests.at(-1)?.body).toEqual({
      version: 4,
      status: "in_progress",
      note: input.note,
    });
  });
  test("creation uses the existing V3 service and rejects technical specialties", async () => {
    const f = fixture();
    const input = {
      building_id: I.building,
      ticket_id: I.ticket,
      ticket_version: 2,
      description: "Vệ sinh sàn",
      required_specialty_id: I.cleaning,
      idempotency_key: "create-work-1",
    };
    expect((await f.call("cleaning.create_work_order", input)).status).toBe(
      "OK",
    );
    expect(
      (
        await f.call("cleaning.create_work_order", {
          ...input,
          required_specialty_id: I.technical,
          idempotency_key: "create-technical-specialty",
        })
      ).status,
    ).toBe("FORBIDDEN");
    const r = await f.call("cleaning.create_work_order", {
      ...input,
      description: "Vệ sinh cửa kính",
      idempotency_key: "create-other-cleaning-work",
    });
    expect(r.status).toBe("OK");
    expect(f.requests.at(-1)?.body).toMatchObject({ category_id: I.cleaning });
  });
  test.each([403, 404, 409, 422] as const)(
    "preserves backend rejection %s",
    async (code) => {
      const f = fixture();
      f.setFailure(code);
      const r = await f.call("cleaning.read_work_order", {
        building_id: I.building,
        work_order_id: I.work,
      });
      expect(r.status).toBe(
        (
          {
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            422: "INVALID_INPUT",
          } as const
        )[code],
      );
    },
  );
});

describe("technical capability parity, only cleaning workforce differs", () => {
  test.each(technicalTools.map((source) => [source.name, source] as const))(
    "%s keeps the original schema, effect, capability, timeout and delegates its implementation",
    async (_name, source) => {
      const name = cleaningNames[source.name]!;
      const tool = findCleaningTool(name)!;
      expect(tool.outputSchema).toBe(source.outputSchema);
      expect(tool.effect).toBe(source.effect);
      expect(tool.capability).toBe(source.capability);
      expect(tool.timeoutMs).toBe(source.timeoutMs);
      if (source.name !== "sop_kb.retrieve")
        expect(tool.inputSchema).toBe(source.inputSchema);
      else {
        const cleaningSchema = z.toJSONSchema(tool.inputSchema) as any;
        const technicalSchema = z.toJSONSchema(source.inputSchema) as any;
        delete cleaningSchema.properties.issue_code.pattern;
        delete technicalSchema.properties.issue_code.pattern;
        expect(cleaningSchema).toEqual(technicalSchema);
      }
      const f = fixture();
      const { grants, ...identity } = f.identity;
      const context: ToolContext = {
        ...identity,
        received_at: NOW.toISOString(),
        capabilities: new Set(grants.map((g) => g.capability)),
      };
      const input = { building_id: I.building };
      const answer = {
        status: "NEEDS_INPUT" as const,
        data: null,
        missingFields: ["fixture"],
      };
      let calls = 0;
      const probe = reuseTechnicalTool(
        {
          ...source,
          run: async (c, args, deps) => {
            calls++;
            expect(c).toBe(context);
            expect(args).toBe(input);
            expect(deps.executorResults).toBe(f.deps.executorResults);
            expect(deps.measurements).toBe(f.deps.measurements);
            expect(
              await deps.workOrders.getWorkOrder({
                tenantId: I.tenant,
                buildingId: I.building,
                workOrderId: I.work,
              }),
            ).not.toBeNull();
            return answer;
          },
        },
        name,
      );
      expect(await probe.run(context, input, f.deps)).toBe(answer);
      expect(calls).toBe(1);
    },
  );
  test("retrieves only approved cleaning guidance with the same SOP rules", async () => {
    const f = fixture();
    const input = {
      building_id: I.building,
      issue_code: "CLEAN.FLOOR.DIRT",
      query: "vệ sinh sàn",
    };
    expect((await f.call("cleaning.retrieve_sop", input)).data).toMatchObject({
      documents: [{ code: "SOP-CLEAN-001" }],
    });
    f.sop.status = "draft";
    expect((await f.call("cleaning.retrieve_sop", input)).status).toBe(
      "NOT_FOUND",
    );
    expect(
      (
        await f.call("cleaning.retrieve_sop", {
          ...input,
          issue_code: "TECH.ELEC.BREAKER_TRIP",
        })
      ).status,
    ).toBe("INVALID_INPUT");
  });
  test("same SOP ACL: explicit deny overrides an allow", async () => {
    const f = fixture();
    f.sop.acl.push({
      principalKind: "role",
      roleCode: "management",
      userId: null,
      workspaceId: null,
      effect: "deny",
    });
    expect(
      (
        await f.call("cleaning.retrieve_sop", {
          building_id: I.building,
          issue_code: "CLEAN.FLOOR.DIRT",
          query: "vệ sinh sàn",
        })
      ).status,
    ).toBe("FORBIDDEN");
  });
  test("submits with the exact technical contract, without completing work, and verifies read-only", async () => {
    const f = fixture();
    const r = await f.call("cleaning.submit_executor_result", submission());
    expect(r.status).toBe("OK");
    expect((r.data as any).validation_status).toBe("ACCEPTED");
    expect(f.status()).toBe("in_progress");
    expect(
      (await f.call("cleaning.submit_executor_result", submission())).data,
    ).toEqual(r.data);
    expect(f.stored.size).toBe(1);
    const v = await f.call("cleaning.verify_resolution", {
      building_id: I.building,
      incident_id: I.ticket,
      workorder_id: I.work,
      result_id: (r.data as any).result_id,
      sop_document_ids: [I.sop],
    });
    expect((v.data as any).verification_status).toBe("VERIFIED");
    expect(f.status()).toBe("in_progress");
    expect(f.requests.filter((r) => r.method !== "GET")).toHaveLength(0);
  });
  test("missing evidence/SOP follows the same human review behavior", async () => {
    const f = fixture();
    const r = await f.call("cleaning.submit_executor_result", {
      ...submission(),
      evidence_ids: [I.before],
    });
    expect((r.data as any).validation_status).toBe("NEEDS_EVIDENCE");
    const v = await f.call("cleaning.verify_resolution", {
      building_id: I.building,
      incident_id: I.ticket,
      workorder_id: I.work,
      result_id: (r.data as any).result_id,
    });
    expect((v.data as any).verification_status).toBe("HUMAN_REVIEW");
  });
  test("does not add version or future-time rejection to technical result semantics", async () => {
    const f = fixture();
    const input = { ...submission(), completed_at: "2026-10-07T09:00:00Z" };
    const source = technicalTools.find(
      (t) => t.name === "technical.submit_executor_result",
    )!;
    const { grants, ...identity } = f.identity;
    const context: ToolContext = {
      ...identity,
      received_at: NOW.toISOString(),
      capabilities: new Set(grants.map((g) => g.capability)),
    };
    const original = await source.run(
      context,
      source.inputSchema.parse(input),
      f.deps,
    );
    const r = await f.call("cleaning.submit_executor_result", input);
    expect(r.status).toBe(original.status);
    expect((r.data as any).validation_status).toBe(
      (original.data as any).validation_status,
    );
    expect((r.data as any).conflicts).toEqual((original.data as any).conflicts);
    expect(
      (
        await f.call("cleaning.submit_executor_result", {
          ...submission(),
          expected_version: 4,
        })
      ).status,
    ).toBe("INVALID_INPUT");
  });
  test("original evidence checks still reject uploads and withdrawn evidence", async () => {
    for (const change of ["upload", "withdrawn", "ticket"]) {
      const f = fixture();
      const e = f.evidence[1] as any;
      if (change === "upload") e.fileStatus = "staged";
      if (change === "withdrawn") e.status = "withdrawn";
      if (change === "ticket") e.ticketId = I.otherBuilding;
      expect(
        (await f.call("cleaning.submit_executor_result", submission())).status,
      ).toBe("CONFLICT");
      expect(f.stored.size).toBe(0);
    }
  });
  test("released assignments/unrelated callers cannot submit; technical work is excluded", async () => {
    const f = fixture();
    f.setAssignment("released");
    expect(
      (await f.call("cleaning.submit_executor_result", submission())).status,
    ).toBe("CONFLICT");
    f.setAssignment("accepted");
    f.identity.role_code = "staff";
    f.identity.user_id = "another-cleaner";
    expect(
      (await f.call("cleaning.submit_executor_result", submission())).status,
    ).toBe("FORBIDDEN");
    f.setCategory(I.technical);
    expect(
      (await f.call("cleaning.submit_executor_result", submission())).status,
    ).toBe("NOT_FOUND");
  });
  test("workforce filter also applies to shared incident requests", async () => {
    const f = fixture();
    const scoped = cleaningTechnicalDependencies(f.deps);
    expect(
      await scoped.workOrders.listWorkOrders({
        tenantId: I.tenant,
        buildingId: I.building,
        ticketId: I.ticket,
      }),
    ).toHaveLength(1);
    f.setCategory(I.technical);
    expect(
      await scoped.workOrders.listWorkOrders({
        tenantId: I.tenant,
        buildingId: I.building,
        ticketId: I.ticket,
      }),
    ).toEqual([]);
    expect(
      await scoped.workOrders.getWorkOrder({
        tenantId: I.tenant,
        buildingId: I.building,
        workOrderId: I.work,
      }),
    ).toBeNull();
  });
  test("vendor requests select cleaning specialties and remain pending approval", async () => {
    const f = fixture();
    f.deps.vendors.findBySpecialty = async (q) => [
      {
        tenantId: I.tenant,
        vendorId: "cleaning-vendor",
        displayName: "Đội vệ sinh ngoài",
        specialtyCodes: [q.specialtyCode],
        siteIds: [I.site],
        status: "active",
        licenseExpiresAt: new Date("2027-01-01T00:00:00Z"),
        insuranceVerified: true,
        contactPhone: "+84900000000",
        hourlyRate: 100000,
      },
    ];
    const input = {
      building_id: I.building,
      incident_id: I.ticket,
      workorder_id: I.work,
      service: "Vệ sinh sàn",
      reason: "Cần đội vệ sinh bên ngoài hỗ trợ",
      urgency: "routine",
      required_specialty_code: "CLEANING",
      idempotency_key: "vendor-cleaning-1",
    };
    const r = await f.call("cleaning.request_vendor_dispatch", input);
    expect(r.status).toBe("PENDING_APPROVAL");
    expect(r.data).toMatchObject({
      eligible_vendors: [{ vendor_id: "cleaning-vendor" }],
    });
    expect(
      (
        await f.call("cleaning.request_vendor_dispatch", {
          ...input,
          required_specialty_code: "HV_ELECTRICAL",
          idempotency_key: "vendor-technical-1",
        })
      ).status,
    ).toBe("FORBIDDEN");
  });
  test("cleaning workers record actual measurements using the original technician-source contract", async () => {
    const f = fixture();
    f.identity.user_id = "cleaner";
    f.identity.role_code = "staff";
    const r = await f.call("cleaning.record_measurement", {
      building_id: I.building,
      workorder_id: I.work,
      metric: "surface_moisture",
      value: 5,
      unit: "%",
      measured_at: "2026-10-06T09:00:00Z",
      measured_by: { kind: "technician", source_id: "cleaner" },
      source: "manual_entry",
      idempotency_key: "measurement-cleaning-1",
    });
    expect(r.status).toBe("OK");
    expect(r.data).toMatchObject({
      metric: "surface_moisture",
      normalized_value: 5,
      normalized_unit: "%",
    });
  });
  test("complete delegates to V3 without requiring a cleaning result or VERIFIED SOP", async () => {
    const f = fixture();
    f.identity.role_code = "staff";
    f.identity.user_id = "cleaner";
    const update = {
      building_id: I.building,
      work_order_id: I.work,
      assignment_id: I.assignment,
      expected_version: 4,
      status: "completed",
      note: "Nhân viên báo hoàn thành",
      idempotency_key: "completed-v3-1",
    };
    expect((await f.call("cleaning.update_work_status", update)).status).toBe(
      "OK",
    );
    expect(f.requests.at(-1)?.body).toEqual({
      version: 4,
      status: "completed",
      note: update.note,
    });
    expect(f.status()).toBe("completed");
    const rejected = fixture();
    rejected.setFailure(409);
    expect(
      (await rejected.call("cleaning.update_work_status", update)).status,
    ).toBe("CONFLICT");
  });
});
