import { BUILDING } from "./world";

export type ToolCall =
  | {
      tool: "technical.get_active_outage";
      args: { building_id: string; service_type: string; occurred_at: string };
      /** Interruption fixture keys, in the order the tool must return them. */
      expect: readonly string[];
    }
  | {
      tool: "utility_schedule.read";
      args: {
        building_id: string;
        utility_type: string;
        time_range: { from: string; to: string };
      };
      expect: readonly string[];
    };

export type LevelCase = {
  id: string;
  /** Level 1 is immediate danger, 2 is spreading or significant, 3 is routine (general.md §3). */
  level: 1 | 2 | 3;
  issueCode: string;
  /** What the resident reported. Times in the reports are UTC, like the fixtures. */
  report: string;
  /** What the agent needs these calls for at this level. */
  why: string;
  calls: readonly ToolCall[];
};

const outage = (
  building_id: string,
  service_type: "water" | "power",
  occurred_at: string,
  expect: readonly string[],
): ToolCall => ({
  tool: "technical.get_active_outage",
  args: { building_id, service_type, occurred_at },
  expect,
});

const schedule = (
  building_id: string,
  utility_type: "water" | "power",
  from: string,
  to: string,
  expect: readonly string[],
): ToolCall => ({
  tool: "utility_schedule.read",
  args: { building_id, utility_type, time_range: { from, to } },
  expect,
});

/**
 * Concrete incidents by severity level, each with the calls Technical Agent A2 makes at that point
 * in the flow (general.md §6 step 6, §10) and exactly what must come back.
 */
export const LEVEL_CASES: readonly LevelCase[] = [
  {
    id: "L3-1",
    level: 3,
    issueCode: "TECH.PLUMB.SUPPLY_DRAIN_JOINT",
    report: "Vòi bếp căn A1-1205 chảy rất yếu từ 08:30.",
    why: "Rule out a building-wide cut before sending a technician to one apartment.",
    calls: [outage(BUILDING.a1, "water", "2026-09-30T08:30:00Z", ["I1"])],
  },
  {
    id: "L3-2",
    level: 3,
    issueCode: "TECH.ELEC.FIXTURE_FAILURE",
    report: "Ổ cắm và đèn căn A2-0803 không có điện lúc 09:00.",
    why: "The cut was declared for zone S1, not for building A2 by name.",
    calls: [outage(BUILDING.a2, "power", "2026-09-30T09:00:00Z", ["I6"])],
  },
  {
    id: "L3-3",
    level: 3,
    issueCode: "TECH.PLUMB.WATER_HEATER",
    report:
      "Máy nước nóng căn A1-1205 không nóng; cư dân hỏi ngày mai có cắt điện không để hẹn thợ.",
    why: "Book the repair around the announced cut, ignoring the cancelled and the malformed one.",
    calls: [
      schedule(
        BUILDING.a1,
        "power",
        "2026-10-01T00:00:00Z",
        "2026-10-02T00:00:00Z",
        ["I2"],
      ),
    ],
  },
  {
    id: "L3-4",
    level: 3,
    issueCode: "TECH.ELEC.FIXTURE_FAILURE",
    report: "Đèn hành lang căn A1-1205 không sáng từ 07:00.",
    why: "Nothing was cut at that hour, so the agent carries on to the SOP for the fixture.",
    calls: [outage(BUILDING.a1, "power", "2026-09-30T07:00:00Z", [])],
  },
  {
    id: "L2-1",
    level: 2,
    issueCode: "TECH.ELEC.BREAKER_TRIP",
    report: "Cầu dao căn A1-1205 nhảy liên tục, 09:00 vẫn chưa có điện.",
    why: "Tell a tripping breaker from a zone that has lost power.",
    calls: [outage(BUILDING.a1, "power", "2026-09-30T09:00:00Z", ["I6"])],
  },
  {
    id: "L2-2",
    level: 2,
    issueCode: "TECH.PLUMB.SEWAGE_BACKFLOW",
    report: "Nước thải trào ngược ở phễu thu sàn WC căn A1-1205 lúc 09:00.",
    why: "The outage check general.md §10.5 requires before the agent plans anything.",
    calls: [outage(BUILDING.a1, "water", "2026-09-30T09:00:00Z", ["I1"])],
  },
  {
    id: "L2-3",
    level: 2,
    issueCode: "TECH.PLUMB.CONCEALED_LEAK",
    report:
      "Tường phòng tắm căn A1-1205 thấm, căn dưới bị ố trần; cần hẹn lịch sửa ống trong ba ngày tới.",
    why: "See every official water cut in the window, building-level and site-level alike.",
    calls: [
      schedule(
        BUILDING.a1,
        "water",
        "2026-09-30T00:00:00Z",
        "2026-10-03T00:00:00Z",
        ["I1", "I7"],
      ),
    ],
  },
  {
    id: "L2-4",
    level: 2,
    issueCode: "TECH.PLUMB.CONCEALED_LEAK",
    report: "Cư dân báo lại: chiều hôm qua khoảng 15:00 căn A1-1205 mất nước.",
    why: "An incident reported late is placed against the hours the outage actually ran.",
    calls: [
      outage(BUILDING.a1, "water", "2026-09-29T15:00:00Z", ["I5"]),
      outage(BUILDING.a1, "water", "2026-09-29T16:30:00Z", []),
    ],
  },
  {
    id: "L1-1",
    level: 1,
    issueCode: "TECH.PLUMB.CONCEALED_LEAK",
    report:
      "Nước ngập nhanh gần tủ điện tầng 8 tòa A2; agent vừa gửi đề nghị khóa nước, chưa ai duyệt.",
    why: "The shut-off is only proposed. Reporting it would let the agent say the water is off while it is still running near live equipment.",
    calls: [
      outage(BUILDING.a2, "water", "2026-09-30T09:00:00Z", []),
      schedule(
        BUILDING.a2,
        "water",
        "2026-09-30T00:00:00Z",
        "2026-10-01T00:00:00Z",
        [],
      ),
    ],
  },
  {
    id: "L1-2",
    level: 1,
    issueCode: "TECH.ELEC.BREAKER_TRIP",
    report: "Ổ cắm căn A1-1205 tóe lửa, có mùi khét, lúc 09:00.",
    why: "The tool reports that the zone is without power and leaves the safety judgement to a person.",
    calls: [outage(BUILDING.a1, "power", "2026-09-30T09:00:00Z", ["I6"])],
  },
];
