import {
  and,
  eq,
  gt,
  inArray,
  isNotNull,
  isNull,
  lt,
  lte,
  or,
} from "drizzle-orm";
import type { Database } from "../db/client";
import { interruptionScopes, serviceInterruptions } from "../db/schema";
import type { ExecutionContext } from "./context";
import type { InterruptionPort } from "./ports";

/** Chiến supplies a DB session with app.tenant_id set for RLS before this callback runs. */
export interface TenantReadSessionPort {
  withTenantRead<T>(
    context: ExecutionContext,
    query: (db: Database) => Promise<T>,
  ): Promise<T>;
}

/** Chiến resolves the building's own and ancestor access scope IDs in the same tenant. */
export interface CoveringScopesPort {
  forBuilding(
    context: ExecutionContext,
    buildingId: string,
  ): Promise<readonly string[]>;
}

type Row = {
  id: string;
  utility: string;
  status: string;
  plannedStart: Date;
  plannedEnd: Date;
  actualStart: Date | null;
  actualEnd: Date | null;
  updatedAt: Date;
  scopeId: string;
};

function groupRows(rows: readonly Row[]) {
  const grouped = new Map<string, Row & { scopeIds: string[] }>();
  for (const row of rows) {
    const existing = grouped.get(row.id);
    if (existing) {
      if (!existing.scopeIds.includes(row.scopeId))
        existing.scopeIds.push(row.scopeId);
    } else {
      grouped.set(row.id, { ...row, scopeIds: [row.scopeId] });
    }
  }
  return [...grouped.values()];
}

export function createInterruptionDbPort(
  sessions: TenantReadSessionPort,
  coveringScopes: CoveringScopesPort,
): InterruptionPort {
  async function query(
    context: ExecutionContext,
    buildingId: string,
    utility: "water" | "power",
    mode:
      | { kind: "outage"; at: Date }
      | { kind: "schedule"; from: Date; to: Date },
  ) {
    const scopeIds = await coveringScopes.forBuilding(context, buildingId);
    if (scopeIds.length === 0) return [];
    return sessions.withTenantRead(context, (db) =>
      db
        .select({
          id: serviceInterruptions.id,
          utility: serviceInterruptions.utility,
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
            eq(serviceInterruptions.tenantId, context.tenant_id),
            eq(interruptionScopes.tenantId, context.tenant_id),
            inArray(interruptionScopes.scopeId, [...scopeIds]),
            eq(serviceInterruptions.utility, utility),
            mode.kind === "outage"
              ? and(
                  inArray(serviceInterruptions.status, ["active", "restored"]),
                  isNotNull(serviceInterruptions.actualStart),
                  lte(serviceInterruptions.actualStart, mode.at),
                  or(
                    isNull(serviceInterruptions.actualEnd),
                    gt(serviceInterruptions.actualEnd, mode.at),
                  ),
                )
              : and(
                  inArray(serviceInterruptions.status, [
                    "approved",
                    "notified",
                    "active",
                    "restored",
                  ]),
                  lt(serviceInterruptions.plannedStart, mode.to),
                  gt(serviceInterruptions.plannedEnd, mode.from),
                ),
          ),
        ),
    );
  }

  return {
    async getActiveOutages(context, input) {
      const rows = groupRows(
        await query(context, input.building_id, input.service_type, {
          kind: "outage",
          at: new Date(input.occurred_at),
        }),
      );
      const actualStart = (row: (typeof rows)[number]) => {
        if (!row.actualStart)
          throw new Error("Active interruption has no actual start.");
        return row.actualStart.toISOString();
      };
      return {
        data: {
          outages: rows.map((row) => ({
            outage_id: row.id,
            service_type: row.utility as "water" | "power",
            status: row.status as "active" | "restored",
            scope_ids: row.scopeIds,
            started_at: actualStart(row),
            ended_at: row.actualEnd?.toISOString() ?? null,
            published_eta: null, // No published ETA column in the current catalog.
          })),
        },
        provenance: rows.map((row) => ({
          source_system: "application_db",
          source_record_id: row.id,
          source_version: row.updatedAt.toISOString(),
          retrieved_at: context.received_at,
        })),
      };
    },
    async readSchedule(context, input) {
      const rows = groupRows(
        await query(context, input.building_id, input.utility_type, {
          kind: "schedule",
          from: new Date(input.time_range.from),
          to: new Date(input.time_range.to),
        }),
      );
      return {
        data: {
          schedules: rows.map((row) => ({
            schedule_id: row.id,
            utility_type: row.utility as "water" | "power",
            status: row.status as
              | "approved"
              | "notified"
              | "active"
              | "restored",
            planned_start: row.plannedStart.toISOString(),
            planned_end: row.plannedEnd.toISOString(),
            scope_ids: row.scopeIds,
          })),
        },
        provenance: rows.map((row) => ({
          source_system: "application_db",
          source_record_id: row.id,
          source_version: row.updatedAt.toISOString(),
          retrieved_at: context.received_at,
        })),
      };
    },
  };
}
