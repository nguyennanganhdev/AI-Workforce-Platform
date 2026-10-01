import { randomUUID } from "node:crypto";
import { ToolError } from "./errors";
import type { MockAsset, MockMaintenanceEvent } from "./mock-read-ports";
import { createMockReadPorts } from "./mock-read-ports";
import type { MaintenancePort } from "./ports";

export interface MockVerifiedResult {
  id: string;
  tenantId: string;
  buildingId: string;
  assetId: string;
  workorderId: string;
  status: "VERIFIED" | "PENDING" | "REJECTED";
  allowedPrincipalIds: readonly string[];
}

export interface MockMaintenanceSeed {
  assets: readonly MockAsset[];
  verifiedResults: readonly MockVerifiedResult[];
  events?: readonly MockMaintenanceEvent[];
}

/** Single-process POC only. A production adapter needs durable transactional idempotency. */
export function createMockMaintenancePort(
  seed: MockMaintenanceSeed,
  now: () => Date = () => new Date(),
): MaintenancePort {
  const events = [...(seed.events ?? [])];
  const retries = new Map<
    string,
    {
      payload: string;
      result: Awaited<ReturnType<MaintenancePort["appendVerified"]>>;
    }
  >();
  return {
    async read(context, input) {
      return createMockReadPorts({
        assets: seed.assets,
        readings: [],
        events,
      }).maintenance.read(context, input);
    },
    async appendVerified(context, input) {
      const asset = seed.assets.find(
        (item) =>
          item.tenantId === context.tenant_id &&
          item.buildingId === input.building_id &&
          item.asset_id === input.asset_id,
      );
      if (!asset)
        throw new ToolError(
          "NOT_FOUND",
          "Asset not found in the permitted scope.",
        );
      const verified = seed.verifiedResults.find(
        (item) =>
          item.id === input.verified_result_id &&
          item.tenantId === context.tenant_id &&
          item.buildingId === input.building_id &&
          item.assetId === input.asset_id &&
          item.workorderId === input.workorder_id,
      );
      if (verified?.status !== "VERIFIED") {
        throw new ToolError(
          "CONFLICT",
          "The executor result is not verified for this work order and asset.",
        );
      }
      if (!verified.allowedPrincipalIds.includes(context.principal_id)) {
        throw new ToolError(
          "FORBIDDEN",
          "The principal cannot append this maintenance result.",
        );
      }
      const retryKey = `${context.tenant_id}:${input.asset_id}:${input.workorder_id}:${input.idempotency_key}`;
      const payload = JSON.stringify(input);
      const previous = retries.get(retryKey);
      if (previous) {
        if (previous.payload !== payload)
          throw new ToolError(
            "CONFLICT",
            "Idempotency key was used for another payload.",
          );
        return previous.result;
      }
      const superseded = input.supersedes_event_id
        ? events.find(
            (item) =>
              item.event_id === input.supersedes_event_id &&
              item.tenantId === context.tenant_id &&
              item.buildingId === input.building_id &&
              item.asset_id === input.asset_id,
          )
        : undefined;
      if (input.supersedes_event_id && !superseded) {
        throw new ToolError(
          "CONFLICT",
          "The superseded event does not belong to this asset.",
        );
      }
      const revision = superseded
        ? Number(superseded.sourceVersion ?? 1) + 1
        : 1;
      const createdAt = now().toISOString();
      const eventId = randomUUID();
      events.push({
        tenantId: context.tenant_id,
        buildingId: input.building_id,
        event_id: eventId,
        asset_id: input.asset_id,
        workorder_id: input.workorder_id,
        occurred_at: input.occurred_at ?? context.received_at,
        outcome: input.outcome,
        source_refs: input.source_refs,
        sourceVersion: revision,
      });
      const result = {
        data: {
          maintenance_event_id: eventId,
          created_at: createdAt,
          revision,
          supersedes_event_id: superseded?.event_id ?? null,
        },
        provenance: [
          {
            source_system: "maintenance_mock_poc",
            source_record_id: eventId,
            source_version: revision,
            retrieved_at: createdAt,
          },
        ],
      };
      retries.set(retryKey, { payload, result });
      return result;
    },
  };
}
