import { randomUUID } from "node:crypto";
import {
  recordMeasurementInputSchema,
  recordMeasurementOutputSchema,
} from "../contracts/measurement";
import type { Measurement } from "../domain/measurement";
import { defineTool } from "../tool";
import { evidenceProblems } from "./evidence-rules";
import {
  DEVICE_SOURCES,
  measuredInFuture,
  normalize,
  qualityFlags,
  technicianMayRecord,
} from "./measurement-rules";
import {
  conflict,
  forbidden,
  invalidInput,
  notFound,
  provenanceOf,
} from "./outcomes";

/** The POC store names itself, so provenance does not imply the measurement is in the database. */
const MEASUREMENT_ADAPTER = "measurement_adapter";

/**
 * `technical.record_measurement` (tools.md §4.2).
 *
 * Writes down a value a technician or a registered device actually measured. Its one firm rule is
 * general.md §3.1's: the agent never creates a measurement. So a measurement is recorded only under
 * the name of the person the run acts for, on a work order they have accepted, or of a sensor that
 * is registered in the building. Unusual values are recorded and flagged, never refused: the
 * extreme reading is the one a person on duty most needs to see.
 */
export const recordMeasurementTool = defineTool({
  name: "technical.record_measurement",
  version: "1.0.0",
  description:
    "Record a measurement a technician took on site, or one a registered device reported, " +
    "against a work order. Only record a value somebody actually measured and told you: never " +
    "estimate, round, or supply a value yourself. measured_by must be the technician you are " +
    "acting for, or a registered sensor. The value is converted to the metric's standard unit; an " +
    "unusual value is recorded and flagged out_of_expected_range, not refused. Retry with the same " +
    "idempotency_key after a timeout; it will not record the value twice.",
  effect: "write",
  capability: "measurement:write",
  timeoutMs: 5_000,
  inputSchema: recordMeasurementInputSchema,
  outputSchema: recordMeasurementOutputSchema,
  async run(context, input, { workOrders, sensors, measurements, clock }) {
    const workOrder = await workOrders.getWorkOrder({
      tenantId: context.tenant_id,
      buildingId: input.building_id,
      workOrderId: input.workorder_id,
    });
    if (!workOrder) {
      return notFound("No work order with that id is in this building.", {
        field: "workorder_id",
      });
    }

    const now = clock.now();
    const measuredAt = new Date(input.measured_at);
    if (measuredInFuture(measuredAt, now)) {
      return invalidInput(
        "measured_at is later than the server's clock. Record the time the value was actually measured.",
        "measured_at",
      );
    }

    const normalized = normalize(input.metric, input.value, input.unit);
    if (!normalized.ok)
      return invalidInput(normalized.message, normalized.field);

    if (input.measured_by.kind === "technician") {
      if (
        !technicianMayRecord(
          context.user_id,
          input.measured_by.source_id,
          workOrder,
        )
      ) {
        return forbidden();
      }
    } else {
      // A device must be one the building knows, measuring this metric, reporting as a device does.
      const { sensors: registered } = DEVICE_SOURCES.has(input.source)
        ? await sensors.find({
            tenantId: context.tenant_id,
            buildingId: input.building_id,
            sensorId: input.measured_by.source_id,
            ...(input.asset_id ? { assetId: input.asset_id } : {}),
            metric: input.metric,
            window: { from: measuredAt, to: now },
          })
        : { sensors: [] };
      if (registered.length === 0) return forbidden();
    }

    const evidenceIds = input.evidence_ids ?? [];
    if (evidenceIds.length > 0) {
      const problems = evidenceProblems(
        evidenceIds,
        await workOrders.findEvidence({
          tenantId: context.tenant_id,
          ids: evidenceIds,
        }),
        workOrder.ticketId,
      );
      if (problems.length > 0) return conflict(problems, "evidence_ids");
    }

    const measurement: Measurement = {
      measurementId: randomUUID(),
      tenantId: context.tenant_id,
      buildingId: input.building_id,
      workOrderId: workOrder.workOrderId,
      assetId: input.asset_id ?? null,
      metric: input.metric,
      rawValue: input.value,
      rawUnit: input.unit,
      normalizedValue: normalized.value,
      normalizedUnit: normalized.unit,
      measuredAt,
      measuredBy: {
        kind: input.measured_by.kind,
        sourceId: input.measured_by.source_id,
      },
      source: input.source,
      evidenceIds,
      qualityFlags: qualityFlags(
        input.metric,
        normalized.value,
        measuredAt,
        now,
      ),
      createdAt: now,
      sourceRunId: context.source_run_id,
    };
    await measurements.append(measurement);

    return {
      status: "OK",
      data: {
        measurement_id: measurement.measurementId,
        metric: measurement.metric,
        normalized_value: measurement.normalizedValue,
        normalized_unit: measurement.normalizedUnit,
        created_at: measurement.createdAt.toISOString(),
        quality_flags: [...measurement.qualityFlags],
      },
      provenance: provenanceOf(
        [{ id: measurement.measurementId, version: 1 }],
        now.toISOString(),
        MEASUREMENT_ADAPTER,
      ),
      resultCount: 1,
    };
  },
});
