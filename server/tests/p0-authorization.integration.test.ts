import { afterAll, expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import postgres from "postgres";
import { testDatabaseUrl } from "./support/database";

const db = postgres(testDatabaseUrl(), { max: 1, onnotice: () => {} });
afterAll(() => db.end());
type Tx = postgres.TransactionSql;
async function isolated(run: (tx: Tx) => Promise<void>) {
  const rollback = new Error("fixture rollback");
  try {
    await db.begin(async (tx) => {
      await run(tx);
      throw rollback;
    });
  } catch (e) {
    if (e !== rollback) throw e;
  }
}
async function denied(
  tx: Tx,
  work: (s: Tx) => Promise<unknown>,
  code = "23514",
) {
  let failure: unknown;
  try {
    await tx.savepoint(work);
  } catch (e) {
    failure = e;
  }
  expect((failure as { code?: string })?.code).toBe(code);
}
async function fixture(tx: Tx) {
  const user = randomUUID();
  const [tenant] =
    await tx`insert into platform_tenant(code,name,status) values (${randomUUID()},'P0 test','ACTIVE') returning id`;
  await tx`insert into users(id,email) values (${user},${user + "@p0.test"})`;
  await tx`insert into platform_tenant_membership(tenant_id,user_id,status,valid_from) values (${tenant!.id},${user},'ACTIVE',now())`;
  return { tenant: tenant!.id as string, user };
}

test("P0 seeds separate operational permissions from agent publish and never assigns users", async () => {
  const roles = await db`select code from auth_role where tenant_id is null`;
  expect(roles).toHaveLength(13);
  const granted =
    await db`select p.code from auth_role_permission rp join auth_role r on r.id=rp.role_id join auth_permission p on p.id=rp.permission_id where r.code='VH_BQL_MANAGER'`;
  expect(granted.some((p) => p.code === "vh.approval.decide.operational")).toBe(
    true,
  );
  expect(granted.some((p) => p.code.startsWith("platform."))).toBe(false);
  const [count] = await db`select count(*)::int as n from auth_role_assignment`;
  expect(count!.n).toBe(0);
});

test("SSO issuer/subject maps uniquely and cannot be moved to another user", () =>
  isolated(async (tx) => {
    const a = await fixture(tx);
    const b = await fixture(tx);
    const subject = randomUUID();
    const [identity] =
      await tx`insert into auth_external_identity(tenant_id,local_user_id,provider,issuer,external_subject) values (${a.tenant},${a.user},'vinhomes','https://iam.example.test',${subject}) returning id`;
    await denied(
      tx,
      (s) =>
        s`insert into auth_external_identity(tenant_id,local_user_id,provider,issuer,external_subject) values (${b.tenant},${b.user},'vinhomes','https://iam.example.test',${subject})`,
      "23505",
    );
    await denied(
      tx,
      (s) =>
        s`update auth_external_identity set local_user_id=${b.user} where id=${identity!.id}`,
    );
    await tx`update auth_external_identity set status='REVOKED' where id=${identity!.id}`;
    const [updated] =
      await tx`select version from auth_external_identity where id=${identity!.id}`;
    expect(String(updated!.version)).toBe("2");
  }));

test("assignments enforce tenant, namespace, validity, membership and immutable scope", () =>
  isolated(async (tx) => {
    const a = await fixture(tx);
    const b = await fixture(tx);
    const [role] =
      await tx`insert into auth_role(tenant_id,domain_namespace,code,name,role_type) values (${a.tenant},'VINHOMES',${randomUUID()},'Custom technician','CUSTOM') returning id`;
    const insert = (s: Tx, tenant: string, user: string, domain = "VINHOMES") =>
      s`insert into auth_role_assignment(tenant_id,user_id,role_id,domain_namespace,scope_type,scope_ref,valid_from) values (${tenant},${user},${role!.id},${domain},'TENANT',${tenant},now()) returning id`;
    await denied(tx, (s) => insert(s, b.tenant, b.user));
    await denied(tx, (s) => insert(s, a.tenant, a.user, "PLATFORM"));
    await denied(tx, (s) => insert(s, a.tenant, b.user), "23503");
    const [assignment] = await insert(tx, a.tenant, a.user);
    await denied(
      tx,
      (s) =>
        s`update auth_role_assignment set scope_ref=${b.tenant} where id=${assignment!.id}`,
    );
    await denied(
      tx,
      (s) =>
        s`update auth_role_assignment set valid_until=valid_from where id=${assignment!.id}`,
    );
    await tx`update auth_role_assignment set status='REVOKED' where id=${assignment!.id}`;
    await denied(
      tx,
      (s) => s`update auth_role set tenant_id=${b.tenant} where id=${role!.id}`,
    );
  }));

test("non-bypass database role reads system templates but cannot edit them or cross tenant", () =>
  isolated(async (tx) => {
    const a = await fixture(tx);
    const b = await fixture(tx);
    await tx`insert into auth_role(tenant_id,domain_namespace,code,name,role_type) values (${a.tenant},'VINHOMES',${randomUUID()},'A','CUSTOM'), (${b.tenant},'VINHOMES',${randomUUID()},'B','CUSTOM')`;
    const roleName = "p0_auth_" + randomUUID().replaceAll("-", "");
    await tx.unsafe(`CREATE ROLE ${roleName} NOSUPERUSER NOBYPASSRLS`);
    await tx.unsafe(`GRANT USAGE ON SCHEMA public TO ${roleName}`);
    await tx.unsafe(
      `GRANT SELECT,INSERT,UPDATE,DELETE ON auth_role,auth_permission,auth_role_permission,auth_external_identity,auth_role_assignment TO ${roleName}`,
    );
    await tx.unsafe(`SET LOCAL ROLE ${roleName}`);
    await tx`select set_config('app.tenant_id',${a.tenant},true)`;
    const visible =
      await tx`select name from auth_role where tenant_id is not null`;
    expect(visible.map((r) => r.name)).toEqual(["A"]);
    const modified =
      await tx`update auth_role set name='tampered' where tenant_id is null returning id`;
    expect(modified).toHaveLength(0);
    await denied(
      tx,
      (s) =>
        s`insert into auth_role(tenant_id,domain_namespace,code,name,role_type) values (${b.tenant},'VINHOMES','ATTACK','Attack','CUSTOM')`,
      "42501",
    );
    const [permission] = await tx`select id from auth_permission limit 1`;
    const [systemRole] =
      await tx`select id from auth_role where tenant_id is null limit 1`;
    await denied(
      tx,
      (s) =>
        s`insert into auth_role_permission(role_id,permission_id) values (${systemRole!.id},${permission!.id})`,
      "42501",
    );
    await tx`select set_config('app.tenant_id','',true)`;
    expect(
      await tx`select id from auth_role where tenant_id is not null`,
    ).toHaveLength(0);
    await tx.unsafe("RESET ROLE");
  }));
