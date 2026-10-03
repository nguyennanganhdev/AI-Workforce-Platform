import { and, desc, eq, or, sql, type SQL } from "drizzle-orm";
import type { VinhomesTicketSummary } from "../../../shared/vinhomes-ticket";
import type { Database } from "../db/client";
import { withDatabaseScope } from "../db/deployment-scope";
import {
  accessScopes,
  scopedUserRoles,
  tenantMemberships,
  tickets,
} from "../db/schema";

export type TicketReader = {
  listForManagement: (
    userId: string,
    isPlatformAdmin: boolean,
  ) => Promise<VinhomesTicketSummary[]>;
};

export function createTicketReader(
  database: Database,
  tenantId: string,
): TicketReader {
  return {
    async listForManagement(userId, isPlatformAdmin) {
      return withDatabaseScope(database, { tenantId, userId }, async (tx) => {
        let visibility: SQL | undefined;
        if (!isPlatformAdmin) {
          const grants = await tx
            .select({
              kind: accessScopes.kind,
              managementUnitId: accessScopes.managementUnitId,
              siteId: accessScopes.siteId,
              zoneId: accessScopes.zoneId,
              buildingId: accessScopes.buildingId,
            })
            .from(scopedUserRoles)
            .innerJoin(
              tenantMemberships,
              eq(tenantMemberships.id, scopedUserRoles.membershipId),
            )
            .innerJoin(
              accessScopes,
              eq(accessScopes.id, scopedUserRoles.scopeId),
            )
            .where(
              and(
                eq(tenantMemberships.userId, userId),
                eq(tenantMemberships.status, "active"),
                eq(scopedUserRoles.roleCode, "management"),
                sql`${scopedUserRoles.validFrom} <= now() and (${scopedUserRoles.validTo} is null or ${scopedUserRoles.validTo} > now())`,
                eq(scopedUserRoles.tenantId, tenantId),
              ),
            );

          const scopes: SQL[] = [];
          for (const grant of grants) {
            if (grant.kind === "tenant") {
              scopes.push(eq(tickets.tenantId, tenantId));
            } else if (grant.kind === "management" && grant.managementUnitId) {
              scopes.push(eq(tickets.managementUnitId, grant.managementUnitId));
            } else if (grant.kind === "site" && grant.siteId) {
              scopes.push(eq(tickets.siteId, grant.siteId));
            } else if (grant.kind === "zone" && grant.zoneId) {
              scopes.push(eq(tickets.zoneId, grant.zoneId));
            } else if (grant.kind === "building" && grant.buildingId) {
              scopes.push(eq(tickets.buildingId, grant.buildingId));
            }
          }
          if (scopes.length === 0) return [];
          visibility = or(...scopes);
        }

        const rows = await tx
          .select({
            id: tickets.id,
            code: tickets.code,
            title: tickets.title,
            status: tickets.status,
            priority: tickets.priority,
            severity: tickets.severity,
            triageStatus: tickets.triageStatus,
            createdAt: tickets.createdAt,
          })
          .from(tickets)
          .where(and(eq(tickets.tenantId, tenantId), visibility))
          .orderBy(desc(tickets.createdAt), desc(tickets.id))
          .limit(50);
        return rows.map((row) => ({
          ...row,
          createdAt: row.createdAt.toISOString(),
        }));
      });
    },
  };
}
