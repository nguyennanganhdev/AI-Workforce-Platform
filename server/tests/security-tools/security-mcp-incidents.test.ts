/**
 * Test P3 (Incident / Evidence / Timeline, spec §6.1, §7). Viết trước code P3:
 * - READ của 7 tool, create_incident và ràng buộc schema của update_incident chạy được ngay trên mock.
 * - Phần cần code P3 tự bật khi có: luật update_incident khi mock có handler, mô tả tool khi
 *   INCIDENT_TOOLS/AUDIT_TOOLS được đăng ký, tham chiếu inc_06–inc_08 khi incidents.json bổ sung.
 */
import { beforeEach, describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { SECURITY_TOOLS } from "../../src/security-tools/tools";
import {
  createHarness,
  expectFailure,
  type Row,
  session,
  TICKET,
} from "./helpers/write-harness";

const h = createHarness();
beforeEach(() => h.reset());

const fixture = (name: string): Row[] =>
  JSON.parse(
    readFileSync(new URL(`./fixtures/${name}.json`, import.meta.url), "utf8"),
  );
const INCIDENTS = fixture("incidents");
/** Kết quả search kỳ vọng tính từ fixture, để test không phụ thuộc số bản ghi cụ thể. */
function expectedSearch(f: Row): string[] {
  return INCIDENTS.filter(
    (i) =>
      (f.severity === undefined || i.severity === f.severity) &&
      (f.status === undefined || i.status === f.status) &&
      (f.location_id === undefined ||
        i.location.location_id === f.location_id) &&
      (f.from === undefined || i.created_at >= f.from) &&
      (f.to === undefined || i.created_at < f.to),
  )
    .sort((a, b) =>
      a.created_at === b.created_at
        ? a.incident_id < b.incident_id
          ? -1
          : 1
        : a.created_at < b.created_at
          ? -1
          : 1,
    )
    .map((i) => i.incident_id);
}
const P3_TOOLS = [
  "get_incident",
  "search_incidents",
  "create_incident",
  "update_incident",
  "get_incident_evidence",
  "get_dispatch_history",
  "get_security_event_timeline",
];

const ids = (rows: Row[]) => rows.map((r) => r.incident_id);
const NEW = {
  incident_type: "SUSPICIOUS_ACTIVITY",
  description: "Người lạ đi lại nhiều lần quanh hầm",
  severity: "P2",
  location_id: "loc_03",
};
const create = (key: string, args: Row = NEW, ticket: string = TICKET.inc_01) =>
  h.write({ action: "create_incident", args, key, session: session(ticket) });
/** Grant ký trên arguments đã bỏ null (JCS không nhận null); request gửi nguyên bản để wrapper tự từ chối. */
const update = (
  incident: string,
  args: Row,
  key: string,
  ticket: string = TICKET[incident as keyof typeof TICKET] ?? TICKET.inc_01,
) => {
  const sent = { incident_id: incident, ...args };
  const signed = Object.fromEntries(
    Object.entries(sent).filter(([, v]) => v !== null),
  );
  return h.write(
    { action: "update_incident", args: signed, key, session: session(ticket) },
    { sentArgs: sent },
  );
};

describe("P3 fixture", () => {
  test("related_counts của incident khớp dispatch/escalation/camera/evidence trong fixture", () => {
    const evidence = fixture("evidence");
    for (const inc of INCIDENTS) {
      const count = (rows: Row[]) =>
        rows.filter((r) => r.incident_id === inc.incident_id).length;
      expect({ id: inc.incident_id, ...inc.related_counts }).toEqual({
        id: inc.incident_id,
        dispatches: count(fixture("dispatches")),
        escalations: count(fixture("escalations")),
        cameras: count(fixture("incident-cameras")),
        evidence: count(evidence),
      });
    }
  });

  test("incident-cameras chỉ trỏ tới incident có trong incidents.json", () => {
    const missing = [
      ...new Set(fixture("incident-cameras").map((c) => c.incident_id)),
    ].filter((id) => !INCIDENTS.some((i) => i.incident_id === id));
    expect(missing).toEqual([]);
  });
});

describe("get_incident", () => {
  test("trả đúng bản ghi Incident theo contract", async () => {
    const env = await h.read("get_incident", { incident_id: "inc_01" });
    expect(env).toMatchObject({ success: true, evidence: null });
    expect(env.data).toEqual(INCIDENTS.find((i) => i.incident_id === "inc_01"));
  });

  test("không tồn tại → NOT_FOUND", async () => {
    expectFailure(
      await h.read("get_incident", { incident_id: "inc_missing" }),
      "NOT_FOUND",
    );
  });

  test("input lạ → VALIDATION_ERROR", async () => {
    expectFailure(
      await h.read("get_incident", {
        incident_id: "inc_01",
        tenant_id: "tenant_other",
      }),
      "VALIDATION_ERROR",
    );
  });
});

describe("search_incidents (§7)", () => {
  test("không filter: liệt kê trong property, sắp (created_at, incident_id)", async () => {
    const env = await h.read("search_incidents", { limit: 100 });
    expect(ids(env.data.incidents)).toEqual(expectedSearch({}));
    expect(env.data.next_cursor).toBeNull();
  });

  test.each([
    ["severity", { severity: "P1" }],
    ["status", { status: "RESOLVED" }],
    ["location", { location_id: "loc_03" }],
    ["kết hợp AND", { severity: "P1", location_id: "loc_02" }],
    ["không khớp", { status: "CLOSED" }],
  ] as const)("filter %s", async (_label, filter) => {
    const env = await h.read("search_incidents", { ...filter, limit: 100 });
    expect(ids(env.data.incidents)).toEqual(expectedSearch(filter));
  });

  test("fixture đủ dữ liệu để các filter trên có nghĩa", () => {
    expect(expectedSearch({ severity: "P1" }).length).toBeGreaterThan(1);
    expect(expectedSearch({ status: "RESOLVED" }).length).toBeGreaterThan(0);
    expect(
      expectedSearch({ severity: "P1", location_id: "loc_02" }).length,
    ).toBeGreaterThan(0);
  });

  test("khoảng thời gian [from, to) trên created_at: gồm from, không gồm to", async () => {
    const range = {
      from: "2026-09-29T04:14:00.000Z",
      to: "2026-09-29T04:22:30.000Z",
    };
    const found = ids((await h.read("search_incidents", range)).data.incidents);
    expect(found).toEqual(expectedSearch(range));
    expect(found).toContain("inc_01");
    expect(found).not.toContain("inc_03");
  });

  test("from không nhỏ hơn to → VALIDATION_ERROR", async () => {
    expectFailure(
      await h.read("search_incidents", {
        from: "2026-09-29T05:00:00.000Z",
        to: "2026-09-29T05:00:00.000Z",
      }),
      "VALIDATION_ERROR",
    );
  });

  test("phân trang đi hết không trùng, không sót; trang rỗng không có cursor", async () => {
    const seen: string[] = [];
    let cursor: string | null = null;
    do {
      const env: Row = await h.read("search_incidents", {
        limit: 1,
        ...(cursor ? { cursor } : {}),
      });
      seen.push(...ids(env.data.incidents));
      cursor = env.data.next_cursor;
    } while (cursor);
    expect(seen).toEqual(expectedSearch({}));
    expect(
      (await h.read("search_incidents", { status: "CLOSED" })).data,
    ).toEqual({ incidents: [], next_cursor: null });
  });

  test("cursor đổi filter → VALIDATION_ERROR", async () => {
    const first = await h.read("search_incidents", { limit: 1 });
    expectFailure(
      await h.read("search_incidents", {
        limit: 1,
        status: "OPEN",
        cursor: first.data.next_cursor,
      }),
      "VALIDATION_ERROR",
    );
  });
});

describe("audit READ: evidence, dispatch history, timeline", () => {
  test("get_dispatch_history: projection DispatchSummary, sắp (created_at, dispatch_id)", async () => {
    const env = await h.read("get_dispatch_history", { incident_id: "inc_04" });
    expect(env.data.dispatches.map((d: Row) => d.dispatch_id)).toEqual([
      "dsp_0001",
      "dsp_0002",
    ]);
    for (const d of env.data.dispatches)
      expect(Object.keys(d).sort()).toEqual([
        "created_at",
        "dispatch_id",
        "guard_id",
        "incident_id",
        "status",
        "updated_at",
        "version",
      ]);
  });

  test.each([
    "get_incident_evidence",
    "get_dispatch_history",
    "get_security_event_timeline",
  ])(
    "%s: parent không tồn tại → NOT_FOUND, không giả danh sách rỗng",
    async (tool) => {
      expectFailure(
        await h.read(tool, { incident_id: "inc_missing" }),
        "NOT_FOUND",
      );
    },
  );

  test("incident mới chưa có dispatch/escalation → [] và next_cursor null", async () => {
    const id = (await create("k_empty_lists")).data.incident_id;
    expect(
      (await h.read("get_dispatch_history", { incident_id: id })).data,
    ).toEqual({ dispatches: [], next_cursor: null });
    expect(
      (await h.read("get_incident_escalations", { incident_id: id })).data,
    ).toEqual({ escalations: [], next_cursor: null });
  });

  test("evidence của từng incident khớp related_counts.evidence; mọi event trỏ evidence có thật", async () => {
    for (const inc of INCIDENTS) {
      const evidence = (
        await h.read("get_incident_evidence", {
          incident_id: inc.incident_id,
          limit: 100,
        })
      ).data.evidence as Row[];
      const events = (
        await h.read("get_security_event_timeline", {
          incident_id: inc.incident_id,
          limit: 100,
        })
      ).data.events as Row[];
      expect({ id: inc.incident_id, evidence: evidence.length }).toEqual({
        id: inc.incident_id,
        evidence: inc.related_counts.evidence,
      });
      const known = new Set(evidence.map((e) => e.evidence_id));
      expect(
        events.filter((e) => !known.has(e.evidence_id)).map((e) => e.event_id),
      ).toEqual([]);
    }
  });

  test("sau một WRITE: evidence và timeline đọc lại được, cùng evidence_id", async () => {
    const env = await create("k_audit_read");
    const id = env.data.incident_id;
    const evidence = (
      await h.read("get_incident_evidence", { incident_id: id })
    ).data.evidence;
    const events = (
      await h.read("get_security_event_timeline", { incident_id: id })
    ).data.events;
    expect(evidence.map((e: Row) => e.evidence_id)).toEqual([
      env.evidence.evidence_id,
    ]);
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({
      event_type: "INCIDENT_CREATED",
      evidence_id: env.evidence.evidence_id,
      data: { status: "OPEN", severity: "P2" },
    });
  });
});

describe("create_incident (§6.1)", () => {
  test("luôn OPEN v1, severity theo payload, location tra trong scope, ticket lấy từ phiên", async () => {
    const env = await create("k_create", { ...NEW, severity: "P0" });
    expect(env.data).toMatchObject({
      status: "OPEN",
      severity: "P0",
      version: 1,
      ticket_id: TICKET.inc_01,
      incident_type: "SUSPICIOUS_ACTIVITY",
      description: NEW.description,
    });
    expect(env.data.location).toEqual(
      fixture("locations").find((l) => l.location_id === "loc_03"),
    );
    expect(env.data.related_counts).toEqual({
      dispatches: 0,
      escalations: 0,
      cameras: 0,
      evidence: 1,
    });
    expect(
      (await h.read("get_incident", { incident_id: env.data.incident_id }))
        .data,
    ).toEqual(env.data);
  });

  test("replay cùng key không tạo incident thứ hai", async () => {
    const first = await create("k_create_r");
    const again = await create("k_create_r");
    expect(again).toMatchObject({
      success: true,
      meta: { replayed: true },
      data: first.data,
    });
    expect(
      (await h.read("search_incidents", { location_id: "loc_03" })).data
        .incidents,
    ).toHaveLength(2);
  });

  test("location không có trong property → NOT_FOUND", async () => {
    expectFailure(
      await create("k_create_loc", { ...NEW, location_id: "loc_missing" }),
      "NOT_FOUND",
    );
  });

  test.each([
    ["description rỗng", { ...NEW, description: "" }],
    [
      "location object kiểu v0.2",
      {
        incident_type: "THEFT",
        description: "x",
        severity: "P2",
        location: { location_id: "loc_01" },
      },
    ],
    ["incident_type lạ", { ...NEW, incident_type: "EARTHQUAKE" }],
    [
      "thiếu severity",
      { incident_type: "THEFT", description: "x", location_id: "loc_01" },
    ],
  ])("%s → VALIDATION_ERROR, không tạo incident", async (_label, args) => {
    expectFailure(
      await create("k_create_bad", args as Row),
      "VALIDATION_ERROR",
    );
    expect((await h.read("search_incidents", {})).data.incidents).toHaveLength(
      INCIDENTS.length,
    );
  });
});

describe("update_incident: ràng buộc input (§6.1, chặn ở wrapper)", () => {
  test.each([
    ["patch rỗng", { expected_version: 6 }],
    [
      "đổi status không có note",
      {
        expected_version: 6,
        status: "RESOLVED",
        resolution_evidence_id: "ev_x",
      },
    ],
    ["đổi severity không có note", { expected_version: 6, severity: "P0" }],
    [
      "RESOLVED thiếu resolution_evidence_id",
      { expected_version: 6, status: "RESOLVED", note: "Xong" },
    ],
    [
      "field optional gửi null",
      { expected_version: 6, note: "x", severity: null },
    ],
    ["thiếu expected_version", { note: "x" }],
  ])("%s → VALIDATION_ERROR", async (_label, args) => {
    expectFailure(
      await update("inc_01", args, "k_upd_bad"),
      "VALIDATION_ERROR",
    );
    expect(
      (await h.read("get_incident", { incident_id: "inc_01" })).data.version,
    ).toBe(6);
  });
});

describe("update_incident: luật nghiệp vụ (§6.1)", () => {
  const open = async (key: string) => (await create(key)).data as Row;

  test("chỉ note: thành công, version +1, status giữ nguyên, có evidence và event INCIDENT_UPDATED", async () => {
    const env = await update(
      "inc_01",
      { expected_version: 6, note: "Đã kiểm tra hiện trường" },
      "k_note",
    );
    expect(env.data).toMatchObject({
      incident_id: "inc_01",
      status: "IN_PROGRESS",
      severity: "P1",
      version: 7,
    });
    expect(env.data.related_counts.evidence).toBe(
      INCIDENTS.find((i) => i.incident_id === "inc_01")!.related_counts
        .evidence + 1,
    );
    const events = (
      await h.read("get_security_event_timeline", { incident_id: "inc_01" })
    ).data.events;
    expect(events.at(-1)).toMatchObject({
      event_type: "INCIDENT_UPDATED",
      evidence_id: env.evidence.evidence_id,
      data: {
        previous_status: "IN_PROGRESS",
        status: "IN_PROGRESS",
        previous_severity: "P1",
        severity: "P1",
        note: "Đã kiểm tra hiện trường",
      },
    });
  });

  test("OPEN → IN_PROGRESS kèm note", async () => {
    const inc = await open("k_t1");
    expect(
      (
        await update(
          inc.incident_id,
          {
            expected_version: inc.version,
            status: "IN_PROGRESS",
            note: "Bảo vệ đang xử lý",
          },
          "k_t1u",
          TICKET.inc_01,
        )
      ).data.status,
    ).toBe("IN_PROGRESS");
  });

  test("đổi severity ở IN_PROGRESS kèm note", async () => {
    const env = await update(
      "inc_01",
      { expected_version: 6, severity: "P0", note: "Khói lan rộng" },
      "k_sev",
    );
    expect(env.data.severity).toBe("P0");
  });

  test.each([
    [
      "IN_PROGRESS → OPEN",
      "inc_01",
      { expected_version: 6, status: "OPEN", note: "Quay lại" },
    ],
    [
      "IN_PROGRESS → CLOSED",
      "inc_01",
      { expected_version: 6, status: "CLOSED", note: "Đóng luôn" },
    ],
    [
      "status trùng trạng thái hiện tại",
      "inc_01",
      { expected_version: 6, status: "IN_PROGRESS", note: "Không đổi gì" },
    ],
    [
      "RESOLVED → OPEN",
      "inc_04",
      { expected_version: 5, status: "OPEN", note: "Mở lại sai cách" },
    ],
    [
      "đổi severity khi đã RESOLVED",
      "inc_04",
      { expected_version: 5, severity: "P1", note: "Nâng mức" },
    ],
  ])(
    "%s → INVALID_STATE_TRANSITION, incident không đổi",
    async (_label, incident, args) => {
      const before = (await h.read("get_incident", { incident_id: incident }))
        .data;
      expectFailure(
        await update(incident, args, `k_bad_${incident}`),
        "INVALID_STATE_TRANSITION",
      );
      expect(
        (await h.read("get_incident", { incident_id: incident })).data,
      ).toEqual(before);
    },
  );

  test("RESOLVED → IN_PROGRESS (mở lại có note) được phép", async () => {
    const env = await update(
      "inc_04",
      {
        expected_version: 5,
        status: "IN_PROGRESS",
        note: "Cư dân báo tái diễn",
      },
      "k_reopen",
    );
    expect(env.data).toMatchObject({ status: "IN_PROGRESS", version: 6 });
  });

  test("RESOLVED → CLOSED khi không còn dispatch mở hay escalation đang chờ", async () => {
    const env = await update(
      "inc_04",
      { expected_version: 5, status: "CLOSED", note: "Hoàn tất" },
      "k_close",
    );
    expect(env.data.status).toBe("CLOSED");
    const after = env.data.version;
    expectFailure(
      await update(
        "inc_04",
        { expected_version: after, note: "Ghi chú sau khi đóng" },
        "k_after_close",
      ),
      "INVALID_STATE_TRANSITION",
    );
  });

  test("expected_version cũ → CONFLICT", async () => {
    expectFailure(
      await update(
        "inc_01",
        { expected_version: 5, note: "Version cũ" },
        "k_stale",
      ),
      "CONFLICT",
    );
  });

  test("RESOLVED với evidence của incident khác → bị từ chối", async () => {
    const other = await create("k_other_inc");
    const env = await update(
      "inc_01",
      {
        expected_version: 6,
        status: "RESOLVED",
        note: "Xong",
        resolution_evidence_id: other.evidence.evidence_id,
      },
      "k_foreign_ev",
    );
    expectFailure(env, [
      "NOT_FOUND",
      "VALIDATION_ERROR",
      "INVALID_STATE_TRANSITION",
      "CONFLICT",
    ]);
    expect(
      (await h.read("get_incident", { incident_id: "inc_01" })).data.status,
    ).toBe("IN_PROGRESS");
  });

  test("phiên của ticket khác → SCOPE_MISMATCH", async () => {
    expectFailure(
      await update(
        "inc_02",
        { expected_version: 6, note: "Sai phiên" },
        "k_ticket",
        TICKET.inc_01,
      ),
      "SCOPE_MISMATCH",
    );
  });

  test("incident không tồn tại → NOT_FOUND", async () => {
    expectFailure(
      await update(
        "inc_missing",
        { expected_version: 1, note: "x" },
        "k_missing",
      ),
      "NOT_FOUND",
    );
  });

  test("replay cùng key trả kết quả lần đầu, không tăng version lần nữa", async () => {
    const first = await update(
      "inc_01",
      { expected_version: 6, note: "Ghi chú" },
      "k_upd_replay",
    );
    const again = await update(
      "inc_01",
      { expected_version: 6, note: "Ghi chú" },
      "k_upd_replay",
    );
    expect(again).toMatchObject({
      success: true,
      meta: { replayed: true },
      data: first.data,
    });
    expect(
      (await h.read("get_incident", { incident_id: "inc_01" })).data.version,
    ).toBe(7);
  });

  const resolutionNote = (incident: string) =>
    fixture("evidence").find(
      (e) =>
        e.incident_id === incident &&
        (e.evidence_type === "OPERATOR_NOTE" ||
          e.evidence_type === "EXTERNAL_REFERENCE"),
    );

  test("ACTION_RECEIPT của chính incident không được nhận làm bằng chứng giải quyết", async () => {
    const receipt = (
      await update("inc_01", { expected_version: 6, note: "Ghi chú" }, "k_rcpt")
    ).evidence.evidence_id;
    const env = await update(
      "inc_01",
      {
        expected_version: 7,
        status: "RESOLVED",
        note: "Xong",
        resolution_evidence_id: receipt,
      },
      "k_rcpt_resolve",
    );
    expectFailure(env, ["VALIDATION_ERROR", "INVALID_STATE_TRANSITION"]);
    expect(
      (await h.read("get_incident", { incident_id: "inc_01" })).data.status,
    ).toBe("IN_PROGRESS");
  });

  test("RESOLVED → CLOSED bị chặn khi còn dispatch mở; hủy dispatch rồi đóng được", async () => {
    const note = resolutionNote("inc_04")!.evidence_id;
    const s4 = session(TICKET.inc_04);
    const version = async () =>
      (await h.read("get_incident", { incident_id: "inc_04" })).data
        .version as number;
    expect(
      (
        await update(
          "inc_04",
          {
            expected_version: await version(),
            status: "IN_PROGRESS",
            note: "Cư dân báo tái diễn",
          },
          "k_cl_1",
        )
      ).success,
    ).toBe(true);
    const dispatch = await h.write({
      action: "dispatch_guard",
      args: {
        incident_id: "inc_04",
        guard_id: "guard_002",
        incident_version: await version(),
      },
      key: "k_cl_2",
      session: s4,
    });
    expect(dispatch.success).toBe(true);
    expect(
      (
        await update(
          "inc_04",
          {
            expected_version: await version(),
            status: "RESOLVED",
            note: "Đã xử lý lại",
            resolution_evidence_id: note,
          },
          "k_cl_3",
        )
      ).success,
    ).toBe(true);
    expectFailure(
      await update(
        "inc_04",
        {
          expected_version: await version(),
          status: "CLOSED",
          note: "Đóng",
        },
        "k_cl_4",
      ),
      "INVALID_STATE_TRANSITION",
    );
    const cancelled = await h.write({
      action: "cancel_dispatch",
      args: {
        dispatch_id: dispatch.data.dispatch_id,
        expected_version: 1,
        reason: "Xong việc",
      },
      key: "k_cl_5",
      session: s4,
    });
    expect(cancelled.success).toBe(true);
    expect(
      (
        await update(
          "inc_04",
          {
            expected_version: await version(),
            status: "CLOSED",
            note: "Đóng",
          },
          "k_cl_6",
        )
      ).data.status,
    ).toBe("CLOSED");
  });
});

describe("đăng ký tool P3", () => {
  test("7 tool P3 có mô tả riêng và annotation đúng mode", () => {
    for (const name of P3_TOOLS) {
      const tool = SECURITY_TOOLS.find((t) => t.name === name)!;
      expect(tool.description.length).toBeGreaterThan(20);
      if (tool.mode === "READ")
        expect(tool.annotations.readOnlyHint).toBe(true);
      else expect(tool.annotations.idempotentHint).toBe(false);
    }
  });
});
