/**
 * Provider mock: cùng contract với real provider (spec v0.3 §9), dữ liệu trong memory, chỉ dùng cho
 * test và chạy local. Không bao giờ dùng cho production.
 *
 * - Dữ liệu tách theo (tenant, property): ID ở scope khác trả NOT_FOUND, không lộ sự tồn tại.
 * - READ đủ 16 tool, sort/pagination/cursor theo §7.
 * - WRITE: domain owner cắm handler qua `writeHandlers` (P3 incident, P4 dispatch/emergency, dùng
 *   hàm service của domain để có cùng semantics). Chưa cắm thì từ chối trước khi đổi state.
 * - Fault injection là cấu hình constructor, không phải field trong arguments.
 */
import { existsSync, readFileSync } from "node:fs";
import { camerasAtLocation, searchCameras, sortIncidentCameras } from "../cameras/service";
import type { CameraSummary, IncidentCamera, SearchCamerasInput } from "../cameras/types";
import type { ReadContext } from "../common/context";
import { type ErrorCode, ToolFailure, toolError, toToolError } from "../common/errors";
import { availableGuards, compareIds } from "../guards/service";
import type { GuardSummary, Location } from "../guards/types";
import {
  createCursorCodec,
  type CursorCodec,
  type PageRequest,
  paginate,
  type ProviderCallOptions,
  type ReadResult,
  type ReadToolName,
  type SecurityProvider,
  type ToolData,
  type ToolInput,
  type ToolName,
  type VerifiedWrite,
  type WriteResult,
  type WriteToolName,
} from "./provider";

/** Bản ghi của domain chưa có type trên nhánh này: chỉ khai báo field mock cần để lọc/sắp. */
type Row = Record<string, unknown>;
type IncidentRow = Row & { incident_id: string; created_at: string; location: Location; severity: string; status: string };
type DispatchRow = Row & { dispatch_id: string; incident_id: string; guard_id: string; status: string; created_at: string };
type EscalationRow = Row & { escalation_id: string; incident_id: string; created_at: string };
type ProtocolRow = Row & { protocol_id: string; version: number; incident_type: string; severity: string };
type ContactRow = Row & { contact_id: string; priority: number; supported_severities: string[] };
type EvidenceRow = Row & { evidence_id: string; incident_id: string; created_at: string };
type EventRow = Row & { event_id: string; incident_id: string; created_at: string };

export type MockScopeData = {
  tenant_id: string;
  property_id: string;
  locations: Location[];
  guards: GuardSummary[];
  cameras: CameraSummary[];
  incident_cameras: IncidentCamera[];
  incidents: IncidentRow[];
  dispatches: DispatchRow[];
  escalations: EscalationRow[];
  protocols: ProtocolRow[];
  contacts: ContactRow[];
  evidence: EvidenceRow[];
  events: EventRow[];
};

export type MockFault = "timeout" | "provider_error" | "invalid_response";

export type MockWriteHandler = (args: {
  scope: MockScopeData;
  input: Record<string, unknown>;
  invocation: VerifiedWrite;
  now: Date;
}) => WriteResult<unknown> | Promise<WriteResult<unknown>>;

export type MockProviderOptions = {
  scopes: MockScopeData[];
  /** Đồng hồ giả cho cursor TTL và handler WRITE. */
  now?: () => Date;
  cursorSecret?: string;
  faults?: Partial<Record<ToolName, MockFault>>;
  writeHandlers?: Partial<Record<WriteToolName, MockWriteHandler>>;
};

const OPEN_DISPATCH = new Set(["PENDING", "EN_ROUTE", "ON_SITE"]);
const DISPATCH_SUMMARY_KEYS = ["dispatch_id", "incident_id", "guard_id", "status", "version", "created_at", "updated_at"];

export class MockSecurityProvider implements SecurityProvider {
  readonly name = "mock";
  private readonly scopes = new Map<string, MockScopeData>();
  private readonly cursors: CursorCodec;
  private readonly now: () => Date;
  /** Tăng mỗi lần dữ liệu đổi; cursor cũ hết hiệu lực khi snapshot đổi. */
  private revision = 0;

  constructor(private readonly options: MockProviderOptions) {
    this.now = options.now ?? (() => new Date());
    this.cursors = createCursorCodec({ secret: options.cursorSecret ?? crypto.randomUUID(), now: this.now });
    for (const scope of options.scopes) this.scopes.set(scopeKey(scope), structuredClone(scope));
  }

  /** Thay dữ liệu một scope trong test; cursor phát trước đó hết hiệu lực. */
  replaceScope(scope: MockScopeData): void {
    this.scopes.set(scopeKey(scope), structuredClone(scope));
    this.revision += 1;
  }

  async read<T extends ReadToolName>(
    tool: T,
    input: ToolInput<T>,
    context: ReadContext,
    _options: ProviderCallOptions,
  ): Promise<ReadResult<ToolData<T>>> {
    const fault = this.options.faults?.[tool];
    if (fault === "timeout") return { ok: false, error: toolError("PROVIDER_TIMEOUT", "Mock: hết thời gian.", { mode: "READ" }) };
    if (fault === "provider_error") return { ok: false, error: toolError("PROVIDER_ERROR", "Mock: lỗi provider.", { mode: "READ" }) };
    try {
      const data = this.query(tool, input as Row, context);
      const out = structuredClone(data) as Row;
      if (fault === "invalid_response") out.stream_url = "rtsp://mock.invalid/live";
      return { ok: true, data: out as ToolData<T> };
    } catch (error) {
      return { ok: false, error: toToolError(error, "READ") };
    }
  }

  async write<T extends WriteToolName>(
    tool: T,
    input: ToolInput<T>,
    invocation: VerifiedWrite,
    _options: ProviderCallOptions,
  ): Promise<WriteResult<ToolData<T>>> {
    const handler = this.options.writeHandlers?.[tool];
    if (!handler) {
      return { ok: false, error: toolError("AUTH_ERROR", `Mock chưa có handler WRITE cho ${tool}.`, { mode: "WRITE" }) };
    }
    const scope = this.scopeOf(invocation.context);
    try {
      const result = await handler({ scope, input: input as Row, invocation, now: this.now() });
      if (result.ok) this.revision += 1;
      return result as WriteResult<ToolData<T>>;
    } catch (error) {
      return { ok: false, error: toToolError(error, "WRITE") };
    }
  }

  private query(tool: ReadToolName, input: Row, context: ReadContext): unknown {
    const s = this.scopeOf(context);
    const page = <T>(items: readonly T[], key: string) => {
      const { items: slice, next_cursor } = paginate(items, input as PageRequest & Row, this.binding(tool, context), this.cursors);
      return { [key]: slice, next_cursor };
    };
    const id = (field: string) => input[field] as string;

    switch (tool) {
      case "get_incident":
        return found(s.incidents.find((i) => i.incident_id === id("incident_id")));
      case "search_incidents": {
        const from = input.from as string | undefined;
        const to = input.to as string | undefined;
        if (from !== undefined && to !== undefined && !(from < to)) throw invalid("from phải nhỏ hơn to.");
        const items = s.incidents.filter(
          (i) =>
            (input.location_id === undefined || i.location.location_id === input.location_id) &&
            (input.severity === undefined || i.severity === input.severity) &&
            (input.status === undefined || i.status === input.status) &&
            (from === undefined || i.created_at >= from) &&
            (to === undefined || i.created_at < to),
        );
        return page(byCreated(items, "incident_id"), "incidents");
      }
      case "get_available_guards": {
        requireLocation(s, id("location_id"));
        const busy = new Set(s.dispatches.filter((d) => OPEN_DISPATCH.has(d.status)).map((d) => d.guard_id));
        return page(availableGuards(s.guards, busy), "guards");
      }
      case "get_guard_status":
        return found(s.guards.find((g) => g.guard_id === id("guard_id")));
      case "get_dispatch":
        return found(s.dispatches.find((d) => d.dispatch_id === id("dispatch_id")));
      case "get_emergency_protocol": {
        const matches = s.protocols.filter((p) => p.incident_type === input.incident_type && p.severity === input.severity);
        return found(matches.sort((a, b) => b.version - a.version)[0]);
      }
      case "get_escalation_contacts": {
        const items = s.contacts
          .filter((c) => c.supported_severities.includes(input.severity as string))
          .sort((a, b) => a.priority - b.priority || compareIds(a.contact_id, b.contact_id));
        return page(items, "contacts");
      }
      case "get_emergency_escalation":
        return found(s.escalations.find((e) => e.escalation_id === id("escalation_id")));
      case "get_incident_escalations":
        requireIncident(s, id("incident_id"));
        return page(byCreated(s.escalations.filter((e) => e.incident_id === id("incident_id")), "escalation_id"), "escalations");
      case "get_camera_metadata":
        return found(s.cameras.find((c) => c.camera_id === id("camera_id")));
      case "search_cameras": {
        const { limit: _limit, cursor: _cursor, ...filters } = input as SearchCamerasInput;
        return page(searchCameras(s.cameras, filters), "cameras");
      }
      case "get_cameras_by_location":
        requireLocation(s, id("location_id"));
        return page(camerasAtLocation(s.cameras, id("location_id")), "cameras");
      case "get_incident_cameras":
        requireIncident(s, id("incident_id"));
        return page(sortIncidentCameras(s.incident_cameras.filter((c) => c.incident_id === id("incident_id"))), "cameras");
      case "get_incident_evidence":
        requireIncident(s, id("incident_id"));
        return page(byCreated(s.evidence.filter((e) => e.incident_id === id("incident_id")), "evidence_id"), "evidence");
      case "get_dispatch_history": {
        requireIncident(s, id("incident_id"));
        const items = byCreated(s.dispatches.filter((d) => d.incident_id === id("incident_id")), "dispatch_id");
        return page(items.map((d) => Object.fromEntries(DISPATCH_SUMMARY_KEYS.map((k) => [k, d[k]]))), "dispatches");
      }
      case "get_security_event_timeline":
        requireIncident(s, id("incident_id"));
        return page(byCreated(s.events.filter((e) => e.incident_id === id("incident_id")), "event_id"), "events");
    }
  }

  private scopeOf(context: { tenant_id: string; property_id: string }): MockScopeData {
    return this.scopes.get(scopeKey(context)) ?? emptyScope(context.tenant_id, context.property_id);
  }

  private binding(tool: ReadToolName, context: ReadContext) {
    return {
      tenant_id: context.tenant_id,
      property_id: context.property_id,
      principal_id: context.principal_id,
      tool,
      snapshot: String(this.revision),
    };
  }
}

// ---------------------------------------------------------------------------------------------
// Fixture
// ---------------------------------------------------------------------------------------------

/**
 * Dữ liệu mặc định từ các file `*.mock.json` cạnh từng domain (xem MOCK_DATA.md của bộ mock v0.3).
 * File của domain chưa có thì để mảng rỗng; P3/P4 thêm file là provider tự nạp.
 */
export function loadFixtureScope(tenant_id = "tenant_demo", property_id = "property_demo"): MockScopeData {
  const load = <T>(path: string): T[] => {
    const url = new URL(`../${path}`, import.meta.url);
    return existsSync(url) ? (JSON.parse(readFileSync(url, "utf8")) as T[]) : [];
  };
  return {
    tenant_id,
    property_id,
    locations: load("mock-locations.json"),
    guards: load("guards/guards.mock.json"),
    cameras: load("cameras/cameras.mock.json"),
    incident_cameras: load("cameras/incident-cameras.mock.json"),
    incidents: load("incidents/incidents.mock.json"),
    dispatches: load("dispatch/dispatches.mock.json"),
    escalations: load("emergency/escalations.mock.json"),
    protocols: load("emergency/protocols.mock.json"),
    contacts: load("emergency/contacts.mock.json"),
    evidence: load("audits/evidence.mock.json"),
    events: load("audits/events.mock.json"),
  };
}

export function emptyScope(tenant_id: string, property_id: string): MockScopeData {
  return {
    tenant_id,
    property_id,
    locations: [],
    guards: [],
    cameras: [],
    incident_cameras: [],
    incidents: [],
    dispatches: [],
    escalations: [],
    protocols: [],
    contacts: [],
    evidence: [],
    events: [],
  };
}

const scopeKey = (scope: { tenant_id: string; property_id: string }) => `${scope.tenant_id}\u0000${scope.property_id}`;

/** Sort `(created_at, id)` tăng dần (§7). */
function byCreated<T extends Row & { created_at: string }>(items: readonly T[], idField: string): T[] {
  return [...items].sort((a, b) => compareIds(a.created_at, b.created_at) || compareIds(String(a[idField]), String(b[idField])));
}

function found<T>(item: T | undefined): T {
  if (item === undefined) throw failure("NOT_FOUND", "Không tìm thấy dữ liệu trong property.");
  return item;
}

/** Parent không tồn tại → NOT_FOUND, không giả danh sách rỗng (§7). */
function requireIncident(scope: MockScopeData, incidentId: string): void {
  found(scope.incidents.find((i) => i.incident_id === incidentId));
}

function requireLocation(scope: MockScopeData, locationId: string): void {
  found(scope.locations.find((l) => l.location_id === locationId));
}

const invalid = (message: string) => failure("VALIDATION_ERROR", message);
const failure = (code: ErrorCode, message: string) => new ToolFailure(toolError(code, message, { mode: "READ" }));
