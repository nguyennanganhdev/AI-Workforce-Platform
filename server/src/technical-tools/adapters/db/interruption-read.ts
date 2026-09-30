import { and, eq, gt, inArray, isNull, lte, or, sql } from "drizzle-orm";
import type { PgDatabase, PgQueryResultHKT } from "drizzle-orm/pg-core";
import type { Database } from "../../../db/client";
import type * as schema from "../../../db/schema";
import {
  accessScopes,
  buildings,
  interruptionScopes,
  serviceInterruptions,
} from "../../../db/schema";
import type { InterruptionRecord } from "../../domain/interruption";
import type { InterruptionReadPort } from "../../ports/interruption-read";

/**
 * Any Drizzle PostgreSQL database over the application schema.
 *
 * Wider than the server's own `Database`, which is tied to Bun's driver, so the same queries run
 * against the PGlite instance the tests load the real baseline migration into.
 */
export type TechnicalToolsDatabase = PgDatabase<
  PgQueryResultHKT,
  typeof schema
>;

/** The server's database, as this module takes it. */
export function technicalToolsDatabase(
  database: Database,
): TechnicalToolsDatabase {
  return database;
}

/**
 * Reads `service_interruptions` and `interruption_scopes`.
 *
 * Each call is one read-only transaction that sets `app.tenant_id` first, the way
 * `withDatabaseScope` does, so the tables' row-level security agrees with the `tenant_id` filter
 * written into the query rather than relying on it. `SET LOCAL` ends with the transaction and
 * cannot follow the connection back into the pool.
 */
export function createDbInterruptionReadPort(
  database: TechnicalToolsDatabase,
): InterruptionReadPort {
  return {
    listCovering: ({ tenantId, buildingId, utility, window }) =>
      database.transaction(
        async (tx) => {
          await tx.execute(
            sql`select set_config('app.tenant_id', ${tenantId}, true)`,
          );

          const [building] = await tx
            .select({ siteId: buildings.siteId, zoneId: buildings.zoneId })
            .from(buildings)
            .where(
              and(
                eq(buildings.tenantId, tenantId),
                eq(buildings.id, buildingId),
              ),
            )
            .limit(1);
          if (!building) return null;

          // A cut declared for a zone or a whole site reaches every building inside it.
          const covering = tx
            .select({ id: interruptionScopes.interruptionId })
            .from(interruptionScopes)
            .innerJoin(
              accessScopes,
              and(
                eq(accessScopes.tenantId, interruptionScopes.tenantId),
                eq(accessScopes.id, interruptionScopes.scopeId),
              ),
            )
            .where(
              and(
                eq(interruptionScopes.tenantId, tenantId),
                or(
                  and(
                    eq(accessScopes.kind, "building"),
                    eq(accessScopes.buildingId, buildingId),
                  ),
                  and(
                    eq(accessScopes.kind, "site"),
                    eq(accessScopes.siteId, building.siteId),
                  ),
                  building.zoneId
                    ? and(
                        eq(accessScopes.kind, "zone"),
                        eq(accessScopes.zoneId, building.zoneId),
                      )
                    : undefined,
                ),
              ),
            );

          /*
           * Bounded by the window, loosely. These two conditions keep every row the rules could
           * select and drop only what cannot matter: anything that begins after the window, and
           * anything already over before it. They decide nothing about status.
           */
          const rows = await tx
            .select({
              id: serviceInterruptions.id,
              status: serviceInterruptions.status,
              plannedStart: serviceInterruptions.plannedStart,
              plannedEnd: serviceInterruptions.plannedEnd,
              actualStart: serviceInterruptions.actualStart,
              actualEnd: serviceInterruptions.actualEnd,
              updatedAt: serviceInterruptions.updatedAt,
              scopeId: interruptionScopes.scopeId,
            })
            .from(serviceInterruptions)
            .innerJoin(
              interruptionScopes,
              and(
                eq(interruptionScopes.tenantId, serviceInterruptions.tenantId),
                eq(interruptionScopes.interruptionId, serviceInterruptions.id),
              ),
            )
            .where(
              and(
                eq(serviceInterruptions.tenantId, tenantId),
                eq(serviceInterruptions.utility, utility),
                inArray(serviceInterruptions.id, covering),
                or(
                  lte(serviceInterruptions.plannedStart, window.to),
                  lte(serviceInterruptions.actualStart, window.to),
                ),
                or(
                  gt(serviceInterruptions.plannedEnd, window.from),
                  gt(serviceInterruptions.actualEnd, window.from),
                  and(
                    eq(serviceInterruptions.status, "active"),
                    isNull(serviceInterruptions.actualEnd),
                  ),
                ),
              ),
            );

          // One row per scope: fold them back into one record per interruption.
          const records = new Map<string, InterruptionRecord>();
          for (const { scopeId, ...row } of rows) {
            const record = records.get(row.id);
            if (record) {
              record.scopeIds.push(scopeId);
            } else {
              records.set(row.id, { ...row, utility, scopeIds: [scopeId] });
            }
          }
          for (const record of records.values()) record.scopeIds.sort();
          return [...records.values()];
        },
        { accessMode: "read only" },
      ),
  };
}
