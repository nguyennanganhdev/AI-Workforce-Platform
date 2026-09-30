/**
 * The technical issue codes of docs/teams/quang/general.md §4.
 *
 * An issue code decides which SOP, which tools and which default level apply, so it is reference
 * data rather than something a model may invent. `level` is the default severity; a danger signal
 * always wins over it (§3.1), which is why each code also carries what raises it to level 1.
 *
 * Kept in the module rather than in a fixture because tools read it: `sop_kb.retrieve` matches
 * documents to a code, and the classification and verification tools will read the level rules.
 */
export const ISSUE_GROUPS = ["ELEC", "PLUMB", "HVAC", "ARCH"] as const;

export type IssueGroup = (typeof ISSUE_GROUPS)[number];

/** 1 = immediate danger, 2 = spreading or significant, 3 = routine. */
export type IssueLevel = 1 | 2 | 3;

export type IssueCode = {
  code: string;
  group: IssueGroup;
  /** What a resident reports, in the words general.md uses. */
  name: string;
  defaultLevel: IssueLevel;
  /** Signals that raise this to level 1 regardless of the default. */
  escalatesToLevel1: string;
};

export const ISSUE_CODES: readonly IssueCode[] = [
  {
    code: "TECH.ELEC.BREAKER_TRIP",
    group: "ELEC",
    name: "CB hoặc cầu dao nhảy liên tục",
    defaultLevel: 2,
    escalatesToLevel1: "Khói, tia lửa, điện giật hoặc nước gần điện",
  },
  {
    code: "TECH.ELEC.FIXTURE_FAILURE",
    group: "ELEC",
    name: "Ổ cắm, công tắc hoặc đèn không hoạt động",
    defaultLevel: 3,
    escalatesToLevel1: "Nóng, cháy xém hoặc tóe lửa",
  },
  {
    code: "TECH.PLUMB.WATER_HEATER",
    group: "PLUMB",
    name: "Máy nước nóng không nóng hoặc rò",
    defaultLevel: 3,
    escalatesToLevel1: "Nguy cơ điện hoặc rò nước lớn",
  },
  {
    code: "TECH.PLUMB.WATER_FILTER_LOW_FLOW",
    group: "PLUMB",
    name: "Máy lọc nước chạy yếu",
    defaultLevel: 3,
    escalatesToLevel1: "Có rò hoặc chất lượng nước bất thường",
  },
  {
    code: "TECH.HVAC.CONDENSATION",
    group: "HVAC",
    name: "Điều hòa đọng hoặc chảy nước",
    defaultLevel: 2,
    escalatesToLevel1: "Nước gần điện hoặc trần có nguy cơ rơi",
  },
  {
    code: "TECH.PLUMB.CONCEALED_LEAK",
    group: "PLUMB",
    name: "Rò âm tường hoặc thấm trần",
    defaultLevel: 2,
    escalatesToLevel1: "Ngập nhanh hoặc nước gặp điện",
  },
  {
    code: "TECH.PLUMB.SHOWER_SEAL",
    group: "PLUMB",
    name: "Vách phòng tắm hở",
    defaultLevel: 3,
    escalatesToLevel1: "Thấm lan hoặc rò lớn",
  },
  {
    code: "TECH.PLUMB.TOILET_LEAK",
    group: "PLUMB",
    name: "Bồn cầu rỉ nước",
    defaultLevel: 3,
    escalatesToLevel1: "Tràn nước thải",
  },
  {
    code: "TECH.PLUMB.TRAP_ODOR",
    group: "PLUMB",
    name: "Mùi cống hoặc bẫy nước không hiệu quả",
    defaultLevel: 3,
    escalatesToLevel1: "Có dấu hiệu khí nguy hiểm",
  },
  {
    code: "TECH.PLUMB.SUPPLY_DRAIN_JOINT",
    group: "PLUMB",
    name: "Nước yếu, thoát chậm hoặc rò đầu nối",
    defaultLevel: 3,
    escalatesToLevel1: "Tràn hoặc rò liên tục",
  },
  {
    code: "TECH.ARCH.DOOR_WINDOW",
    group: "ARCH",
    name: "Cửa hoặc cửa sổ lỏng, hở",
    defaultLevel: 3,
    escalatesToLevel1: "Kính hoặc cánh có nguy cơ rơi",
  },
  {
    code: "TECH.ARCH.CABINET_SAG",
    group: "ARCH",
    name: "Tủ bếp xệ hoặc cánh lệch",
    defaultLevel: 3,
    escalatesToLevel1: "Có nguy cơ rơi",
  },
  {
    code: "TECH.ARCH.CRACK",
    group: "ARCH",
    name: "Nứt tường hoặc trần",
    defaultLevel: 3,
    escalatesToLevel1: "Võng, rơi vật liệu hoặc nứt nhanh",
  },
  {
    code: "TECH.ARCH.PAINT_MOISTURE",
    group: "ARCH",
    name: "Sơn bong, vết ố hoặc ẩm mốc",
    defaultLevel: 3,
    escalatesToLevel1: "Nguồn ẩm vẫn tiếp diễn",
  },
  {
    code: "TECH.ARCH.FLOOR_DAMAGE",
    group: "ARCH",
    name: "Sàn trầy, phồng hoặc bong",
    defaultLevel: 3,
    escalatesToLevel1: "Có nguy cơ vấp ngã",
  },
  {
    code: "TECH.PLUMB.SEWAGE_BACKFLOW",
    group: "PLUMB",
    name: "Nước thải trào ngược",
    defaultLevel: 2,
    escalatesToLevel1: "Lan rộng, gần điện hoặc ảnh hưởng sức khỏe",
  },
];

/** The shape `tools.md` gives an issue code, used by every tool that takes one. */
export const ISSUE_CODE_PATTERN = /^TECH\.[A-Z]+\.[A-Z0-9_]+$/;

export function issueCode(code: string): IssueCode | undefined {
  return ISSUE_CODES.find((candidate) => candidate.code === code);
}
