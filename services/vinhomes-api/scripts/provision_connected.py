"""Give the password-login deployment (vinhomes_connected) a real organisation and first accounts.

    python scripts/provision_connected.py

`setup_password_database.py` creates the database with one administrator and nothing else, so
nobody can do anything after signing in. This script brings the schema up to date and adds what
the resident and operations apps need: Vinhomes Ocean Park 1 with its areas and buildings, the
Sapphire management unit with its group chat and Supervisor, and one account for each role
(management, technician, resident). No tickets, no synthetic residents.

It is safe to run again: existing rows and existing accounts are left as they are, and a
password is generated only for an account this run creates. New passwords are written to
`.local-connected/accounts.txt` (ignored by git) and never printed.
"""

import asyncio
import hashlib
import os
import secrets
import shutil
import subprocess
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import asyncpg
from vinhomes_api.password_auth import PROVIDER, password_hash

SERVICE = Path(__file__).resolve().parents[1]
ROOT = SERVICE.parents[1]
LOCAL = SERVICE / ".local-connected"
DEMO_TENANT = "11111111-1111-5111-a111-111111111111"
ZONES = [("sapphire", "Sapphire"), ("pavilion", "Pavilion"), ("zenpark", "Zenpark"), ("hai-au", "Hải Âu"),
         ("ngoc-trai", "Ngọc Trai"), ("san-ho", "San Hô"), ("sao-bien", "Sao Biển"),
         ("masteri-waterfront", "Masteri Waterfront")]
BUILDINGS = [("S1.01", "sapphire", "Sapphire 1 - S1.01"), ("S1.02", "sapphire", "Sapphire 1 - S1.02"),
             ("S2.01", "sapphire", "Sapphire 2 - S2.01"), ("S2.05", "sapphire", "Sapphire 2 - S2.05"),
             ("P1", "pavilion", "Pavilion P1"), ("P2", "pavilion", "Pavilion P2"),
             ("R1.02", "zenpark", "Zenpark R1.02"), ("R1.03", "zenpark", "Zenpark R1.03"),
             ("M1", "masteri-waterfront", "Masteri Waterfront M1"), ("M2", "masteri-waterfront", "Masteri Waterfront M2"),
             ("M3", "masteri-waterfront", "Masteri Waterfront M3"), ("H1", "masteri-waterfront", "Masteri Waterfront H1"),
             ("H2", "masteri-waterfront", "Masteri Waterfront H2"), ("H3", "masteri-waterfront", "Masteri Waterfront H3")]
CATEGORIES = [("technical", "Kỹ thuật"), ("security", "An ninh")]
# The first people of the deployment. Everyone else is added by the administrator in Operations.
ACCOUNTS = {
    "management": ("bql.sapphire@oceanpark.local", "Ban quản lý Sapphire", None),
    "technician": ("kythuat.sapphire@oceanpark.local", "Kỹ thuật viên Sapphire", None),
    "resident": ("cudan.s101.1201@oceanpark.local", "Nguyễn Văn An", "+84900000001"),
}


def envfile(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines()
                if "=" in line and not line.startswith("#"))


async def main() -> None:
    owner_url = envfile(LOCAL / "migration.env")["DATABASE_URL"]
    tenant = envfile(SERVICE / ".env.connected")["VINHOMES_API_TENANT_ID"]
    if tenant == DEMO_TENANT:
        raise RuntimeError("The demo tenant is not a real deployment")
    bun = shutil.which("bun.cmd") or shutil.which("bun")
    subprocess.run([bun, "server/scripts/migrate.ts"], cwd=ROOT, env={**os.environ, "DATABASE_URL": owner_url}, check=True)

    def key(name: str) -> UUID:
        """Stable ids, so running again finds the same rows."""
        return uuid5(NAMESPACE_URL, f"connected:{tenant}:{name}")

    db = await asyncpg.connect(owner_url)
    created: list[tuple[str, str, str]] = []
    try:
        if await db.fetchval("select current_database()") != "vinhomes_connected":
            raise RuntimeError("Refusing to provision a database other than vinhomes_connected")
        admin = await db.fetchval("select user_id from platform_admins order by user_id limit 1")
        if admin is None or not await db.fetchval("select 1 from tenants where id=$1", UUID(tenant)):
            raise RuntimeError("Run setup_password_database.py first")
        grants = (SERVICE / "scripts/grant_v3_api_role.sql").read_text(encoding="utf-8")
        await db.execute(grants.replace("vinhomes_v3_api", "vinhomes_connected_api")
                         .replace("DATABASE vinhomes_v3", "DATABASE vinhomes_connected"))
        await db.execute("GRANT INSERT, UPDATE, DELETE ON sessions TO vinhomes_connected_api")
        await db.execute("GRANT INSERT, UPDATE ON accounts, users, tenant_memberships, scoped_user_roles, access_scopes "
                         "TO vinhomes_connected_api")
        async with db.transaction():
            await db.execute("select set_config('app.tenant_id',$1,true),set_config('app.user_id',$2,true)", tenant, admin)
            t = UUID(tenant)
            await db.execute("update tenants set name='Vinhomes Ocean Park 1' where id=$1 and name='Resident local'", t)
            domain, site, unit = key("domain"), key("site"), key("management-unit")
            await db.execute("insert into domains(id,tenant_id,code,name,status) values($1,$2,'vinhomes','Vinhomes','active') "
                             "on conflict do nothing", domain, t)
            for code, name in CATEGORIES:
                await db.execute("insert into service_categories(id,tenant_id,code,name) values($1,$2,$3,$4) on conflict do nothing",
                                 key("category:" + code), t, code, name)
            await db.execute("insert into sites(id,tenant_id,domain_id,code,name,address,status) "
                             "values($1,$2,$3,'ocean-park-1','Vinhomes Ocean Park 1','Gia Lâm, Hà Nội','active') on conflict do nothing",
                             site, t, domain)
            for code, name in ZONES:
                await db.execute("insert into zones(id,tenant_id,site_id,code,name,status) values($1,$2,$3,$4,$5,'active') "
                                 "on conflict do nothing", key("zone:" + code), t, site, code, name)
            for code, zone, name in BUILDINGS:
                await db.execute("insert into buildings(id,tenant_id,site_id,zone_id,code,name,status) "
                                 "values($1,$2,$3,$4,$5,$6,'active') on conflict do nothing",
                                 key("building:" + code), t, site, key("zone:" + zone), code, name)
            # The apartments of floor 12 in S1.01: enough to sign a first resident in. The real
            # unit list is imported by the organisation's own data owner.
            for number in range(1, 21):
                code = f"12{number:02d}"
                await db.execute("insert into units(id,tenant_id,site_id,building_id,code,unit_kind,floor,status) "
                                 "values($1,$2,$3,$4,$5,'apartment','12','active') on conflict do nothing",
                                 key("unit:S1.01:" + code), t, site, key("building:S1.01"), code)
            await db.execute("insert into management_units(id,tenant_id,code,name,status) "
                             "values($1,$2,'bql-sapphire','Ban quản lý Sapphire','active') on conflict do nothing", unit, t)
            scopes = {"tenant": ("tenant", None), "site": ("site", site), "management": ("management", unit)}
            scopes |= {"zone:" + code: ("zone", key("zone:" + code)) for code, _ in ZONES}
            scopes |= {"building:" + code: ("building", key("building:" + code)) for code, _, _ in BUILDINGS}
            for name, (kind, target) in scopes.items():
                column = {"tenant": None, "site": "site_id", "zone": "zone_id", "building": "building_id",
                          "management": "management_unit_id"}[kind]
                exists = await db.fetchval(
                    f"select id from access_scopes where tenant_id=$1 and kind=$2 and {column + '=$3' if column else '$3::uuid is null'}",
                    t, kind, target)
                if exists is None:
                    await db.execute(f"insert into access_scopes(id,tenant_id,kind{',' + column if column else ''}) "
                                     f"values($1,$2,$3{',$4' if column else ''})", key("scope:" + name), t, kind,
                                     *([target] if column else []))
                scopes[name] = exists or key("scope:" + name)
            # The unit serves the whole Sapphire area, for both kinds of request.
            for code, _ in CATEGORIES:
                await db.execute("insert into management_coverage(id,tenant_id,management_unit_id,scope_id,service_category_id,valid_from) "
                                 "values($1,$2,$3,$4,$5,now()) on conflict do nothing",
                                 key("coverage:sapphire:" + code), t, unit, scopes["zone:sapphire"], key("category:" + code))
            policy = key("triage-policy")
            await db.execute("""insert into triage_policy_versions(id,tenant_id,domain_id,policy_code,version_no,status,
                engine_version,input_schema_version,input_schema,unknown_priority,review_timeout_seconds,max_fact_age_seconds,
                max_queue_wait_seconds,policy_hash,created_by,published_by,published_at)
                values($1,$2,$3,'ocean-park-triage',1,'published','v3','v3','{}'::jsonb,'normal',3600,86400,3600,$4,$5,$5,now())
                on conflict do nothing""", policy, t, domain, hashlib.sha256(b"ocean-park-triage-1").hexdigest(), admin)
            for kind in ("incident", "service_request"):
                await db.execute("""insert into triage_policy_bindings(id,tenant_id,domain_id,scope_id,category_id,request_kind,
                    policy_version_id,valid_from,status,configured_by) values($1,$2,$3,$4,null,$5,$6,now(),'active',$7)
                    on conflict do nothing""", key("triage-binding:" + kind), t, domain, scopes["site"], kind, policy, admin)
            await db.execute("""insert into storage_locations(id,tenant_id,provider,endpoint_ref,bucket_name,tenant_prefix,
                credential_secret_ref,versioning_required,encryption_mode,purpose,status)
                values($1,$2,'local_fs','vinhomes-api-local','vinhomes-connected','evidence/','local-only',false,'none','evidence','active')
                on conflict do nothing""", key("storage"), t)

            async def account(role: str) -> str:
                email, name, phone = ACCOUNTS[role]
                user = await db.fetchval("select id from users where lower(email)=$1", email)
                if user is None:
                    user, password = str(uuid4()), secrets.token_urlsafe(12)
                    await db.execute("insert into users(id,email,name,phone_e164,status) values($1,$2,$3,$4,'active')",
                                     user, email, name, phone)
                    await db.execute("insert into accounts(id,account_id,provider_id,user_id,password) values($1,$2,$3,$2,$4)",
                                     str(uuid4()), user, PROVIDER, await asyncio.to_thread(password_hash, password))
                    created.append((role, email, password))
                await db.execute("insert into tenant_memberships(id,tenant_id,user_id,status,joined_at) "
                                 "values($1,$2,$3,'active',now()) on conflict do nothing", key("membership:" + role), t, user)
                return user

            async def grant(role: str, user: str, scope: str, code: str) -> None:
                membership = await db.fetchval("select id from tenant_memberships where tenant_id=$1 and user_id=$2", t, user)
                await db.execute("insert into scoped_user_roles(id,tenant_id,membership_id,scope_id,role_code,granted_by,valid_from) "
                                 "values($1,$2,$3,$4,$5,$6,now()) on conflict do nothing",
                                 key(f"role:{role}:{scope}"), t, membership, scopes[scope], code, admin)

            manager, technician, resident = await account("management"), await account("technician"), await account("resident")
            await grant("management", manager, "management", "management")
            await grant("management", manager, "site", "management")
            await grant("technician", technician, "site", "staff")
            await grant("resident", resident, "building:S1.01", "customer")
            staff = key("staff:technician")
            await db.execute("insert into staff_profiles(id,tenant_id,user_id,management_unit_id,employee_code,availability) "
                             "values($1,$2,$3,$4,'KT-SAPPHIRE-01','available') on conflict do nothing", staff, t, technician, unit)
            await db.execute("insert into staff_specialties(tenant_id,staff_id,category_id,proficiency) values($1,$2,$3,'standard') "
                             "on conflict do nothing", t, staff, key("category:technical"))
            await db.execute("insert into staff_shifts(id,tenant_id,staff_id,starts_at,ends_at,status) "
                             "values($1,$2,$3,now(),now()+interval '5 years','available') on conflict do nothing",
                             key("shift:technician"), t, staff)
            await db.execute("insert into unit_residents(id,tenant_id,unit_id,user_id,relation,verification_status,valid_from,"
                             "verified_by,verified_at) values($1,$2,$3,$4,'owner','verified',now(),$5,now()) on conflict do nothing",
                             key("resident:1201"), t, key("unit:S1.01:1201"), resident, admin)

            workspace, room = key("workspace"), "bql-sapphire"
            await db.execute("insert into workspaces(id,tenant_id,management_unit_id,code,name,status) "
                             "values($1,$2,$3,'bql-sapphire','Phòng Ban quản lý Sapphire','active') on conflict do nothing",
                             workspace, t, unit)
            await db.execute("insert into workspace_members(tenant_id,workspace_id,user_id,status,joined_at) "
                             "values($1,$2,$3,'active',now()) on conflict do nothing", t, workspace, manager)
            await db.execute("insert into channels(id,tenant_id,workspace_id,name,description,kind,created_by,is_dispatch_default) "
                             "values($1,$2,$3,'Ban quản lý Sapphire','Phòng điều phối yêu cầu của cư dân','management',$4,true) "
                             "on conflict do nothing", room, t, workspace, manager)
            await db.execute("insert into channel_memberships(tenant_id,channel_id,user_id) values($1,$2,$3) on conflict do nothing",
                             t, room, manager)
            await db.execute("insert into agents(id,tenant_id,workspace_id,name,type,configuration,purpose,status) "
                             "values('supervisor-sapphire',$1,$2,'Điều phối Sapphire','built_in','{}','supervisor','active') "
                             "on conflict do nothing", t, workspace)
            await db.execute("insert into agents(id,tenant_id,name,type,configuration,purpose,status) "
                             "values('system-reception',$1,'Lễ tân','built_in','{}','reception','active') on conflict do nothing", t)
            await db.execute("insert into channel_agents(tenant_id,channel_id,agent_id) values($1,$2,'supervisor-sapphire') "
                             "on conflict do nothing", t, room)
            await db.execute("""insert into agent_versions(id,tenant_id,agent_id,version_no,runtime,framework_version,instructions,
                config,config_hash,created_by) values($1,$2,'supervisor-sapphire',1,'agentscope','2.0.9',
                'Supervisor of the Sapphire management room (agent-coordination)','{}',$3,$4) on conflict do nothing""",
                             key("supervisor-version"), t, hashlib.sha256(b"{}").hexdigest(), manager)
            principal = key("workspace-principal")
            await db.execute("insert into execution_principals(id,tenant_id,kind,workspace_id,status) "
                             "values($1,$2,'workspace_service',$3,'active') on conflict do nothing", principal, t, workspace)
            principal = await db.fetchval("select id from execution_principals where tenant_id=$1 and kind='workspace_service' "
                                          "and workspace_id=$2", t, workspace)
            await db.execute("insert into memory_namespaces(id,tenant_id,owner_principal_id,kind,workspace_id,namespace_key,purpose,status) "
                             "values($1,$2,$3,'workspace',$4,'bql-sapphire-operations','operations','active') on conflict do nothing",
                             key("memory-namespace"), t, principal, workspace)
    finally:
        await db.close()
    if created:
        LOCAL.mkdir(exist_ok=True)
        with (LOCAL / "accounts.txt").open("a", encoding="utf-8") as out:
            for role, email, password in created:
                out.write(f"{role}: {email} / {password}\n")
    print(f"Organisation ready. Accounts created now: {len(created)}"
          + (" (passwords in services/vinhomes-api/.local-connected/accounts.txt)" if created else ""))


if __name__ == "__main__":
    asyncio.run(main())
