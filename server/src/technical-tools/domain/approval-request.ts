import type { Utility } from "./interruption";

/**
 * An access scope as the request tools need it: what kind of area it is, and which building, zone
 * or site it names.
 */
export type ScopeRecord = {
  id: string;
  kind: string;
  buildingId: string | null;
  zoneId: string | null;
  siteId: string | null;
};

/** Where a building sits: the zone and site whose scopes also reach it. */
export type BuildingPlacement = {
  buildingId: string;
  zoneId: string | null;
  siteId: string;
};

/**
 * An isolation already on record for a work order, in whatever state it is in. `status` is the
 * interruption's: `proposed` until somebody with authority approves it.
 */
export type OpenIsolation = {
  requestId: string;
  interruptionId: string;
  status: string;
  plannedStart: Date;
  plannedEnd: Date;
};

/** A water isolation to write: one approval, one proposed interruption, its scopes. */
export type WaterIsolation = {
  tenantId: string;
  workOrderId: string;
  approvalId: string;
  interruptionId: string;
  requiredScopeId: string;
  scopeIds: readonly string[];
  reason: string;
  plannedStart: Date;
  plannedEnd: Date;
  requestDetail: Record<string, unknown>;
  requestHash: string;
};

export const APPROVAL_REQUEST_KINDS = [
  "power_isolation",
  "area_restriction",
  "apartment_entry",
  "vendor_dispatch",
] as const;

export type ApprovalRequestKind = (typeof APPROVAL_REQUEST_KINDS)[number];

/**
 * A request held by the shared approval adapter, for what the database has no approval kind for
 * yet: isolating power, restricting an area, entering an apartment, dispatching a vendor.
 *
 * Always created `pending`. Nothing a technical tool can reach decides it; that is a person's
 * action, in a service the tools do not have.
 */
export type ApprovalRequest = {
  requestId: string;
  kind: ApprovalRequestKind;
  tenantId: string;
  buildingId: string;
  incidentId: string;
  workOrderId: string | null;
  status: "pending";
  requiredApproverScope: string;
  detail: Record<string, unknown>;
  requestHash: string;
  requestedBy: string;
  sourceRunId: string;
  createdAt: Date;
  /** For a power isolation: the interruption it proposes, which is `proposed` until approved. */
  interruption?: {
    interruptionId: string;
    utility: Utility;
    status: "proposed";
    scopeIds: readonly string[];
    plannedStart: Date;
    plannedEnd: Date;
  };
};
