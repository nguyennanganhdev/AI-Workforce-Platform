import { afterAll, describe, expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import postgres from "postgres";
import { testDatabaseUrl } from "./support/database";

// Run against a disposable migrated database. History is intentionally not deletable.
const db = postgres(testDatabaseUrl(), { max: 4, onnotice: () => {} });
afterAll(() => db.end());
type Connection = typeof db | postgres.TransactionSql;
const future = (minutes = 60) => new Date(Date.now() + minutes * 60_000);

async function insert(
  c: Connection,
  table: string,
  values: Record<string, unknown>,
) {
  const [row] = await c`insert into ${c(table)} ${c(values)} returning *`;
  return row!;
}

async function fixture(c: Connection = db) {
  const user = randomUUID();
  await insert(c, "users", { id: user, email: `${user}@workforce.test` });
  const tenant = await insert(c, "platform_tenant", {
    code: randomUUID(),
    name: "Test tenant",
    status: "ACTIVE",
  });
  await insert(c, "platform_tenant_membership", {
    tenant_id: tenant.id,
    user_id: user,
    status: "ACTIVE",
    valid_from: new Date("2026-01-01"),
  });
  const project = await insert(c, "vh_project", {
    tenant_id: tenant.id,
    code: "P1",
    name: "Test project",
    status: "ACTIVE",
  });
  const scope = { tenant_id: tenant.id, project_id: project.id };
  const tower = await insert(c, "vh_tower", {
    ...scope,
    code: "T1",
    name: "Tower",
    status: "ACTIVE",
  });
  const apartment = await insert(c, "vh_apartment", {
    ...scope,
    tower_id: tower.id,
    code: "A101",
    floor: 1,
    status: "ACTIVE",
  });
  const member = await insert(c, "vh_property_membership", {
    ...scope,
    user_id: user,
    tower_id: tower.id,
    apartment_id: apartment.id,
    membership_type: "RESIDENT",
    resident_role: "OWNER",
    granted_by_user_id: user,
    valid_from: new Date("2026-01-01"),
    status: "ACTIVE",
  });
  const incident = await insert(c, "vh_incident", {
    ...scope,
    category: "SANITATION",
    title: "Waste overflow",
    location_json: {},
    severity: "HIGH",
    status: "OPEN",
    stage: "EXECUTION",
  });
  const task = await insert(c, "vh_task", {
    ...scope,
    incident_id: incident.id,
    title: "Clean",
    domain_type: "SANITATION",
    domain_data: {},
    domain_schema_version: 1,
    assignee_type: "HUMAN",
    status: "OPEN",
    priority: 1,
    required: true,
  });
  return {
    user,
    tenant,
    project,
    scope,
    tower,
    apartment,
    member,
    incident,
    task,
  };
}

async function rejectSavepoint(
  tx: postgres.TransactionSql,
  fn: (s: postgres.TransactionSql) => Promise<unknown>,
  code = "23514",
) {
  let error: unknown;
  try {
    await tx.savepoint(fn);
  } catch (caught) {
    error = caught;
  }
  expect(error).toBeDefined();
  expect((error as { code: string }).code).toBe(code);
}

// Every ordinary test rolls back, including immutable rows. Concurrent tests need committed fixtures.
async function isolated(
  fn: (
    tx: postgres.TransactionSql,
    f: Awaited<ReturnType<typeof fixture>>,
  ) => Promise<void>,
) {
  const rollback = new Error("test rollback");
  try {
    await db.begin(async (tx) => {
      await fn(tx, await fixture(tx));
      throw rollback;
    });
  } catch (error) {
    if (error !== rollback) throw error;
  }
}

async function action(c: Connection, f: Awaited<ReturnType<typeof fixture>>) {
  return insert(c, "vh_action_request", {
    ...f.scope,
    incident_id: f.incident.id,
    task_id: f.task.id,
    requested_by_type: "HUMAN",
    requested_by_id: f.user,
    action_type: "DISPATCH",
    target_type: "TASK",
    target_id: f.task.id,
    payload: { cleaning: true },
    payload_hash: "sha256:cleaning",
    policy_version: "1",
    expected_subject_version: 1,
    idempotency_key: randomUUID(),
    status: "AUTHORIZED",
    correlation_id: randomUUID(),
    trace_id: randomUUID(),
  });
}

async function runtime(c: Connection, f: Awaited<ReturnType<typeof fixture>>) {
  const agent = await insert(c, "platform_agent", {
    tenant_id: f.tenant.id,
    name: "Coordinator",
    slug: randomUUID(),
    owner_type: "SYSTEM",
    owner_id: "test",
    status: "ACTIVE",
  });
  const revision = await insert(c, "platform_agent_version", {
    tenant_id: f.tenant.id,
    agent_id: agent.id,
    version_no: 1,
    status: "DRAFT",
    spec_hash: "test",
    created_by: f.user,
  });
  const session = await insert(c, "platform_workflow_session", {
    tenant_id: f.tenant.id,
    domain_namespace: "vinhomes",
    subject_type: "INCIDENT",
    subject_ref: f.incident.id,
    runtime_provider: "test",
    environment: "DEVELOPMENT",
    status: "RUNNING",
    plan_snapshot: {},
    trace_id: randomUUID(),
  });
  const participant = await insert(c, "platform_session_participant", {
    tenant_id: f.tenant.id,
    workflow_session_id: session.id,
    agent_version_id: revision.id,
    role: "COORDINATOR",
    capability_scope_json: {},
    status: "ACTIVE",
    joined_at: new Date(),
  });
  const control = await insert(c, "platform_session_control", {
    tenant_id: f.tenant.id,
    workflow_session_id: session.id,
    coordinator_participant_id: participant.id,
    purpose: "PLAN",
    initiation_key: randomUUID(),
    request_hash: "test",
    lease_owner: "worker-1",
    lease_expires_at: future(),
    fencing_token: 1,
    max_turns: 30,
    max_tool_calls: 50,
  });
  return { session, participant, revision, control };
}

async function field(c: Connection, f: Awaited<ReturnType<typeof fixture>>) {
  const request = await action(c, f);
  const order = await insert(c, "vh_work_order", {
    ...f.scope,
    incident_id: f.incident.id,
    task_id: f.task.id,
    action_request_id: request.id,
    executor_type: "HUMAN",
    status: "OPEN",
    attempt_no: 1,
    result: {},
  });
  const member = await insert(c, "vh_property_membership", {
    ...f.scope,
    user_id: f.user,
    membership_type: "STAFF",
    granted_by_user_id: f.user,
    valid_from: new Date("2026-01-01"),
    status: "ACTIVE",
  });
  const team = await insert(c, "vh_team", {
    ...f.scope,
    code: "TECH",
    name: "Technical",
    specialty: "TECHNICAL",
    status: "ACTIVE",
  });
  const tm = await insert(c, "vh_team_member", {
    ...f.scope,
    team_id: team.id,
    property_membership_id: member.id,
    role: "TECHNICIAN",
    valid_from: new Date("2026-01-01"),
    status: "ACTIVE",
  });
  return {
    order,
    member,
    team,
    tm,
    scope: {
      ...f.scope,
      incident_id: f.incident.id,
      task_id: f.task.id,
      work_order_id: order.id,
    },
  };
}

describe("coordination and field persistence", () => {
  test("production roster refuses a draft undeployed agent", () =>
    isolated(async (tx, f) => {
      const r = await runtime(tx, f);
      const session = await insert(tx, "platform_workflow_session", {
        tenant_id: f.tenant.id,
        domain_namespace: "vinhomes",
        subject_type: "INCIDENT",
        subject_ref: f.incident.id,
        runtime_provider: "test",
        environment: "PRODUCTION",
        status: "PENDING",
        plan_snapshot: {},
        trace_id: randomUUID(),
      });
      await rejectSavepoint(tx, (s) =>
        insert(s, "platform_session_participant", {
          tenant_id: f.tenant.id,
          workflow_session_id: session.id,
          agent_version_id: r.revision.id,
          role: "SPECIALIST",
          capability_scope_json: {},
          status: "ACTIVE",
          joined_at: new Date(),
        }),
      );
    }));

  test("consumer receipts deduplicate per consumer and pin payload identity", () =>
    isolated(async (tx, f) => {
      const value = {
        tenant_id: f.tenant.id,
        consumer: "dispatcher",
        producer_namespace: "vinhomes",
        event_id: "event-1",
        payload_hash: "hash-1",
        correlation_id: "test",
        status: "RECEIVED",
        attempt_count: 0,
        available_at: new Date(),
      };
      const receipt = await insert(tx, "platform_event_receipt", value);
      await rejectSavepoint(
        tx,
        (s) => insert(s, "platform_event_receipt", value),
        "23505",
      );
      await rejectSavepoint(
        tx,
        (s) =>
          s`update platform_event_receipt set payload_hash='hash-2' where id=${receipt.id}`,
      );
      await insert(tx, "platform_event_receipt", {
        ...value,
        consumer: "audit",
      });
      const at = new Date();
      const provider = {
        tenant_id: f.tenant.id,
        provider: "test:merchant-1",
        provider_event_id: "callback-1",
        event_type: "STATUS_CHANGED",
        payload_hash: "hash-1",
        sanitized_payload_json: {},
        received_at: at,
        signature_verified_at: at,
        status: "RECEIVED",
        attempt_count: 0,
      };
      await insert(tx, "vh_provider_event", provider);
      await rejectSavepoint(
        tx,
        (s) => insert(s, "vh_provider_event", provider),
        "23505",
      );
    }));

  test("separates resident conversation ownership, order and immutable history", () =>
    isolated(async (tx, f) => {
      const conv = await insert(tx, "platform_conversation", {
        tenant_id: f.tenant.id,
        owner_user_id: f.user,
        channel: "WEB",
        locale: "vi",
        status: "OPEN",
      });
      const value = {
        tenant_id: f.tenant.id,
        conversation_id: conv.id,
        sequence_no: 1,
        role: "USER",
        author_user_id: f.user,
        body: "Leaking pipe",
        content_schema_version: 1,
        metadata_json: {},
        idempotency_key: "message-1",
      };
      await rejectSavepoint(tx, (s) =>
        insert(s, "platform_conversation_message", {
          ...value,
          author_user_id: "different-user",
        }),
      );
      await rejectSavepoint(tx, (s) =>
        insert(s, "platform_conversation_message", {
          ...value,
          sequence_no: 2,
        }),
      );
      const message = await insert(tx, "platform_conversation_message", value);
      await rejectSavepoint(
        tx,
        (s) =>
          s`update platform_conversation_message set body='changed' where id=${message.id}`,
      );
      await insert(tx, "platform_conversation_message", {
        ...value,
        sequence_no: 2,
        idempotency_key: "message-2",
        reply_to_message_id: message.id,
      });
    }));

  test("group chat pins session participants and rejects senders from another session", () =>
    isolated(async (tx, f) => {
      const a = await runtime(tx, f),
        b = await runtime(tx, f);
      const value = {
        tenant_id: f.tenant.id,
        workflow_session_id: a.session.id,
        sender_participant_id: a.participant.id,
        sequence_no: 1,
        kind: "FINDING",
        body: "Inspect valve",
        payload_json: {},
        schema_version: 1,
        idempotency_key: "one",
        correlation_id: "test",
      };
      await rejectSavepoint(tx, (s) =>
        insert(s, "platform_runtime_message", {
          ...value,
          sender_participant_id: b.participant.id,
        }),
      );
      await insert(tx, "platform_runtime_message", value);
      await rejectSavepoint(tx, (s) =>
        insert(s, "platform_runtime_message", {
          ...value,
          idempotency_key: "two",
        }),
      );
      await rejectSavepoint(
        tx,
        (s) =>
          s`update platform_session_participant set workflow_session_id=${b.session.id} where id=${a.participant.id}`,
      );
      await rejectSavepoint(
        tx,
        (s) =>
          s`update platform_workflow_session set subject_ref='different' where id=${a.session.id}`,
      );
      await tx`update platform_session_participant set status='LEFT', left_at=clock_timestamp() where id=${a.participant.id}`;
      await rejectSavepoint(tx, (s) =>
        insert(s, "platform_runtime_message", {
          ...value,
          sequence_no: 2,
          idempotency_key: "two",
        }),
      );
    }));

  test("checkpoints reject stale leases, bad cursors and provider mismatches", () =>
    isolated(async (tx, f) => {
      const r = await runtime(tx, f);
      const value = {
        tenant_id: f.tenant.id,
        workflow_session_id: r.session.id,
        checkpoint_no: 1,
        runtime_provider: "test",
        runtime_version: "1",
        state_schema_version: 1,
        storage_ref: "object:checkpoint",
        content_hash: "hash",
        last_message_sequence: 0,
        fencing_token: 1,
      };
      await insert(tx, "platform_runtime_checkpoint", value);
      await rejectSavepoint(tx, (s) =>
        insert(s, "platform_runtime_checkpoint", {
          ...value,
          checkpoint_no: 2,
          fencing_token: 0,
        }),
      );
      await rejectSavepoint(tx, (s) =>
        insert(s, "platform_runtime_checkpoint", {
          ...value,
          checkpoint_no: 2,
          last_message_sequence: 1,
        }),
      );
      await rejectSavepoint(tx, (s) =>
        insert(s, "platform_runtime_checkpoint", {
          ...value,
          checkpoint_no: 2,
          runtime_provider: "other",
        }),
      );
      await rejectSavepoint(
        tx,
        (s) =>
          s`update platform_session_control set lease_owner='worker-2' where id=${r.control.id}`,
      );
      await tx`update platform_session_control set lease_owner='worker-2', fencing_token=2 where id=${r.control.id}`;
      await rejectSavepoint(tx, (s) =>
        insert(s, "platform_runtime_checkpoint", {
          ...value,
          checkpoint_no: 2,
        }),
      );
      await insert(tx, "platform_runtime_checkpoint", {
        ...value,
        checkpoint_no: 2,
        fencing_token: 2,
      });
    }));

  test("handoff is durable, deduplicated and acknowledged only by its target session", () =>
    isolated(async (tx, f) => {
      const r = await runtime(tx, f);
      const conv = await insert(tx, "platform_conversation", {
        tenant_id: f.tenant.id,
        owner_user_id: f.user,
        channel: "WEB",
        locale: "vi",
        status: "OPEN",
      });
      const value = {
        tenant_id: f.tenant.id,
        source_conversation_id: conv.id,
        target_agent_version_id: r.revision.id,
        domain_namespace: "vinhomes",
        subject_type: "INCIDENT",
        subject_ref: f.incident.id,
        reason: "Dispatch",
        context_json: {},
        request_hash: "hash",
        idempotency_key: "handoff-1",
        correlation_id: "test",
        trace_id: "test",
        status: "OFFERED",
        attempt_count: 0,
        next_attempt_at: new Date(),
        expires_at: future(),
      };
      const h = await insert(tx, "platform_handoff", value);
      await rejectSavepoint(
        tx,
        (s) => insert(s, "platform_handoff", value),
        "23505",
      );
      await rejectSavepoint(
        tx,
        (s) =>
          s`update platform_handoff set status='COMPLETED', completed_at=now() where id=${h.id}`,
      );
      await tx`update platform_handoff set status='ACCEPTED', accepted_at=now(), target_workflow_session_id=${r.session.id} where id=${h.id}`;
      await tx`update platform_handoff set status='COMPLETED', completed_at=now() where id=${h.id}`;
      await rejectSavepoint(
        tx,
        (s) => s`update platform_handoff set status='OFFERED' where id=${h.id}`,
      );
      const expired = await insert(tx, "platform_handoff", {
        ...value,
        idempotency_key: "expired",
        created_at: new Date("2020-01-01"),
        expires_at: new Date("2020-01-02"),
      });
      await rejectSavepoint(
        tx,
        (s) =>
          s`update platform_handoff set status='ACCEPTED', accepted_at=now(), target_workflow_session_id=${r.session.id} where id=${expired.id}`,
      );
    }));

  test("staff eligibility and cross-team shift overlap are enforced", () =>
    isolated(async (tx, f) => {
      const w = await field(tx, f);
      await rejectSavepoint(tx, (s) =>
        insert(s, "vh_team_member", {
          ...f.scope,
          team_id: w.team.id,
          property_membership_id: f.member.id,
          role: "TECHNICIAN",
          valid_from: new Date(),
          status: "ACTIVE",
        }),
      );
      const other = await insert(tx, "vh_team", {
        ...f.scope,
        code: "OTHER",
        name: "Other",
        specialty: "MULTI",
        status: "ACTIVE",
      });
      const tm = await insert(tx, "vh_team_member", {
        ...f.scope,
        team_id: other.id,
        property_membership_id: w.member.id,
        role: "TECHNICIAN",
        valid_from: new Date("2026-01-01"),
        status: "ACTIVE",
      });
      const shift = {
        ...f.scope,
        team_member_id: w.tm.id,
        starts_at: future(60),
        ends_at: future(120),
        status: "CONFIRMED",
        timezone: "Asia/Ho_Chi_Minh",
      };
      await insert(tx, "vh_staff_shift", shift);
      await rejectSavepoint(tx, (s) =>
        insert(s, "vh_staff_shift", { ...shift, team_member_id: tm.id }),
      );
      await insert(tx, "vh_staff_shift", {
        ...shift,
        team_member_id: tm.id,
        starts_at: shift.ends_at,
        ends_at: future(180),
      });
    }));

  test("one active assignment per work order with immutable transfer history", () =>
    isolated(async (tx, f) => {
      const w = await field(tx, f);
      const value = {
        ...w.scope,
        team_id: w.team.id,
        team_member_id: w.tm.id,
        assigned_by_user_id: f.user,
        offered_at: new Date(),
        status: "OFFERED",
        idempotency_key: "assign-1",
      };
      const a = await insert(tx, "vh_work_assignment", value);
      await rejectSavepoint(
        tx,
        (s) =>
          insert(s, "vh_work_assignment", {
            ...value,
            idempotency_key: "assign-2",
          }),
        "23505",
      );
      await tx`update vh_work_assignment set status='RELEASED', ended_at=now() where id=${a.id}`;
      await rejectSavepoint(
        tx,
        (s) =>
          s`update vh_work_assignment set status='OFFERED' where id=${a.id}`,
      );
      await insert(tx, "vh_work_assignment", {
        ...value,
        idempotency_key: "assign-2",
      });
    }));

  test("appointments exclude overlaps and rescheduling preserves history", () =>
    isolated(async (tx, f) => {
      const w = await field(tx, f);
      const value = {
        ...w.scope,
        requested_by_user_id: f.user,
        starts_at: future(60),
        ends_at: future(120),
        timezone: "Asia/Ho_Chi_Minh",
        status: "PROPOSED",
        idempotency_key: "appt-1",
      };
      const a = await insert(tx, "vh_work_appointment", value);
      await rejectSavepoint(
        tx,
        (s) =>
          insert(s, "vh_work_appointment", {
            ...value,
            idempotency_key: "appt-2",
          }),
        "23P01",
      );
      await rejectSavepoint(
        tx,
        (s) =>
          s`update vh_work_appointment set starts_at=${future(90)} where id=${a.id}`,
      );
      await tx`update vh_work_appointment set status='CANCELLED', cancellation_reason='Reschedule' where id=${a.id}`;
      await insert(tx, "vh_work_appointment", {
        ...value,
        idempotency_key: "appt-2",
      });
    }));

  test("asset location cannot point to an apartment in a different tower", () =>
    isolated(async (tx, f) => {
      const tower = await insert(tx, "vh_tower", {
        ...f.scope,
        code: "OTHER",
        name: "Other",
        status: "ACTIVE",
      });
      const value = {
        ...f.scope,
        tower_id: tower.id,
        apartment_id: f.apartment.id,
        code: "VALVE",
        name: "Valve",
        category: "PLUMBING",
        status: "ACTIVE",
        metadata_json: {},
      };
      await rejectSavepoint(tx, (s) => insert(s, "vh_asset", value));
      await insert(tx, "vh_asset", { ...value, tower_id: f.tower.id });
    }));

  test("resident progress pins recipient, confirmed ETA and event lineage", () =>
    isolated(async (tx, f) => {
      const w = await field(tx, f);
      const c = await insert(tx, "vh_case", {
        ...f.scope,
        resident_user_id: f.user,
        apartment_id: f.apartment.id,
        opened_by_membership_id: f.member.id,
        status: "READY",
        summary: "Leak",
        opened_at: new Date(),
      });
      const report = await insert(tx, "vh_resident_report", {
        ...f.scope,
        case_id: c.id,
        incident_id: f.incident.id,
        reporter_id: f.user,
        reporter_membership_id: f.member.id,
        apartment_id: f.apartment.id,
        category: "SANITATION",
        description: "Leak",
        location_json: {},
        status: "LINKED",
      });
      const time = new Date();
      const e = await insert(tx, "vh_business_event", {
        ...f.scope,
        incident_id: f.incident.id,
        subject_type: "WORK_ORDER",
        subject_id: w.order.id,
        event_type: "work.progressed",
        actor_type: "HUMAN",
        actor_id: f.user,
        data: {},
        correlation_id: "test",
        occurred_at: time,
        visibility: "INTERNAL",
        schema_version: 1,
        subject_version: 1,
      });
      const p = await insert(tx, "vh_work_progress", {
        ...w.scope,
        business_event_id: e.id,
        actor_user_id: f.user,
        stage: "REPAIRING",
        note: "Replacing valve",
        occurred_at: time,
        idempotency_key: "progress-1",
        expected_completion_at: future(30),
        estimated_by_user_id: f.user,
        estimate_reason: "Field inspection",
      });
      const value = {
        ...f.scope,
        incident_id: f.incident.id,
        report_id: report.id,
        recipient_user_id: f.user,
        business_event_id: e.id,
        work_progress_id: p.id,
        sequence_no: 1,
        incident_version: 1,
        headline: "Đang sửa",
        public_summary: "Kỹ thuật đang thay van",
        public_status: "IN_PROGRESS",
        expected_completion_at: p.expected_completion_at,
        source_occurred_at: time,
        prepared_by_type: "SYSTEM",
        prepared_by_id: "projector",
        idempotency_key: "update-1",
      };
      await rejectSavepoint(tx, (s) =>
        insert(s, "vh_report_update", {
          ...value,
          expected_completion_at: future(999),
        }),
      );
      await rejectSavepoint(tx, (s) =>
        insert(s, "vh_report_update", { ...value, incident_version: 999 }),
      );
      const otherUser = randomUUID();
      await insert(tx, "users", {
        id: otherUser,
        email: `${otherUser}@workforce.test`,
      });
      await rejectSavepoint(
        tx,
        (s) =>
          insert(s, "vh_report_update", {
            ...value,
            recipient_user_id: otherUser,
          }),
        "23503",
      );
      const u = await insert(tx, "vh_report_update", value);
      await rejectSavepoint(
        tx,
        (s) =>
          s`update vh_report_update set public_summary='invented' where id=${u.id}`,
      );
      const notification = {
        ...f.scope,
        business_event_id: e.id,
        type: "PROGRESS",
        subject_type: "REPORT",
        subject_id: report.id,
        title: "Progress",
        body: "Repairing",
        delivery_status: "QUEUED",
      };
      const wrong = await insert(tx, "vh_notification", {
        ...notification,
        recipient_id: otherUser,
        dedupe_key: "wrong",
      });
      const right = await insert(tx, "vh_notification", {
        ...notification,
        recipient_id: f.user,
        dedupe_key: "right",
      });
      const delivery = {
        ...f.scope,
        notification_id: wrong.id,
        report_update_id: u.id,
        channel: "CHAT",
        provider: "test",
        destination_ref: "private-thread",
        attempt_no: 1,
        idempotency_key: "delivery-1",
        status: "QUEUED",
        available_at: time,
      };
      await rejectSavepoint(tx, (s) =>
        insert(s, "vh_notification_delivery", delivery),
      );
      await insert(tx, "vh_notification_delivery", {
        ...delivery,
        notification_id: right.id,
      });
    }));

  test("SLA policy snapshots deadlines and synchronizes the incident deadline", () =>
    isolated(async (tx, f) => {
      const start = new Date();
      const p = await insert(tx, "vh_sla_policy", {
        ...f.scope,
        code: "HIGH",
        version_no: 1,
        category: "SANITATION",
        severity: "HIGH",
        response_minutes: 15,
        resolution_minutes: 60,
        clock_type: "ELAPSED",
        effective_from: new Date("2026-01-01"),
        status: "PUBLISHED",
      });
      const value = {
        ...f.scope,
        incident_id: f.incident.id,
        policy_id: p.id,
        started_at: start,
        response_due_at: new Date(+start + 15 * 60_000),
        resolution_due_at: new Date(+start + 60 * 60_000),
      };
      await rejectSavepoint(tx, (s) =>
        insert(s, "vh_incident_sla", {
          ...value,
          resolution_due_at: new Date(+start + 90 * 60_000),
        }),
      );
      await insert(tx, "vh_incident_sla", value);
      const [i] =
        await tx`select sla_due_at from vh_incident where id=${f.incident.id}`;
      expect(i!.sla_due_at).toEqual(value.resolution_due_at);
      await rejectSavepoint(
        tx,
        (s) =>
          s`update vh_incident set sla_due_at=null where id=${f.incident.id}`,
      );
      await rejectSavepoint(
        tx,
        (s) =>
          s`update vh_sla_policy set resolution_minutes=90 where id=${p.id}`,
      );
    }));

  test("concurrent group-chat appends cannot commit the same next position", async () => {
    const f = await fixture(),
      r = await runtime(db, f);
    const value = {
      tenant_id: f.tenant.id,
      workflow_session_id: r.session.id,
      sequence_no: 1,
      kind: "SYSTEM",
      body: "Wake up",
      payload_json: {},
      schema_version: 1,
      correlation_id: "test",
    };
    const outcomes = await Promise.allSettled(
      ["one", "two"].map((idempotency_key) =>
        insert(db, "platform_runtime_message", { ...value, idempotency_key }),
      ),
    );
    expect(outcomes.filter((v) => v.status === "fulfilled")).toHaveLength(1);
    const rejected = outcomes.find(
      (v) => v.status === "rejected",
    ) as PromiseRejectedResult;
    expect(["23514", "23505"]).toContain(rejected.reason.code);
    await insert(db, "platform_runtime_message", {
      ...value,
      sequence_no: 2,
      idempotency_key: "retry",
    });
  });
});
