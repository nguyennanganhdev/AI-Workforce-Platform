import { describe, expect, test } from "bun:test";
import {
  createInMemoryAssetReadPort,
  createInMemoryMaintenanceReadPort,
  createInMemorySensorReadPort,
  type SensorReadPort,
  type ToolDependencies,
} from "../../src/technical-tools";
import { ASSETS } from "./fixtures/assets";
import { MAINTENANCE_EVENTS } from "./fixtures/maintenance";
import { READINGS, SENSORS } from "./fixtures/sensors";
import { AGENT_VERSION, BUILDING, CALLER, NOW, TENANT } from "./fixtures/world";
import { technicalToolHarness } from "./support/harness";

/**
 * `sensor.read` and `maintenance_history.read` end to end: through the function
 * `/api/agent-tools/call` is handed, the host's checks, the in-memory adapters and back out as
 * the envelope the agent reads.
 *
 * No database: neither has a table yet. The adapters are given the test's catalogue, so nothing
 * invented ships in the module.
 */
const ports: Partial<ToolDependencies> = {
  assets: createInMemoryAssetReadPort(ASSETS),
  sensors: createInMemorySensorReadPort(SENSORS, READINGS),
  maintenance: createInMemoryMaintenanceReadPort(MAINTENANCE_EVENTS),
};

const SENSOR = "sensor/read";
const HISTORY = "maintenance_history/read";

const today = (from: string, to = "09:00") => ({
  from: `2026-09-30T${from}:00Z`,
  to: `2026-09-30T${to}:00Z`,
});

const sensorByAsset = (
  asset_id: string,
  metric: string,
  time_range: { from: string; to: string },
  rest: Record<string, unknown> = {},
) => ({ building_id: BUILDING.a1, asset_id, metric, time_range, ...rest });

const history = (
  asset_id: string,
  from: string,
  rest: Record<string, unknown> = {},
) => ({
  building_id: BUILDING.a1,
  asset_id,
  time_range: { from, to: NOW.toISOString() },
  ...rest,
});

type Reading = {
  sensor_id: string;
  value: number;
  unit: string;
  observed_at: string;
  quality: string;
};

const readingsOf = (data: unknown) =>
  (data as { readings: Reading[] }).readings;

type History = {
  events: { event_id: string; outcome: string }[];
  last_maintenance_at: string | null;
  repeat_count: number;
};

/*
 * Level 3 is routine. Sensor data can settle a question remotely, and an empty history says this
 * is the first time.
 */
describe("level 3: a routine fault", () => {
  test("L3-11: máy lọc nước chạy yếu — no history, so this is the first time", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope, isError } = await harness.call(
      HISTORY,
      history("WF-A1-1205-01", "2026-01-01T00:00:00Z"),
    );

    expect(envelope.status).toBe("OK");
    expect(isError).toBe(false);
    expect(envelope.data).toEqual({
      events: [],
      last_maintenance_at: null,
      repeat_count: 0,
    });
  });

  /*
   * general.md §11: data too old is marked stale and is never the basis for a safety conclusion.
   * The readings still come back, because a technician can use them and hiding them would hide
   * that the sensor went quiet at 07:30.
   */
  test("L3-12: máy nước nóng không nóng — the sensor went quiet, so nothing is concluded remotely", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope, isError } = await harness.call(
      SENSOR,
      sensorByAsset("WH-A1-1205-01", "outlet_temperature", today("06:00")),
    );

    expect(envelope.status).toBe("STALE_DATA");
    // An answer the agent acts on, not a failure.
    expect(isError).toBe(false);
    expect((envelope.data as { freshness: string }).freshness).toBe("stale");
    expect(readingsOf(envelope.data).map((r) => r.value)).toEqual([
      38.5, 39.0, 38.2,
    ]);
    expect(envelope.errors).toEqual([
      {
        code: "STALE_DATA",
        message:
          "The newest reading is older than 900 seconds. Do not use it to conclude the equipment is safe or fixed.",
        retryable: false,
      },
    ]);
  });

  test("L3-13: máy lọc nước, xem lưu lượng — the sensor sent nothing today", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      SENSOR,
      sensorByAsset("WF-A1-1205-01", "flow_rate", today("00:00")),
    );

    expect(envelope.status).toBe("OK");
    expect(envelope.data).toEqual({ readings: [], freshness: "unknown" });
    // Its silence is the finding, so the sensor that said nothing is still named.
    expect(envelope.provenance).toEqual([
      expect.objectContaining({ source_record_id: "SNS-WF1-FLOW" }),
    ]);
  });
});

describe("level 2: a fault that is spreading", () => {
  test("L2-11: điều hòa chảy nước — the drain level rising through the hour", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      SENSOR,
      sensorByAsset("AC-A1-1205-01", "condensate_level", today("08:00")),
    );

    expect(envelope.status).toBe("OK");
    expect((envelope.data as { freshness: string }).freshness).toBe("fresh");
    const values = readingsOf(envelope.data).map((r) => r.value);
    expect(values).toEqual([4.1, 5.0, 6.2, 7.9, 9.6, 12.4]);
    expect(values).toEqual([...values].sort((a, b) => a - b));
  });

  /*
   * The fault has come back twice this year. Cleaning the drain a third time is not a fix, and the
   * count is what lets the agent say so.
   */
  test("L2-12: điều hòa chảy nước lần nữa — a recurring fault, with the wrong entry corrected", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope, text } = await harness.call(
      HISTORY,
      history("AC-A1-1205-01", "2026-01-01T00:00:00Z"),
    );

    expect(envelope.status).toBe("OK");
    const data = envelope.data as History;
    expect(data.repeat_count).toBe(2);
    expect(data.events.map((e) => e.event_id)).toEqual([
      "ME-104",
      "ME-102",
      "ME-101",
    ]);
    expect(data.last_maintenance_at).toBe("2026-08-15T03:00:00.000Z");
    // Nobody replaced the pump; the entry that said so was corrected.
    expect(text).not.toContain("replaced_drain_pump");
    // The wrong entry is gone as an event, and the correction still says what it corrected.
    const corrected = data.events.find((e) => e.event_id === "ME-104") as
      | { source_refs: string[] }
      | undefined;
    expect(corrected?.source_refs).toContain("correction:ME-103");
  });

  test("L2-13: tường thấm, đo độ ẩm — a reading in degrees is shown but marked bad", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(SENSOR, {
      building_id: BUILDING.a1,
      sensor_id: "SNS-1205-HUM",
      metric: "surface_moisture",
      time_range: today("08:00"),
    });

    expect(envelope.status).toBe("OK");
    const readings = readingsOf(envelope.data);
    expect(readings).toEqual([
      expect.objectContaining({ value: 22, unit: "%", quality: "good" }),
      // Value and unit exactly as the sensor sent them; only the verdict changed.
      expect.objectContaining({ value: 24, unit: "C", quality: "bad" }),
    ]);
  });

  test("L2-14: the whole morning of a busy sensor is too much for one answer", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope, isError } = await harness.call(
      SENSOR,
      sensorByAsset("AC-A1-1205-02", "condensate_level", today("03:00")),
    );

    expect(envelope.status).toBe("NEEDS_INPUT");
    expect(isError).toBe(false);
    expect(envelope.missing_fields).toEqual(["time_range"]);
    // Not cut to two hundred: a cut list looks complete.
    expect(envelope.data).toBeNull();
    expect(envelope.errors[0]?.message).toContain("360 readings");
  });

  test("L2-15: and the last hour of it is answered", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      SENSOR,
      sensorByAsset("AC-A1-1205-02", "condensate_level", today("08:00")),
    );

    expect(envelope.status).toBe("OK");
    expect(readingsOf(envelope.data)).toHaveLength(60);
  });
});

/*
 * Level 1 is immediate danger. What these tools must not do is make the danger look smaller: a bad
 * spike hidden, or old service notes read as a clean bill of health.
 */
describe("level 1: immediate danger", () => {
  test("L1-11: ổ cắm tóe lửa — the spike the sensor flags as bad is reported, not hidden", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      SENSOR,
      sensorByAsset("BP-A1-COMMON-12", "leakage_current", today("08:30")),
    );

    expect(envelope.status).toBe("OK");
    const readings = readingsOf(envelope.data);
    expect(readings.at(-1)).toMatchObject({ value: 180, quality: "bad" });
    expect(readings).toHaveLength(3);
  });

  test("L1-12: the apartment panel's two sensors both report", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      SENSOR,
      sensorByAsset("BP-A1-1205-01", "leakage_current", today("08:30")),
    );

    expect(
      readingsOf(envelope.data).map((r) => [r.sensor_id, r.value]),
    ).toEqual([
      ["SNS-BP1-CUR-A", 8],
      ["SNS-BP1-CUR-B", 7.5],
      ["SNS-BP1-CUR-B", 7.8],
      ["SNS-BP1-CUR-A", 9],
    ]);
    expect(envelope.provenance.map((p) => p.source_record_id).sort()).toEqual([
      "SNS-BP1-CUR-A",
      "SNS-BP1-CUR-B",
    ]);
  });

  /*
   * No work in the last thirty days is not the same as never serviced. The breaker was replaced
   * last November, and an agent told only "no events" might say otherwise to the person on duty.
   */
  test("L1-13: cầu dao tóe lửa — nothing this month, but the last service is still named", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      HISTORY,
      history("BP-A1-1205-01", "2026-08-31T09:00:00Z"),
    );

    expect(envelope.data).toEqual({
      events: [],
      last_maintenance_at: "2025-11-20T06:00:00.000Z",
      repeat_count: 0,
    });
  });

  test("L1-14: a sensor feed that fails mid-incident is a retryable error, not a hang", async () => {
    const failing: SensorReadPort = {
      find: async () => {
        throw new Error("BMS gateway 10.0.4.12 refused the connection");
      },
    };
    const harness = technicalToolHarness({ ...ports, sensors: failing });
    const { envelope, isError, text } = await harness.call(
      SENSOR,
      sensorByAsset("BP-A1-1205-01", "leakage_current", today("08:30")),
    );

    expect(envelope.status).toBe("INTERNAL_ERROR");
    expect(isError).toBe(true);
    expect(envelope.errors[0]?.retryable).toBe(true);
    expect(text).not.toContain("10.0.4.12");
  });

  test("L1-15: a feed that never answers is given up on", async () => {
    const hanging: SensorReadPort = { find: () => new Promise(() => {}) };
    const harness = technicalToolHarness(
      { ...ports, sensors: hanging },
      { options: { timeoutMs: 50 } },
    );
    const started = performance.now();
    const { envelope } = await harness.call(
      SENSOR,
      sensorByAsset("BP-A1-1205-01", "leakage_current", today("08:30")),
    );

    expect(envelope.status).toBe("INTERNAL_ERROR");
    expect(performance.now() - started).toBeLessThan(2_000);
  });
});

describe("what does not exist", () => {
  test("a metric no sensor on the asset measures is NOT_FOUND, not an empty list", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      SENSOR,
      sensorByAsset("AC-A1-1205-01", "outlet_temperature", today("08:00")),
    );

    expect(envelope.status).toBe("NOT_FOUND");
    expect(envelope.errors[0]?.field).toBe("asset_id");
  });

  test("an unknown sensor id is NOT_FOUND on sensor_id", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(SENSOR, {
      building_id: BUILDING.a1,
      sensor_id: "SNS-DOES-NOT-EXIST",
      metric: "condensate_level",
      time_range: today("08:00"),
    });

    expect(envelope.status).toBe("NOT_FOUND");
    expect(envelope.errors[0]?.field).toBe("sensor_id");
  });

  /*
   * "No repairs on record" for a machine that does not exist is an answer an agent would repeat to
   * a resident, so the asset is checked before the history is read.
   */
  test("history of an asset that is not in the building is NOT_FOUND, not empty", async () => {
    const harness = technicalToolHarness(ports);
    for (const asset of ["AC-A1-9999-99", "AC-B1-0501-01"]) {
      const { envelope } = await harness.call(
        HISTORY,
        history(asset, "2026-01-01T00:00:00Z"),
      );
      expect(envelope.status).toBe("NOT_FOUND");
      expect(envelope.errors[0]?.field).toBe("asset_id");
    }
  });
});

describe("a page of history", () => {
  test("is cut to the limit while the repeat count covers the whole window", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      HISTORY,
      history("AC-A1-1105-01", "2026-01-01T00:00:00Z"),
    );

    const data = envelope.data as History;
    expect(data.events).toHaveLength(20);
    // Thirteen of the twenty-five were raised by an incident.
    expect(data.repeat_count).toBe(13);
    expect(data.events[0]?.event_id).toBe("ME-1105-25");
  });

  test("a smaller limit changes the page and nothing else", async () => {
    const harness = technicalToolHarness(ports);
    const { envelope } = await harness.call(
      HISTORY,
      history("AC-A1-1105-01", "2026-01-01T00:00:00Z", { limit: 5 }),
    );

    const data = envelope.data as History;
    expect(data.events).toHaveLength(5);
    expect(data.repeat_count).toBe(13);
  });
});

describe("a building or a tenant the caller may not ask about", () => {
  test.each([
    ["in the same tenant but outside the grant", BUILDING.b1],
    ["in another tenant", BUILDING.x1],
    ["nowhere at all", BUILDING.missing],
  ])("a building %s is refused alike by both tools", async (_label, id) => {
    const harness = technicalToolHarness(ports);
    const sensor = await harness.call(SENSOR, {
      building_id: id,
      asset_id: "AC-B1-0501-01",
      metric: "condensate_level",
      time_range: today("08:00"),
    });
    const past = await harness.call(HISTORY, {
      building_id: id,
      asset_id: "AC-B1-0501-01",
      time_range: { from: "2026-01-01T00:00:00Z", to: NOW.toISOString() },
    });

    for (const { envelope, text } of [sensor, past]) {
      expect(envelope.status).toBe("FORBIDDEN");
      expect(envelope.data).toBeNull();
      expect(text).not.toContain("3.3");
      expect(text).not.toContain("ME-B1-01");
    }
  });

  test.each([
    ["sensor.read", SENSOR, "sensor:read"],
    ["maintenance_history.read", HISTORY, "maintenance:read"],
  ])(
    "%s refuses a Bot never granted its capability",
    async (_n, tool, capability) => {
      const harness = technicalToolHarness(ports);
      const { envelope } = await harness.call(
        tool,
        tool === SENSOR
          ? sensorByAsset("AC-A1-1205-01", "condensate_level", today("08:00"))
          : history("AC-A1-1205-01", "2026-01-01T00:00:00Z"),
        CALLER.ungrantedAgent,
      );

      expect(envelope.status).toBe("FORBIDDEN");
      expect(harness.auditEntries[0]?.detail).toContain(capability);
    },
  );
});

describe("what an answer carries back", () => {
  /*
   * The adapters name themselves rather than the database or a real BMS, so an answer built from
   * sample data cannot pass for one read from a live feed.
   */
  test("provenance names the adapter each answer came from", async () => {
    const harness = technicalToolHarness(ports);
    const sensor = await harness.call(
      SENSOR,
      sensorByAsset("AC-A1-1205-01", "condensate_level", today("08:00")),
    );
    const past = await harness.call(
      HISTORY,
      history("AC-A1-1205-01", "2026-01-01T00:00:00Z"),
    );

    expect(sensor.envelope.provenance).toEqual([
      {
        source_system: "sensor_adapter",
        source_record_id: "SNS-AC1-COND",
        source_version: null,
        retrieved_at: NOW.toISOString(),
      },
    ]);
    expect(past.envelope.provenance).toEqual([
      {
        source_system: "maintenance_adapter",
        source_record_id: "AC-A1-1205-01",
        source_version: "ME-104",
        retrieved_at: NOW.toISOString(),
      },
    ]);
  });

  test("the audit trail records the calls, never the readings or the history", async () => {
    const harness = technicalToolHarness(ports);
    await harness.call(
      SENSOR,
      sensorByAsset("AC-A1-1205-01", "condensate_level", today("08:00")),
    );
    await harness.call(
      HISTORY,
      history("AC-A1-1205-01", "2026-01-01T00:00:00Z"),
    );

    expect(harness.auditEntries).toHaveLength(2);
    expect(
      harness.auditEntries.map((entry) => [
        entry.tool,
        entry.status,
        entry.result_count,
      ]),
    ).toEqual([
      ["sensor.read", "OK", 6],
      ["maintenance_history.read", "OK", 3],
    ]);
    for (const entry of harness.auditEntries) {
      expect(entry).toMatchObject({
        agent_version: AGENT_VERSION,
        tenant_id: TENANT.vinhomes,
        building_id: BUILDING.a1,
      });
    }
    const recorded = JSON.stringify(harness.auditEntries);
    expect(recorded).not.toContain("12.4");
    expect(recorded).not.toContain("cleaned_drain_line");
  });

  test("a STALE_DATA answer is recorded as such", async () => {
    const harness = technicalToolHarness(ports);
    await harness.call(
      SENSOR,
      sensorByAsset("WH-A1-1205-01", "outlet_temperature", today("06:00")),
    );

    expect(harness.auditEntries[0]).toMatchObject({
      status: "STALE_DATA",
      result_count: 3,
    });
  });
});

describe("the door the server opens to these tools", () => {
  test.each([
    ["sensor.read", "sensor__read", "sensor/read"],
    [
      "maintenance_history.read",
      "maintenance_history__read",
      "maintenance_history/read",
    ],
  ])("%s answers to each of its spellings", async (name, modelName, ref) => {
    for (const spelling of [name, modelName, ref]) {
      const harness = technicalToolHarness(ports);
      const { envelope } = await harness.call(
        spelling,
        name === "sensor.read"
          ? sensorByAsset("AC-A1-1205-01", "condensate_level", today("08:00"))
          : history("AC-A1-1205-01", "2026-01-01T00:00:00Z"),
      );
      expect(envelope.status).toBe("OK");
    }
  });
});
