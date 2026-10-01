import { describe, expect, test } from "bun:test";
import type {
  MaintenanceEvent,
  SensorReading,
} from "../../src/technical-tools";
import { unitAccepted } from "../../src/technical-tools";
import {
  currentEvents,
  summarise,
} from "../../src/technical-tools/tools/maintenance-rules";
import {
  freshnessOf,
  freshnessReference,
  readingsWithin,
  withUnitChecked,
} from "../../src/technical-tools/tools/sensor-rules";

/**
 * The rules that decide which readings may be trusted and what the history says, with no adapter
 * in the way.
 *
 * The failure worth guarding hardest is the quiet one: a stale reading reported as fresh, a bad
 * reading hidden, a corrected entry reported as fact. Each of those reads as a normal answer.
 */
const at = (time: string) => new Date(`2026-09-30T${time}:00Z`);

function reading(
  time: string,
  overrides: Partial<SensorReading> = {},
): SensorReading {
  return {
    sensorId: "SNS-1",
    metric: "condensate_level",
    value: 10,
    unit: "mm",
    observedAt: at(time),
    quality: "good",
    ...overrides,
  };
}

describe("how old a reading may be", () => {
  const FIFTEEN_MINUTES = 900;

  test.each([
    ["taken a minute ago", "08:59", "fresh"],
    ["exactly at the limit", "08:45", "fresh"],
    ["one second past the limit", "08:44:59", "stale"],
    ["taken an hour and a half ago", "07:30", "stale"],
  ])("a reading %s", (_label, time, expected) => {
    const observed =
      time.length > 5 ? new Date(`2026-09-30T${time}Z`) : at(time);
    expect(
      freshnessOf(
        [reading("00:00", { observedAt: observed })],
        at("09:00"),
        FIFTEEN_MINUTES,
      ),
    ).toBe(expected);
  });

  test("only the newest reading decides", () => {
    const readings = [reading("06:00"), reading("08:58")];
    expect(freshnessOf(readings, at("09:00"), FIFTEEN_MINUTES)).toBe("fresh");
  });

  /*
   * No readings is a different fact from old readings: nothing arrived, rather than something
   * arrived late. Calling it stale would suggest there was data to be wary of.
   */
  test("no readings at all is unknown, not stale", () => {
    expect(freshnessOf([], at("09:00"), FIFTEEN_MINUTES)).toBe("unknown");
  });

  test("the limit is whatever the caller asked for", () => {
    const oneHourOld = [reading("08:00")];
    expect(freshnessOf(oneHourOld, at("09:00"), 900)).toBe("stale");
    expect(freshnessOf(oneHourOld, at("09:00"), 3_600)).toBe("fresh");
  });
});

/*
 * A question about yesterday's incident asks whether the sensor was reporting at the time, not
 * whether it is reporting now. Measured from now, every reading of yesterday would be stale,
 * including the ones taken at the minute the incident happened.
 */
describe("the moment a reading's age is measured from", () => {
  const now = at("09:00");

  test("the end of a window in the past", () => {
    const yesterday = new Date("2026-09-29T16:00:00Z");
    expect(freshnessReference(yesterday, now)).toEqual(yesterday);
  });

  test("now, when the window runs into the future", () => {
    expect(freshnessReference(at("12:00"), now)).toEqual(now);
  });

  test("so yesterday's readings are fresh for a question about yesterday", () => {
    const end = new Date("2026-09-29T16:00:00Z");
    const taken = [
      reading("00:00", { observedAt: new Date("2026-09-29T15:55:00Z") }),
    ];
    expect(freshnessOf(taken, freshnessReference(end, now), 900)).toBe("fresh");
    // Asked about now, the same reading is seventeen hours old.
    expect(freshnessOf(taken, freshnessReference(now, now), 900)).toBe("stale");
  });
});

describe("which readings fall in the window", () => {
  test("from its start up to but not including its end, earliest first", () => {
    const readings = [
      reading("09:00"),
      reading("08:30"),
      reading("08:00"),
      reading("07:59"),
    ];
    expect(
      readingsWithin(readings, at("08:00"), at("09:00")).map((r) =>
        r.observedAt.toISOString(),
      ),
    ).toEqual([at("08:00").toISOString(), at("08:30").toISOString()]);
  });

  /*
   * The window is about time, not trust. A reading the sensor flags as bad or uncertain is still
   * a reading: dropping it here would hide from the agent that a sensor is reporting nonsense,
   * which on a breaker panel is itself a reason to send somebody.
   */
  test("keeps readings of every quality, bad ones included", () => {
    const readings = [
      reading("08:10", { quality: "good" }),
      reading("08:20", { quality: "uncertain" }),
      reading("08:30", { quality: "bad" }),
      reading("08:40", { quality: "unknown" }),
    ];
    expect(
      readingsWithin(readings, at("08:00"), at("09:00")).map((r) => r.quality),
    ).toEqual(["good", "uncertain", "bad", "unknown"]);
  });

  test("two sensors at the same minute come back in a stable order", () => {
    const readings = [
      reading("08:30", { sensorId: "SNS-B" }),
      reading("08:30", { sensorId: "SNS-A" }),
    ];
    expect(
      readingsWithin(readings, at("08:00"), at("09:00")).map((r) => r.sensorId),
    ).toEqual(["SNS-A", "SNS-B"]);
  });
});

describe("a reading in the wrong unit", () => {
  test("is kept, value and unit untouched, and marked bad", () => {
    const wrong = reading("08:55", {
      metric: "surface_moisture",
      value: 24,
      unit: "C",
    });
    expect(withUnitChecked(wrong)).toEqual({ ...wrong, quality: "bad" });
  });

  test("a reading in an accepted unit keeps the quality the source gave it", () => {
    const right = reading("08:55", { quality: "uncertain" });
    expect(withUnitChecked(right)).toEqual(right);
  });

  /*
   * An unlisted metric has no rule to break. Marking its readings bad would punish a sensor for
   * the list being short, which is a gap for the Domain Owner to fill, not a fault in the data.
   */
  test("a metric the list does not know is left as the source gave it", () => {
    const unlisted = reading("08:55", { metric: "vibration", unit: "mm/s" });
    expect(unitAccepted("vibration", "mm/s")).toBeUndefined();
    expect(withUnitChecked(unlisted)).toEqual(unlisted);
  });

  test("a reading the source already called bad stays bad", () => {
    const bad = reading("08:55", { quality: "bad" });
    expect(withUnitChecked(bad).quality).toBe("bad");
  });
});

function event(
  eventId: string,
  date: string,
  overrides: Partial<MaintenanceEvent> = {},
): MaintenanceEvent {
  return {
    eventId,
    tenantId: "t",
    buildingId: "b",
    assetId: "AC-1",
    incidentId: null,
    workorderId: null,
    occurredAt: new Date(`${date}T00:00:00Z`),
    outcome: "cleaned",
    sourceRefs: [],
    supersedesEventId: null,
    ...overrides,
  };
}

describe("which events are still the record", () => {
  test("a corrected entry gives way to its correction", () => {
    const events = [
      event("E1", "2026-08-15", { outcome: "replaced_pump" }),
      event("E2", "2026-08-15", { supersedesEventId: "E1" }),
    ];
    expect(currentEvents(events).map((e) => e.eventId)).toEqual(["E2"]);
  });

  test("a chain of corrections leaves only the last", () => {
    const events = [
      event("E1", "2026-08-15"),
      event("E2", "2026-08-15", { supersedesEventId: "E1" }),
      event("E3", "2026-08-15", { supersedesEventId: "E2" }),
    ];
    expect(currentEvents(events).map((e) => e.eventId)).toEqual(["E3"]);
  });
});

describe("what the history reports for a window", () => {
  const from = new Date("2026-01-01T00:00:00Z");
  const to = new Date("2026-09-30T09:00:00Z");

  test("newest first", () => {
    const summary = summarise(
      [event("E1", "2026-03-01"), event("E2", "2026-07-02")],
      from,
      to,
      20,
    );
    expect(summary.events.map((e) => e.eventId)).toEqual(["E2", "E1"]);
  });

  /*
   * A repeat is a fault that came back. Scheduled upkeep is not one, and counting it would make a
   * well-kept machine look like a failing one.
   */
  test("counts as repeats only the events an incident raised", () => {
    const summary = summarise(
      [
        event("E1", "2026-03-01"),
        event("E2", "2026-07-02", { incidentId: "I1" }),
        event("E3", "2026-08-15", { incidentId: "I2" }),
      ],
      from,
      to,
      20,
    );
    expect(summary.repeatCount).toBe(2);
  });

  test("counts repeats over the whole window, not over the page", () => {
    const events = Array.from({ length: 10 }, (_, n) =>
      event(`E${n}`, `2026-0${1 + (n % 9)}-10`, { incidentId: `I${n}` }),
    );
    const summary = summarise(events, from, to, 3);
    expect(summary.events).toHaveLength(3);
    expect(summary.repeatCount).toBe(10);
  });

  test("a corrected entry is neither reported nor counted", () => {
    const summary = summarise(
      [
        event("E1", "2026-08-15", {
          incidentId: "I1",
          outcome: "replaced_pump",
        }),
        event("E2", "2026-08-15", {
          incidentId: "I1",
          supersedesEventId: "E1",
        }),
      ],
      from,
      to,
      20,
    );
    expect(summary.events.map((e) => e.eventId)).toEqual(["E2"]);
    expect(summary.repeatCount).toBe(1);
  });

  test("events outside the window are left out, on both sides", () => {
    const summary = summarise(
      [
        event("before", "2025-12-31"),
        event("inside", "2026-06-01"),
        event("after", "2026-10-01"),
      ],
      from,
      to,
      20,
    );
    expect(summary.events.map((e) => e.eventId)).toEqual(["inside"]);
  });

  /*
   * Bounded by `from`, a question about the last thirty days would answer null for equipment
   * serviced last year — which an agent would read as "never serviced".
   */
  test("the last service date reaches back before the window", () => {
    const summary = summarise(
      [event("old", "2025-11-20")],
      new Date("2026-08-31T00:00:00Z"),
      to,
      20,
    );
    expect(summary.events).toEqual([]);
    expect(summary.lastMaintenanceAt).toEqual(new Date("2025-11-20T00:00:00Z"));
  });

  test("but never past the window's end", () => {
    const summary = summarise([event("later", "2026-10-01")], from, to, 20);
    expect(summary.lastMaintenanceAt).toBeNull();
  });

  test("an asset with no history has no last service and no repeats", () => {
    expect(summarise([], from, to, 20)).toEqual({
      events: [],
      lastMaintenanceAt: null,
      repeatCount: 0,
    });
  });
});
