/**
 * Gate R8 (spec §2.2, §5, §6.3): mọi WRITE thành công có WriteEvidence, một ACTION_RECEIPT và một
 * event trỏ đúng evidence; related_counts và version của incident tăng đúng một lần. Replay và lệnh
 * bị từ chối không ghi thêm gì.
 */
import { beforeEach, describe, expect, test } from "bun:test";
import {
  ACTOR,
  createHarness,
  expectFailure,
  type GrantSpec,
  type Row,
  session,
  TICKET,
} from "./helpers/write-harness";

const h = createHarness();
beforeEach(() => {
  h.reset();
  h.clock.set(new Date("2026-09-29T04:21:45.000Z"));
});

type Case = {
  label: string;
  incident: keyof typeof TICKET | null;
  spec: () => GrantSpec;
  event: string;
  counter: "dispatches" | "escalations" | null;
};

const CASES: Case[] = [
  {
    label: "dispatch_guard",
    incident: "inc_01",
    spec: () => ({
      action: "dispatch_guard",
      args: {
        incident_id: "inc_01",
        guard_id: "guard_001",
        incident_version: 6,
      },
      key: "k_ev_dispatch",
      session: session(TICKET.inc_01),
    }),
    event: "DISPATCH_CREATED",
    counter: "dispatches",
  },
  {
    label: "cancel_dispatch",
    incident: "inc_01",
    spec: () => ({
      action: "cancel_dispatch",
      args: {
        dispatch_id: "dsp_0003",
        expected_version: 3,
        reason: "Đã xử lý xong",
      },
      key: "k_ev_cancel",
      session: session(TICKET.inc_01),
    }),
    event: "DISPATCH_STATUS_CHANGED",
    counter: null,
  },
  {
    label: "escalate_emergency",
    incident: "inc_02",
    spec: () => ({
      action: "escalate_emergency",
      args: {
        incident_id: "inc_02",
        incident_version: 6,
        protocol_id: "prt_intrusion_p0",
        protocol_version: 2,
        contact_id: "ct_pm_01",
        reason: "Cần quản lý tòa nhà",
      },
      key: "k_ev_escalate",
      session: session(TICKET.inc_02),
    }),
    event: "ESCALATION_CREATED",
    counter: "escalations",
  },
  {
    label: "acknowledge_emergency",
    incident: "inc_02",
    spec: () => ({
      action: "acknowledge_emergency",
      args: {
        escalation_id: "esc_0003",
        expected_version: 2,
        ack_receipt_id: "ack_7101",
      },
      key: "k_ev_ack",
      session: session(TICKET.inc_02),
      actor: ACTOR,
    }),
    event: "ESCALATION_STATUS_CHANGED",
    counter: null,
  },
  {
    label: "create_incident",
    incident: null,
    spec: () => ({
      action: "create_incident",
      args: {
        incident_type: "THEFT",
        description: "Mất xe đạp tại hầm",
        severity: "P2",
        location_id: "loc_03",
      },
      key: "k_ev_create",
    }),
    event: "INCIDENT_CREATED",
    counter: null,
  },
];

async function audit(incidentId: string) {
  const incident = (await h.read("get_incident", { incident_id: incidentId }))
    .data;
  const evidence = (
    await h.read("get_incident_evidence", {
      incident_id: incidentId,
      limit: 100,
    })
  ).data.evidence as Row[];
  const events = (
    await h.read("get_security_event_timeline", {
      incident_id: incidentId,
      limit: 100,
    })
  ).data.events as Row[];
  return { incident, evidence, events };
}

describe("R8: mỗi WRITE thành công để lại đúng một bằng chứng", () => {
  test.each(CASES.map((c) => [c.label, c] as const))(
    "%s",
    async (_label, c) => {
      const spec = c.spec();
      const before = c.incident ? await audit(c.incident) : null;
      const env = await h.write(spec);
      expect(env.success).toBe(true);
      expect(Object.keys(env.evidence).sort()).toEqual([
        "committed_at",
        "evidence_id",
        "provider",
        "provider_reference_id",
      ]);
      expect(env.evidence.committed_at).toBe("2026-09-29T04:21:45.000Z");

      const incidentId = c.incident ?? env.data.incident_id;
      const after = await audit(incidentId);
      const receipts = after.evidence.filter(
        (e) => e.evidence_id === env.evidence.evidence_id,
      );
      expect(receipts).toHaveLength(1);
      expect(receipts[0]).toMatchObject({
        incident_id: incidentId,
        evidence_type: "ACTION_RECEIPT",
        action: spec.action,
        idempotency_key: spec.key,
        provider: env.evidence.provider,
        provider_reference_id: env.evidence.provider_reference_id,
        actor: spec.actor ?? ACTOR,
      });
      const events = after.events.filter(
        (e) => e.evidence_id === env.evidence.evidence_id,
      );
      expect(events).toHaveLength(1);
      expect(events[0]!.event_type).toBe(c.event);

      if (before) {
        expect(after.evidence).toHaveLength(before.evidence.length + 1);
        expect(after.events).toHaveLength(before.events.length + 1);
        expect(after.incident.version).toBe(before.incident.version + 1);
        expect(after.incident.related_counts.evidence).toBe(
          before.incident.related_counts.evidence + 1,
        );
        if (c.counter)
          expect(after.incident.related_counts[c.counter]).toBe(
            before.incident.related_counts[c.counter] + 1,
          );
        for (const k of ["dispatches", "escalations", "cameras"] as const) {
          if (k !== c.counter)
            expect(after.incident.related_counts[k]).toBe(
              before.incident.related_counts[k],
            );
        }
        expect(after.incident.updated_at).toBe("2026-09-29T04:21:45.000Z");
      } else {
        expect(after.incident).toMatchObject({
          status: "OPEN",
          version: 1,
          related_counts: {
            evidence: 1,
            dispatches: 0,
            escalations: 0,
            cameras: 0,
          },
        });
        expect(after.evidence).toHaveLength(1);
      }

      const replay = await h.write(spec);
      expect(replay).toMatchObject({
        success: true,
        meta: { replayed: true },
        evidence: env.evidence,
      });
      expect(await audit(incidentId)).toEqual(after);
    },
  );
});

describe("R8: không bằng chứng cho lệnh không commit", () => {
  const dispatch = (): GrantSpec => ({
    action: "dispatch_guard",
    args: { incident_id: "inc_01", guard_id: "guard_001", incident_version: 6 },
    key: "k_ev_fail",
    session: session(TICKET.inc_01),
  });

  test("lệnh bị luật nghiệp vụ từ chối không ghi evidence/event, version giữ nguyên", async () => {
    const before = await audit("inc_01");
    expectFailure(
      await h.write({
        ...dispatch(),
        args: { ...dispatch().args, incident_version: 5 },
      }),
      "CONFLICT",
    );
    expect(await audit("inc_01")).toEqual(before);
  });

  test("grant sai không chạm provider", async () => {
    const before = await audit("inc_01");
    expectFailure(
      await h.write(dispatch(), {
        token: await h.grant(dispatch(), { aud: "other" }),
      }),
      "GRANT_INVALID",
    );
    expect(await audit("inc_01")).toEqual(before);
  });

  test.each(["provider_error_before_commit", "timeout_before_commit"] as const)(
    "%s không để lại evidence",
    async (fault) => {
      const before = await audit("inc_01");
      h.control.setFault("dispatch_guard", fault);
      expect((await h.write(dispatch())).success).toBe(false);
      expect(await audit("inc_01")).toEqual(before);
    },
  );

  test("timeout_after_commit: đã commit nên có đúng một bằng chứng, replay không thêm", async () => {
    const before = await audit("inc_01");
    h.control.setFault("dispatch_guard", "timeout_after_commit");
    expectFailure(await h.write(dispatch()), "PROVIDER_TIMEOUT");
    const mid = await audit("inc_01");
    expect(mid.evidence).toHaveLength(before.evidence.length + 1);
    expect((await h.write(dispatch())).meta.replayed).toBe(true);
    expect(await audit("inc_01")).toEqual(mid);
  });
});
