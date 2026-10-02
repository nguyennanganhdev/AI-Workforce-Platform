import type {
  ApprovalRequest,
  ApprovalRequestKind,
  BuildingPlacement,
  OpenIsolation,
  ScopeRecord,
  WaterIsolation,
} from "../domain/approval-request";
import type { Utility } from "../domain/interruption";

export type ScopeReadPort = {
  /** The building's zone and site, or `null` when the building is not in this tenant. */
  placement(query: {
    tenantId: string;
    buildingId: string;
  }): Promise<BuildingPlacement | null>;
  /** The scopes among `ids` that exist in this tenant. Unknown ids are simply absent. */
  findScopes(query: {
    tenantId: string;
    ids: readonly string[];
  }): Promise<ScopeRecord[]>;
};

/**
 * Where water isolations are written: `work_approvals`, `service_interruptions` and
 * `interruption_scopes`, in one transaction.
 *
 * It can only create. A request is `pending` and its interruption `proposed` when written, and
 * this port has no way to change either: approving, notifying and starting an interruption belong
 * to the service with the authority to do them.
 */
export type IsolationWriter = {
  /** Water isolations on the work order that are not cancelled or restored. */
  findOpen(query: {
    tenantId: string;
    workOrderId: string;
    utility: Utility;
  }): Promise<OpenIsolation[]>;
  /** All three tables or none of them. */
  createWaterIsolation(isolation: WaterIsolation): Promise<void>;
};

/**
 * The shared approval adapter (tools.md §2): requests the database has no kind for yet.
 *
 * Create and read, nothing else. There is no method to approve, because nothing the agent can
 * reach may approve.
 */
export type ApprovalRequestStore = {
  create(request: ApprovalRequest): Promise<void>;
  /** Pending requests of one kind, on one incident. */
  listOpen(query: {
    tenantId: string;
    kind: ApprovalRequestKind;
    incidentId: string;
  }): Promise<ApprovalRequest[]>;
};
