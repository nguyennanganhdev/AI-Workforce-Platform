"""Create or refresh the agent evaluation sandbox: a database of its own in the same PostgreSQL cluster.

    python scripts/provision_eval_sandbox.py --source-url <owner URL of the production database>
        [--sandbox-database vinhomes_eval] [--role vinhomes_eval_api] [--isolate-source] [--output .local-eval/sandbox.env]

Why a database and not a second tenant in the production database: several ids are unique across the
whole database (channels.id, agents.id, mcp_servers.id; the gateway names 'technical-tools' and
'cleaning-tools'), and tenant row security rests on a session setting any role can change. A separate
database gives the sandbox the same ids and code paths, and PostgreSQL itself keeps its role out of
production: the role has CONNECT on the sandbox database only.

What it holds: one synthetic organisation (one site, building, management unit, room with a Supervisor,
three fixture residents with invented names), the production database's first-party tool catalogue and
model registry rows that name environment variables (never a sealed key), the sandbox marker and the
fixture profiles. No resident, ticket, message or credential is copied from production.

--isolate-source makes the production database refuse roles that were never granted CONNECT: every
login role that connects today is granted CONNECT explicitly first, then CONNECT is revoked from PUBLIC.
Without it the sandbox's role may still connect to production through PUBLIC, the worker's attestation
reports that, and every run ends unsafe.

Repeatable: an existing sandbox keeps its tenant, accounts and fixture ids; the catalogue is refreshed.
Settings (database URL, tenant, sandbox token) go to --output, outside git, and are never printed.
"""
import argparse
import asyncio
import hashlib
import json
import os
import secrets
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import asyncpg

SERVICE = Path(__file__).resolve().parents[1]
ROOT = SERVICE.parents[1]
FIXTURE_VERSION = 'eval-fixtures-2026-10-07'
FIXTURES = [  # (fixture id, unit code, invented name, phone, description shown to case authors)
    ('resident-a', '0101', 'Cư dân Thử A', '+84900009001', 'Chủ hộ căn 0101, tòa thử EV1'),
    ('resident-b', '0102', 'Cư dân Thử B', '+84900009002', 'Người thuê căn 0102, tòa thử EV1'),
    ('resident-c', '0201', 'Cư dân Thử C', '+84900009003', 'Chủ hộ căn 0201, tòa thử EV1'),
]
CATEGORIES = [('technical', 'Kỹ thuật'), ('security', 'An ninh'), ('cleaning', 'Vệ sinh')]


def with_database(url: str, name: str) -> str:
    return urlunsplit(urlsplit(url)._replace(path='/' + name))


def envfile(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return dict(line.split('=', 1) for line in path.read_text(encoding='utf-8').splitlines() if '=' in line and not line.startswith('#'))


async def seed(db: asyncpg.Connection, tenant: UUID) -> str:
    """The synthetic organisation. Returns the management room id."""
    def key(name: str) -> UUID:
        return uuid5(NAMESPACE_URL, f'eval-sandbox:{tenant}:{name}')
    t = tenant
    await db.execute("insert into tenants(id,code,name,status) values($1,'agent-eval','Sandbox đánh giá agent','active') on conflict do nothing", t)
    await db.execute("select set_config('app.tenant_id',$1,true)", str(t))
    admin = await db.fetchval("select id from users where email='eval-admin@sandbox.local'")
    if admin is None:
        admin = str(uuid4())
        await db.execute("insert into users(id,email,name,status) values($1,'eval-admin@sandbox.local','Quản trị sandbox','active')", admin)
    await db.execute("insert into platform_admins(user_id) values($1) on conflict do nothing", admin)
    await db.execute("insert into tenant_memberships(id,tenant_id,user_id,status,joined_at) values($1,$2,$3,'active',now()) on conflict do nothing",
                     key('membership:admin'), t, admin)
    await db.execute("select set_config('app.user_id',$1,true)", admin)
    domain, site, zone, building, unit = key('domain'), key('site'), key('zone'), key('building'), key('management-unit')
    await db.execute("insert into domains(id,tenant_id,code,name,status) values($1,$2,'vinhomes','Vinhomes','active') on conflict do nothing", domain, t)
    for code, name in CATEGORIES:
        await db.execute('insert into service_categories(id,tenant_id,code,name) values($1,$2,$3,$4) on conflict do nothing', key('category:' + code), t, code, name)
    await db.execute("insert into sites(id,tenant_id,domain_id,code,name,address,status) values($1,$2,$3,'eval-site','Khu thử nghiệm','Địa chỉ thử','active') on conflict do nothing", site, t, domain)
    await db.execute("insert into zones(id,tenant_id,site_id,code,name,status) values($1,$2,$3,'eval-zone','Phân khu thử','active') on conflict do nothing", zone, t, site)
    await db.execute("insert into buildings(id,tenant_id,site_id,zone_id,code,name,status) values($1,$2,$3,$4,'EV1','Tòa thử EV1','active') on conflict do nothing",
                     building, t, site, zone)
    for _, code, *_ in FIXTURES:
        await db.execute("insert into units(id,tenant_id,site_id,building_id,code,unit_kind,floor,status) values($1,$2,$3,$4,$5,'apartment',$6,'active') on conflict do nothing",
                         key('unit:' + code), t, site, building, code, code[:2])
    await db.execute("insert into management_units(id,tenant_id,code,name,status) values($1,$2,'bql-eval','Ban quản lý thử','active') on conflict do nothing", unit, t)
    scopes = {}
    for name, kind, column, target in (('tenant', 'tenant', None, None), ('site', 'site', 'site_id', site), ('zone', 'zone', 'zone_id', zone),
                                       ('building', 'building', 'building_id', building), ('management', 'management', 'management_unit_id', unit)):
        found = await db.fetchval(f"select id from access_scopes where tenant_id=$1 and kind=$2 and {column + '=$3' if column else '$3::uuid is null'}", t, kind, target)
        if found is None:
            found = key('scope:' + name)
            await db.execute(f"insert into access_scopes(id,tenant_id,kind{',' + column if column else ''}) values($1,$2,$3{',$4' if column else ''})",
                             found, t, kind, *([target] if column else []))
        scopes[name] = found
    for code, _ in CATEGORIES:
        await db.execute('insert into management_coverage(id,tenant_id,management_unit_id,scope_id,service_category_id,valid_from) values($1,$2,$3,$4,$5,now()) on conflict do nothing',
                         key('coverage:' + code), t, unit, scopes['zone'], key('category:' + code))
    policy = key('triage-policy')
    await db.execute("""insert into triage_policy_versions(id,tenant_id,domain_id,policy_code,version_no,status,engine_version,input_schema_version,input_schema,
        unknown_priority,review_timeout_seconds,max_fact_age_seconds,max_queue_wait_seconds,policy_hash,created_by,published_by,published_at)
        values($1,$2,$3,'eval-triage',1,'published','v3','v3','{}'::jsonb,'normal',3600,86400,3600,$4,$5,$5,now()) on conflict do nothing""",
                     policy, t, domain, '0' * 64, admin)
    for kind in ('incident', 'service_request'):
        await db.execute("""insert into triage_policy_bindings(id,tenant_id,domain_id,scope_id,category_id,request_kind,policy_version_id,valid_from,status,configured_by)
            values($1,$2,$3,$4,null,$5,$6,now(),'active',$7) on conflict do nothing""", key('triage-binding:' + kind), t, domain, scopes['site'], kind, policy, admin)
    await db.execute("""insert into storage_locations(id,tenant_id,provider,endpoint_ref,bucket_name,tenant_prefix,credential_secret_ref,versioning_required,encryption_mode,purpose,status)
        values($1,$2,'local_fs','vinhomes-api-local','vinhomes-eval','evidence/','local-only',false,'none','evidence','active') on conflict do nothing""", key('storage'), t)
    manager = await db.fetchval("select id from users where email='eval-bql@sandbox.local'")
    if manager is None:
        manager = str(uuid4())
        await db.execute("insert into users(id,email,name,status) values($1,'eval-bql@sandbox.local','Ban quản lý thử','active')", manager)
    await db.execute("insert into tenant_memberships(id,tenant_id,user_id,status,joined_at) values($1,$2,$3,'active',now()) on conflict do nothing", key('membership:bql'), t, manager)
    membership = await db.fetchval('select id from tenant_memberships where tenant_id=$1 and user_id=$2', t, manager)
    await db.execute("insert into scoped_user_roles(id,tenant_id,membership_id,scope_id,role_code,granted_by,valid_from) values($1,$2,$3,$4,'management',$5,now()) on conflict do nothing",
                     key('role:bql'), t, membership, scopes['management'], admin)
    workspace, room = key('workspace'), 'bql-eval'
    await db.execute("insert into workspaces(id,tenant_id,management_unit_id,code,name,status) values($1,$2,$3,'bql-eval','Phòng Ban quản lý thử','active') on conflict do nothing",
                     workspace, t, unit)
    await db.execute("insert into workspace_members(tenant_id,workspace_id,user_id,status,joined_at) values($1,$2,$3,'active',now()) on conflict do nothing", t, workspace, manager)
    await db.execute("""insert into channels(id,tenant_id,workspace_id,name,description,kind,created_by,is_dispatch_default)
        values($1,$2,$3,'Ban quản lý thử','Phòng điều phối của sandbox đánh giá','management',$4,true) on conflict do nothing""", room, t, workspace, manager)
    await db.execute('insert into channel_memberships(tenant_id,channel_id,user_id) values($1,$2,$3) on conflict do nothing', t, room, manager)
    await db.execute("""insert into agents(id,tenant_id,workspace_id,name,type,configuration,purpose,status)
        values('supervisor-eval',$1,$2,'Điều phối thử','built_in','{}','supervisor','active') on conflict do nothing""", t, workspace)
    await db.execute("insert into agents(id,tenant_id,name,type,configuration,purpose,status) values('system-reception',$1,'Lễ tân','built_in','{}','reception','active') on conflict do nothing", t)
    await db.execute("insert into channel_agents(tenant_id,channel_id,agent_id) values($1,$2,'supervisor-eval') on conflict do nothing", t, room)
    await db.execute("""insert into agent_versions(id,tenant_id,agent_id,version_no,runtime,framework_version,instructions,config,config_hash,created_by)
        values($1,$2,'supervisor-eval',1,'agentscope','2.0.9','Supervisor of the evaluation sandbox (agent-coordination)','{}',$3,$4) on conflict do nothing""",
                     key('supervisor-version'), t, hashlib.sha256(b'{}').hexdigest(), manager)
    await db.execute("insert into execution_principals(id,tenant_id,kind,workspace_id,status) values($1,$2,'workspace_service',$3,'active') on conflict do nothing",
                     key('workspace-principal'), t, workspace)
    principal = await db.fetchval("select id from execution_principals where tenant_id=$1 and kind='workspace_service' and workspace_id=$2", t, workspace)
    await db.execute("""insert into memory_namespaces(id,tenant_id,owner_principal_id,kind,workspace_id,namespace_key,purpose,status)
        values($1,$2,$3,'workspace',$4,'bql-eval-operations','operations','active') on conflict do nothing""", key('memory-namespace'), t, principal, workspace)
    for fixture_id, code, name, phone, description in FIXTURES:
        user = await db.fetchval('select id from users where email=$1', f'{fixture_id}@sandbox.local')
        if user is None:
            user = str(uuid4())
            await db.execute("insert into users(id,email,name,phone_e164,status) values($1,$2,$3,$4,'active')", user, f'{fixture_id}@sandbox.local', name, phone)
        await db.execute("insert into tenant_memberships(id,tenant_id,user_id,status,joined_at) values($1,$2,$3,'active',now()) on conflict do nothing",
                         key('membership:' + fixture_id), t, user)
        membership = await db.fetchval('select id from tenant_memberships where tenant_id=$1 and user_id=$2', t, user)
        await db.execute("insert into scoped_user_roles(id,tenant_id,membership_id,scope_id,role_code,granted_by,valid_from) values($1,$2,$3,$4,'customer',$5,now()) on conflict do nothing",
                         key('role:' + fixture_id), t, membership, scopes['building'], admin)
        await db.execute("""insert into unit_residents(id,tenant_id,unit_id,user_id,relation,verification_status,valid_from,verified_by,verified_at)
            values($1,$2,$3,$4,$5,'verified',now(),$6,now()) on conflict do nothing""",
                         key('resident:' + fixture_id), t, key('unit:' + code), user, 'tenant' if 'thuê' in description else 'owner', admin)
        await db.execute("""insert into vh_agent_eval_fixtures(tenant_id,id,user_id,unit_id,building_id,description) values($1,$2,$3,$4,$5,$6)
            on conflict(tenant_id,id) do update set description=excluded.description""", t, fixture_id, user, key('unit:' + code), building, description)
    return room


async def copy_catalogue(source: asyncpg.Connection, sandbox: asyncpg.Connection, tenant: UUID) -> tuple[int, int]:
    """First-party tools and env-referenced models, as production registers them. Never a custom connection or a sealed key."""
    tenants = await source.fetch('select id from tenants')
    if len(tenants) != 1:
        raise SystemExit('The source database must hold exactly one tenant to copy its catalogue from')
    await source.execute("select set_config('app.tenant_id',$1,false)", str(tenants[0]['id']))
    servers = await source.fetch("select id,title,vendor,url,provenance from mcp_servers where provenance<>'custom' and status='active'")
    tools = await source.fetch("""select t.server_id,t.name,t.description,t.input_schema,t.effect,t.version from mcp_tools t
        join mcp_servers s on s.id=t.server_id where s.provenance<>'custom' and s.status='active' and not t.destructive""")
    for s in servers:
        await sandbox.execute("""insert into mcp_servers(id,title,vendor,url,provenance,tenant_id) values($1,$2,$3,$4,$5,$6)
            on conflict(id) do update set title=excluded.title,url=excluded.url""", s['id'], s['title'], s['vendor'], s['url'], s['provenance'], tenant)
    for x in tools:
        await sandbox.execute("""insert into mcp_tools(server_id,name,description,input_schema,effect,destructive,version,tenant_id)
            values($1,$2,$3,$4,$5,false,$6,$7) on conflict(server_id,name) do update set description=excluded.description,
            input_schema=excluded.input_schema,effect=excluded.effect,version=excluded.version""",
                              x['server_id'], x['name'], x['description'], x['input_schema'], x['effect'], x['version'], tenant)
    models = await source.fetch("""select name,provider,kind,credential_env,base_url_env,allowed,dimension,check_status from admin_model_registry
        where credential_env is not null and workspace_id is null""")
    admin = await sandbox.fetchval("select id from users where email='eval-admin@sandbox.local'")
    for m in models:
        await sandbox.execute("""insert into admin_model_registry(tenant_id,name,provider,kind,credential_env,base_url_env,allowed,dimension,check_status,created_by)
            select $1,$2,$3,$4,$5,$6,$7,$8,$9,$10 where not exists(select 1 from admin_model_registry where name=$2 and provider=$3 and kind=$4 and workspace_id is null)""",
                              tenant, m['name'], m['provider'], m['kind'], m['credential_env'], m['base_url_env'], m['allowed'], m['dimension'], m['check_status'], admin)
    return len(tools), len(models)


async def main(args) -> None:
    source_url = args.source_url.replace('postgresql+asyncpg://', 'postgresql://')
    if urlsplit(source_url).hostname not in ('127.0.0.1', 'localhost', '::1', 'host.docker.internal') and not args.allow_remote:
        raise SystemExit('Refusing a non-local cluster without --allow-remote')
    output = Path(args.output)
    existing = envfile(output)
    source = await asyncpg.connect(source_url)
    try:
        source_db = await source.fetchval('select current_database()')
        if source_db == args.sandbox_database:
            raise SystemExit('The sandbox must be a database of its own')
        if not await source.fetchval('select 1 from pg_database where datname=$1', args.sandbox_database):
            await source.execute(f'CREATE DATABASE "{args.sandbox_database}"')
        sandbox_owner = with_database(source_url, args.sandbox_database)
        bun = shutil.which('bun.cmd') or shutil.which('bun')
        if bun is None:
            raise SystemExit('bun is required to run the migrations (server/scripts/migrate.ts)')
        subprocess.run([bun, 'server/scripts/migrate.ts'], cwd=ROOT, env={**os.environ, 'DATABASE_URL': sandbox_owner}, check=True)
        sandbox = await asyncpg.connect(sandbox_owner)
        try:
            marker = await sandbox.fetchrow('select tenant_id,source_database from vh_agent_eval_sandbox')
            if marker is None and await sandbox.fetchval('select count(*) from tenants'):
                raise SystemExit(f'{args.sandbox_database} already holds a tenant without the sandbox marker; refusing to touch it')
            if marker is not None and marker['source_database'] != source_db:
                raise SystemExit(f"{args.sandbox_database} is the sandbox of {marker['source_database']}, not of {source_db}")
            tenant = marker['tenant_id'] if marker else uuid4()
            password = existing.get('EVAL_SANDBOX_ROLE_PASSWORD') or secrets.token_hex(24)
            role = args.role
            async with sandbox.transaction():
                await sandbox.execute("select set_config('app.tenant_id',$1,true)", str(tenant))
                verb = 'ALTER' if await sandbox.fetchval('select 1 from pg_roles where rolname=$1', role) else 'CREATE'
                await sandbox.execute(f"{verb} ROLE {role} LOGIN PASSWORD '{password}' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE")
                grants = (SERVICE / 'scripts/grant_v3_api_role.sql').read_text(encoding='utf-8')
                await sandbox.execute(grants.replace('vinhomes_v3_api', role).replace('DATABASE vinhomes_v3', f'DATABASE "{args.sandbox_database}"'))
                await sandbox.execute(f'REVOKE CONNECT ON DATABASE "{args.sandbox_database}" FROM PUBLIC')
                await sandbox.execute(f'GRANT CONNECT ON DATABASE "{args.sandbox_database}" TO {role}')
                await sandbox.execute(f'REVOKE CONNECT ON DATABASE "{source_db}" FROM {role}')
                if marker is None:
                    await sandbox.execute('insert into tenants(id,code,name,status) values($1,$2,$3,$4)', tenant, 'agent-eval', 'Sandbox đánh giá agent', 'active')
                    await sandbox.execute('insert into vh_agent_eval_sandbox(tenant_id,source_database,fixture_version) values($1,$2,$3)', tenant, source_db, FIXTURE_VERSION)
                room = await seed(sandbox, tenant)
                await sandbox.execute('update vh_agent_eval_sandbox set fixture_version=$1 where tenant_id=$2', FIXTURE_VERSION, tenant)
                tools, models = await copy_catalogue(source, sandbox, tenant)
        finally:
            await sandbox.close()
        if args.isolate_source:
            # Every login role that connects today keeps doing so, explicitly; nothing else may connect.
            roles = await source.fetch("""select rolname from pg_roles where rolcanlogin and not rolsuper and rolname<>$1
                and has_database_privilege(rolname,$2,'CONNECT')""", role, source_db)
            for r in roles:
                await source.execute(f'GRANT CONNECT ON DATABASE "{source_db}" TO "{r["rolname"]}"')
            await source.execute(f'REVOKE CONNECT ON DATABASE "{source_db}" FROM PUBLIC')
            await source.execute(f'REVOKE CONNECT ON DATABASE "{source_db}" FROM {role}')
    finally:
        await source.close()
    runtime = with_database(source_url, args.sandbox_database)
    parts = urlsplit(runtime)
    runtime = urlunsplit(parts._replace(netloc=f'{role}:{quote(password)}@{parts.hostname}:{parts.port or 5432}'))
    probe = await asyncpg.connect(runtime)
    try:
        facts = await probe.fetchrow("""select current_database() as database, r.rolsuper, r.rolbypassrls,
            has_database_privilege(current_user,$1,'CONNECT') as source_connect from pg_roles r where r.rolname=current_user""", source_db)
    finally:
        await probe.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    token = existing.get('VINHOMES_API_EVAL_SANDBOX_TOKEN') or secrets.token_urlsafe(32)
    output.write_text(
        f"# Sandbox API (a second vinhomes-api process). Never commit this file.\n"
        f"VINHOMES_API_DATABASE_URL={runtime.replace('postgresql://', 'postgresql+asyncpg://')}\n"
        f"VINHOMES_API_TENANT_ID={tenant}\nVINHOMES_API_EVAL_SANDBOX_TOKEN={token}\nEVAL_SANDBOX_ROLE_PASSWORD={password}\n"
        f"# Worker: EVAL_SANDBOX_TOKEN is the same value as VINHOMES_API_EVAL_SANDBOX_TOKEN.\n"
        f"EVAL_SANDBOX_TOKEN={token}\n", encoding='utf-8')
    safe = not facts['rolsuper'] and not facts['rolbypassrls'] and not facts['source_connect']
    print(json.dumps({'sandbox_database': args.sandbox_database, 'source_database': source_db, 'room': room, 'tools': tools,
                      'models': models, 'fixtures': [f[0] for f in FIXTURES], 'isolated_from_source': safe, 'settings': str(output)}, ensure_ascii=False))
    if not safe:
        print('WARNING: the sandbox role can still connect to the source database. Run again with --isolate-source; until then every run ends unsafe.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create or refresh the agent evaluation sandbox database')
    parser.add_argument('--source-url', required=True, help='owner URL of the production database (read only here, except --isolate-source)')
    parser.add_argument('--sandbox-database', default='vinhomes_eval')
    parser.add_argument('--role', default='vinhomes_eval_api')
    parser.add_argument('--isolate-source', action='store_true')
    parser.add_argument('--allow-remote', action='store_true')
    parser.add_argument('--output', default=str(SERVICE / '.local-eval' / 'sandbox.env'))
    asyncio.run(main(parser.parse_args()))
