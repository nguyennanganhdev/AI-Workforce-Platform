/** Isolated PostgreSQL/WASM verification. Never opens DATABASE_URL. */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";
import { randomUUID } from "node:crypto";
import { PGlite } from "@electric-sql/pglite";
import { vector } from "@electric-sql/pglite-pgvector";
import { btree_gist } from "@electric-sql/pglite/contrib/btree_gist";

const server = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const db = new PGlite({ extensions: { vector, btree_gist } });
let checks = 0;
const insert = async (table, data) => {
  const keys = Object.keys(data);
  const { rows } = await db.query(
    `INSERT INTO "${table}" (${keys.map((k) => `"${k}"`).join(",")}) VALUES (${keys.map((_, i) => "$" + (i + 1)).join(",")}) RETURNING *`,
    Object.values(data),
  );
  return rows[0];
};
async function rejects(name, fn) {
  await assert.rejects(fn);
  checks++;
  console.log("PASS", name);
}
try {
  if (!process.argv[2]) await db.exec("CREATE EXTENSION vector;");
  // Every table the loaded SQL declares must exist afterwards. Counted from the SQL itself, so
  // adding a table to the design does not need this script edited.
  let declared = 0;
  for (const path of process.argv[2]
    ? [process.argv[2]]
    : [
        "../.codex-artifacts/schema-check/schema.sql",
        "src/db/invariants.sql",
        "src/db/generated-invariants.sql",
      ]) {
    const statements = await readFile(resolve(server, path), "utf8");
    declared += (statements.match(/^CREATE TABLE /gm) ?? []).length;
    await db.exec(statements);
  }
  const { rows } = await db.query(
    "SELECT count(*)::int AS n FROM pg_tables WHERE schemaname='public'",
  );
  assert.ok(declared > 0, "no CREATE TABLE statement was loaded");
  assert.equal(rows[0].n, declared);
  checks++;
  const t1 = await insert("tenants", {
    code: "tenant-a",
    name: "A",
    status: "active",
  });
  const t2 = await insert("tenants", {
    code: "tenant-b",
    name: "B",
    status: "active",
  });
  await insert("users", {
    id: "alice",
    email: "alice@example.test",
    status: "active",
  });
  await insert("users", {
    id: "bob",
    phone_e164: "+84900000001",
    status: "active",
  });
  const d1 = await insert("domains", {
    tenant_id: t1.id,
    code: "housing",
    name: "Housing",
    status: "active",
  });
  await rejects("cross-tenant geographical FK", () =>
    insert("sites", {
      tenant_id: t2.id,
      domain_id: d1.id,
      code: "s",
      name: "S",
      status: "active",
    }),
  );
  const scope = await insert("access_scopes", {
    tenant_id: t1.id,
    kind: "tenant",
  });
  const policy = await insert("triage_policy_versions", {
    tenant_id: t1.id,
    domain_id: d1.id,
    policy_code: "risk",
    version_no: 1,
    status: "draft",
    engine_version: "1",
    input_schema_version: "1",
    input_schema: {},
    unknown_priority: "high",
    review_timeout_seconds: 60,
    max_fact_age_seconds: 600,
    max_queue_wait_seconds: 600,
    policy_hash: "hash",
    created_by: "alice",
  });
  const rule = await insert("triage_rules", {
    tenant_id: t1.id,
    policy_version_id: policy.id,
    rule_code: "default",
    rule_kind: "decision",
    precedence: 1,
    condition_expr: { all: [] },
    severity_result: "moderate",
    priority_result: "normal",
    reason_template: "normal",
  });
  await db.query(
    "UPDATE triage_policy_versions SET status='published',published_by='alice',published_at=now() WHERE id=$1",
    [policy.id],
  );
  await rejects("published rules cannot change", () =>
    db.query("UPDATE triage_rules SET priority_result='low' WHERE id=$1", [
      rule.id,
    ]),
  );
  const bindingData = {
    tenant_id: t1.id,
    domain_id: d1.id,
    scope_id: scope.id,
    request_kind: "incident",
    policy_version_id: policy.id,
    valid_from: "2026-01-01T00:00:00Z",
    status: "active",
    configured_by: "alice",
  };
  const policyBinding = await insert("triage_policy_bindings", bindingData);
  await rejects("overlapping fallback policy excluded", () =>
    insert("triage_policy_bindings", bindingData),
  );
  const pa = await insert("execution_principals", {
    tenant_id: t1.id,
    kind: "user",
    user_id: "alice",
    status: "active",
  });
  const pb = await insert("execution_principals", {
    tenant_id: t1.id,
    kind: "user",
    user_id: "bob",
    status: "active",
  });
  const backend = await insert("runtime_backends", {
    code: "lg",
    framework: "langgraph",
    sdk_language: "python",
    package_version: "pinned",
    backend_kind: "postgres",
    connection_secret_ref: "vault/lg",
    schema_name: "lg_runtime",
  });
  const identity = await insert("runtime_identities", {
    tenant_id: t1.id,
    backend_id: backend.id,
    principal_id: pa.id,
    runtime_user_key: "opaque-a",
    status: "active",
  });
  await insert("agents", {
    id: "reception",
    tenant_id: t1.id,
    name: "Reception",
    type: "built_in",
    configuration: {},
    purpose: "reception",
    status: "active",
  });
  const av = await insert("agent_versions", {
    tenant_id: t1.id,
    agent_id: "reception",
    version_no: 1,
    runtime: "langgraph",
    framework_version: "pinned",
    instructions: "Reception",
    config: {},
    config_hash: "hash",
    created_by: "alice",
  });
  await insert("channels", {
    id: "alice-room",
    tenant_id: t1.id,
    name: "Alice",
    description: "Reception",
    kind: "reception",
  });
  const runtime = {
    tenant_id: t1.id,
    identity_id: identity.id,
    channel_id: "alice-room",
    agent_id: "reception",
    agent_version_id: av.id,
    audience_kind: "personal",
    customer_user_id: "bob",
    runtime_session_key: "thread-a",
    status: "active",
    policy_version: "1",
    backend_id: backend.id,
  };
  await rejects("thread cannot belong to another user", () =>
    insert("runtime_session_bindings", runtime),
  );
  await insert("runtime_session_bindings", {
    ...runtime,
    customer_user_id: "alice",
  });
  await rejects("thread cannot be assigned twice in backend", () =>
    insert("runtime_session_bindings", {
      ...runtime,
      customer_user_id: "alice",
      status: "closed",
    }),
  );
  const memory = await insert("memory_namespaces", {
    tenant_id: t1.id,
    owner_principal_id: pa.id,
    kind: "personal",
    namespace_key: "alice-memory",
    purpose: "preferences",
    status: "active",
  });
  await rejects("memory owner cannot be reassigned", () =>
    db.query("UPDATE memory_namespaces SET owner_principal_id=$1 WHERE id=$2", [
      pb.id,
      memory.id,
    ]),
  );
  const ticket = await insert("tickets", {
    tenant_id: t1.id,
    code: "T1",
    requester_user_id: "alice",
    channel_id: "alice-room",
    title: "Leak",
    description: "Reported leak",
    status: "new",
    contact_name: "Alice",
    contact_phone: "+84900000002",
    address_snapshot: {},
    domain_id: d1.id,
    request_kind: "incident",
  });
  const assessment = await insert("ticket_assessments", {
    tenant_id: t1.id,
    ticket_id: ticket.id,
    ticket_generation: 0,
    basis_ticket_version: 0,
    stage: "intake",
    assessor_kind: "human",
    assessor_user_id: "alice",
    input_schema_version: "1",
    facts: {},
    proposed_severity: "moderate",
    proposed_urgency: "soon",
    rationale: "Reported facts",
    observed_at: new Date(),
    submitted_at: new Date(),
    idempotency_key: "assessment-1",
  });
  const decision = {
    tenant_id: t1.id,
    ticket_id: ticket.id,
    ticket_generation: 0,
    decision_seq: 1,
    assessment_id: assessment.id,
    policy_binding_id: policyBinding.id,
    policy_version_id: policy.id,
    outcome: "applied",
    decision_mode: "automatic",
    severity: "moderate",
    priority: "normal",
    is_emergency: false,
    evaluation_trace: {},
    reason: "Rule result",
    basis_ticket_version: 0,
    applied_ticket_version: 1,
    decided_at: new Date(),
    idempotency_key: "decision-1",
  };
  await rejects(
    "applied decision cannot commit without ticket projection",
    () => insert("ticket_triage_decisions", decision),
  );
  await db.exec("BEGIN");
  const applied = await insert("ticket_triage_decisions", decision);
  await db.query(
    "UPDATE tickets SET current_triage_decision_id=$1,priority='normal',severity='moderate',triage_status='confirmed',version=1 WHERE id=$2",
    [applied.id, ticket.id],
  );
  await db.exec("COMMIT");
  checks++;
  await rejects("stale decision cannot overwrite current", () =>
    insert("ticket_triage_decisions", {
      ...decision,
      idempotency_key: "stale",
      decision_seq: 2,
    }),
  );
  await rejects("ticket priority must match applied decision", () =>
    db.query("UPDATE tickets SET priority='low' WHERE id=$1", [ticket.id]),
  );
  await rejects("assessment cannot be edited after submission", () =>
    db.query("UPDATE ticket_assessments SET rationale='changed' WHERE id=$1", [
      assessment.id,
    ]),
  );
  const location = await insert("storage_locations", {
    tenant_id: t1.id,
    provider: "minio",
    endpoint_ref: "minio",
    bucket_name: "evidence",
    tenant_prefix: "t/a/",
    credential_secret_ref: "vault/s3",
    encryption_mode: "sse_s3",
    purpose: "evidence",
    status: "active",
  });
  const file = await insert("files", {
    tenant_id: t1.id,
    owner_principal_id: pa.id,
    scope_kind: "ticket",
    ticket_id: ticket.id,
    status: "staged",
    original_name: "leak.jpg",
  });
  const object = {
    tenant_id: t1.id,
    file_id: file.id,
    location_id: location.id,
    object_key: "t/b/leak.jpg",
    version_id: "v1",
    variant: "original",
    mime_type: "image/jpeg",
    size_bytes: 10,
    sha256: "a".repeat(64),
    scan_status: "clean",
    verified_at: new Date(),
    encryption_mode: "sse_s3",
    status: "ready",
  };
  await rejects("S3 object key cannot escape tenant prefix", () =>
    insert("file_objects", object),
  );
  const original = await insert("file_objects", {
    ...object,
    object_key: "t/a/leak.jpg",
  });
  await db.query(
    "UPDATE files SET accepted_object_id=$1,status='ready' WHERE id=$2",
    [original.id, file.id],
  );
  await rejects("accepted evidence hash is immutable", () =>
    db.query("UPDATE file_objects SET sha256=$1 WHERE id=$2", [
      "b".repeat(64),
      original.id,
    ]),
  );
  await rejects("audit truncate is forbidden", () =>
    db.exec("TRUNCATE audit_events"),
  );
  await db.exec(
    "CREATE ROLE app_test NOLOGIN; GRANT USAGE ON SCHEMA public TO app_test; GRANT SELECT ON domains TO app_test; SET ROLE app_test;",
  );
  const noScope = await db.query("SELECT * FROM domains");
  assert.equal(noScope.rows.length, 0);
  checks++;
  await db.query("SELECT set_config('app.tenant_id',$1,false)", [t2.id]);
  const wrongTenant = await db.query("SELECT * FROM domains");
  assert.equal(wrongTenant.rows.length, 0);
  checks++;
  await db.query("SELECT set_config('app.tenant_id',$1,false)", [t1.id]);
  const rightTenant = await db.query("SELECT * FROM domains");
  assert.equal(rightTenant.rows.length, 1);
  checks++;
  console.log(
    `PASS ${checks} isolated PostgreSQL baseline and invariant checks`,
  );
} finally {
  await db.close();
}
