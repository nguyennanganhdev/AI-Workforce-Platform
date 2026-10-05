import {
  sensorReadInputSchema,
  sensorReadOutputSchema,
} from "../contracts/sensor";
import { defineTool } from "../tool";
import { needsInput, notFound, provenanceOf, staleData } from "./outcomes";
import {
  freshnessOf,
  freshnessReference,
  MAX_READINGS,
  readingsWithin,
  withUnitChecked,
} from "./sensor-rules";

/** The POC adapter names itself, so provenance does not imply a live BMS feed. */
const SENSOR_ADAPTER = "sensor_adapter";

/**
 * `sensor.read` (tools.md §3.3).
 *
 * What a BMS or IoT sensor on the equipment has been reporting, and whether that is recent enough
 * to reason from. Its rule is general.md §11's: data too old is marked stale and is never the basis
 * for calling something safe. Old readings still come back, flagged, because a technician can use
 * them and hiding them would hide that the sensor went quiet. Bad readings come back too, with
 * their quality, for the same reason.
 */
export const sensorReadTool = defineTool({
  name: "sensor.read",
  version: "1.0.0",
  description:
    "Read what a BMS or IoT sensor reported for one metric over a time range, by sensor id or by " +
    "the asset it is fitted to. Each reading carries its unit, time and quality. STALE_DATA means " +
    "the newest reading is older than max_age_seconds: show it if useful, but never conclude from " +
    "it that equipment is safe or fixed. Treat readings of quality 'bad' or 'uncertain' the same " +
    "way. An empty list with freshness 'unknown' means the sensor sent nothing in that range.",
  effect: "read",
  capability: "sensor:read",
  timeoutMs: 5_000,
  inputSchema: sensorReadInputSchema,
  outputSchema: sensorReadOutputSchema,
  async run(context, input, { sensors, clock }) {
    const from = new Date(input.time_range.from);
    const to = new Date(input.time_range.to);
    const { sensors: matched, readings } = await sensors.find({
      tenantId: context.tenant_id,
      buildingId: input.building_id,
      ...(input.sensor_id ? { sensorId: input.sensor_id } : {}),
      ...(input.asset_id ? { assetId: input.asset_id } : {}),
      metric: input.metric,
      window: { from, to },
    });

    if (matched.length === 0) {
      return notFound(
        `No sensor in this building reports ${input.metric} for that ${input.sensor_id ? "sensor" : "asset"}.`,
        { field: input.sensor_id ? "sensor_id" : "asset_id" },
      );
    }

    const inWindow = readingsWithin(readings, from, to);
    if (inWindow.length > MAX_READINGS) {
      return needsInput(
        `${inWindow.length} readings fall in that range, more than the ${MAX_READINGS} one answer carries. Ask for a narrower time_range.`,
        ["time_range"],
        { field: "time_range" },
      );
    }

    const now = clock.now();
    const checked = inWindow.map(withUnitChecked);
    const freshness = freshnessOf(
      checked,
      freshnessReference(to, now),
      input.max_age_seconds,
    );
    const assetOf = new Map(
      matched.map((sensor) => [sensor.sensorId, sensor.assetId]),
    );
    const data = {
      readings: checked.map((reading) => ({
        sensor_id: reading.sensorId,
        asset_id: assetOf.get(reading.sensorId) ?? null,
        metric: reading.metric,
        value: reading.value,
        unit: reading.unit,
        observed_at: reading.observedAt.toISOString(),
        quality: reading.quality,
      })),
      freshness,
    };
    // One entry per sensor asked, including one that sent nothing: its silence is the finding.
    const provenance = provenanceOf(
      matched.map((sensor) => ({ id: sensor.sensorId, version: null })),
      now.toISOString(),
      SENSOR_ADAPTER,
    );

    if (freshness === "stale") {
      return {
        ...staleData(
          data,
          `The newest reading is older than ${input.max_age_seconds} seconds. Do not use it to conclude the equipment is safe or fixed.`,
          provenance,
        ),
        resultCount: checked.length,
      };
    }
    return {
      status: "OK",
      data,
      provenance,
      resultCount: checked.length,
    };
  },
});
