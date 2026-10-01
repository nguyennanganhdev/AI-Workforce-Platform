/**
 * Phần WRITE của provider mock (spec v0.3 §5, §6, §9): handler cắm vào `MockProviderOptions.writeHandlers`,
 * ledger idempotency trong memory và bộ điều khiển fault/barrier cho test. Chỉ dùng cho test và chạy
 * local, không bao giờ cho production.
 *
 *   const control = createWriteControl();
 *   const ledger = new MockOperationLedger();
 *   new MockSecurityProvider({ scopes, now, writeHandlers: createWriteHandlers({ control, ledger }) });
 *   control.setFault("dispatch_guard", "timeout_after_commit");
 *
 * Luật nghiệp vụ lấy từ dispatch/service.ts và emergency/service.ts để mock và Core cùng semantics.
 * Một lần commit ghi cùng lúc: entity, evidence ACTION_RECEIPT, event, related_counts và version của
 * incident, rồi mới lưu kết quả vào ledger. Mock không gửi thông báo và không chạy SLA timer:
 * dispatch/escalation mới dừng ở PENDING như Core (§1).
 *
 * `create_incident` ở đây là bản TẠM để chạy được luồng grant/idempotency; tool này thuộc P3, P3 thay
 * bằng handler thật. `update_incident` chưa có handler.
 */
import { type ErrorCode, type ToolError, toolError } from "../common/errors";
import { decideIdempotency, type IdempotencyDecision, type OperationRecord, resultOf } from "../common/idempotency";
import { timestamp, type WriteEvidence } from "../common/responses";
import { applyCancel, checkCancelDispatch, checkDispatchGuard, createDispatch, isOpenDispatch, type Rejection } from "../dispatch/service";
import type { Dispatch } from "../dispatch/types";
import { applyAcknowledge, applyNotificationResult, checkAcknowledge, checkEscalate, createEscalation } from "../emergency/service";
import type { AckReceipt, EmergencyEscalation, EmergencyProtocol, EscalationContact } from "../emergency/types";
import type { GuardStatus, Location } from "../guards/types";
import type { MockScopeData, MockWriteHandler } from "./mock-provider";
import type { VerifiedWrite, WriteResult, WriteToolName } from "./provider";

// ---------------------------------------------------------------------------------------------
// Fault và barrier (test-only, không phải field trong arguments)
// ---------------------------------------------------------------------------------------------

/** Danh sách fault của spec §9. */
export type MockWriteFault =
  /** dispatch_guard: guard bị request khác lấy mất ngay lúc commit → GUARD_NOT_AVAILABLE. */
  | "guard_unavailable"
  /** escalate_emergency: contact hết khả dụng lúc commit → CONTACT_NOT_AVAILABLE. */
  | "contact_unavailable"
  /** Core xác nhận chắc chắn không commit → PROVIDER_ERROR (NEVER/FAILED). */
  | "provider_error_before_commit"
  /** Mất kết nối trước khi commit → PROVIDER_TIMEOUT (RECONCILE/UNKNOWN), không có side effect. */
  | "timeout_before_commit"
  /** Đã commit nhưng caller không nhận được kết quả → PROVIDER_TIMEOUT; replay cùng key trả kết quả. */
  | "timeout_after_commit"
  /** Đã commit nhưng response hỏng → wrapper trả PROVIDER_INVALID_RESPONSE; replay trả kết quả đúng. */
  | "invalid_response"
  /** Đã commit; worker gửi thất bại ngay sau đó → entity sang FAILED/DELIVERY_FAILED. */
  | "delivery_failed";

export type WriteControl = {
  /** Bật fault cho `times` lần gọi kế tiếp của tool (mặc định 1). */
  setFault(tool: WriteToolName, fault: MockWriteFault, times?: number): void;
  /**
   * Giữ các lần gọi kế tiếp của tool ở trạng thái IN_PROGRESS (sau khi claim key, trước khi commit)
   * cho tới khi gọi hàm trả về. Dùng để dựng hai request đồng thời.
   */
  hold(tool: WriteToolName): () => void;
  /** Bỏ mọi fault và barrier. */
  reset(): void;
  /** Handler dùng: lấy fault đang bật và trừ số lần còn lại. */
  takeFault(tool: WriteToolName): MockWriteFault | null;
  /** Handler dùng: chờ nếu tool đang bị giữ. */
  waitIfHeld(tool: WriteToolName): Promise<void>;
};

export function createWriteControl(): WriteControl {
  const faults = new Map<WriteToolName, { fault: MockWriteFault; times: number }>();
  const holds = new Map<WriteToolName, { promise: Promise<void>; release: () => void }>();
  return {
    setFault(tool, fault, times = 1) {
      if (times > 0) faults.set(tool, { fault, times });
    },
    hold(tool) {
      let release = () => {};
      const promise = new Promise<void>((resolve) => {
        release = resolve;
      });
      holds.set(tool, { promise, release });
      return () => {
        if (holds.get(tool)?.promise === promise) holds.delete(tool);
        release();
      };
    },
    reset() {
      faults.clear();
      for (const hold of holds.values()) hold.release();
      holds.clear();
    },
    takeFault(tool) {
      const entry = faults.get(tool);
      if (!entry) return null;
      entry.times -= 1;
      if (entry.times <= 0) faults.delete(tool);
      return entry.fault;
    },
    async waitIfHeld(tool) {
      await holds.get(tool)?.promise;
    },
  };
}

// ---------------------------------------------------------------------------------------------
// Ledger idempotency
// ---------------------------------------------------------------------------------------------

type Scope = { tenant_id: string; property_id: string };

/**
 * Bản ghi operation trong memory, mô phỏng claim atomic của Core: khóa unique
 * `(tenant_id, property_id, idempotency_key)`, không gồm action/ticket; một proposal chỉ gắn một
 * operation. `begin` chạy đồng bộ nên hai request cùng key không thể cùng được EXECUTE.
 */
export class MockOperationLedger {
  private readonly byKey = new Map<string, OperationRecord>();
  private readonly byProposal = new Map<string, OperationRecord>();

  /** Quyết định theo §5; EXECUTE thì đồng thời claim key ở trạng thái IN_PROGRESS. */
  begin(invocation: VerifiedWrite): IdempotencyDecision {
    const request = {
      idempotency_key: invocation.idempotency_key,
      payload_hash: invocation.claims.payload_hash,
      proposal_id: invocation.claims.proposal_id,
    };
    const keyId = id(invocation.context, request.idempotency_key);
    const proposalId = id(invocation.context, request.proposal_id);
    const decision = decideIdempotency(request, this.byKey.get(keyId) ?? null, this.byProposal.get(proposalId) ?? null);
    if (decision.action === "EXECUTE") {
      const record: OperationRecord = { ...request, status: "IN_PROGRESS", result: null, rejection: null };
      this.byKey.set(keyId, record);
      this.byProposal.set(proposalId, record);
    }
    return decision;
  }

  commit(invocation: VerifiedWrite, data: unknown, evidence: WriteEvidence): void {
    Object.assign(this.record(invocation), { status: "COMMITTED", result: { data: structuredClone(data), evidence } });
  }

  reject(invocation: VerifiedWrite, error: ToolError): void {
    Object.assign(this.record(invocation), { status: "REJECTED", rejection: error });
  }

  markUnknown(invocation: VerifiedWrite): void {
    this.record(invocation).status = "UNKNOWN";
  }

  /** Tương ứng `getOperation` của Core: executor đối soát operation, không expose cho model. */
  get(scope: Scope, idempotencyKey: string): OperationRecord | null {
    const record = this.byKey.get(id(scope, idempotencyKey));
    return record ? structuredClone(record) : null;
  }

  /** Mô phỏng archive sau thời gian giữ kết quả: tombstone key/hash/proposal còn, result mất. */
  archiveResult(scope: Scope, idempotencyKey: string): void {
    const record = this.byKey.get(id(scope, idempotencyKey));
    if (record) Object.assign(record, { result: null, rejection: null });
  }

  private record(invocation: VerifiedWrite): OperationRecord {
    const record = this.byKey.get(id(invocation.context, invocation.idempotency_key));
    if (!record) throw new Error("Operation chưa được claim");
    return record;
  }
}

const id = (scope: Scope, value: string) => `${scope.tenant_id}\u0000${scope.property_id}\u0000${value}`;

// ---------------------------------------------------------------------------------------------
// Handler
// ---------------------------------------------------------------------------------------------

export type WriteHandlersOptions = {
  control?: WriteControl;
  ledger?: MockOperationLedger;
};

/** Field của incident mà WRITE cần. Kiểu Incident thuộc P3; đây là cấu trúc theo common.schema.json. */
type IncidentRecord = {
  incident_id: string;
  ticket_id: string;
  incident_type: string;
  description: string | null;
  status: string;
  severity: string;
  location: Location;
  version: number;
  created_at: string;
  updated_at: string;
  related_counts: { dispatches: number; escalations: number; cameras: number; evidence: number };
};

type Commit = {
  data: unknown;
  incident: IncidentRecord;
  event: { event_type: string; data: Record<string, unknown> };
  summary: string;
  /** Chạy sau khi kết quả đã vào ledger (ví dụ worker gửi thất bại). */
  after?: () => void;
};
type Outcome = Commit | { rejection: NonNullable<Rejection> };

export function createWriteHandlers(options: WriteHandlersOptions = {}): Partial<Record<WriteToolName, MockWriteHandler>> {
  const control = options.control ?? createWriteControl();
  const ledger = options.ledger ?? new MockOperationLedger();
  /** Trạng thái guard trước khi bị reserve, để trả lại đúng khi dispatch kết thúc. */
  const reservedFrom = new Map<string, GuardStatus>();
  let sequence = 0;
  const nextId = (prefix: string) => `${prefix}_mock_${String(++sequence).padStart(4, "0")}`;

  const handler =
    (tool: WriteToolName, body: (ctx: { scope: MockScopeData; input: Record<string, unknown>; invocation: VerifiedWrite; now: string; fault: MockWriteFault | null }) => Outcome): MockWriteHandler =>
    async ({ scope, input, invocation, now: clock }) => {
      const early = resultOf(ledger.begin(invocation));
      if (early) return early;

      const fail = (code: ErrorCode, message: string, outcome?: "NOT_COMMITTED"): WriteResult<unknown> => ({
        ok: false,
        error: toolError(code, message, { mode: "WRITE", outcome }),
      });
      try {
        await control.waitIfHeld(tool);
        const fault = control.takeFault(tool);
        if (fault === "provider_error_before_commit") {
          const result = fail("PROVIDER_ERROR", "Mock: provider lỗi, xác nhận chưa commit.", "NOT_COMMITTED");
          if (!result.ok) ledger.reject(invocation, result.error);
          return result;
        }
        if (fault === "timeout_before_commit") {
          ledger.markUnknown(invocation);
          return fail("PROVIDER_TIMEOUT", "Mock: hết thời gian trước khi biết kết quả.");
        }

        const now = timestamp(clock);
        const outcome = body({ scope, input, invocation, now, fault });
        if ("rejection" in outcome) {
          const result = fail(outcome.rejection.code, outcome.rejection.reason);
          if (!result.ok) ledger.reject(invocation, result.error);
          return result;
        }

        const evidence = record(scope, tool, invocation, outcome, now, nextId);
        const data = structuredClone(outcome.data);
        ledger.commit(invocation, data, evidence);
        outcome.after?.();

        if (fault === "timeout_after_commit") return fail("PROVIDER_TIMEOUT", "Mock: hết thời gian sau khi đã commit.");
        if (fault === "invalid_response") {
          return { ok: true, data: { ...(data as object), mock_invalid_field: true }, evidence, replayed: false };
        }
        return { ok: true, data, evidence, replayed: false };
      } catch (error) {
        // Lỗi lạ giữa chừng: không biết đã đổi state tới đâu, để executor đối soát.
        ledger.markUnknown(invocation);
        throw error;
      }
    };

  const release = (scope: MockScopeData, guardId: string, now: string) => {
    const guard = scope.guards.find((g) => g.guard_id === guardId);
    if (!guard || guard.status !== "ASSIGNED") return;
    // Mock không có roster để hỏi lại như Core; trả về trạng thái trước khi reserve nếu biết.
    guard.status = reservedFrom.get(reservationKey(scope, guardId)) ?? "AVAILABLE";
    guard.updated_at = now;
    reservedFrom.delete(reservationKey(scope, guardId));
  };

  return {
    create_incident: handler("create_incident", ({ scope, input, invocation, now }) => {
      const location = scope.locations.find((l) => l.location_id === input.location_id);
      if (!location) return { rejection: { code: "NOT_FOUND", reason: "Không tìm thấy location trong property" } };
      const incident: IncidentRecord = {
        incident_id: nextId("inc"),
        ticket_id: invocation.context.ticket_id,
        incident_type: input.incident_type as string,
        description: input.description as string,
        status: "OPEN",
        severity: input.severity as string,
        location,
        version: 0,
        created_at: now,
        updated_at: now,
        related_counts: { dispatches: 0, escalations: 0, cameras: 0, evidence: 0 },
      };
      scope.incidents.push(incident);
      return {
        data: incident,
        incident,
        event: { event_type: "INCIDENT_CREATED", data: { status: "OPEN", severity: incident.severity } },
        summary: "Tạo incident",
      };
    }),

    dispatch_guard: handler("dispatch_guard", ({ scope, input, invocation, now, fault }) => {
      const incident = findIncident(scope, input.incident_id);
      if (!incident) return { rejection: { code: "NOT_FOUND", reason: "Không tìm thấy incident trong property" } };
      const mismatch = ticketMismatch(incident, invocation);
      if (mismatch) return { rejection: mismatch };
      const guard = scope.guards.find((g) => g.guard_id === input.guard_id) ?? null;
      const open = dispatches(scope).find((d) => d.guard_id === input.guard_id && isOpenDispatch(d)) ?? null;
      const rejection =
        checkDispatchGuard({ incident: incident as never, incidentVersion: input.incident_version as number, guard, guardOpenDispatch: open }) ??
        (fault === "guard_unavailable" ? { code: "GUARD_NOT_AVAILABLE" as const, reason: `Guard ${String(input.guard_id)} vừa được điều cho request khác` } : null);
      if (rejection || !guard) return { rejection: rejection ?? { code: "NOT_FOUND", reason: "Không tìm thấy guard trong property" } };

      const dispatch = createDispatch({
        dispatchId: nextId("dsp"),
        incident: incident as never,
        guardId: guard.guard_id,
        instruction: input.instruction as string | undefined,
        now,
      });
      // Reserve guard và tạo dispatch trong cùng một bước (§6.1).
      reservedFrom.set(reservationKey(scope, guard.guard_id), guard.status);
      guard.status = "ASSIGNED";
      guard.updated_at = now;
      scope.dispatches.push(dispatch);
      incident.related_counts.dispatches += 1;
      return {
        data: dispatch,
        incident,
        event: { event_type: "DISPATCH_CREATED", data: { dispatch_id: dispatch.dispatch_id, guard_id: dispatch.guard_id, status: "PENDING" } },
        summary: `Điều ${guard.guard_id} tới incident`,
        after:
          fault === "delivery_failed"
            ? () => {
                Object.assign(dispatch, { status: "FAILED", version: dispatch.version + 1, failure_code: "DELIVERY_FAILED", updated_at: now });
                release(scope, guard.guard_id, now);
              }
            : undefined,
      };
    }),

    cancel_dispatch: handler("cancel_dispatch", ({ scope, input, invocation, now }) => {
      const current = dispatches(scope).find((d) => d.dispatch_id === input.dispatch_id);
      const incident = current ? findIncident(scope, current.incident_id) : undefined;
      if (!current || !incident) return { rejection: { code: "NOT_FOUND", reason: "Không tìm thấy dispatch trong property" } };
      const mismatch = ticketMismatch(incident, invocation);
      if (mismatch) return { rejection: mismatch };
      const rejection = checkCancelDispatch(current, input.expected_version as number);
      if (rejection) return { rejection };

      const previous = current.status;
      const cancelled = applyCancel(current, input.reason as string, now);
      Object.assign(current, cancelled);
      release(scope, current.guard_id, now);
      return {
        data: current,
        incident,
        event: {
          event_type: "DISPATCH_STATUS_CHANGED",
          data: { dispatch_id: current.dispatch_id, previous_status: previous, status: "CANCELLED", reason: cancelled.cancel_reason },
        },
        summary: "Hủy lệnh điều động",
      };
    }),

    escalate_emergency: handler("escalate_emergency", ({ scope, input, invocation, now, fault }) => {
      const incident = findIncident(scope, input.incident_id);
      if (!incident) return { rejection: { code: "NOT_FOUND", reason: "Không tìm thấy incident trong property" } };
      const mismatch = ticketMismatch(incident, invocation);
      if (mismatch) return { rejection: mismatch };
      const protocol = (scope.protocols as unknown as EmergencyProtocol[]).find((p) => p.protocol_id === input.protocol_id) ?? null;
      const contact = (scope.contacts as unknown as EscalationContact[]).find((c) => c.contact_id === input.contact_id) ?? null;
      const rejection =
        checkEscalate({
          incident: incident as never,
          incidentVersion: input.incident_version as number,
          protocol,
          protocolVersion: input.protocol_version as number,
          contact,
          existingForIncident: escalations(scope).filter((e) => e.incident_id === incident.incident_id),
        }) ??
        (fault === "contact_unavailable" ? { code: "CONTACT_NOT_AVAILABLE" as const, reason: `Contact ${String(input.contact_id)} vừa hết khả dụng` } : null);
      if (rejection || !protocol || !contact) return { rejection: rejection ?? { code: "NOT_FOUND", reason: "Không có protocol/contact trong property" } };

      const escalation = createEscalation({
        escalationId: nextId("esc"),
        incident: incident as never,
        protocol,
        contactId: contact.contact_id,
        reason: input.reason as string,
        now,
      });
      scope.escalations.push(escalation);
      incident.related_counts.escalations += 1;
      return {
        data: escalation,
        incident,
        event: { event_type: "ESCALATION_CREATED", data: { escalation_id: escalation.escalation_id, contact_id: contact.contact_id, status: "PENDING" } },
        summary: `Báo khẩn tới ${contact.contact_id}`,
        after:
          fault === "delivery_failed"
            ? () => {
                const failed = applyNotificationResult(escalation, {
                  expectedVersion: escalation.version,
                  result: "FAILED",
                  providerReferenceId: nextId("ntf"),
                  failureCode: "DELIVERY_FAILED",
                  now,
                });
                if (failed.ok) Object.assign(escalation, failed.escalation);
              }
            : undefined,
      };
    }),

    acknowledge_emergency: handler("acknowledge_emergency", ({ scope, input, invocation, now }) => {
      const current = escalations(scope).find((e) => e.escalation_id === input.escalation_id);
      const incident = current ? findIncident(scope, current.incident_id) : undefined;
      if (!current || !incident) return { rejection: { code: "NOT_FOUND", reason: "Không tìm thấy escalation trong property" } };
      const mismatch = ticketMismatch(incident, invocation);
      if (mismatch) return { rejection: mismatch };
      // Receipt nằm trong dữ liệu của scope (Core `recordAckReceipt`): receipt của property khác không dùng được.
      const receipt = (scope.ack_receipts as unknown as AckReceipt[]).find((r) => r.ack_receipt_id === input.ack_receipt_id) ?? null;
      const rejection = checkAcknowledge({
        escalation: current,
        expectedVersion: input.expected_version as number,
        receipt,
        grantActor: invocation.claims.actor,
        now,
      });
      if (rejection || !receipt) return { rejection: rejection ?? { code: "ACK_NOT_AUTHORIZED", reason: "Không có receipt" } };

      const previous = current.status;
      Object.assign(current, applyAcknowledge(current, receipt, now));
      return {
        data: current,
        incident,
        event: {
          event_type: "ESCALATION_STATUS_CHANGED",
          data: { escalation_id: current.escalation_id, previous_status: previous, status: "ACKNOWLEDGED", reason: null },
        },
        summary: "Ghi nhận xác nhận của người trực",
      };
    }),
  };
}

/**
 * Phần audit của một commit: evidence ACTION_RECEIPT + event, tăng related_counts.evidence và version
 * của incident đúng một lần cho cả lệnh (§2.2: đổi counts cũng tăng incident.version).
 */
function record(
  scope: MockScopeData,
  tool: WriteToolName,
  invocation: VerifiedWrite,
  commit: Commit,
  now: string,
  nextId: (prefix: string) => string,
): WriteEvidence {
  const actor = invocation.claims.actor;
  const evidence: WriteEvidence = { evidence_id: nextId("ev"), provider: "mock", provider_reference_id: nextId("ref"), committed_at: now };
  scope.evidence.push({
    evidence_id: evidence.evidence_id,
    incident_id: commit.incident.incident_id,
    evidence_type: "ACTION_RECEIPT",
    actor,
    provider: evidence.provider,
    provider_reference_id: evidence.provider_reference_id,
    action: tool,
    idempotency_key: invocation.idempotency_key,
    summary: commit.summary,
    created_at: now,
  });
  scope.events.push({
    event_id: nextId("evt"),
    incident_id: commit.incident.incident_id,
    event_type: commit.event.event_type,
    actor,
    created_at: now,
    evidence_id: evidence.evidence_id,
    data: commit.event.data,
  });
  commit.incident.related_counts.evidence += 1;
  commit.incident.version += 1;
  commit.incident.updated_at = now;
  return evidence;
}

const reservationKey = (scope: MockScopeData, guardId: string) => `${scope.tenant_id}\u0000${scope.property_id}\u0000${guardId}`;
const findIncident = (scope: MockScopeData, incidentId: unknown) =>
  (scope.incidents as unknown as IncidentRecord[]).find((i) => i.incident_id === incidentId);

/** §3.1: WRITE trên incident đã có thì ticket của phiên phải là ticket của incident đó. */
function ticketMismatch(incident: IncidentRecord, invocation: VerifiedWrite): Rejection {
  return incident.ticket_id === invocation.context.ticket_id
    ? null
    : { code: "SCOPE_MISMATCH", reason: "Ticket của phiên không phải ticket của incident" };
}
const dispatches = (scope: MockScopeData) => scope.dispatches as unknown as Dispatch[];
const escalations = (scope: MockScopeData) => scope.escalations as unknown as EmergencyEscalation[];
