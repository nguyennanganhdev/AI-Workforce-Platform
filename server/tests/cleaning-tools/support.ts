import type {
  ToolContext,
  ResolvedIdentity,
} from "../../src/technical-tools/contracts/context";
import { createInMemoryIdempotencyStore } from "../../src/technical-tools/adapters/poc/idempotency-store";
import type { ToolAuditEntry } from "../../src/technical-tools/ports/audit-sink";
import type {
  SopDocumentRecord,
  SopProfile,
} from "../../src/technical-tools/domain/sop";
import type { EvidenceLookup } from "../../src/technical-tools/domain/work-order";
import { createV3CleaningOperations } from "../../src/cleaning-tools/adapters/v3-operations";
import {
  CleaningBackendError,
  type BackendRequest,
} from "../../src/cleaning-tools/ports/backend";
import type { ExecutorResult } from "../../src/technical-tools/domain/executor-result";
import { createInMemoryAssetReadPort } from "../../src/technical-tools/adapters/poc/asset-read";
import { createInMemorySensorReadPort } from "../../src/technical-tools/adapters/poc/sensor-read";
import { createInMemoryMaintenanceReadPort } from "../../src/technical-tools/adapters/poc/maintenance-read";
import { createInMemoryMaintenanceStore } from "../../src/technical-tools/adapters/poc/maintenance-store";
import { createInMemoryMeasurementStore } from "../../src/technical-tools/adapters/poc/measurement-store";
import { createInMemoryApprovalRequestStore } from "../../src/technical-tools/adapters/poc/approval-request-store";
import { createInMemoryVendorCatalog } from "../../src/technical-tools/adapters/poc/vendor-catalog";
import { createInMemoryScopeReadPort } from "../../src/technical-tools/adapters/poc/scope-read";
import { cleaningTools } from "../../src/cleaning-tools/catalog";
import {
  createCleaningToolHost,
  type CleaningHostDependencies,
} from "../../src/cleaning-tools/host";

const id = (n: number) =>
  `11111111-1111-4111-8111-${String(n).padStart(12, "0")}`;
export const I = {
  tenant: id(1),
  building: id(2),
  otherBuilding: id(3),
  ticket: id(4),
  work: id(5),
  assignment: id(6),
  staff: id(7),
  techStaff: id(8),
  cleaning: id(9),
  technical: id(10),
  unit: id(11),
  site: id(12),
  domain: id(13),
  sop: id(14),
  before: id(15),
  after: id(16),
  run: id(17),
  scope: id(18),
};
export const NOW = new Date("2026-10-06T10:00:00Z");
export const CALLER = { botId: "bot", actorId: "agent" };

export function fixture() {
  let status = "in_progress",
    workVersion = 4,
    assignmentStatus = "accepted",
    category = I.cleaning;
  let unavailable = false,
    backendFailure: number | null = null;
  const requests: BackendRequest[] = [],
    audit: ToolAuditEntry[] = [];
  const stored = new Map<string, ExecutorResult>();
  const identity: ResolvedIdentity = {
    tenant_id: I.tenant,
    principal_id: "manager",
    user_id: "manager",
    role_code: "management",
    source_run_id: I.run,
    trace_id: "trace-cleaning",
    agent_version: "cleaning-v1",
    grants: cleaningTools.map((t) => ({
      capability: t.capability,
      scope_ids: [I.scope],
    })),
  };
  const sop: SopDocumentRecord = {
    documentId: I.sop,
    code: "SOP-CLEAN-001",
    title: "Vệ sinh sàn",
    status: "published",
    knowledgeBaseStatus: "active",
    language: "vi",
    updatedAt: NOW,
    activeVersion: {
      id: id(19),
      versionNo: 1,
      effectiveFrom: new Date("2026-01-01T00:00:00Z"),
      effectiveTo: null,
      contentHash: "hash",
    },
    acl: [
      {
        principalKind: "role",
        roleCode: "management",
        userId: null,
        workspaceId: null,
        effect: "allow",
      },
      {
        principalKind: "role",
        roleCode: "staff",
        userId: null,
        workspaceId: null,
        effect: "allow",
      },
    ],
  };
  const profile: SopProfile = {
    code: sop.code,
    versionNo: 1,
    issueCodes: ["CLEAN.FLOOR.DIRT"],
    excerpt: "Vệ sinh sàn và chụp ảnh sau khi thực hiện.",
    acceptanceCriteria: [
      {
        id: "floor",
        text: "Sàn đã được vệ sinh",
        check: { kind: "checklist", itemCode: "floor" },
      },
    ],
  };
  const evidence: EvidenceLookup[] = [I.before, I.after].map((id, n) => ({
    kind: "evidence",
    id,
    ticketId: I.ticket,
    workOrderId: I.work,
    assignmentId: I.assignment,
    purpose: n ? "after" : "before",
    status: "active",
    fileStatus: "ready",
  }));
  const order = () => ({
    id: I.work,
    ticket_id: I.ticket,
    category_id: category,
    required_specialty_id: category,
    description: "Vệ sinh sàn",
    status,
    version: workVersion,
  });
  const backend = {
    async request(context: ToolContext, r: BackendRequest): Promise<unknown> {
      requests.push(r);
      if (backendFailure) throw new CleaningBackendError(backendFailure as 403);
      if (context.tenant_id !== I.tenant) throw new CleaningBackendError(403);
      if (r.path === "/catalogs")
        return {
          serviceCategories: [
            { id: I.cleaning, code: "cleaning", parent_id: null },
            { id: I.technical, code: "technical", parent_id: null },
          ],
          buildings: [{ id: I.building, site_id: I.site }],
          sites: [{ id: I.site, domain_id: I.domain }],
        };
      if (r.path === "/management-units/resolve")
        return { managementUnitId: I.unit };
      if (r.method === "GET" && r.path === `/tickets/${I.ticket}`)
        return {
          ticket: {
            id: I.ticket,
            building_id: I.building,
            management_unit_id: I.unit,
            version: 2,
          },
          workOrders: [order()],
          events: [],
        };
      if (r.method === "GET" && r.path === `/work-orders/${I.work}`)
        return {
          workOrder: order(),
          assignments: [
            {
              id: I.assignment,
              staff_id: I.staff,
              status: assignmentStatus,
              eta_at: NOW.toISOString(),
              accepted_at: "2026-10-06T08:00:00Z",
            },
          ],
        };
      if (r.path === "/staff/available")
        return {
          items: unavailable
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
      if (r.path === `/tickets/${I.ticket}/timeline`)
        return {
          items: [
            {
              id: id(20),
              event_type: "work_order.status_changed",
              occurred_at: NOW.toISOString(),
              from_status: "arrived",
              to_status: status,
              payload: { workOrderId: I.work },
            },
            {
              id: id(21),
              event_type: "technical.private",
              occurred_at: NOW.toISOString(),
              from_status: null,
              to_status: null,
              payload: { workOrderId: id(22) },
            },
          ],
        };
      if (r.path.endsWith("/assignments") && r.method === "POST") {
        if (r.body?.work_order_version !== workVersion || status !== "queued")
          throw new CleaningBackendError(409);
        status = "offered";
        assignmentStatus = "offered";
        workVersion++;
        return {
          id: I.assignment,
          work_order_id: I.work,
          staff_id: r.body.staff_id,
          status: "offered",
        };
      }
      if (r.path.endsWith("/status") && r.method === "PATCH") {
        if (context.user_id !== "cleaner" && context.role_code !== "admin")
          throw new CleaningBackendError(403);
        if (r.body?.version !== workVersion)
          throw new CleaningBackendError(409);
        status = String(r.body?.status);
        workVersion++;
        return { id: I.work, status, version: workVersion };
      }
      if (r.path.endsWith("/work-orders") && r.method === "POST")
        return {
          id: id(30),
          ticket_id: I.ticket,
          status: "queued",
          version: 0,
        };
      throw new Error(`Unexpected backend request ${r.method} ${r.path}`);
    },
  };
  const deps: CleaningHostDependencies = {
    interruptions: { listCovering: async () => [] },
    assets: createInMemoryAssetReadPort(),
    sensors: createInMemorySensorReadPort(),
    maintenance: createInMemoryMaintenanceReadPort(),
    maintenanceStore: createInMemoryMaintenanceStore(),
    approvalRequests: createInMemoryApprovalRequestStore(),
    vendors: createInMemoryVendorCatalog(),
    scopes: createInMemoryScopeReadPort(
      [
        {
          tenantId: I.tenant,
          buildingId: I.building,
          siteId: I.site,
          zoneId: null,
        },
      ],
      [],
    ),
    isolations: {
      findOpen: async () => [],
      createWaterIsolation: async () => {},
    },
    units: { findUnit: async () => null, residents: async () => [] },
    isCleaningSpecialty: async (tenant, code) =>
      tenant === I.tenant && code === "CLEANING",
    operations: createV3CleaningOperations(backend),
    clock: { now: () => NOW },
    contextResolver: async () => identity,
    buildingAccess: {
      canAccessBuilding: async (q) =>
        q.buildingId === I.building && q.scopeIds.includes(I.scope),
    },
    audit: {
      record: async (entry) => {
        audit.push(entry);
      },
    },
    idempotency: createInMemoryIdempotencyStore(),
    isCleaningWorkOrder: async (tenant, building, work) =>
      tenant === I.tenant &&
      building === I.building &&
      work === I.work &&
      category === I.cleaning,
    workOrders: {
      getWorkOrder: async (q) =>
        q.workOrderId === I.work &&
        q.tenantId === I.tenant &&
        q.buildingId === I.building
          ? {
              workOrderId: I.work,
              ticketId: I.ticket,
              buildingId: I.building,
              status,
              assignments: [
                {
                  assignmentId: I.assignment,
                  status: assignmentStatus,
                  staffUserId: "cleaner",
                  acceptedAt: new Date("2026-10-06T08:00:00Z"),
                },
              ],
            }
          : null,
      getTicket: async (q) =>
        q.tenantId === I.tenant &&
        q.buildingId === I.building &&
        q.ticketId === I.ticket
          ? {
              ticketId: I.ticket,
              buildingId: I.building,
              unitId: null,
              isEmergency: false,
              priority: "routine",
            }
          : null,
      listWorkOrders: async (q) => {
        const order = await deps.workOrders.getWorkOrder({
          ...q,
          workOrderId: I.work,
        });
        return order ? [order] : [];
      },
      findEvidence: async (q) => evidence.filter((e) => q.ids.includes(e.id)),
    },
    executorResults: {
      append: async (r) => {
        stored.set(r.resultId, r);
      },
      findById: async (tenant, id) =>
        tenant === I.tenant ? (stored.get(id) ?? null) : null,
    },
    measurements: createInMemoryMeasurementStore(),
    sop: { listForBuilding: async () => [sop] },
    sopProfiles: {
      find: (code, v) => (code === sop.code && v === 1 ? profile : undefined),
    },
  };
  const host = createCleaningToolHost(deps);
  const call = (name: string, args: Record<string, unknown>) =>
    host.call(CALLER, host.find(name)!, args);
  return {
    deps,
    host,
    call,
    requests,
    audit,
    identity,
    sop,
    profile,
    evidence,
    stored,
    status: () => status,
    version: () => workVersion,
    setWork: (s: string, v = 4) => {
      status = s;
      workVersion = v;
    },
    setCategory: (c: string) => {
      category = c;
    },
    setAssignment: (s: string) => {
      assignmentStatus = s;
    },
    setUnavailable: () => {
      unavailable = true;
    },
    setFailure: (code: number) => {
      backendFailure = code;
    },
  };
}
export const submission = () => ({
  building_id: I.building,
  workorder_id: I.work,
  assignment_id: I.assignment,
  checklist: [{ item_code: "floor", status: "passed" }],
  evidence_ids: [I.before, I.after],
  started_at: "2026-10-06T08:10:00Z",
  completed_at: "2026-10-06T09:00:00Z",
  idempotency_key: "cleaning-result-1",
});
