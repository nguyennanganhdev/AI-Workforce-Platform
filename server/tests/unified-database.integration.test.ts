import { afterAll, expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import postgres from "postgres";
import { testDatabaseUrl } from "./support/database";

const db = postgres(testDatabaseUrl(), { max: 3, onnotice: () => {} });
afterAll(() => db.end());
type Tx = postgres.TransactionSql;
async function row(tx: Tx, table: string, data: Record<string, unknown>) {
  return (await tx`insert into ${tx(table)} ${tx(data)} returning *`)[0]!;
}
async function isolated(run: (tx: Tx) => Promise<void>) {
  const rollback = new Error("rollback fixture");
  try {
    await db.begin(async (tx) => {
      await run(tx);
      throw rollback;
    });
  } catch (e) {
    if (e !== rollback) throw e;
  }
}
async function rejects(tx: Tx, run: (s: Tx) => Promise<unknown>, code: string) {
  let caught: unknown;
  try {
    await tx.savepoint(run);
  } catch (e) {
    caught = e;
  }
  expect((caught as { code?: string })?.code).toBe(code);
}
async function tenant(tx: Tx) {
  return row(tx, "platform_tenant", {
    code: randomUUID(),
    name: "Test",
    status: "ACTIVE",
  });
}
async function member(tx: Tx, tenantId: string) {
  const id = randomUUID();
  await row(tx, "users", { id, email: `${id}@unified.test` });
  await row(tx, "platform_tenant_membership", {
    tenant_id: tenantId,
    user_id: id,
    status: "ACTIVE",
    valid_from: new Date("2026-01-01"),
  });
  return id;
}
async function channel(tx: Tx, tenantId: string) {
  return row(tx, "channels", {
    id: randomUUID(),
    tenant_id: tenantId,
    name: "Resident",
    description: "Test",
  });
}

test("canonical channel supports several members, persists once and emits an atomic outbox intent", () =>
  isolated(async (tx) => {
    const t = await tenant(tx),
      c = await channel(tx, t.id);
    const first = await member(tx, t.id),
      second = await member(tx, t.id);
    for (const user of [first, second])
      await row(tx, "channel_memberships", {
        tenant_id: t.id,
        channel_id: c.id,
        user_id: user,
      });
    const value = {
      tenant_id: t.id,
      channel_id: c.id,
      sequence_no: 1,
      role: "USER",
      author_user_id: first,
      body: "Leak",
      content_schema_version: 1,
      metadata_json: {},
      idempotency_key: "one",
    };
    const message = await row(tx, "channel_messages", value);
    await row(tx, "channel_messages", {
      ...value,
      sequence_no: 2,
      author_user_id: second,
      idempotency_key: "two",
      reply_to_message_id: message.id,
    });
    await rejects(
      tx,
      (s) => row(s, "channel_messages", { ...value, sequence_no: 3 }),
      "23505",
    );
    const events =
      await tx`select * from platform_outbox_event where tenant_id=${t.id} and aggregate_id=${c.id}`;
    expect(events).toHaveLength(2);
    expect(
      events.find((e) => e.payload_json.messageId === message.id)?.event_type,
    ).toBe("CHANNEL_MESSAGE_COMMITTED");
    await rejects(
      tx,
      (s) =>
        s`update channel_messages set body='replacement' where id=${message.id}`,
      "23514",
    );
    await tx`update platform_tenant_membership set status='REVOKED' where tenant_id=${t.id} and user_id=${second}`;
    await rejects(
      tx,
      (s) =>
        row(s, "channel_messages", {
          ...value,
          sequence_no: 3,
          idempotency_key: "three",
          author_user_id: second,
        }),
      "23514",
    );
    await tx`update channels set status='CLOSED' where id=${c.id}`;
    await rejects(
      tx,
      (s) =>
        row(s, "channel_messages", {
          ...value,
          sequence_no: 3,
          idempotency_key: "three",
        }),
      "23514",
    );
  }));

test("canonical relationships reject foreign tenant agents, credentials and channel membership", () =>
  isolated(async (tx) => {
    const a = await tenant(tx),
      b = await tenant(tx),
      c = await channel(tx, a.id);
    const user = await member(tx, b.id);
    const agent = await row(tx, "agents", {
      id: randomUUID(),
      tenant_id: b.id,
      name: "Remote tenant",
      type: "built_in",
      configuration: {},
    });
    await rejects(
      tx,
      (s) =>
        row(s, "channel_agents", {
          tenant_id: a.id,
          channel_id: c.id,
          agent_id: agent.id,
        }),
      "23503",
    );
    await rejects(
      tx,
      (s) =>
        row(s, "channel_memberships", {
          tenant_id: a.id,
          channel_id: c.id,
          user_id: user,
        }),
      "23503",
    );
    const credential = await row(tx, "credentials", {
      tenant_id: b.id,
      kind: "mcp",
      provider: "test",
      encrypted_value: "test-only",
      key_id: "test",
      metadata: {},
    });
    await rejects(
      tx,
      (s) =>
        row(s, "mcp_servers", {
          id: randomUUID(),
          tenant_id: a.id,
          title: "Wrong scope",
          vendor: "test",
          url: "https://example.invalid",
          credential_id: credential.id,
        }),
      "23503",
    );
    await rejects(
      tx,
      (s) => s`update agents set tenant_id=${a.id} where id=${agent.id}`,
      "23514",
    );
  }));

test("assistant identity and pinned version must belong to the same assigned agent", () =>
  isolated(async (tx) => {
    const t = await tenant(tx),
      c = await channel(tx, t.id),
      user = await member(tx, t.id);
    const make = () =>
      row(tx, "agents", {
        id: randomUUID(),
        tenant_id: t.id,
        name: "Assistant",
        type: "built_in",
        configuration: {},
      });
    const a = await make(),
      b = await make();
    await row(tx, "channel_agents", {
      tenant_id: t.id,
      channel_id: c.id,
      agent_id: a.id,
    });
    const version = await row(tx, "platform_agent_version", {
      tenant_id: t.id,
      agent_id: b.id,
      version_no: 1,
      status: "DRAFT",
      spec_hash: "test",
      created_by: user,
    });
    const value = {
      tenant_id: t.id,
      channel_id: c.id,
      sequence_no: 1,
      role: "ASSISTANT",
      author_agent_id: a.id,
      body: "Received",
      content_schema_version: 1,
      metadata_json: {},
      idempotency_key: "one",
    };
    await rejects(
      tx,
      (s) => row(s, "channel_messages", { ...value, author_agent_id: b.id }),
      "23514",
    );
    await rejects(
      tx,
      (s) =>
        row(s, "channel_messages", { ...value, agent_version_id: version.id }),
      "23503",
    );
    await row(tx, "channel_messages", value);
  }));

test("capability revisions survive MCP cache refresh and freeze their source schema", () =>
  isolated(async(tx)=>{
    const t=await tenant(tx),user=await member(tx,t.id);
    const server=await row(tx,"mcp_servers",{id:randomUUID(),tenant_id:t.id,title:"MCP",vendor:"test",url:"https://example.invalid"});
    await row(tx,"mcp_tools",{tenant_id:t.id,server_id:server.id,name:"inspect"});
    const value={tenant_id:t.id,type:"MCP_TOOL",code:"inspect",version_no:1,name:"Inspect",owner_id:user,risk_level:"LOW",status:"ACTIVE",source_type:"MCP_SERVER",source_ref:server.id,config_json:{toolName:"inspect",inputSchema:{},outputSchema:{},fingerprint:"sha:test"}};
    const capability=await row(tx,"platform_capability",value);
    await tx`delete from mcp_tools where tenant_id=${t.id} and server_id=${server.id}`;
    expect(await tx`select id from platform_capability where id=${capability.id}`).toHaveLength(1);
    await rejects(tx,s=>s`update platform_capability set config_json='{}' where id=${capability.id}`,"23514");
    await rejects(tx,s=>s`delete from platform_capability where id=${capability.id}`,"23514");
    await rejects(tx,s=>row(s,"platform_capability",{...value,version_no:2,config_json:{}}),"23514");
    await row(tx,"platform_capability",{...value,version_no:2});
  }));

test("actual database has every snapshot column and foreign key after consolidation", async () => {
  const snapshot = await Bun.file(
    new URL("../drizzle/meta/0058_snapshot.json", import.meta.url),
  ).json();
  const columns =
    await db`select table_name,column_name from information_schema.columns where table_schema='public'`;
  const keys =
    await db`select c.relname as table_name,k.conname from pg_constraint k join pg_class c on c.oid=k.conrelid join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and k.contype='f'`;
  const foundColumns = new Set(
    columns.map((c) => `${c.table_name}.${c.column_name}`),
  );
  const foundKeys = new Set(keys.map((k) => `${k.table_name}.${k.conname}`));
  for (const table of Object.values(snapshot.tables) as any[]) {
    for (const col of Object.keys(table.columns))
      expect(foundColumns.has(`${table.name}.${col}`)).toBe(true);
    for (const name of Object.keys(table.foreignKeys))
      expect(foundKeys.has(`${table.name}.${name.slice(0, 63)}`)).toBe(true);
  }
  for (const name of [
    "platform_agent",
    "platform_conversation",
    "platform_mcp_server",
    "platform_skill",
  ]) {
    expect(
      (await db`select to_regclass(${`public.${name}`}) as relation`)[0]
        ?.relation,
    ).toBeNull();
  }
});

test("RLS on reused OpenBot tables fails closed without scope and isolates tenants", () =>
  isolated(async (tx) => {
    const a = await tenant(tx),
      b = await tenant(tx);
    const agent = await row(tx, "agents", {
      id: randomUUID(),
      tenant_id: b.id,
      name: "Private",
      type: "built_in",
      configuration: {},
    });
    const role = `unified_reader_${randomUUID().replaceAll("-", "")}`;
    await tx`create role ${tx(role)} nologin nosuperuser nobypassrls`;
    await tx`grant usage on schema public to ${tx(role)}`;
    await tx`grant select, insert on agents to ${tx(role)}`;
    await tx`set local role ${tx(role)}`;
    expect(await tx`select id from agents where id=${agent.id}`).toHaveLength(
      0,
    );
    await tx`select set_config('app.tenant_id',${a.id},true)`;
    expect(await tx`select id from agents where id=${agent.id}`).toHaveLength(
      0,
    );
    await rejects(
      tx,
      (s) =>
        row(s, "agents", {
          id: randomUUID(),
          tenant_id: b.id,
          name: "Wrong",
          type: "built_in",
          configuration: {},
        }),
      "42501",
    );
    await tx`select set_config('app.tenant_id',${b.id},true)`;
    expect(await tx`select id from agents where id=${agent.id}`).toHaveLength(
      1,
    );
  }));
