import { describe, expect, test } from "bun:test";
import {
  buildDispatch,
  buildResidentCase,
  classifyIssue,
  type ResidentCaseInput,
} from "../src/features/vinhomes-operations/lib/resident-intake";
import type { FieldFlow, FieldStage } from "../src/features/vinhomes-operations/types/field-flow";
import type { VhIncident } from "../src/features/vinhomes-operations/types/incident";
import type { VhWorkOrder } from "../src/features/vinhomes-operations/types/work-order";
import { reply } from "../src/features/vinhomes-resident/lib/reception-agent";
import type { OperationsSnapshot } from "../src/features/vinhomes-resident/lib/snapshot";
import { deriveTicketEvents } from "../src/features/vinhomes-resident/lib/ticket-events";
import { projectTicket } from "../src/features/vinhomes-resident/lib/ticket-projection";
import { DEMO_RESIDENT } from "../src/features/vinhomes-resident/mock/profile";

/**
 * The resident app and the staff app share one operations store in the demo. These tests pin the
 * contract between them: what a resident submission becomes on the staff side, and what each staff
 * step looks like to the resident (status, the action waiting for them, the notifications they get).
 */

const input: ResidentCaseInput = {
  resident: {
    userId: DEMO_RESIDENT.userId,
    name: DEMO_RESIDENT.name,
    phone: DEMO_RESIDENT.phone,
    towerCode: DEMO_RESIDENT.towerCode,
    floor: DEMO_RESIDENT.floor,
    apartmentCode: DEMO_RESIDENT.apartmentCode,
  },
  description: "Vòi nước dưới bồn rửa bị rò, nước chảy ra sàn",
  location: "Bếp căn hộ",
  photoUrls: [],
};

const at = (minutes: number) => new Date(Date.UTC(2026, 9, 1, 2, minutes)).toISOString();

function scenario() {
  const { kase, candidate } = buildResidentCase(input, new Date(at(0)));
  const incident: VhIncident = {
    id: "INC-TEST-1",
    tenant_id: "tenant-vhm-sc",
    project_id: "proj-smart-city",
    tower_id: "S2.02",
    category: candidate.category,
    title: candidate.normalized_summary,
    location_json: candidate.location_json,
    severity: candidate.severity,
    status: "OPEN",
    stage: "EXECUTION",
    owner_user_id: null,
    sla_due_at: null,
    resolved_at: null,
    closed_at: null,
    version: 1,
    created_at: at(5),
    updated_at: at(5),
  };
  const dispatch = buildDispatch(incident, "MEP", new Date(at(5)));
  if (!dispatch) throw new Error("expected a dispatch");
  const snapshot: OperationsSnapshot = {
    cases: [kase],
    issueCandidates: [{ ...candidate, status: "MATERIALIZED", materialized_incident_id: incident.id }],
    incidents: [incident],
    workOrders: [dispatch.workOrder],
    evidence: [],
  };
  const setFlow = (patch: Partial<FieldFlow> & { stage: FieldStage }, version = 2) => {
    const wo: VhWorkOrder = snapshot.workOrders[0];
    const flow = wo.field_flow as FieldFlow;
    snapshot.workOrders = [{ ...wo, version, updated_at: at(30), field_flow: { ...flow, ...patch } }];
  };
  return { caseId: kase.id, snapshot, setFlow };
}

describe("resident submission → staff intake", () => {
  test("classifies the issue by whole phrases, so 'đến' is not read as 'đèn'", () => {
    expect(classifyIssue("Vòi nước dưới bồn rửa bị rò").category).toBe("MEP_PLUMBING");
    expect(classifyIssue("Đèn hành lang tầng 12 nhấp nháy").category).toBe("ELECTRICAL");
    expect(classifyIssue("Nhờ nhân viên đến kiểm tra giúp").category).toBe("TECHNICAL");
    expect(classifyIssue("Căn bên cạnh hát karaoke ồn ào").domain).toBe("SECURITY");
  });

  test("water running on the floor is not a fire (P1)", () => {
    expect(classifyIssue("nước chảy ra sàn").severity).toBe("P3");
    expect(classifyIssue("nước ngập sàn nhà").severity).toBe("P1");
  });

  test("creates a case and a READY candidate from the app channel", () => {
    const { kase, candidate } = buildResidentCase(input);
    expect(kase.resident_user_id).toBe(DEMO_RESIDENT.userId);
    expect(candidate.case_id).toBe(kase.id);
    expect(candidate.status).toBe("READY");
    expect(candidate.source_channel).toBe("APP");
    expect(candidate.location_json.towerCode).toBe("S2.02");
  });

  test("rejects a submission without a usable description or location", () => {
    expect(() => buildResidentCase({ ...input, description: "rò" })).toThrow();
    expect(() => buildResidentCase({ ...input, location: "" })).toThrow();
  });

  test("dispatches to the matching field staff, and leaves elevators to BQL", () => {
    const { snapshot } = scenario();
    const wo = snapshot.workOrders[0];
    expect(wo.executor_id).toBe("usr-tech-01");
    expect(wo.field_flow?.stage).toBe("ASSIGNED");
    expect(buildDispatch(snapshot.incidents[0], "ELEVATOR")).toBeNull();
  });
});

describe("staff progress → what the resident sees", () => {
  test("a submitted case not yet confirmed by BQL is 'received'", () => {
    const { kase } = buildResidentCase(input);
    const view = projectTicket(kase.id, { cases: [kase], issueCandidates: [], incidents: [], workOrders: [], evidence: [] });
    expect(view?.status).toBe("received");
    expect(view?.pendingAction).toBeNull();
  });

  test("awaiting agreement asks the resident, carrying the version they saw", () => {
    const { caseId, snapshot, setFlow } = scenario();
    setFlow({ stage: "AWAITING_RESIDENT_AGREEMENT", resident_channel: "APP" }, 7);
    const view = projectTicket(caseId, snapshot);
    expect(view?.status).toBe("waiting_you");
    expect(view?.pendingAction).toMatchObject({ type: "AGREE_QUOTE", version: 7, channel: "APP" });
  });

  test("awaiting completion asks for confirmation; after it the ticket is closed", () => {
    const { caseId, snapshot, setFlow } = scenario();
    setFlow({ stage: "AWAITING_COMPLETION", submitted_at: at(40), auto_complete_at: at(59) });
    expect(projectTicket(caseId, snapshot)?.pendingAction?.type).toBe("CONFIRM_COMPLETION");
    setFlow({ stage: "COMPLETED_BY_RESIDENT", completed_at: at(50), completion_type: "RESIDENT_CONFIRMED" });
    const done = projectTicket(caseId, snapshot);
    expect(done?.status).toBe("completed");
    expect(done?.isOpen).toBe(false);
  });

  test("a redo attempt is followed instead of the finished first attempt", () => {
    const { caseId, snapshot, setFlow } = scenario();
    setFlow({ stage: "REWORK_REQUIRED", completed_at: at(50), rework_note: "Vẫn rò" });
    const first = snapshot.workOrders[0];
    const redo: VhWorkOrder = {
      ...first,
      id: "WO-REDO",
      attempt_no: 2,
      created_at: at(51),
      field_flow: { ...(first.field_flow as FieldFlow), stage: "ACCEPTED", accepted_at: at(51), completed_at: null },
    };
    snapshot.workOrders = [first, redo];
    expect(projectTicket(caseId, snapshot)?.status).toBe("on_the_way");
  });

  test("event ids are stable, so re-deriving only yields the new step", () => {
    const { caseId, snapshot, setFlow } = scenario();
    const before = deriveTicketEvents(caseId, snapshot).map((e) => e.id);
    expect(deriveTicketEvents(caseId, snapshot).map((e) => e.id)).toEqual(before);
    setFlow({ stage: "ACCEPTED", accepted_at: at(10) });
    const after = deriveTicketEvents(caseId, snapshot).map((e) => e.id);
    expect(after.filter((id) => !before.includes(id))).toEqual([`${snapshot.workOrders[0].id}:job.accepted`]);
  });

  test("the case receipt is on the timeline but not re-sent as a chat notification", () => {
    const { caseId, snapshot } = scenario();
    const received = deriveTicketEvents(caseId, snapshot).find((e) => e.type === "case.received");
    expect(received?.notify).toBe(false);
  });
});

describe("reception agent draft flow", () => {
  const ctx = { profile: DEMO_RESIDENT, ticket: null, openTickets: [] };

  test("description → location → review, with a shortcut for the resident's own apartment", () => {
    const first = reply({ draft: null, caseId: null }, "Vòi nước bếp bị rò rỉ", [], ctx);
    expect(first.draft?.step).toBe("location");
    const second = reply({ draft: first.draft, caseId: null }, "Tại căn hộ của tôi", [], ctx);
    expect(second.draft?.step).toBe("review");
    expect(second.draft?.location).toBe(`Căn hộ ${DEMO_RESIDENT.apartmentLabel}`);
  });

  test("a bare 'báo sự cố' or a starter chip asks for a description first", () => {
    expect(reply({ draft: null, caseId: null }, "Báo sự cố", [], ctx).draft?.step).toBe("description");
    expect(reply({ draft: null, caseId: null }, "Báo sự cố điện", [], ctx).draft?.step).toBe("description");
    expect(reply({ draft: null, caseId: null }, "Phản ánh tiếng ồn", [], ctx).draft?.step).toBe("description");
  });

  test("a question does not start a report", () => {
    expect(reply({ draft: null, caseId: null }, "Giờ yên tĩnh là mấy giờ?", [], ctx).draft).toBeNull();
  });
});
