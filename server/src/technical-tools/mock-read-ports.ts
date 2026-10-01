import type { z } from "zod";
import { ToolError } from "./errors";
import type { AssetPort, MaintenancePort, SensorPort } from "./ports";
import type {
  assetReadOutput,
  maintenanceReadOutput,
  sensorReadOutput,
} from "./schemas";

type AssetData = z.output<typeof assetReadOutput>["assets"][number];
type ReadingData = z.output<typeof sensorReadOutput>["readings"][number];
type EventData = z.output<typeof maintenanceReadOutput>["events"][number];

interface ScopedFixture {
  tenantId: string;
  buildingId: string;
  sourceVersion?: string | number | null;
}

export type MockAsset = ScopedFixture & AssetData;
export type MockSensorReading = ScopedFixture & ReadingData;
export type MockMaintenanceEvent = ScopedFixture & EventData;

export interface MockReadSeed {
  assets: readonly MockAsset[];
  readings: readonly MockSensorReading[];
  events: readonly MockMaintenanceEvent[];
}

/** POC only: caller supplies fixtures. Nothing here connects to a live asset/BMS system. */
export function createMockReadPorts(seed: MockReadSeed): {
  asset: AssetPort;
  sensor: SensorPort;
  maintenance: Pick<MaintenancePort, "read">;
} {
  const assets = [...seed.assets];
  const readings = [...seed.readings];
  const events = [...seed.events];

  const findAsset = (tenantId: string, buildingId: string, assetId: string) =>
    assets.find(
      (asset) =>
        asset.tenantId === tenantId &&
        asset.buildingId === buildingId &&
        asset.asset_id === assetId,
    );

  const requireAsset = (
    tenantId: string,
    buildingId: string,
    assetId: string,
  ) => {
    const asset = findAsset(tenantId, buildingId, assetId);
    if (!asset)
      throw new ToolError(
        "NOT_FOUND",
        "Asset not found in the permitted scope.",
      );
    return asset;
  };

  return {
    asset: {
      async read(context, input) {
        const matches = assets.filter(
          (asset) =>
            asset.tenantId === context.tenant_id &&
            asset.buildingId === input.building_id &&
            (input.asset_id
              ? asset.asset_id === input.asset_id
              : asset.location
                  .toLocaleLowerCase()
                  .includes((input.location ?? "").toLocaleLowerCase())) &&
            (!input.asset_type || asset.type === input.asset_type),
        );
        if (matches.length === 0) {
          throw new ToolError("NOT_FOUND", "No matching asset was found.");
        }
        const visible = matches.map(
          ({
            tenantId: _tenant,
            buildingId: _building,
            sourceVersion: _version,
            ...asset
          }) => asset,
        );
        return {
          data: { assets: visible },
          provenance: matches.map((asset) => ({
            source_system: "asset_mock_poc",
            source_record_id: asset.asset_id,
            source_version: asset.sourceVersion ?? null,
            retrieved_at: context.received_at,
          })),
          ...(matches.length > 1
            ? {
                notice: {
                  code: "NEEDS_INPUT" as const,
                  message: "Several assets match; specify asset_id.",
                  missingFields: ["asset_id"],
                },
              }
            : {}),
        };
      },
    },
    sensor: {
      async read(context, input) {
        if (input.asset_id)
          requireAsset(context.tenant_id, input.building_id, input.asset_id);
        const matches = readings
          .filter(
            (reading) =>
              reading.tenantId === context.tenant_id &&
              reading.buildingId === input.building_id &&
              reading.metric === input.metric &&
              (input.sensor_id
                ? reading.sensor_id === input.sensor_id
                : reading.asset_id === input.asset_id) &&
              Date.parse(reading.observed_at) >=
                Date.parse(input.time_range.from) &&
              Date.parse(reading.observed_at) <=
                Date.parse(input.time_range.to),
          )
          .sort(
            (a, b) => Date.parse(b.observed_at) - Date.parse(a.observed_at),
          );
        if (matches.length === 0) {
          throw new ToolError(
            "NOT_FOUND",
            "No sensor readings were found in the permitted scope.",
          );
        }
        const latest = matches[0];
        if (!latest)
          throw new ToolError(
            "NOT_FOUND",
            "No sensor readings were found in the permitted scope.",
          );
        const ageMs =
          Date.parse(context.received_at) - Date.parse(latest.observed_at);
        const stale = ageMs < 0 || ageMs > input.max_age_seconds * 1000;
        const visible = matches.map(
          ({
            tenantId: _tenant,
            buildingId: _building,
            sourceVersion: _version,
            ...reading
          }) => reading,
        );
        return {
          data: {
            freshness: stale ? ("stale" as const) : ("fresh" as const),
            readings: visible,
          },
          provenance: matches.map((reading) => ({
            source_system: "sensor_mock_poc",
            source_record_id: reading.sensor_id,
            source_version: reading.sourceVersion ?? null,
            retrieved_at: context.received_at,
          })),
          ...(stale
            ? {
                notice: {
                  code: "STALE_DATA" as const,
                  message: "Sensor readings are outside the freshness window.",
                },
              }
            : {}),
        };
      },
    },
    maintenance: {
      async read(context, input) {
        requireAsset(context.tenant_id, input.building_id, input.asset_id);
        const matches = events
          .filter(
            (event) =>
              event.tenantId === context.tenant_id &&
              event.buildingId === input.building_id &&
              event.asset_id === input.asset_id &&
              Date.parse(event.occurred_at) >=
                Date.parse(input.time_range.from) &&
              Date.parse(event.occurred_at) <= Date.parse(input.time_range.to),
          )
          .sort(
            (a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at),
          );
        const visible = matches
          .slice(0, input.limit)
          .map(
            ({
              tenantId: _tenant,
              buildingId: _building,
              sourceVersion: _version,
              ...event
            }) => event,
          );
        return {
          data: {
            events: visible,
            last_maintenance_at: matches[0]?.occurred_at ?? null,
            repeat_count: matches.length,
          },
          provenance: visible.map((event) => ({
            source_system: "maintenance_mock_poc",
            source_record_id: event.event_id,
            source_version:
              matches.find((item) => item.event_id === event.event_id)
                ?.sourceVersion ?? null,
            retrieved_at: context.received_at,
          })),
        };
      },
    },
  };
}
