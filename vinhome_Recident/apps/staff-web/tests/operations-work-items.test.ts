import { expect, test } from "vitest";
import { seedWorkspace } from "../src/features/vinhomes-operations/workspace/model";
import {
  caseAction,
  setAvailability,
} from "../src/features/vinhomes-operations/workspace/service";
import {
  workItems,
  ticketHref,
  ticketPhase,
} from "../src/features/vinhomes-operations/workspace/work-items";
import {
  MOCK_TASKS,
  MOCK_INCIDENTS,
  MOCK_WORK_ORDERS,
  MOCK_EVIDENCE,
} from "../src/features/vinhomes-operations/mock";
const legacy = {
  tasks: MOCK_TASKS,
  incidents: MOCK_INCIDENTS,
  workOrders: MOCK_WORK_ORDERS,
  evidence: MOCK_EVIDENCE,
};
test("one list references both existing work orders and new tickets without copying records", () => {
  let s = seedWorkspace();
  const actor = s.accounts.find((a) => a.id === "demo-tech")!;
  s = caseAction(s, "demo-manager", "DEMO-1001", "assign", actor.id);
  const before = JSON.stringify({ s, legacy }),
    rows = workItems(actor, s, legacy);
  expect(rows.some((r) => r.ticket === "DEMO-1001")).toBe(true);
  expect(rows.some((r) => r.job)).toBe(true);
  expect(new Set(rows.map((r) => r.key)).size).toBe(rows.length);
  expect(rows.every((r) => r.place.startsWith(actor.scope))).toBe(true);
  expect(JSON.stringify({ s, legacy })).toBe(before);
});
test("assignment exposes the same ticket to manager and only its assigned employee", () => {
  let s = caseAction(
    seedWorkspace(),
    "demo-manager",
    "DEMO-1001",
    "assign",
    "demo-tech",
  );
  const rows = (id: string) =>
    workItems(s.accounts.find((a) => a.id === id)!, s, legacy);
  expect(
    rows("demo-manager").find((r) => r.ticket === "DEMO-1001")!.ticketId,
  ).toBe(rows("demo-tech").find((r) => r.ticket === "DEMO-1001")!.ticketId);
  expect(rows("demo-security").some((r) => r.ticket === "DEMO-1001")).toBe(
    false,
  );
  expect(rows("demo-manager2").some((r) => r.ticket === "DEMO-1001")).toBe(
    false,
  );
  expect(
    workItems(
      { ...s.accounts.find((a) => a.id === "demo-tech")!, id: "new-employee" },
      s,
      legacy,
    ),
  ).toHaveLength(0);
});
test("completion moves the same record into history; waiting is not completion", () => {
  let s = caseAction(
    seedWorkspace(),
    "demo-manager",
    "DEMO-1001",
    "assign",
    "demo-tech",
  );
  for (const action of [
    "arrive",
    "ask-consent",
    "resident-consent",
    "start",
  ] as const)
    s = caseAction(s, "demo-tech", "DEMO-1001", action);
  s = caseAction(
    s,
    "demo-tech",
    "DEMO-1001",
    "evidence",
    "data:image/jpeg;base64,AA==",
  );
  s = caseAction(s, "demo-tech", "DEMO-1001", "submit");
  const rows = () =>
    workItems(s.accounts.find((a) => a.id === "demo-tech")!, s, legacy);
  expect(rows().find((r) => r.ticket === "DEMO-1001")!.phase).toBe("waiting");
  s = caseAction(s, "demo-tech", "DEMO-1001", "resident-confirm");
  expect(rows().filter((r) => r.ticket === "DEMO-1001")).toHaveLength(1);
  expect(rows().find((r) => r.ticket === "DEMO-1001")!.phase).toBe("history");
  expect(ticketPhase("isolation-requested")).toBe("waiting");
  expect(ticketPhase("controlled")).toBe("waiting");
});
test("manager list has one row per task even with several execution attempts", () => {
  const s = seedWorkspace(),
    manager = s.accounts.find((a) => a.id === "demo-manager")!;
  const rows = workItems(manager, s, legacy);
  const visibleTasks = legacy.tasks.filter(
    (t) =>
      legacy.incidents.find((i) => i.id === t.incident_id)?.location_json
        .towerCode === manager.scope,
  );
  expect(rows.filter((r) => r.task)).toHaveLength(visibleTasks.length);
  for (const task of visibleTasks)
    expect(rows.filter((r) => r.task === task.id)).toHaveLength(1);
});
test("canonical links use role-specific work page and encode ticket IDs", () => {
  expect(ticketHref("manager", "T/1")).toBe("/operations/kanban?ticket=T%2F1");
  expect(ticketHref("technical", "T/1")).toBe(
    "/operations/my-tasks?ticket=T%2F1",
  );
});
test("availability switch affects dispatch without changing existing assignments", () => {
  let s = seedWorkspace();
  s = setAvailability(s, "demo-tech", false);
  s = caseAction(s, "demo-manager", "DEMO-1001", "assign", "demo-tech");
  expect(s.cases[0].stage).toBe("queued");
  expect(s.cases[0].workerId).toBeUndefined();
  s = setAvailability(s, "demo-tech", true);
  s = caseAction(s, "demo-manager", "DEMO-1001", "assign", "demo-tech");
  expect(s.cases[0].workerId).toBe("demo-tech");
  expect(() => setAvailability(s, "demo-manager", false)).toThrow();
});
