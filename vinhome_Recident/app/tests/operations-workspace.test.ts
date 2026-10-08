import { expect, test } from "bun:test";
import {
  seedWorkspace,
  canViewPath,
  landing,
} from "../src/features/vinhomes-operations/workspace/model";
import {
  caseAction,
  createAccount,
  changeAccount,
  createAgent,
  sendRoomMessage,
  createReport,
  finishReport,
  reportRows,
  readWorkspace,
  writeWorkspace,
} from "../src/features/vinhomes-operations/workspace/service";
import { createDocx } from "../src/features/vinhomes-operations/workspace/docx";
import { readOperationsSnapshot } from "../src/features/vinhomes-operations/lib/priority-storage";
const admin = "demo-admin",
  manager = "demo-manager",
  tech = "demo-tech",
  guard = "demo-security";
const photo = "data:image/jpeg;base64,AA==";

test("assigned roles gate routes; residents never enter operations", () => {
  expect(landing("admin")).toBe("/operations/accounts");
  expect(canViewPath("technical", "/operations/accounts")).toBe(false);
  expect(canViewPath("security", "/operations/team")).toBe(false);
  expect(canViewPath("resident", "/operations/dispatch")).toBe(false);
  expect(canViewPath("manager", "/operations/reports")).toBe(true);
});
test("admin provisions, approves, suspends and deletes; rejects self-lock and duplicate identifiers", () => {
  let s = seedWorkspace();
  const input = {
    name: "Nhân viên mới",
    identifier: "KT-NEW",
    role: "technical" as const,
    scope: "S2.01" as const,
  };
  expect(() => createAccount(s, tech, input)).toThrow();
  s = createAccount(s, admin, input);
  const id = s.accounts[0].id;
  expect(() =>
    createAccount(s, admin, { ...input, identifier: " kt-new " }),
  ).toThrow();
  expect(() => changeAccount(s, admin, admin, "suspend")).toThrow();
  expect(() => changeAccount(s, admin, id, "delete", "wrong")).toThrow();
  s = changeAccount(s, admin, "demo-resident", "approve");
  expect(s.accounts.find((a) => a.id === "demo-resident")!.status).toBe(
    "active",
  );
  s = changeAccount(s, admin, id, "suspend");
  expect(s.accounts[0].status).toBe("suspended");
  s = changeAccount(s, admin, id, "activate");
  expect(s.accounts[0].status).toBe("active");
  s = changeAccount(s, admin, id, "delete", "KT-NEW");
  expect(s.accounts.some((a) => a.id === id)).toBe(false);
});
test("agents join their scoped group; mentions cannot attach another building ticket", () => {
  let s = createAgent(seedWorkspace(), manager, "An ninh tòa nhà", "security");
  const agent = s.agents.at(-1)!;
  expect(s.rooms[0].agentIds).toContain(agent.id);
  expect(() => sendRoomMessage(s, manager, "room-S2.02", "hello")).toThrow();
  expect(() =>
    sendRoomMessage(s, manager, "room-S2.01", "hello", agent.id, "DEMO-2001"),
  ).toThrow();
  s = sendRoomMessage(
    s,
    manager,
    "room-S2.01",
    "Kiểm tra sự cố",
    agent.id,
    "DEMO-1003",
  );
  expect(s.rooms[0].messages.at(-2)!.context).toContain("DEMO-1003");
  expect(s.rooms[0].messages.at(-1)!.author).toContain("mô phỏng");
});
test("busy employees queue tickets and staff cannot self-assign or act outside scope", () => {
  let s = caseAction(seedWorkspace(), manager, "DEMO-1001", "assign", tech);
  expect(() => caseAction(s, tech, "DEMO-1002", "assign", tech)).toThrow();
  expect(() => caseAction(s, "demo-manager2", "DEMO-1001", "arrive")).toThrow();
  expect(() => changeAccount(s, admin, tech, "delete", "KT-01")).toThrow();
  s = caseAction(s, manager, "DEMO-1002", "assign", tech);
  expect(s.cases[1].stage).toBe("queued");
  expect(s.cases[1].workerId).toBeUndefined();
  expect(s.cases[1].events.at(-1)!.label).toContain("đang bận");
});
test("electrical work requires consent, evidence and resident confirmation", () => {
  let s = caseAction(seedWorkspace(), manager, "DEMO-1001", "assign", tech);
  s = caseAction(s, tech, "DEMO-1001", "arrive");
  expect(() => caseAction(s, tech, "DEMO-1001", "start")).toThrow();
  for (const a of ["ask-consent", "resident-consent", "start"] as const)
    s = caseAction(s, tech, "DEMO-1001", a);
  expect(() => caseAction(s, tech, "DEMO-1001", "submit")).toThrow();
  s = caseAction(s, tech, "DEMO-1001", "evidence", photo);
  s = caseAction(s, tech, "DEMO-1001", "submit");
  expect(s.cases[0].stage).toBe("awaiting-confirmation");
  s = caseAction(s, tech, "DEMO-1001", "resident-confirm");
  expect(s.cases[0].stage).toBe("completed");
  expect(() => caseAction(s, tech, "DEMO-1001", "resident-confirm")).toThrow();
});
test("major water enforces approval, outage notification, isolation and restoration order", () => {
  let s = caseAction(seedWorkspace(), manager, "DEMO-1002", "assign", tech);
  for (const a of [
    "arrive",
    "ask-consent",
    "resident-consent",
    "request-isolation",
  ] as const)
    s = caseAction(s, tech, "DEMO-1002", a);
  expect(() => caseAction(s, tech, "DEMO-1002", "approve-isolation")).toThrow();
  expect(() => caseAction(s, manager, "DEMO-1002", "isolate")).toThrow();
  for (const a of ["approve-isolation", "notify-outage"] as const)
    s = caseAction(s, manager, "DEMO-1002", a);
  for (const a of ["isolate", "start"] as const)
    s = caseAction(s, tech, "DEMO-1002", a);
  s = caseAction(s, tech, "DEMO-1002", "evidence", photo);
  expect(() => caseAction(s, tech, "DEMO-1002", "submit")).toThrow();
  for (const a of ["restore", "submit", "resident-confirm"] as const)
    s = caseAction(s, tech, "DEMO-1002", a);
  expect(s.cases[1].stage).toBe("completed");
});
test("security escalation stays open; urgent cases require acknowledgment, evidence and BQL closure", () => {
  let s = caseAction(seedWorkspace(), manager, "DEMO-1003", "escalate");
  expect(s.cases[2].stage).toBe("queued");
  s = caseAction(s, manager, "DEMO-1003", "assign", guard);
  s = caseAction(s, guard, "DEMO-1003", "arrive");
  s = caseAction(
    s,
    guard,
    "DEMO-1003",
    "raise-emergency",
    "Có dấu hiệu gây nguy hiểm",
  );
  expect(() => caseAction(s, guard, "DEMO-1003", "start")).toThrow();
  expect(() =>
    caseAction(s, guard, "DEMO-1003", "request-cancel", "Không cần nữa"),
  ).toThrow();
  s = caseAction(s, guard, "DEMO-1003", "escalate");
  expect(s.cases[2].stage).toBe("on-site");
  for (const a of ["acknowledge", "start"] as const)
    s = caseAction(s, guard, "DEMO-1003", a);
  s = caseAction(s, guard, "DEMO-1003", "evidence", photo);
  s = caseAction(s, guard, "DEMO-1003", "submit");
  expect(s.cases[2].stage).toBe("controlled");
  expect(() => caseAction(s, guard, "DEMO-1003", "manager-close")).toThrow();
  s = caseAction(s, manager, "DEMO-1003", "manager-close");
  expect(s.cases[2].stage).toBe("completed");
});
test("ordinary cancellation waits for manager; locked staff cannot mutate", () => {
  let s = caseAction(seedWorkspace(), manager, "DEMO-1003", "assign", guard);
  s = caseAction(
    s,
    guard,
    "DEMO-1003",
    "request-cancel",
    "Không còn sự cố tại sảnh",
  );
  expect(s.cases[2].stage).toBe("cancel-requested");
  expect(() => caseAction(s, guard, "DEMO-1003", "approve-cancel")).toThrow();
  s = changeAccount(s, admin, guard, "suspend");
  expect(() => caseAction(s, guard, "DEMO-1003", "escalate")).toThrow();
  expect(
    caseAction(s, manager, "DEMO-1003", "approve-cancel").cases[2].stage,
  ).toBe("cancelled");
});
test("reports have scoped date filters, error/retry states and only completed technical revenue", () => {
  const s = seedWorkspace(),
    date = s.cases[0].createdAt.slice(0, 10);
  const input = {
    kind: "revenue" as const,
    name: "Báo cáo",
    from: date,
    to: date,
  };
  expect(() => createReport(s, tech, input)).toThrow();
  expect(() =>
    createReport(s, manager, { ...input, from: "2099-01-01" }),
  ).toThrow();
  let next = createReport(s, manager, input),
    r = next.reports[0];
  expect(reportRows(next, r)).toHaveLength(0);
  expect(reportRows(next, { ...r, kind: "frequency" })).toHaveLength(3);
  expect(reportRows(next, { ...r, scope: "S2.02" })).toHaveLength(1);
  expect(() => finishReport(next, "demo-manager2", r.id)).toThrow();
  next = finishReport(next, manager, r.id, true);
  expect(next.reports[0].status).toBe("failed");
  next = finishReport(next, manager, r.id);
  expect(next.reports[0].status).toBe("ready");
});
test("DOCX is a ZIP with OOXML parts, Unicode text and XML escaping", () => {
  const bytes = createDocx(["Cư dân & <báo cáo>"]);
  expect(new DataView(bytes.buffer).getUint32(0, true)).toBe(0x04034b50);
  const text = new TextDecoder().decode(bytes);
  expect(text).toContain("[Content_Types].xml");
  expect(text).toContain("word/document.xml");
  expect(text).toContain("Cư dân &amp; &lt;báo cáo&gt;");
  expect(new DataView(bytes.buffer).getUint32(bytes.length - 22, true)).toBe(
    0x06054b50,
  );
});
test("persisted legacy priorities migrate without rewriting IDs, notes or original snapshots", () => {
  const old = JSON.stringify([
    { severity: "P1", note: "P1", id: "P4", nested: { severity: "P4" } },
  ]);
  const getItem = (key: string) =>
    key === "vhm_operations_data_v9_incidents" ? old : null;
  expect(
    JSON.parse(
      readOperationsSnapshot("vhm_operations_data_v10_incidents", { getItem })!,
    ),
  ).toEqual([
    { severity: "P0", note: "P1", id: "P4", nested: { severity: "P3" } },
  ]);
  expect(getItem("vhm_operations_data_v9_incidents")).toBe(old);
  expect(
    readOperationsSnapshot("vhm_operations_data_v10_incidents", {
      getItem: () => '[{"severity":"P1"}]',
    }),
  ).toBe('[{"severity":"P1"}]');
});
test("storage errors do not report success or overwrite corrupted data", () => {
  expect(() => readWorkspace({ getItem: () => "{" })).toThrow();
  expect(() => readWorkspace({ getItem: () => "{}" })).toThrow();
  expect(() =>
    writeWorkspace(seedWorkspace(), {
      setItem: () => {
        throw new Error("Quota");
      },
    }),
  ).toThrow("Chưa lưu");
});

test("pending cancellation cannot bypass the emergency closure workflow", () => {
  let s = caseAction(
    seedWorkspace(),
    manager,
    "DEMO-1003",
    "request-cancel",
    "Không còn sự cố tại sảnh",
  );
  expect(() =>
    caseAction(
      s,
      manager,
      "DEMO-1003",
      "raise-emergency",
      "Có nguy hiểm tại sảnh",
    ),
  ).toThrow();
  // A changed server snapshot must also prevent approving cancellation of an urgent case.
  s.cases[2].severity = "P1";
  expect(() => caseAction(s, manager, "DEMO-1003", "approve-cancel")).toThrow();
  expect(s.cases[2].stage).toBe("cancel-requested");
});
