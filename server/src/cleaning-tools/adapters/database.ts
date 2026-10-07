import { sql } from "drizzle-orm";
import {
  asTenantSession,
  type TenantSessionSource,
  type TenantTransaction,
} from "../../technical-tools/adapters/db/tenant-session";
async function rows<T>(
  tx: TenantTransaction,
  statement: ReturnType<typeof sql>,
): Promise<T[]> {
  const value: unknown = await tx.execute(statement);
  if (Array.isArray(value)) return value as T[];
  if (
    value &&
    typeof value === "object" &&
    "rows" in value &&
    Array.isArray(value.rows)
  )
    return value.rows as T[];
  throw new Error("Invalid database row set");
}

/** Category/tenant/building check independent of model-supplied tool input. */
export function createDbCleaningWorkOrderCheck(source: TenantSessionSource) {
  const session = asTenantSession(source);
  return (tenantId: string, buildingId: string, workOrderId: string) =>
    session.read(tenantId, async (tx) => {
      const result = await rows<{ id: string }>(
        tx,
        sql`
      with recursive cleaning as (
        select id from service_categories where tenant_id=${tenantId} and code='cleaning' and enabled
        union select c.id from service_categories c join cleaning p on p.id=c.parent_id
          where c.tenant_id=${tenantId} and c.enabled
      ) select w.id from work_orders w join tickets t on t.tenant_id=w.tenant_id and t.id=w.ticket_id
        where w.tenant_id=${tenantId} and w.id=${workOrderId} and t.building_id=${buildingId}
          and w.category_id in(select id from cleaning)`,
      );
      return result.length === 1;
    });
}
