import { sql } from "drizzle-orm";
import type { SQL } from "drizzle-orm";
import {
  createDbInterruptionReadPort,
  createDbIsolationWriter,
  createDbScopeReadPort,
  createDbSopReadPort,
  createDbUnitReadPort,
  createDbWorkOrderReadPort,
  createScopeBuildingAccess,
  systemClock,
} from "../technical-tools";
import type {
  Asset,
  ApprovalRequest,
  ExecutorResult,
  HostDependencies,
  MaintenanceEvent,
  Measurement,
  SopProfile,
  TenantSession,
  TenantTransaction,
  Vendor,
} from "../technical-tools";

export async function rows<T>(
  tx: TenantTransaction,
  statement: SQL,
): Promise<T[]> {
  const result: unknown = await tx.execute(statement);
  const values = Array.isArray(result)
    ? result
    : result && typeof result === "object" && "rows" in result
      ? result.rows
      : null;
  if (!Array.isArray(values))
    throw new Error("Database returned an invalid row set");
  return values.map((value: Record<string, unknown>) => {
    const record = { ...value };
    // Bun raw queries may return JSONB text; Drizzle's typed select parses it itself.
    for (const field of [
      "payload",
      "details",
      "issue_codes",
      "acceptance_criteria",
      "outcome",
      "response",
    ]) {
      if (typeof record[field] === "string")
        record[field] = JSON.parse(record[field]);
    }
    return record as T;
  });
}

/** Dates are JSON strings on disk; ports require Date objects at their boundary. */
function decode<T>(
  payload: Record<string, unknown>,
  dateFields: readonly string[],
): T {
  const record = { ...payload };
  for (const field of dateFields)
    if (typeof record[field] === "string")
      record[field] = new Date(record[field]);
  return record as T;
}
const encoded = (value: unknown) => JSON.stringify(value);
type Stored = { payload: Record<string, unknown> };

export async function databasePorts(
  tx: TenantTransaction,
  tenantId: string,
): Promise<
  Omit<HostDependencies, "contextResolver" | "idempotency" | "audit">
> {
  const session: TenantSession = {
    kind: "tenant-session",
    read: (tenant, work) => {
      if (tenant !== tenantId) throw new Error("Tenant mismatch");
      return work(tx);
    },
    write: (tenant, work) => {
      if (tenant !== tenantId) throw new Error("Tenant mismatch");
      return work(tx);
    },
  };
  const scopes = createDbScopeReadPort(session);
  const profiles = await rows<{
    document_code: string;
    version_no: number;
    issue_codes: string[];
    excerpt: string;
    acceptance_criteria: SopProfile["acceptanceCriteria"];
  }>(
    tx,
    sql`select document_code,version_no,issue_codes,excerpt,acceptance_criteria
        from vh_technical_sop_profiles where tenant_id=${tenantId}`,
  );
  const maintenance = {
    listForAsset: async (q: {
      tenantId: string;
      buildingId: string;
      assetId: string;
      until: Date;
    }) =>
      (
        await rows<Stored>(
          tx,
          sql`select payload from vh_technical_maintenance_events
        where tenant_id=${q.tenantId} and building_id=${q.buildingId} and asset_id=${q.assetId}
        and occurred_at<${q.until}`,
        )
      ).map((r) =>
        decode<MaintenanceEvent>(r.payload, ["occurredAt", "createdAt"]),
      ),
    findEvent: async (tenant: string, id: string) => {
      const [record] = await rows<Stored>(
        tx,
        sql`select payload from vh_technical_maintenance_events where tenant_id=${tenant} and id=${id}`,
      );
      return record
        ? decode<MaintenanceEvent>(record.payload, ["occurredAt", "createdAt"])
        : null;
    },
    supersededBy: async (tenant: string, id: string) => {
      const [record] = await rows<{ id: string }>(
        tx,
        sql`select id from vh_technical_maintenance_events where tenant_id=${tenant} and supersedes_event_id=${id}`,
      );
      return record?.id ?? null;
    },
    append: async (event: MaintenanceEvent) => {
      const added = await rows<{ id: string }>(
        tx,
        sql`insert into vh_technical_maintenance_events
        (tenant_id,id,building_id,asset_id,work_order_id,supersedes_event_id,occurred_at,payload)
        values(${event.tenantId},${event.eventId},${event.buildingId},${event.assetId},${event.workorderId},
          ${event.supersedesEventId},${event.occurredAt},${encoded(event)}::text::jsonb)
        on conflict(tenant_id,supersedes_event_id) do nothing returning id`,
      );
      if (added.length) return { state: "appended" as const };
      const [replacement] = await rows<{ id: string }>(
        tx,
        sql`select id from vh_technical_maintenance_events
        where tenant_id=${event.tenantId} and supersedes_event_id=${event.supersedesEventId}`,
      );
      if (!replacement)
        throw new Error("Maintenance correction was not recorded");
      return {
        state: "already_superseded" as const,
        byEventId: replacement.id,
      };
    },
  };
  return {
    clock: systemClock,
    scopes,
    buildingAccess: createScopeBuildingAccess(scopes),
    workOrders: createDbWorkOrderReadPort(session),
    units: createDbUnitReadPort(session),
    interruptions: createDbInterruptionReadPort(session),
    isolations: createDbIsolationWriter(session),
    sop: createDbSopReadPort(session),
    sopProfiles: {
      find: (code, version) => {
        const p = profiles.find(
          (r) => r.document_code === code && r.version_no === version,
        );
        return p
          ? {
              code,
              versionNo: version,
              issueCodes: p.issue_codes,
              excerpt: p.excerpt,
              acceptanceCriteria: p.acceptance_criteria,
            }
          : undefined;
      },
    },
    assets: {
      find: async (q) => {
        const all = await rows<{
          id: string;
          code: string;
          details: Record<string, unknown>;
          status: string;
          created_at: Date;
        }>(
          tx,
          sql`select id,code,details,status,created_at from vh_assets
        where tenant_id=${q.tenantId} and building_id=${q.buildingId}`,
        );
        const assets: Asset[] = all.map((r) => ({
          assetId: r.code,
          tenantId: q.tenantId,
          buildingId: q.buildingId,
          type: String(r.details.type ?? "unknown"),
          model: typeof r.details.model === "string" ? r.details.model : null,
          location: String(r.details.location ?? ""),
          ownership:
            typeof r.details.ownership === "string"
              ? r.details.ownership
              : null,
          warrantyUntil:
            typeof r.details.warrantyUntil === "string"
              ? r.details.warrantyUntil
              : null,
          status: r.status === "active" ? "in_service" : "inactive",
          updatedAt: new Date(String(r.details.updatedAt ?? r.created_at)),
          etag: r.id,
        }));
        const normalized = (s: string) =>
          s
            .normalize("NFD")
            .replace(/\p{Diacritic}/gu, "")
            .toLowerCase();
        return assets.filter(
          (a) =>
            (!q.assetId || a.assetId === q.assetId) &&
            (!q.assetType || a.type === q.assetType) &&
            (!q.location ||
              normalized(a.location).includes(normalized(q.location))),
        );
      },
    },
    sensors: {
      find: async (q) => {
        const sensors = await rows<{
          sensor_id: string;
          asset_id: string | null;
          metric: string;
          unit: string;
        }>(
          tx,
          sql`select sensor_id,asset_id,metric,unit from vh_technical_sensors
        where tenant_id=${q.tenantId} and building_id=${q.buildingId} and metric=${q.metric}
        and (${q.sensorId ?? null}::text is null or sensor_id=${q.sensorId ?? null})
        and (${q.assetId ?? null}::text is null or asset_id=${q.assetId ?? null})`,
        );
        const readings = await rows<{
          sensor_id: string;
          metric: string;
          value: string;
          unit: string;
          observed_at: Date;
          quality: "good" | "uncertain" | "bad" | "unknown";
        }>(
          tx,
          sql`select r.sensor_id,s.metric,r.value,r.unit,r.observed_at,r.quality from vh_technical_sensor_samples r
        join vh_technical_sensors s on s.tenant_id=r.tenant_id and s.sensor_id=r.sensor_id
        where s.tenant_id=${q.tenantId} and s.building_id=${q.buildingId} and s.metric=${q.metric}
        and (${q.sensorId ?? null}::text is null or s.sensor_id=${q.sensorId ?? null})
        and (${q.assetId ?? null}::text is null or s.asset_id=${q.assetId ?? null})
        and r.observed_at>=${q.window.from} and r.observed_at<=${q.window.to}`,
        );
        return {
          sensors: sensors.map((s) => ({
            sensorId: s.sensor_id,
            tenantId: q.tenantId,
            buildingId: q.buildingId,
            assetId: s.asset_id,
            metric: s.metric,
            unit: s.unit,
          })),
          readings: readings.map((r) => ({
            sensorId: r.sensor_id,
            metric: r.metric,
            value: Number(r.value),
            unit: r.unit,
            observedAt: new Date(r.observed_at),
            quality: r.quality,
          })),
        };
      },
    },
    maintenance,
    maintenanceStore: maintenance,
    measurements: {
      append: async (m) => {
        await tx.execute(sql`insert into vh_technical_measurement_records
        (tenant_id,id,building_id,work_order_id,asset_id,payload)
        values(${m.tenantId},${m.measurementId},${m.buildingId},${m.workOrderId},${m.assetId},${encoded(m)}::text::jsonb)`);
      },
      findByIds: async (tenant, ids) =>
        ids.length
          ? (
              await rows<Stored>(
                tx,
                sql`select payload from vh_technical_measurement_records
          where tenant_id=${tenant} and id in (${sql.join(
            ids.map((id) => sql`${id}`),
            sql`,`,
          )})`,
              )
            ).map((r) =>
              decode<Measurement>(r.payload, ["measuredAt", "createdAt"]),
            )
          : [],
    },
    executorResults: {
      append: async (r) => {
        await tx.execute(sql`insert into vh_technical_executor_results
        (tenant_id,id,building_id,work_order_id,payload)
        values(${r.tenantId},${r.resultId},${r.buildingId},${r.workOrderId},${encoded(r)}::text::jsonb)`);
      },
      findById: async (tenant, id) => {
        const [record] = await rows<Stored>(
          tx,
          sql`select payload from vh_technical_executor_results where tenant_id=${tenant} and id=${id}`,
        );
        return record
          ? decode<ExecutorResult>(record.payload, [
              "startedAt",
              "completedAt",
              "createdAt",
            ])
          : null;
      },
    },
    approvalRequests: {
      create: async (r) => {
        await tx.execute(sql`insert into vh_technical_approval_requests
        (tenant_id,id,building_id,incident_id,kind,payload)
        values(${r.tenantId},${r.requestId},${r.buildingId},${r.incidentId},${r.kind},${encoded(r)}::text::jsonb)`);
      },
      listOpen: async (q) =>
        (
          await rows<Stored>(
            tx,
            sql`select payload from vh_technical_approval_requests
        where tenant_id=${q.tenantId} and kind=${q.kind} and incident_id=${q.incidentId} and status='pending'`,
          )
        ).map((r) => {
          const request = decode<ApprovalRequest>(r.payload, ["createdAt"]);
          if (request.interruption)
            request.interruption = {
              ...request.interruption,
              plannedStart: new Date(request.interruption.plannedStart),
              plannedEnd: new Date(request.interruption.plannedEnd),
            };
          return request;
        }),
    },
    vendors: {
      findBySpecialty: async (q) =>
        (
          await rows<Stored>(
            tx,
            sql`select payload from vh_technical_vendors where tenant_id=${q.tenantId} and payload->'specialtyCodes' ? ${q.specialtyCode}`,
          )
        ).map((r) => decode<Vendor>(r.payload, ["licenseExpiresAt"])),
    },
  };
}
