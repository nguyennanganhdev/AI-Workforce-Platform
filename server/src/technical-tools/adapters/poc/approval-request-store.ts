import type { ApprovalRequest } from "../../domain/approval-request";
import type { ApprovalRequestStore } from "../../ports/request-ports";

/**
 * The shared approval adapter, in memory, until the database has request kinds for isolating
 * power and restricting an area.
 *
 * It creates and lists. There is deliberately no way here to approve, reject or act on a request:
 * the approval workflow belongs to a person in another service, and a store the agent's tools could
 * approve through would make every request a self-approval.
 *
 * Lost on restart. `all()` is for tests.
 */
export function createInMemoryApprovalRequestStore(): ApprovalRequestStore & {
  all(): readonly ApprovalRequest[];
} {
  const requests: ApprovalRequest[] = [];
  return {
    create: async (request) => {
      requests.push(request);
    },
    listOpen: async ({ tenantId, kind, incidentId }) =>
      requests.filter(
        (request) =>
          request.tenantId === tenantId &&
          request.kind === kind &&
          request.incidentId === incidentId &&
          request.status === "pending",
      ),
    all: () => [...requests],
  };
}
