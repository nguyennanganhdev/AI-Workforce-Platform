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

async function slot(
  c: Connection,
  f: Awaited<ReturnType<typeof fixture>>,
  capacity = 1,
) {
  const facility = await insert(c, "vh_facility", {
    ...f.scope,
    code: randomUUID(),
    name: "Court",
    category: "SPORT",
    capacity,
    fee_minor: 0,
    currency: "VND",
    booking_policy_json: {},
    exclusive_resource: true,
    status: "ACTIVE",
  });
  return insert(c, "vh_time_slot", {
    ...f.scope,
    facility_id: facility.id,
    starts_at: future(120),
    ends_at: future(180),
    capacity,
    status: "OPEN",
  });
}

describe("workforce PostgreSQL invariants", () => {
  test("P0 case keeps issue candidates as JSON without losing report-to-incident linkage", () =>
    isolated(async (tx, f) => {
      const c = await insert(tx, "vh_case", {
        ...f.scope,
        resident_user_id: f.user,
        apartment_id: f.apartment.id,
        opened_by_membership_id: f.member.id,
        status: "CLARIFYING",
        summary: "Rò nước và sàn ướt",
        opened_at: new Date(),
        intake_state_json: {
          issueCandidates: [
            { category: "TECHNICAL", summary: "Rò nước", status: "READY" },
            { category: "CLEANING", summary: "Sàn ướt", status: "NEEDS_CLARIFICATION" },
          ],
        },
      });
      expect(c.intake_state_json.issueCandidates).toHaveLength(2);
      await rejectSavepoint(tx, (s) =>
        s`update vh_case set intake_state_json='{"issueCandidates":{}}'::jsonb where id=${c.id}`,
      );
      const report = await insert(tx, "vh_resident_report", {
        ...f.scope,
        case_id: c.id,
        incident_id: f.incident.id,
        reporter_id: f.user,
        reporter_membership_id: f.member.id,
        apartment_id: f.apartment.id,
        category: "TECHNICAL",
        description: "Rò nước",
        location_json: {},
        status: "LINKED",
      });
      expect(report.incident_id).toBe(f.incident.id);
    }));
  test("rejects cross-tenant, cross-project and cross-incident references", () =>
    isolated(async (tx, f) => {
      const other = await fixture(tx);
      await rejectSavepoint(
        tx,
        (s) =>
          insert(s, "vh_tower", {
            ...f.scope,
            project_id: other.project.id,
            code: "BAD",
            name: "Bad",
            status: "ACTIVE",
          }),
        "23503",
      );
      const anotherProject = await insert(tx, "vh_project", {
        tenant_id: f.tenant.id,
        code: "P2",
        name: "Other project",
        status: "ACTIVE",
      });
      await rejectSavepoint(
        tx,
        (s) =>
          insert(s, "vh_apartment", {
            ...f.scope,
            project_id: anotherProject.id,
            tower_id: f.tower.id,
            code: "BAD",
            floor: 2,
            status: "ACTIVE",
          }),
        "23503",
      );
      const a = await action(tx, f);
      await rejectSavepoint(
        tx,
        (s) =>
          insert(s, "vh_work_order", {
            ...f.scope,
            incident_id: other.incident.id,
            task_id: f.task.id,
            action_request_id: a.id,
            executor_type: "HUMAN",
            status: "OPEN",
            attempt_no: 1,
            result: {},
          }),
        "23503",
      );
    }));

  test("rejects overlapping memberships and accepts adjacent validity ranges", () =>
    isolated(async (tx, f) => {
      const values = {
        ...f.scope,
        user_id: f.user,
        tower_id: f.tower.id,
        apartment_id: f.apartment.id,
        membership_type: "RESIDENT",
        resident_role: "OWNER",
        granted_by_user_id: f.user,
        valid_from: new Date("2026-02-01"),
        status: "ACTIVE",
      };
      await rejectSavepoint(
        tx,
        (s) => insert(s, "vh_property_membership", values),
        "23P01",
      );
      await tx`update vh_property_membership set valid_until='2026-02-01' where id=${f.member.id}`;
      expect(
        (await insert(tx, "vh_property_membership", values)).id,
      ).toBeDefined();
    }));

  test("increments versions and rejects stale compare-and-set writes", () =>
    isolated(async (tx, f) => {
      const first =
        await tx`update vh_incident set title='Assigned' where id=${f.incident.id} and version=1 returning version`;
      const stale =
        await tx`update vh_incident set title='Lost update' where id=${f.incident.id} and version=1 returning version`;
      expect(String(first[0]?.version)).toBe("2");
      expect(stale).toHaveLength(0);
      await rejectSavepoint(
        tx,
        (s) => s`update vh_incident set version=99 where id=${f.incident.id}`,
        "40001",
      );
    }));

  test("binds approval to payload and policy and keeps action payload immutable", () =>
    isolated(async (tx, f) => {
      const a = await action(tx, f);
      const values = {
        ...f.scope,
        action_request_id: a.id,
        action_payload_hash: "different",
        policy_version: "1",
        status: "PENDING",
        requested_by_id: f.user,
        expires_at: future(),
      };
      await rejectSavepoint(
        tx,
        (s) => insert(s, "vh_action_approval", values),
        "23503",
      );
      await rejectSavepoint(
        tx,
        (s) =>
          insert(s, "vh_action_approval", {
            ...values,
            action_payload_hash: a.payload_hash,
            policy_version: "wrong",
          }),
        "23503",
      );
      await insert(tx, "vh_action_approval", {
        ...values,
        action_payload_hash: a.payload_hash,
      });
      await rejectSavepoint(
        tx,
        (s) =>
          s`update vh_action_request set payload='{}'::jsonb where id=${a.id}`,
      );
    }));

  test("rejects dependency cycles", () =>
    isolated(async (tx, f) => {
      const second = await insert(tx, "vh_task", {
        ...f.scope,
        incident_id: f.incident.id,
        title: "Inspect",
        domain_type: "SANITATION",
        domain_data: {},
        domain_schema_version: 1,
        assignee_type: "HUMAN",
        status: "OPEN",
        priority: 1,
        required: true,
      });
      await tx`update vh_task set depends_on_json=${tx.json({ taskIds: [second.id] })} where id=${f.task.id}`;
      await rejectSavepoint(tx, (s) =>
        s`update vh_task set depends_on_json=${s.json({ taskIds: [f.task.id] })} where id=${second.id}`,
      );
      await rejectSavepoint(tx, (s) =>
        s`update vh_task set depends_on_json=${s.json({ taskIds: [f.task.id] })} where id=${f.task.id}`,
      );
      await rejectSavepoint(tx, (s) =>
        s`update vh_task set depends_on_json=${s.json({ taskIds: [second.id, second.id] })} where id=${f.task.id}`,
      );
    }));

  test("QC history cannot be updated, deleted or truncated; redo requires failed QC", () =>
    isolated(async (tx, f) => {
      const a = await action(tx, f);
      const base = {
        ...f.scope,
        incident_id: f.incident.id,
        task_id: f.task.id,
        action_request_id: a.id,
        executor_type: "HUMAN",
        status: "COMPLETED",
        attempt_no: 1,
        result: {},
      };
      const first = await insert(tx, "vh_work_order", base);
      await rejectSavepoint(tx, (s) =>
        insert(s, "vh_work_order", {
          ...base,
          attempt_no: 2,
          redo_of_work_order_id: first.id,
        }),
      );
      const qc = await insert(tx, "vh_qc_result", {
        ...f.scope,
        incident_id: f.incident.id,
        task_id: f.task.id,
        work_order_id: first.id,
        outcome: "FAIL",
        criteria: {},
        failed_criteria: { odour: true },
        redo_required: true,
        checked_by: f.user,
        checked_at: new Date(),
      });
      const redo = await insert(tx, "vh_work_order", {
        ...base,
        status: "OPEN",
        attempt_no: 2,
        redo_of_work_order_id: first.id,
      });
      expect(redo.redo_of_work_order_id).toBe(first.id);
      await rejectSavepoint(
        tx,
        (s) => s`update vh_qc_result set outcome='PASS' where id=${qc.id}`,
      );
      await rejectSavepoint(
        tx,
        (s) => s`delete from vh_qc_result where id=${qc.id}`,
      );
      await rejectSavepoint(tx, (s) => s`truncate vh_qc_result cascade`);
      await rejectSavepoint(
        tx,
        (s) =>
          insert(s, "vh_work_order", {
            ...base,
            attempt_no: 3,
            redo_of_work_order_id: first.id,
          }),
        "23505",
      );
    }));

  test("quarantined files cannot become report attachments", () =>
    isolated(async (tx, f) => {
      const file = await insert(tx, "vh_file_object", {
        tenant_id: f.tenant.id,
        storage_provider: "test",
        storage_key: randomUUID(),
        mime_type: "image/jpeg",
        size_bytes: 12,
        checksum: "hash",
        uploaded_by_user_id: f.user,
        upload_status: "QUARANTINED",
        visibility: "PRIVATE",
        original_filename: "proof.jpg",
      });
      const application = await insert(tx, "vh_membership_application", {
        ...f.scope,
        requested_apartment_id: f.apartment.id,
        applicant_user_id: f.user,
        requested_role: "OWNER",
        status: "PENDING",
      });
      await rejectSavepoint(tx, (s) =>
        insert(s, "vh_membership_application_file", {
          ...f.scope,
          application_id: application.id,
          file_id: file.id,
        }),
      );
      await tx`update vh_file_object set upload_status='AVAILABLE' where id=${file.id}`;
      await insert(tx, "vh_membership_application_file", {
        ...f.scope,
        application_id: application.id,
        file_id: file.id,
      });
    }));

  test("booking capacity, price snapshots and duplicate reservations are enforced", () =>
    isolated(async (tx, f) => {
      const time = await slot(tx, f, 2);
      const values = {
        ...f.scope,
        slot_id: time.id,
        apartment_id: f.apartment.id,
        booked_by_membership_id: f.member.id,
        party_size: 3,
        status: "CONFIRMED",
        price_minor: 0,
        currency: "VND",
      };
      await rejectSavepoint(tx, (s) => insert(s, "vh_booking", values));
      const booking = await insert(tx, "vh_booking", {
        ...values,
        party_size: 1,
      });
      await rejectSavepoint(
        tx,
        (s) => insert(s, "vh_booking", { ...values, party_size: 1 }),
        "23505",
      );
      await rejectSavepoint(
        tx,
        (s) => s`update vh_booking set price_minor=99 where id=${booking.id}`,
      );
      await tx`update vh_booking set status='CANCELLED', cancelled_at=now() where id=${booking.id}`;
      await insert(tx, "vh_booking", { ...values, party_size: 2 });
      await rejectSavepoint(
        tx,
        (s) => s`update vh_time_slot set capacity=1 where id=${time.id}`,
      );
    }));

  test("simulated payments cannot settle; verified allocations settle exactly once", () =>
    isolated(async (tx, f) => {
      const invoice = await insert(tx, "vh_invoice", {
        ...f.scope,
        apartment_id: f.apartment.id,
        billed_to_user_id: f.user,
        invoice_number: randomUUID(),
        period_start: "2026-09-01",
        period_end: "2026-09-30",
        due_at: future(),
        total_minor: 100000,
        currency: "VND",
        status: "DRAFT",
      });
      await rejectSavepoint(
        tx,
        (s) => s`update vh_invoice set status='ISSUED' where id=${invoice.id}`,
      );
      const line = await insert(tx, "vh_invoice_line", {
        ...f.scope,
        invoice_id: invoice.id,
        description: "Service",
        quantity: "1",
        unit_price_minor: 100000,
        total_minor: 100000,
      });
      await tx`update vh_invoice set status='ISSUED' where id=${invoice.id}`;
      await rejectSavepoint(
        tx,
        (s) => s`update vh_invoice_line set total_minor=0 where id=${line.id}`,
      );
      const paymentValues = {
        ...f.scope,
        invoice_id: invoice.id,
        initiated_by_user_id: f.user,
        amount_minor: 100000,
        currency: "VND",
        provider: "test",
        idempotency_key: randomUUID(),
        status: "SIMULATED",
      };
      const simulated = await insert(tx, "vh_payment_attempt", paymentValues);
      await rejectSavepoint(tx, (s) =>
        insert(s, "vh_payment_allocation", {
          ...f.scope,
          payment_attempt_id: simulated.id,
          invoice_id: invoice.id,
          amount_minor: 100000,
        }),
      );
      await rejectSavepoint(
        tx,
        (s) => s`update vh_invoice set status='PAID' where id=${invoice.id}`,
      );
      const success = await insert(tx, "vh_payment_attempt", {
        ...paymentValues,
        idempotency_key: randomUUID(),
        status: "SUCCEEDED",
        provider_payment_ref: randomUUID(),
        confirmed_at: new Date(),
      });
      await insert(tx, "vh_payment_allocation", {
        ...f.scope,
        payment_attempt_id: success.id,
        invoice_id: invoice.id,
        amount_minor: 100000,
      });
      expect(
        (await tx`select status from vh_invoice where id=${invoice.id}`)[0]
          ?.status,
      ).toBe("PAID");
      await rejectSavepoint(tx, (s) =>
        insert(s, "vh_payment_allocation", {
          ...f.scope,
          payment_attempt_id: success.id,
          invoice_id: invoice.id,
          amount_minor: 1,
        }),
      );
      await rejectSavepoint(
        tx,
        (s) =>
          s`update vh_payment_attempt set amount_minor=1 where id=${success.id}`,
      );
    }));

  test("AgentSpec JSON freezes before evaluation and rejects incomplete publication", () =>
    isolated(async (tx, f) => {
      const agent = await insert(tx, "agents", { id: randomUUID(), type: "built_in", configuration: {}, tenant_id: f.tenant.id, name: "Test" });
      const revision = await insert(tx, "platform_agent_version", { tenant_id: f.tenant.id, agent_id: agent.id, version_no: 1, status: "DRAFT", spec_hash: "ignored", created_by: f.user });
      await rejectSavepoint(tx, s => s`update platform_agent_version set status='READY_FOR_EVAL' where id=${revision.id}`);
      await tx`update platform_agent_version set spec_json=${tx.json({schemaVersion:1,instructions:"Propose only",capabilities:[]})} where id=${revision.id}`;
      await tx`update platform_agent_version set status='READY_FOR_EVAL' where id=${revision.id}`;
      await rejectSavepoint(tx, s => s`update platform_agent_version set spec_json='{}' where id=${revision.id}`);
      await rejectSavepoint(tx, s => s`delete from platform_agent_version where id=${revision.id}`);
      await rejectSavepoint(tx, s => s`update platform_agent_version set status='DRAFT' where id=${revision.id}`);
      for (const status of ["EVALUATING","READY_FOR_REVIEW","READY_FOR_PUBLISH"])
        await tx`update platform_agent_version set status=${status} where id=${revision.id}`;
      await rejectSavepoint(tx, s => s`update platform_agent_version set status='PUBLISHED' where id=${revision.id}`);
      await rejectSavepoint(tx, s => insert(s,"platform_agent_deployment", { tenant_id:f.tenant.id, agent_version_id:revision.id, environment:"PRODUCTION",scope_type:"TENANT",scope_ref:f.tenant.id,status:"ACTIVE",deployed_at:new Date() }));
    }));

  test("JSON evaluation and independent approvals publish a revision and remain immutable", () =>
    isolated(async (tx,f) => {
      const reviewer=randomUUID();
      await insert(tx,"users",{id:reviewer,email:`${reviewer}@workforce.test`});
      const agent=await insert(tx,"agents",{id:randomUUID(),tenant_id:f.tenant.id,type:"built_in",name:"Test",configuration:{}});
      const revision=await insert(tx,"platform_agent_version",{tenant_id:f.tenant.id,agent_id:agent.id,version_no:1,status:"DRAFT",spec_hash:"ignored",created_by:f.user,spec_json:{schemaVersion:1,instructions:"Read only",capabilities:[]}});
      const session=await insert(tx,"platform_workflow_session",{tenant_id:f.tenant.id,domain_namespace:"vinhomes",subject_type:"INCIDENT",subject_ref:f.incident.id,runtime_provider:"test",environment:"PRODUCTION",status:"PENDING",plan_json:{steps:[{key:"analyze",dependsOn:[]}]},trace_id:randomUUID()});
      const runValues={tenant_id:f.tenant.id,workflow_session_id:session.id,step_key:"analyze",agent_id:agent.id,agent_version_id:revision.id,status:"RUNNING",input_json:{},output_json:{},trace_id:randomUUID()};
      await rejectSavepoint(tx,s=>insert(s,"platform_agent_run",runValues));
      for(const status of ["READY_FOR_EVAL","EVALUATING"]) await tx`update platform_agent_version set status=${status} where id=${revision.id}`;
      const values={tenant_id:f.tenant.id,agent_version_id:revision.id,status:"PASSED",result:"PASS",tests_json:[{code:"C1",input:{},expected:{}}],results_json:["CONTRACT","QUALITY","SAFETY","REGRESSION"].map(type=>({type,status:"PASS",evidenceRef:"object:test"})),evidence_json:[{ref:"object:test"}],evaluated_by:reviewer,environment_snapshot:{},model_snapshot:{},started_at:new Date(),completed_at:new Date()};
      await rejectSavepoint(tx,s=>insert(s,"platform_eval_run",{...values,result:null}));
      await rejectSavepoint(tx,s=>insert(s,"platform_eval_run",{...values,evidence_json:[]}));
      const evaluation=await insert(tx,"platform_eval_run",values);
      await rejectSavepoint(tx,s=>s`update platform_eval_run set results_json='[]' where id=${evaluation.id}`);
      await tx`update platform_agent_version set status='READY_FOR_REVIEW' where id=${revision.id}`;
      const approval={tenant_id:f.tenant.id,agent_version_id:revision.id,approval_type:"DOMAIN",reviewer_id:reviewer,status:"APPROVED",decided_at:new Date()};
      await rejectSavepoint(tx,s=>insert(s,"platform_publish_approval",{...approval,reviewer_id:f.user}));
      for(const approval_type of ["DOMAIN","EVALUATION","SECURITY","PLATFORM"]) await insert(tx,"platform_publish_approval",{...approval,approval_type});
      for(const status of ["READY_FOR_PUBLISH","PUBLISHED"]) await tx`update platform_agent_version set status=${status} where id=${revision.id}`;
      await insert(tx,"platform_agent_deployment",{tenant_id:f.tenant.id,agent_version_id:revision.id,environment:"PRODUCTION",scope_type:"TENANT",scope_ref:f.tenant.id,status:"ACTIVE",deployed_at:new Date()});
      expect((await insert(tx,"platform_agent_run",runValues)).agent_version_id).toBe(revision.id);
      await rejectSavepoint(tx,s=>s`update platform_workflow_session set plan_json='{"steps":[]}' where id=${session.id}`);
      await tx`update platform_agent_version set status='SUSPENDED' where id=${revision.id}`;
      await rejectSavepoint(tx,s=>insert(s,"platform_agent_run",{...runValues,attempt_no:2}));
    }));

  test("workflow JSON rejects missing, duplicate, cyclic and dangling plan steps", () =>
    isolated(async(tx,f)=>{
      const value={tenant_id:f.tenant.id,domain_namespace:"vinhomes",subject_type:"INCIDENT",subject_ref:f.incident.id,runtime_provider:"test",environment:"DEVELOPMENT",status:"PENDING",trace_id:randomUUID()};
      for(const plan_json of [{},{steps:[{key:"a",dependsOn:["b"]}]},{steps:[{key:"a",dependsOn:[]},{key:"a",dependsOn:[]}]},{steps:[{key:"a",dependsOn:["b"]},{key:"b",dependsOn:["a"]}]}])
        await rejectSavepoint(tx,s=>insert(s,"platform_workflow_session",{...value,plan_json}));
      await insert(tx,"platform_workflow_session",{...value,plan_json:{steps:[{key:"a",dependsOn:[]},{key:"b",dependsOn:["a"]}]}});
      await rejectSavepoint(tx,s=>s`update vh_task set depends_on_json='{}' where id=${f.task.id}`);
    }));

  test("confirmation is scoped to the reporter and current resolution round", () =>
    isolated(async (tx, f) => {
      const c = await insert(tx, "vh_case", {
        ...f.scope,
        resident_user_id: f.user,
        apartment_id: f.apartment.id,
        opened_by_membership_id: f.member.id,
        status: "READY",
        summary: "Test",
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
        description: "Test",
        location_json: {},
        status: "LINKED",
      });
      await tx`update vh_incident set status='RESOLVED', resolved_at=now(), resolution_version=2 where id=${f.incident.id}`;
      const response = {
        ...f.scope,
        report_id: report.id,
        incident_id: f.incident.id,
        resolution_version: 1,
        response: "ACCEPTED",
        confirmed_by_user_id: f.user,
      };
      await rejectSavepoint(tx, (s) =>
        insert(s, "vh_resident_confirmation", response),
      );
      await insert(tx, "vh_resident_confirmation", {
        ...response,
        resolution_version: 2,
      });
      await rejectSavepoint(
        tx,
        (s) =>
          insert(s, "vh_resident_confirmation", {
            ...response,
            resolution_version: 2,
          }),
        "23505",
      );
    }));

  test("command receipts have actor/command scoped keys and immutable completed responses", () =>
    isolated(async (tx, f) => {
      const values = {
        tenant_id: f.tenant.id,
        actor_user_id: f.user,
        command_type: "CREATE_REPORT",
        idempotency_key: "request-1",
        payload_hash: "hash-1",
        subject_type: "REPORT",
        status: "IN_PROGRESS",
      };
      const receipt = await insert(tx, "vh_command_receipt", values);
      await rejectSavepoint(
        tx,
        (s) => insert(s, "vh_command_receipt", values),
        "23505",
      );
      await insert(tx, "vh_command_receipt", {
        ...values,
        command_type: "BOOK_FACILITY",
      });
      await tx`update vh_command_receipt set status='COMPLETED', completed_at=now(), response_json='{"ok":true}'::jsonb where id=${receipt.id}`;
      await rejectSavepoint(
        tx,
        (s) =>
          s`update vh_command_receipt set response_json='{}'::jsonb where id=${receipt.id}`,
      );
      await rejectSavepoint(
        tx,
        (s) =>
          s`update vh_command_receipt set payload_hash='different' where id=${receipt.id}`,
      );
    }));

  test("event registration enforces capacity, closure and attendance lineage", () =>
    isolated(async (tx, f) => {
      const event = await insert(tx, "vh_community_event", {
        ...f.scope,
        title: "Residents",
        starts_at: future(120),
        ends_at: future(180),
        registration_closes_at: future(60),
        capacity: 2,
        status: "PUBLISHED",
      });
      const values = {
        ...f.scope,
        event_id: event.id,
        membership_id: f.member.id,
        guest_count: 2,
        status: "REGISTERED",
      };
      await rejectSavepoint(tx, (s) =>
        insert(s, "vh_event_registration", values),
      );
      await rejectSavepoint(tx, (s) =>
        insert(s, "vh_event_registration", { ...values, status: "ATTENDED" }),
      );
      const registration = await insert(tx, "vh_event_registration", {
        ...values,
        guest_count: 1,
      });
      await rejectSavepoint(
        tx,
        (s) => s`update vh_community_event set capacity=1 where id=${event.id}`,
      );
      await tx`update vh_event_registration set status='CANCELLED' where id=${registration.id}`;
      await tx`update vh_community_event set status='CANCELLED' where id=${event.id}`;
      await rejectSavepoint(
        tx,
        (s) =>
          s`update vh_event_registration set status='REGISTERED' where id=${registration.id}`,
      );
    }));

  test("memory vectors require approved revisions and revocation queues deletion", () =>
    isolated(async (tx, f) => {
      const namespace = await insert(tx, "platform_memory_namespace", {
        tenant_id: f.tenant.id,
        namespace_type: "TENANT",
        subject_ref: f.tenant.id,
        retention_policy: {},
        status: "ACTIVE",
      });
      const item = await insert(tx, "platform_memory_item", {
        tenant_id: f.tenant.id,
        memory_namespace_id: namespace.id,
        memory_type: "FACT",
        source_type: "REVIEW",
        source_ref: "test",
        status: "ACTIVE",
      });
      const revision = await insert(tx, "platform_memory_revision", {
        tenant_id: f.tenant.id,
        memory_item_id: item.id,
        revision_no: 1,
        content_ref: "object:test",
        content_hash: "v1",
        redaction_status: "CLEAN",
      });
      const vector = {
        tenant_id: f.tenant.id,
        memory_revision_id: revision.id,
        qdrant_collection: "test",
        qdrant_point_id: randomUUID(),
        embedding_model: "test",
        dimension: 3,
        sync_status: "PENDING",
      };
      await rejectSavepoint(tx, (s) =>
        insert(s, "platform_memory_vector_ref", vector),
      );
      await insert(tx, "platform_memory_review", {
        tenant_id: f.tenant.id,
        memory_revision_id: revision.id,
        reviewer_id: f.user,
        decision: "APPROVED",
        reason: "Verified",
        reviewed_at: new Date("2026-01-01"),
      });
      const stored = await insert(tx, "platform_memory_vector_ref", vector);
      await insert(tx, "platform_memory_review", {
        tenant_id: f.tenant.id,
        memory_revision_id: revision.id,
        reviewer_id: f.user,
        decision: "REVOKED",
        reason: "Removed",
        reviewed_at: new Date("2026-01-02"),
      });
      expect(
        (
          await tx`select sync_status from platform_memory_vector_ref where id=${stored.id}`
        )[0]?.sync_status,
      ).toBe("DELETE_PENDING");
      await rejectSavepoint(
        tx,
        (s) =>
          s`update platform_memory_revision set content_hash='changed' where id=${revision.id}`,
      );
    }));

  test("tenant RLS fails closed for a non-owner, including WITH CHECK", async () => {
    // A transaction-local role is rolled back even when an assertion fails.
    await isolated(async (tx, f) => {
      const role = `wf_test_${randomUUID().replaceAll("-", "")}`;
      await tx`create role ${tx(role)} nologin`;
      await tx`grant usage on schema public to ${tx(role)}`;
      await tx`grant select, insert on vh_project to ${tx(role)}`;
      await tx`set local role ${tx(role)}`;
      expect(await tx`select id from vh_project`).toHaveLength(0);
      await tx`select set_config('app.tenant_id',${f.tenant.id},true)`;
      expect(
        (await tx`select id from vh_project`).map((row) => row.id),
      ).toEqual([f.project.id]);
      await rejectSavepoint(
        tx,
        (s) =>
          insert(s, "vh_project", {
            tenant_id: randomUUID(),
            code: "BAD",
            name: "Bad",
            status: "ACTIVE",
          }),
        "42501",
      );
      await tx`reset role`;
    });
  });

  test("two concurrent bookings cannot consume the last capacity twice", async () => {
    const f = await fixture();
    const time = await slot(db, f);
    const otherUser = randomUUID();
    await insert(db, "users", {
      id: otherUser,
      email: `${otherUser}@workforce.test`,
    });
    await insert(db, "platform_tenant_membership", {
      tenant_id: f.tenant.id,
      user_id: otherUser,
      status: "ACTIVE",
      valid_from: new Date("2026-01-01"),
    });
    const otherMember = await insert(db, "vh_property_membership", {
      ...f.scope,
      user_id: otherUser,
      tower_id: f.tower.id,
      apartment_id: f.apartment.id,
      membership_type: "RESIDENT",
      resident_role: "HOUSEHOLD",
      granted_by_user_id: f.user,
      valid_from: new Date("2026-01-01"),
      status: "ACTIVE",
    });
    const values = {
      ...f.scope,
      slot_id: time.id,
      apartment_id: f.apartment.id,
      party_size: 1,
      status: "CONFIRMED",
      price_minor: 0,
      currency: "VND",
    };
    const results = await Promise.allSettled(
      [f.member.id, otherMember.id].map((member) =>
        db.begin(async (tx) => {
          await insert(tx, "vh_booking", {
            ...values,
            booked_by_membership_id: member,
          });
          await tx`select pg_sleep(0.1)`;
        }),
      ),
    );
    expect(results.filter((r) => r.status === "fulfilled")).toHaveLength(1);
    expect(results.filter((r) => r.status === "rejected")).toHaveLength(1);
    expect(
      (
        await db`select sum(party_size) as occupied from vh_booking where slot_id=${time.id}`
      )[0]?.occupied,
    ).toBe("1");
  });
});
