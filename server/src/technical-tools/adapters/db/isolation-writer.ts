import { and, eq, inArray, notInArray } from "drizzle-orm";
import {
  accessScopes,
  buildings,
  interruptionScopes,
  serviceInterruptions,
  workApprovals,
} from "../../../db/schema";
import type { IsolationWriter, ScopeReadPort } from "../../ports/request-ports";
import { asTenantSession, type TenantSessionSource } from "./tenant-session";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Reads `buildings` and `access_scopes`, one read-only transaction per call with the tenant set. */
export function createDbScopeReadPort(
  source: TenantSessionSource,
): ScopeReadPort {
  const session = asTenantSession(source);
  return {
    placement: ({ tenantId, buildingId }) =>
      session.read(tenantId, async (tx) => {
        const [building] = await tx
          .select({
            buildingId: buildings.id,
            zoneId: buildings.zoneId,
            siteId: buildings.siteId,
          })
          .from(buildings)
          .where(
            and(eq(buildings.tenantId, tenantId), eq(buildings.id, buildingId)),
          )
          .limit(1);
        return building ?? null;
      }),

    findScopes: ({ tenantId, ids }) => {
      const candidates = [...new Set(ids)].filter((id) => UUID.test(id));
      if (candidates.length === 0) return Promise.resolve([]);
      return session.read(tenantId, (tx) =>
        tx
          .select({
            id: accessScopes.id,
            kind: accessScopes.kind,
            buildingId: accessScopes.buildingId,
            zoneId: accessScopes.zoneId,
            siteId: accessScopes.siteId,
          })
          .from(accessScopes)
          .where(
            and(
              eq(accessScopes.tenantId, tenantId),
              inArray(accessScopes.id, candidates),
            ),
          ),
      );
    },
  };
}

/**
 * Writes a water isolation request into the tables the deployment already has for one
 * (tools.md §2): an approval of kind `management_water_shutdown`, `pending`, and the interruption
 * it would authorise, `proposed`, with its scopes.
 *
 * One transaction, so a request is never left half written: an approval with no interruption is a
 * request nobody can see the reach of, and an interruption with no approval is one nothing gates.
 * The ids are chosen by the caller, so nothing needs to be read back and the role it runs as needs
 * to insert into these tables, not to update them.
 *
 * It never writes any other status. What would change one, approving, notifying, starting, is not
 * in this module and not in the grant the tools run under.
 */
export function createDbIsolationWriter(
  source: TenantSessionSource,
): IsolationWriter {
  const session = asTenantSession(source);
  return {
    findOpen: ({ tenantId, workOrderId, utility }) =>
      session.read(tenantId, async (tx) => {
        const rows = await tx
          .select({
            requestId: serviceInterruptions.approvalId,
            interruptionId: serviceInterruptions.id,
            status: serviceInterruptions.status,
            plannedStart: serviceInterruptions.plannedStart,
            plannedEnd: serviceInterruptions.plannedEnd,
          })
          .from(serviceInterruptions)
          .where(
            and(
              eq(serviceInterruptions.tenantId, tenantId),
              eq(serviceInterruptions.workOrderId, workOrderId),
              eq(serviceInterruptions.utility, utility),
              notInArray(serviceInterruptions.status, [
                "cancelled",
                "restored",
              ]),
            ),
          );
        return rows;
      }),

    createWaterIsolation: (isolation) =>
      session.write(isolation.tenantId, async (tx) => {
        await tx.insert(workApprovals).values({
          id: isolation.approvalId,
          tenantId: isolation.tenantId,
          workOrderId: isolation.workOrderId,
          kind: "management_water_shutdown",
          requiredScopeId: isolation.requiredScopeId,
          requestDetail: isolation.requestDetail,
          status: "pending",
          requestHash: isolation.requestHash,
        });
        await tx.insert(serviceInterruptions).values({
          id: isolation.interruptionId,
          tenantId: isolation.tenantId,
          workOrderId: isolation.workOrderId,
          approvalId: isolation.approvalId,
          utility: "water",
          reason: isolation.reason,
          plannedStart: isolation.plannedStart,
          plannedEnd: isolation.plannedEnd,
          status: "proposed",
        });
        await tx.insert(interruptionScopes).values(
          isolation.scopeIds.map((scopeId) => ({
            tenantId: isolation.tenantId,
            interruptionId: isolation.interruptionId,
            scopeId,
          })),
        );
      }),
  };
}
