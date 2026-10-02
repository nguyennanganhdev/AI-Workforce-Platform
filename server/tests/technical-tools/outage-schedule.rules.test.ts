import { describe, expect, test } from "bun:test";
import type { InterruptionRecord } from "../../src/technical-tools/domain/interruption";
import {
  isWellFormed,
  selectOutagesAt,
  selectSchedulesWithin,
} from "../../src/technical-tools/tools/interruption-rules";

/**
 * The rules that decide which interruptions are reported, with no database in the way.
 *
 * Every interruption here is planned for 10:00-12:00 and, where it ran, ran 10:05-11:40. The tests
 * move the question around that one window, so a wrong boundary shows up as one failing row rather
 * than as a fixture nobody can work out.
 */
const at = (time: string) => new Date(`2026-09-30T${time}:00Z`);

function interruption(
  overrides: Partial<InterruptionRecord> & { status: string },
): InterruptionRecord {
  return {
    id: `id-${overrides.status}`,
    utility: "water",
    plannedStart: at("10:00"),
    plannedEnd: at("12:00"),
    actualStart: null,
    actualEnd: null,
    updatedAt: at("09:00"),
    scopeIds: ["scope"],
    ...overrides,
  };
}

const reportedAt = (record: InterruptionRecord, time: string) =>
  selectOutagesAt([record], at(time)).length === 1;

describe("which interruptions count as an outage at a moment", () => {
  describe("active: from when it started until somebody records the restoration", () => {
    const active = interruption({
      status: "active",
      actualStart: at("10:05"),
    });

    test.each([
      ["before it started", "10:04", false],
      ["the minute it started", "10:05", true],
      ["while it runs", "11:00", true],
      ["past its planned end, still not restored", "13:30", true],
    ])("%s", (_label, time, expected) => {
      expect(reportedAt(active, time)).toBe(expected);
    });

    test("with no recorded start, the planned start stands in", () => {
      const unstamped = interruption({ status: "active" });
      expect(reportedAt(unstamped, "09:59")).toBe(false);
      expect(reportedAt(unstamped, "10:00")).toBe(true);
    });
  });

  describe("restored: only the hours it actually ran", () => {
    const restored = interruption({
      status: "restored",
      actualStart: at("10:05"),
      actualEnd: at("11:40"),
    });

    test.each([
      ["before it started", "10:04", false],
      ["the minute it started", "10:05", true],
      ["while it ran", "11:00", true],
      ["the minute it was restored", "11:40", false],
      ["after restoration but inside the plan", "11:50", false],
    ])("%s", (_label, time, expected) => {
      expect(reportedAt(restored, time)).toBe(expected);
    });
  });

  describe.each(["approved", "notified"])(
    "%s: the planned window, since nothing has happened yet",
    (status) => {
      const planned = interruption({ status });

      test.each([
        ["before the plan", "09:59", false],
        ["the minute the plan begins", "10:00", true],
        ["inside the plan", "11:00", true],
        ["the minute the plan ends", "12:00", false],
      ])("%s", (_label, time, expected) => {
        expect(reportedAt(planned, time)).toBe(expected);
      });
    },
  );

  /*
   * The two that must never appear. A proposal is somebody asking; treating it as an outage is how
   * an agent ends up telling a resident the water is off while it is still running.
   */
  test.each(["proposed", "cancelled"])(
    "%s is never an outage, even inside its window",
    (status) => {
      const record = interruption({ status, actualStart: at("10:05") });
      expect(reportedAt(record, "11:00")).toBe(false);
    },
  );

  test("a status the table does not define is not an outage either", () => {
    expect(reportedAt(interruption({ status: "draft" }), "11:00")).toBe(false);
  });

  test("outages come back earliest first, by when they actually began", () => {
    const later = interruption({
      id: "later",
      status: "active",
      actualStart: at("10:30"),
    });
    const earlier = interruption({
      id: "earlier",
      status: "active",
      plannedStart: at("10:45"),
      plannedEnd: at("12:30"),
      actualStart: at("10:10"),
    });
    expect(
      selectOutagesAt([later, earlier], at("11:00")).map((r) => r.id),
    ).toEqual(["earlier", "later"]);
  });
});

describe("which interruptions count as a schedule inside a window", () => {
  const scheduled = interruption({ status: "notified" });
  const within = (record: InterruptionRecord, from: string, to: string) =>
    selectSchedulesWithin([record], at(from), at(to)).length === 1;

  test.each([
    ["a window that ends as the plan begins", "08:00", "10:00", false],
    ["a window that reaches one minute into the plan", "08:00", "10:01", true],
    ["a window inside the plan", "10:30", "11:00", true],
    ["a window that contains the plan", "09:00", "13:00", true],
    ["a window that begins in the plan's last minute", "11:59", "13:00", true],
    ["a window that begins as the plan ends", "12:00", "13:00", false],
  ])("%s", (_label, from, to, expected) => {
    expect(within(scheduled, from, to)).toBe(expected);
  });

  test.each([
    ["approved", true],
    ["notified", true],
    ["active", true],
    ["restored", true],
    ["proposed", false],
    ["cancelled", false],
  ])("a %s interruption inside the window", (status, expected) => {
    expect(within(interruption({ status }), "09:00", "13:00")).toBe(expected);
  });

  /*
   * An outage that has overrun is still reported by the outage tool. The schedule tool answers a
   * different question, what was planned, so it goes by the plan and not by how things turned out.
   */
  test("goes by the planned times, not by when the cut really happened", () => {
    const overrun = interruption({
      status: "active",
      actualStart: at("10:05"),
    });
    expect(within(overrun, "13:00", "14:00")).toBe(false);
    expect(reportedAt(overrun, "13:30")).toBe(true);
  });

  test("schedules come back earliest planned first", () => {
    const second = interruption({
      id: "second",
      status: "approved",
      plannedStart: at("11:00"),
      plannedEnd: at("11:30"),
    });
    const first = interruption({ id: "first", status: "notified" });
    expect(
      selectSchedulesWithin([second, first], at("09:00"), at("13:00")).map(
        (r) => r.id,
      ),
    ).toEqual(["first", "second"]);
  });
});

/*
 * The table has no CHECK that `planned_end` follows `planned_start`, so such a row can exist. A
 * plain overlap test matches it against any window at all: it "starts before the window ends" and
 * "ends after the window starts" for windows on either side of it.
 */
describe("a row whose times contradict themselves", () => {
  const backwards = interruption({
    status: "notified",
    plannedStart: at("12:00"),
    plannedEnd: at("10:00"),
  });

  test("is recognised as malformed", () => {
    expect(isWellFormed(backwards)).toBe(false);
    expect(isWellFormed(interruption({ status: "notified" }))).toBe(true);
  });

  test("is left out of schedules it would otherwise overlap", () => {
    expect(
      selectSchedulesWithin([backwards], at("09:00"), at("13:00")),
    ).toEqual([]);
  });

  test("is left out of outages", () => {
    expect(selectOutagesAt([backwards], at("11:00"))).toEqual([]);
  });

  test("so is one restored before it started", () => {
    const record = interruption({
      status: "restored",
      actualStart: at("11:00"),
      actualEnd: at("10:30"),
    });
    expect(isWellFormed(record)).toBe(false);
    expect(selectOutagesAt([record], at("10:45"))).toEqual([]);
  });
});
