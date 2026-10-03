/** Manual HTTP + PostgreSQL check, exclusively against the local faker database. */
import assert from "node:assert/strict";
import { randomBytes, randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { sql } from "drizzle-orm";
import { createDatabase } from "../src/db/client";
import {
  hashCallbackToken,
  mintCallbackToken,
  mintRunAssertion,
} from "../src/agents/callback-token";
import { createTechnicalApiRoutes } from "../src/technical-api/routes";
import { createTechnicalApiDependencies } from "../src/technical-api/runtime";

const local = resolve(
  import.meta.dir,
  "../../services/vinhomes-api/.local-v3-faker",
);
async function env(file: string) {
  return Object.fromEntries(
    (await readFile(resolve(local, file), "utf8"))
      .split(/\r?\n/)
      .filter((line) => line && !line.startsWith("#"))
      .map((line) => {
        const p = line.indexOf("=");
        return [line.slice(0, p), line.slice(p + 1)];
      }),
  );
}
const runtimeEnv = await env("technical-api.env");
const ownerEnv = await env("migration.env");
const address = new URL(ownerEnv.DATABASE_URL!);
assert.equal(address.hostname, "127.0.0.1");
assert.equal(address.pathname, "/vinhomes_v3");
const owner = createDatabase(ownerEnv.DATABASE_URL!);
const database = createDatabase(runtimeEnv.TECHNICAL_API_DATABASE_URL!);
const tenantId = runtimeEnv.TECHNICAL_API_TENANT_ID!;
const key = randomBytes(32).toString("base64");
const token = mintCallbackToken();
const prefix = "/buildings/77777777-7777-5777-a777-777777777777";
const app = createTechnicalApiRoutes(
  createTechnicalApiDependencies({
    database,
    tenantId,
    encryptionKey: key,
    lookupToken: async (hash) =>
      hash === hashCallbackToken(token) ? { id: "demo-technical-a2" } : null,
  }),
);
const headers = {
  "X-OpenBot-Agent-Token": token,
  "X-OpenBot-Run": mintRunAssertion(
    {
      botId: "demo-technical-a2",
      actorId: "local-v3-management",
      runId: randomUUID(),
    },
    key,
  ),
  "Content-Type": "application/json",
};
async function request(
  path: string,
  expected: number[],
  body?: unknown,
  idempotency?: string,
) {
  const response = await app.request(path, {
    method: body ? "POST" : "GET",
    headers: {
      ...headers,
      ...(idempotency ? { "Idempotency-Key": idempotency } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json();
  assert.ok(
    expected.includes(response.status),
    `${path}: ${response.status} ${JSON.stringify(data)}`,
  );
  console.log(`${response.status} ${path.split("?")[0]}`);
  return data;
}
try {
  const now = new Date().toISOString(),
    from = new Date(Date.now() - 86400000).toISOString();
  await request("/tools", [200]);
  await request(
    "/buildings/88888888-8888-4888-8888-888888888888/assets?asset_id=ASSET-DEMO-1",
    [403],
  );
  await request(
    "/buildings/------------------------------------/assets?asset_id=ASSET-DEMO-1",
    [400],
  );
  await request(`${prefix}/assets?asset_id=ASSET-DEMO-1`, [200]);
  await request(
    `${prefix}/outages/active?service_type=water&occurred_at=${now}`,
    [200],
  );
  await request(
    `${prefix}/utility-schedules?utility_type=water&from=${from}&to=${now}`,
    [200],
  );
  await request(
    `${prefix}/sensor-readings?sensor_id=SENSOR-DEMO-SUPPLY-PRESSURE&metric=supply_pressure&from=${from}&to=${now}`,
    [200],
  );
  await request(
    `${prefix}/assets/ASSET-DEMO-1/maintenance-history?from=${from}&to=${now}`,
    [200],
  );
  await request(
    `${prefix}/sops?issue_code=TECH.PLUMB.SEWAGE_BACKFLOW&query=thoat%20nuoc`,
    [200, 404],
  );
  const [work] =
    await owner.execute(sql`select w.id,w.ticket_id,w.status,t.unit_id,a.id as assignment_id,a.accepted_at
    from work_orders w join tickets t on t.tenant_id=w.tenant_id and t.id=w.ticket_id
    join work_assignments a on a.tenant_id=w.tenant_id and a.work_order_id=w.id
    join staff_profiles s on s.tenant_id=a.tenant_id and s.id=a.staff_id
    where w.tenant_id=${tenantId} and a.status='accepted' and s.user_id='local-v3-technical'
    and t.building_id='77777777-7777-5777-a777-777777777777' limit 1`);
  assert.ok(work);
  const body = {
    asset_id: "ASSET-DEMO-1",
    metric: "supply_pressure",
    value: 2.5,
    unit: "bar",
    measured_at: from,
    measured_by: { kind: "device", source_id: "SENSOR-DEMO-SUPPLY-PRESSURE" },
    source: "bms",
  };
  const idempotency = randomUUID(),
    path = `${prefix}/work-orders/${work.id}/measurements`;
  const first = await request(path, [201], body, idempotency);
  assert.deepEqual(await request(path, [201], body, idempotency), first);
  await request(path, [409], { ...body, value: 2.6 }, idempotency);
  await request(path, [400], { ...body, tenant_id: tenantId }, randomUUID());
  const result =
    await owner.execute(sql`select count(*)::int as count from vh_technical_measurement_records
    where tenant_id=${tenantId} and id=${first.data.measurement_id}`);
  assert.equal(result[0]?.count, 1);
  headers["X-OpenBot-Run"] = mintRunAssertion(
    {
      botId: "demo-technical-a2",
      actorId: "local-v3-technical",
      runId: randomUUID(),
    },
    key,
  );
  const evidence =
    await owner.execute(sql`select id from evidence_items where tenant_id=${tenantId}
    and ticket_id=${work.ticket_id} and purpose='after' and work_order_id=${work.id}`);
  const submitted = await request(
    `${prefix}/work-orders/${work.id}/executor-results`,
    [201],
    {
      assignment_id: work.assignment_id,
      checklist: [{ item_code: "DRAIN_CLEAR", status: "passed" }],
      measurement_ids: [first.data.measurement_id],
      evidence_ids: evidence.map((r) => r.id),
      started_at: new Date(
        Math.max(
          new Date(String(work.accepted_at)).getTime(),
          Date.now() - 60000,
        ),
      ).toISOString(),
      completed_at: new Date(Date.now() - 1000).toISOString(),
    },
    randomUUID(),
  );
  const documents = await owner.execute(
    sql`select id from knowledge_documents where tenant_id=${tenantId} and code='SOP-DEMO-DRAIN'`,
  );
  const verified = await request(
    `${prefix}/work-orders/${work.id}/executor-results/${submitted.data.result_id}/verification`,
    [200],
    {
      incident_id: work.ticket_id,
      sop_document_ids: documents.map((r) => r.id),
    },
  );
  await request(
    `${prefix}/assets/ASSET-DEMO-1/maintenance-events`,
    verified.data.verification_status === "VERIFIED" ? [201] : [409],
    {
      workorder_id: work.id,
      verified_result_id: submitted.data.result_id,
      outcome: "Kiểm tra thoát nước demo",
      source_refs: [
        `result:${submitted.data.result_id}`,
        "doc:SOP-DEMO-DRAIN:v1",
      ],
    },
    randomUUID(),
  );
  headers["X-OpenBot-Run"] = mintRunAssertion(
    {
      botId: "demo-technical-a2",
      actorId: "local-v3-management",
      runId: randomUUID(),
    },
    key,
  );
  await request(
    `${prefix}/vendor-dispatch-requests`,
    [202],
    {
      incident_id: work.ticket_id,
      workorder_id: work.id,
      service: `plumbing-demo-${randomUUID()}`,
      required_specialty_code: randomUUID(),
      reason: "Đề nghị nhà thầu kiểm tra thoát nước demo",
      urgency: "routine",
    },
    randomUUID(),
  );
  if (work.unit_id)
    await request(
      `${prefix}/apartment-entry-requests`,
      [202, 409],
      {
        incident_id: work.ticket_id,
        unit_id: "e5555555-5555-4555-8555-555555555555",
        reason: "Kiểm tra điểm rò nước khi cư dân vắng nhà",
        contact_attempts: [
          {
            channel: "phone",
            attempted_at: new Date(Date.now() - 3600000).toISOString(),
            outcome: "no_answer",
          },
          {
            channel: "app",
            attempted_at: new Date(Date.now() - 1800000).toISOString(),
            outcome: "no_answer",
          },
        ],
      },
      randomUUID(),
    );
  await request(
    `${prefix}/area-restriction-requests`,
    [202, 400, 409],
    {
      incident_id: work.ticket_id,
      workorder_id: work.id,
      area: "Sảnh demo",
      hazard: "Nước tràn sàn",
      reason: "Đề nghị hạn chế khu vực có nước tràn",
      evidence_ids: evidence.length ? evidence.map((r) => r.id) : [],
    },
    randomUUID(),
  );
  const scopes =
    await owner.execute(sql`select id from access_scopes where tenant_id=${tenantId}
    and kind='building' and building_id='77777777-7777-5777-a777-777777777777'`);
  await request(
    `${prefix}/utility-isolation-requests`,
    [202, 400, 409],
    {
      incident_id: work.ticket_id,
      workorder_id: work.id,
      utility_type: "water",
      scope_ids: scopes.map((r) => r.id),
      reason: "Đề nghị cô lập nước để kiểm tra demo",
      planned_start: new Date(Date.now() + 60000).toISOString(),
      planned_end: new Date(Date.now() + 3600000).toISOString(),
      evidence_ids: evidence.map((r) => r.id),
    },
    randomUUID(),
  );
  const [after] = await owner.execute(
    sql`select status from work_orders where tenant_id=${tenantId} and id=${work.id}`,
  );
  assert.equal(after?.status, work.status);
  assert.equal((await app.request("/tools")).status, 403);
  console.log(
    "PASS: database persistence, exact replay, key conflict, identity refusal, auth and unchanged work-order state.",
  );
} finally {
  await database.$client.close();
  await owner.$client.close();
}
