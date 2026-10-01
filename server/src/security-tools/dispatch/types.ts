/**
 * Kiểu Dispatch — P4 sở hữu Dispatch và DispatchSummary (spec v0.3 §2.2, §10).
 * Nguồn cấu trúc là schema/common.schema.json (#/$defs/Dispatch, DispatchSummary, *Input).
 */
import type { Location } from "../guards/types"; // P2

export type DispatchStatus = "PENDING" | "EN_ROUTE" | "ON_SITE" | "COMPLETED" | "CANCELLED" | "FAILED";

export type DispatchFailureCode = "GUARD_UNAVAILABLE" | "PROVIDER_REJECTED" | "DELIVERY_FAILED";

export type Dispatch = {
  dispatch_id: string;
  incident_id: string;
  guard_id: string;
  /** Snapshot location của incident lúc tạo dispatch. */
  location: Location;
  instruction: string | null;
  status: DispatchStatus;
  version: number;
  cancel_reason: string | null;
  cancelled_at: string | null;
  failure_code: DispatchFailureCode | null;
  created_at: string;
  updated_at: string;
};

/** Projection đúng các field cùng tên của Dispatch; P3 import cho get_dispatch_history. */
export type DispatchSummary = Pick<
  Dispatch,
  "dispatch_id" | "incident_id" | "guard_id" | "status" | "version" | "created_at" | "updated_at"
>;

export type DispatchGuardInput = {
  incident_id: string;
  incident_version: number;
  guard_id: string;
  instruction?: string;
};

export type GetDispatchInput = { dispatch_id: string };

export type CancelDispatchInput = {
  dispatch_id: string;
  expected_version: number;
  reason: string;
};
