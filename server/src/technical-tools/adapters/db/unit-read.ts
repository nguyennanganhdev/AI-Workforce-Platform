import { and, eq } from "drizzle-orm";
import { unitResidents, units } from "../../../db/schema";
import type { UnitReadPort } from "../../ports/entry-vendor-ports";
import { asTenantSession, type TenantSessionSource } from "./tenant-session";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Reads `units` and `unit_residents`, one read-only transaction per call with the tenant set.
 *
 * Who the residents are is read so the request can say who must approve entry, never handed back
 * to the agent: nothing of a resident leaves this port except through that decision.
 */
export function createDbUnitReadPort(
  source: TenantSessionSource,
): UnitReadPort {
  const session = asTenantSession(source);
  return {
    findUnit: ({ tenantId, unitId }) => {
      if (!UUID.test(unitId)) return Promise.resolve(null);
      return session.read(tenantId, async (tx) => {
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
      return session.read(tenantId, (tx) =>
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
