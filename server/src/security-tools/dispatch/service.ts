/**
 * Quy tắc nghiệp vụ Dispatch theo spec v0.3 §6.1.
 *
 * Hàm thuần: nhận trạng thái đã đọc, trả quyết định. Core API là nơi quyết định cuối trong
 * transaction; mock provider dùng các hàm này để có cùng semantics.
 */
import type { ErrorCode } from "../common/errors"; // P1
import type { GuardSummary } from "../guards/types"; // P2
import type { Incident } from "../incidents/types"; // P3
import type { Dispatch, DispatchFailureCode, DispatchStatus, DispatchSummary } from "./types";

export type Rejection = { code: ErrorCode; reason: string } | null;

export const DISPATCH_TRANSITIONS: Readonly<Record<DispatchStatus, readonly DispatchStatus[]>> = {
  PENDING: ["EN_ROUTE", "CANCELLED", "FAILED"],
  EN_ROUTE: ["ON_SITE", "CANCELLED", "FAILED"],
  ON_SITE: ["COMPLETED", "CANCELLED", "FAILED"],
  COMPLETED: [],
  CANCELLED: [],
  FAILED: [],
};

/** Dispatch mở: đang giữ reservation của guard. */
export const OPEN_DISPATCH_STATUSES: readonly DispatchStatus[] = ["PENDING", "EN_ROUTE", "ON_SITE"];

const DISPATCHABLE_INCIDENT_STATUSES: readonly string[] = ["OPEN", "IN_PROGRESS"];

export const isOpenDispatch = (d: Pick<Dispatch, "status">) => OPEN_DISPATCH_STATUSES.includes(d.status);
export const isTerminalDispatch = (s: DispatchStatus) => DISPATCH_TRANSITIONS[s].length === 0;
export const canTransitionDispatch = (from: DispatchStatus, to: DispatchStatus) =>
  DISPATCH_TRANSITIONS[from].includes(to);

export function toDispatchSummary(d: Dispatch): DispatchSummary {
  return {
    dispatch_id: d.dispatch_id,
    incident_id: d.incident_id,
    guard_id: d.guard_id,
    status: d.status,
    version: d.version,
    created_at: d.created_at,
    updated_at: d.updated_at,
  };
}

/**
 * Precondition cho command `dispatch_guard` MỚI (replay cùng key không đi qua đây — §5).
 * `guard`: null khi guard ngoài scope. `guardOpenDispatch`: dispatch mở của guard trên toàn hệ thống.
 */
export function checkDispatchGuard(args: {
  incident: Incident;
  incidentVersion: number;
  guard: GuardSummary | null;
  guardOpenDispatch: Pick<Dispatch, "dispatch_id"> | null;
}): Rejection {
  const { incident, guard } = args;
  if (!DISPATCHABLE_INCIDENT_STATUSES.includes(incident.status)) {
    // §5.1: state không hợp lệ → INVALID_STATE_TRANSITION (NEVER/FAILED).
    return { code: "INVALID_STATE_TRANSITION", reason: `Incident đang ${incident.status}, không điều động được` };
  }
  // §6.1: kiểm version trước reservation.
  if (incident.version !== args.incidentVersion) {
    return { code: "CONFLICT", reason: `incident_version ${args.incidentVersion} đã cũ (hiện ${incident.version})` };
  }
  if (guard === null) return { code: "NOT_FOUND", reason: "Không tìm thấy guard trong property" };
  if (guard.status !== "AVAILABLE" || args.guardOpenDispatch !== null) {
    return { code: "GUARD_NOT_AVAILABLE", reason: `Guard ${guard.guard_id} không sẵn sàng` };
  }
  return null;
}

export function createDispatch(args: {
  dispatchId: string;
  incident: Incident;
  guardId: string;
  instruction: string | undefined;
  now: string;
}): Dispatch {
  return {
    dispatch_id: args.dispatchId,
    incident_id: args.incident.incident_id,
    guard_id: args.guardId,
    location: args.incident.location,
    instruction: args.instruction ?? null,
    status: "PENDING",
    version: 1,
    cancel_reason: null,
    cancelled_at: null,
    failure_code: null,
    created_at: args.now,
    updated_at: args.now,
  };
}

/** §6.1: với command mới, kiểm terminal state TRƯỚC expected_version. */
export function checkCancelDispatch(dispatch: Dispatch, expectedVersion: number): Rejection {
  if (isTerminalDispatch(dispatch.status)) {
    return { code: "INVALID_STATE_TRANSITION", reason: `Dispatch đã ${dispatch.status}, không hủy được` };
  }
  if (dispatch.version !== expectedVersion) {
    return { code: "CONFLICT", reason: `expected_version ${expectedVersion} đã cũ (hiện ${dispatch.version})` };
  }
  return null;
}

export function applyCancel(dispatch: Dispatch, reason: string, now: string): Dispatch {
  return {
    ...dispatch,
    status: "CANCELLED",
    version: dispatch.version + 1,
    cancel_reason: reason,
    cancelled_at: now,
    updated_at: now,
  };
}

/**
 * Callback đã xác thực từ guard app/operator/provider (Core `recordDispatchStatus`), không phải
 * WRITE của agent. Callback muộn sau terminal bị từ chối, không hồi sinh dispatch.
 */
export function applyDispatchStatus(
  dispatch: Dispatch,
  change: { expectedVersion: number; to: DispatchStatus; now: string; failureCode?: DispatchFailureCode },
): { ok: true; dispatch: Dispatch } | { ok: false; rejection: NonNullable<Rejection> } {
  if (!canTransitionDispatch(dispatch.status, change.to)) {
    return { ok: false, rejection: { code: "INVALID_STATE_TRANSITION", reason: `${dispatch.status} → ${change.to} không hợp lệ` } };
  }
  if (change.to === "CANCELLED") {
    return { ok: false, rejection: { code: "INVALID_STATE_TRANSITION", reason: "Hủy phải đi qua cancel_dispatch" } };
  }
  if (dispatch.version !== change.expectedVersion) {
    return { ok: false, rejection: { code: "CONFLICT", reason: "expected_version đã cũ" } };
  }
  if (change.to === "FAILED" && !change.failureCode) {
    return { ok: false, rejection: { code: "VALIDATION_ERROR", reason: "FAILED cần failure_code" } };
  }
  return {
    ok: true,
    dispatch: {
      ...dispatch,
      status: change.to,
      version: dispatch.version + 1,
      failure_code: change.to === "FAILED" ? (change.failureCode ?? null) : null,
      updated_at: change.now,
    },
  };
}
