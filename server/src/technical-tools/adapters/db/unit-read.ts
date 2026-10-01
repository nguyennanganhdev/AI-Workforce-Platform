import { and, eq, sql } from "drizzle-orm";
import { unitResidents, units } from "../../../db/schema";
import type { UnitReadPort } from "../../ports/entry-vendor-ports";
import type { TechnicalToolsDatabase } from "./interruption-read";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Reads `units` and `unit_residents`, one read-only transaction per call with the tenant set.
 *
 * Who the residents are is read so the request can say who must approve entry, never handed back
 * to the agent: nothing of a resident leaves this port except through that decision.
 */
export function createDbUnitReadPort(
  database: TechnicalToolsDatabase,
): UnitReadPort {
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

  return {
    findUnit: ({ tenantId, unitId }) => {
      if (!UUID.test(unitId)) return Promise.resolve(null);
      return inTenant(tenantId, async (tx) => {
        const [unit] = await tx
          .select({
            unitId: units.id,
            code: units.code,
            buildingId: units.buildingId,
          })
          .from(units)
          .where(and(eq(units.tenantId, tenantId), eq(units.id, unitId)))
          .limit(1);
        return unit ?? null;
      });
    },

    residents: ({ tenantId, unitId }) => {
      if (!UUID.test(unitId)) return Promise.resolve([]);
      return inTenant(tenantId, (tx) =>
        tx
          .select({
            userId: unitResidents.userId,
            relation: unitResidents.relation,
            verificationStatus: unitResidents.verificationStatus,
            validFrom: unitResidents.validFrom,
            validTo: unitResidents.validTo,
          })
          .from(unitResidents)
          .where(
            and(
              eq(unitResidents.tenantId, tenantId),
              eq(unitResidents.unitId, unitId),
            ),
          ),
      );
    },
  };
}
