import { describe, expect, test } from "vitest";
import { shouldPoll } from "../src/features/vinhomes-operations/connected/polling";

describe("when the work list is asked for again", () => {
  test("a visible tab asks every 5 seconds", () => {
    expect([1, 2, 3, 4, 5, 6, 7].map((tick) => shouldPoll(tick, false, false))).toEqual(Array(7).fill(true));
  });
  test("a hidden tab asks every 30 seconds", () => {
    expect([1, 2, 3, 4, 5, 6, 7, 12].map((tick) => shouldPoll(tick, true, false))).toEqual([false, false, false, false, false, true, false, true]);
  });
  test("nothing is asked while a change is being saved", () => {
    expect(shouldPoll(6, false, true)).toBe(false);
    expect(shouldPoll(6, true, true)).toBe(false);
  });
});
