import type {
  ReadingQuality,
  Sensor,
  SensorReading,
} from "../../../src/technical-tools";
import { BUILDING, TENANT } from "./world";

/**
 * The sensors of the sample estate and what they reported around 30/09/2026 09:00 UTC (`NOW`).
 *
 * Each sensor is here for one thing `sensor.read` could get wrong: reporting old data as current,
 * hiding a bad reading, trusting a reading in the wrong unit, or dumping a whole morning of
 * readings into one answer.
 */
export const SENSORS: readonly Sensor[] = [
  {
    sensorId: "SNS-AC1-COND",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.a1,
    assetId: "AC-A1-1205-01",
    metric: "condensate_level",
    unit: "mm",
  },
  {
    sensorId: "SNS-AC2-COND",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.a1,
    assetId: "AC-A1-1205-02",
    metric: "condensate_level",
    unit: "mm",
  },
  {
    sensorId: "SNS-WH1-TEMP",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.a1,
    assetId: "WH-A1-1205-01",
    metric: "outlet_temperature",
    unit: "C",
  },
  {
    sensorId: "SNS-WF1-FLOW",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.a1,
    assetId: "WF-A1-1205-01",
    metric: "flow_rate",
    unit: "L/min",
  },
  {
    sensorId: "SNS-BP12-CUR",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.a1,
    assetId: "BP-A1-COMMON-12",
    metric: "leakage_current",
    unit: "mA",
  },
  {
    sensorId: "SNS-BP1-CUR-A",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.a1,
    assetId: "BP-A1-1205-01",
    metric: "leakage_current",
    unit: "mA",
  },
  {
    sensorId: "SNS-BP1-CUR-B",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.a1,
    assetId: "BP-A1-1205-01",
    metric: "leakage_current",
    unit: "mA",
  },
  {
    // Measures a wall, not a machine.
    sensorId: "SNS-1205-HUM",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.a1,
    assetId: null,
    metric: "surface_moisture",
    unit: "%",
  },
  {
    sensorId: "SNS-B1-COND",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.b1,
    assetId: "AC-B1-0501-01",
    metric: "condensate_level",
    unit: "mm",
  },
  {
    sensorId: "SNS-X1-COND",
    tenantId: TENANT.other,
    buildingId: BUILDING.x1,
    assetId: "AC-X1-0101-01",
    metric: "condensate_level",
    unit: "mm",
  },
];

const reading = (
  sensorId: string,
  metric: string,
  iso: string,
  value: number,
  unit: string,
  quality: ReadingQuality = "good",
): SensorReading => ({
  sensorId,
  metric,
  value,
  unit,
  observedAt: new Date(iso),
  quality,
});

/**
 * One reading a minute from 03:00 to 08:59: 360 of them, more than one answer carries. Asked for
 * the whole morning the tool must ask for a narrower window; asked for the last hour it answers.
 */
const aMinuteApart = Array.from({ length: 360 }, (_, minute) =>
  reading(
    "SNS-AC2-COND",
    "condensate_level",
    new Date(Date.UTC(2026, 8, 30, 3, minute)).toISOString(),
    3 + minute / 100,
    "mm",
  ),
);

export const READINGS: readonly SensorReading[] = [
  // Rising through the hour before the call: the drain is filling.
  reading(
    "SNS-AC1-COND",
    "condensate_level",
    "2026-09-30T08:08:00Z",
    4.1,
    "mm",
  ),
  reading(
    "SNS-AC1-COND",
    "condensate_level",
    "2026-09-30T08:18:00Z",
    5.0,
    "mm",
  ),
  reading(
    "SNS-AC1-COND",
    "condensate_level",
    "2026-09-30T08:28:00Z",
    6.2,
    "mm",
  ),
  reading(
    "SNS-AC1-COND",
    "condensate_level",
    "2026-09-30T08:38:00Z",
    7.9,
    "mm",
  ),
  reading(
    "SNS-AC1-COND",
    "condensate_level",
    "2026-09-30T08:48:00Z",
    9.6,
    "mm",
  ),
  reading(
    "SNS-AC1-COND",
    "condensate_level",
    "2026-09-30T08:58:00Z",
    12.4,
    "mm",
  ),

  ...aMinuteApart,

  // Nothing since 07:30. At 09:00 that is ninety minutes, far past the default fifteen.
  reading(
    "SNS-WH1-TEMP",
    "outlet_temperature",
    "2026-09-30T07:00:00Z",
    38.5,
    "C",
  ),
  reading(
    "SNS-WH1-TEMP",
    "outlet_temperature",
    "2026-09-30T07:15:00Z",
    39.0,
    "C",
  ),
  reading(
    "SNS-WH1-TEMP",
    "outlet_temperature",
    "2026-09-30T07:30:00Z",
    38.2,
    "C",
  ),

  // Only yesterday's. Asked about today, it has nothing to say.
  reading("SNS-WF1-FLOW", "flow_rate", "2026-09-29T10:00:00Z", 1.4, "L/min"),

  // The newest reading is a spike the sensor itself flags as bad.
  reading("SNS-BP12-CUR", "leakage_current", "2026-09-30T08:40:00Z", 12, "mA"),
  reading("SNS-BP12-CUR", "leakage_current", "2026-09-30T08:50:00Z", 14, "mA"),
  reading(
    "SNS-BP12-CUR",
    "leakage_current",
    "2026-09-30T08:59:00Z",
    180,
    "mA",
    "bad",
  ),

  // Two sensors on one panel, reporting a few minutes apart.
  reading("SNS-BP1-CUR-A", "leakage_current", "2026-09-30T08:50:00Z", 8, "mA"),
  reading(
    "SNS-BP1-CUR-B",
    "leakage_current",
    "2026-09-30T08:52:00Z",
    7.5,
    "mA",
  ),
  reading(
    "SNS-BP1-CUR-B",
    "leakage_current",
    "2026-09-30T08:58:00Z",
    7.8,
    "mA",
  ),
  reading("SNS-BP1-CUR-A", "leakage_current", "2026-09-30T08:59:00Z", 9, "mA"),

  // The second reading arrives in degrees: the source calls it good, the unit says otherwise.
  reading("SNS-1205-HUM", "surface_moisture", "2026-09-30T08:30:00Z", 22, "%"),
  reading("SNS-1205-HUM", "surface_moisture", "2026-09-30T08:55:00Z", 24, "C"),

  reading("SNS-B1-COND", "condensate_level", "2026-09-30T08:55:00Z", 3.3, "mm"),
  reading("SNS-X1-COND", "condensate_level", "2026-09-30T08:55:00Z", 5.5, "mm"),
];
