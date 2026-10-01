import { and, eq, inArray, sql } from "drizzle-orm";
import {
  evidenceItems,
  files,
  staffProfiles,
  tickets,
  workAssignments,
  workOrders,
} from "../../../db/schema";
import type { EvidenceLookup } from "../../domain/work-order";
import type { WorkOrderReadPort } from "../../ports/work-order-read";
import type { TechnicalToolsDatabase } from "./interruption-read";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Reads work orders, their assignments and their evidence from the tables that hold them.
 *
 * The write tools check against these before they record anything, as tools.md §2 asks: that the
 * work order is in the building, that the technician is really assigned to it, and that a photo
 * offered as evidence is really evidence of this ticket. Every call is one read-only transaction
 * with `app.tenant_id` set, like the other database adapters, so row-level security agrees with the
 * query rather than relying on it.
 *
 * It reads and never writes. Recording measurements and results is a different store's job, and
 * changing a work order's state is not the technical tools' job at all.
 */
export function createDbWorkOrderReadPort(
  database: TechnicalToolsDatabase,
): WorkOrderReadPort {
  const inTenant = <T>(
    tenantId: string,
    work: (
      tx: Parameters<Parameters<typeof database.transaction>[0]>[0],
    ) => Promise<T>,
  ) =>
    database.transaction(
      async (tx) => {
        await tx.execute(
          sql`select set_config('app.tenant_id', ${tenantId}, true)`,
        );
        return work(tx);
      },
      { accessMode: "read only" },
    );

  const port: WorkOrderReadPort = {
    getWorkOrder: ({ tenantId, buildingId, workOrderId }) =>
      inTenant(tenantId, async (tx) => {
        // The building belongs to the ticket, so a work order is placed through the ticket it serves.
        const [workOrder] = await tx
          .select({
            workOrderId: workOrders.id,
            ticketId: workOrders.ticketId,
            status: workOrders.status,
            buildingId: tickets.buildingId,
          })
          .from(workOrders)
          .innerJoin(
            tickets,
            and(
              eq(tickets.tenantId, workOrders.tenantId),
              eq(tickets.id, workOrders.ticketId),
            ),
          )
          .where(
            and(
              eq(workOrders.tenantId, tenantId),
              eq(workOrders.id, workOrderId),
              eq(tickets.buildingId, buildingId),
            ),
          )
          .limit(1);
        if (!workOrder?.buildingId) return null;

        const assignments = await tx
          .select({
            assignmentId: workAssignments.id,
            status: workAssignments.status,
            staffUserId: staffProfiles.userId,
            acceptedAt: workAssignments.acceptedAt,
          })
          .from(workAssignments)
          .innerJoin(
            staffProfiles,
            and(
              eq(staffProfiles.tenantId, workAssignments.tenantId),
              eq(staffProfiles.id, workAssignments.staffId),
            ),
          )
          .where(
            and(
              eq(workAssignments.tenantId, tenantId),
              eq(workAssignments.workOrderId, workOrderId),
            ),
          );

        return { ...workOrder, buildingId: workOrder.buildingId, assignments };
      }),

    getTicket: ({ tenantId, buildingId, ticketId }) =>
      inTenant(tenantId, async (tx) => {
        const [ticket] = await tx
          .select({
            ticketId: tickets.id,
            buildingId: tickets.buildingId,
            unitId: tickets.unitId,
            isEmergency: tickets.isEmergency,
            priority: tickets.priority,
          })
          .from(tickets)
          .where(
            and(
              eq(tickets.tenantId, tenantId),
              eq(tickets.id, ticketId),
              eq(tickets.buildingId, buildingId),
            ),
          )
          .limit(1);
        return ticket?.buildingId
          ? { ...ticket, buildingId: ticket.buildingId }
          : null;
      }),

    listWorkOrders: async ({ tenantId, buildingId, ticketId }) => {
      const ids = await inTenant(tenantId, (tx) =>
        tx
          .select({ id: workOrders.id })
          .from(workOrders)
          .where(
            and(
              eq(workOrders.tenantId, tenantId),
              eq(workOrders.ticketId, ticketId),
            ),
          ),
      );
      const found = await Promise.all(
        ids.map(({ id }) =>
          port.getWorkOrder({ tenantId, buildingId, workOrderId: id }),
        ),
      );
      return found.filter((workOrder) => workOrder !== null);
    },

    findEvidence: ({ tenantId, ids }) => {
      // An id that is not a UUID cannot name a row, and asking the database would be a type error.
      const candidates = [...new Set(ids)].filter((id) => UUID.test(id));
      if (candidates.length === 0) return Promise.resolve([]);

      return inTenant(tenantId, async (tx) => {
        const evidence = await tx
          .select({
            id: evidenceItems.id,
            ticketId: evidenceItems.ticketId,
            workOrderId: evidenceItems.workOrderId,
            assignmentId: evidenceItems.assignmentId,
            purpose: evidenceItems.purpose,
            status: evidenceItems.status,
            fileStatus: files.status,
          })
          .from(evidenceItems)
          .innerJoin(
            files,
            and(
              eq(files.tenantId, evidenceItems.tenantId),
              eq(files.id, evidenceItems.fileId),
            ),
          )
          .where(
            and(
              eq(evidenceItems.tenantId, tenantId),
              inArray(evidenceItems.id, candidates),
            ),
          );

        const found = new Set(evidence.map((row) => row.id));
        const rest = candidates.filter((id) => !found.has(id));
        const uploads =
          rest.length === 0
            ? []
            : await tx
                .select({
                  id: files.id,
                  ticketId: files.ticketId,
                  fileStatus: files.status,
                })
                .from(files)
                .where(
                  and(
                    eq(files.tenantId, tenantId),
                    eq(files.scopeKind, "ticket"),
                    inArray(files.id, rest),
                  ),
                );

        return [
          ...evidence.map(
            (row): EvidenceLookup => ({ kind: "evidence", ...row }),
          ),
          ...uploads.map((row): EvidenceLookup => ({ kind: "file", ...row })),
        ];
      });
    },
  };
  return port;
}
