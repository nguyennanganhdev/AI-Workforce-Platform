"""Prepare a separate clean database; never drop or modify the source database.

The operator must back up first and switch deployment URLs only after checking the report.
Keeps Domain admins, integration/storage configuration and knowledge; no user business history.
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

import asyncpg

from .bootstrap import OP1, bootstrap
from .database import TENANT, _identifier, _url, migrate


async def copy_rows(target, table, rows):
    if not rows:
        return 0
    columns = list(rows[0].keys())
    names = ','.join('"' + name + '"' for name in columns)
    placeholders = ','.join('$' + str(n) for n in range(1, len(columns) + 1))
    await target.executemany(f'insert into "{table}" ({names}) values ({placeholders})',
                             [tuple(row[name] for name in columns) for row in rows])
    return len(rows)


async def prepare(source_url: str, target_database: str) -> dict:
    _identifier(target_database, "Target database")
    parts = urlsplit(_url(source_url))
    if parts.path.lstrip('/') == target_database:
        raise SystemExit("Source and target must be different databases.")
    target_url = urlunsplit(parts._replace(path='/' + target_database))
    source = await asyncpg.connect(_url(source_url))
    target = None
    try:
        if await source.fetchval('select exists(select 1 from pg_database where datname=$1)', target_database):
            raise SystemExit("Target already exists. It was not changed; use a new database name.")
        tenant = UUID(TENANT)
        await source.execute("select set_config('app.tenant_id',$1,false)", TENANT)
        admins = await source.fetch("""select u.id from users u join platform_admins a on a.user_id=u.id
            join tenant_memberships m on m.user_id=u.id where m.tenant_id=$1 and u.status='active' and m.status='active'""", tenant)
        admin_ids = [r['id'] for r in admins]
        if not admin_ids:
            raise SystemExit("No active Domain administrator to preserve.")
        sites = await source.fetch('select id,code from sites where tenant_id=$1', tenant)
        if len(sites) != 1 or sites[0]['code'] != 'ocean-park-1':
            raise SystemExit("This reset requires the audited single-OP1 source. Review multi-site sources separately.")
        if await source.fetchval("select count(*) from platform_links where tenant_id=$1 and status not in ('closed','cancelled','failed')", tenant):
            raise SystemExit("Open Platform links exist. Reconcile them before resetting business history.")
        if await source.fetchval('select count(*) from platform_connection_settings where tenant_id=$1 and enabled', tenant):
            raise SystemExit("Disable and reconcile the Platform connection before preparing a clean database.")
        await source.execute(f'create database "{target_database}"')
        await migrate(target_url)
        target = await asyncpg.connect(target_url)
        counts = {}
        async with target.transaction():
            await target.execute("select set_config('app.tenant_id',$1,true)", TENANT)
            for table in ('tenants', 'domains', 'service_categories'):
                column = 'id' if table == 'tenants' else 'tenant_id'
                counts[table] = await copy_rows(target, table, await source.fetch(f'select * from {table} where {column}=$1', tenant))
            # All administrative sign-ins survive, but sessions, personal files and work history do not.
            for table, column in [('users','id'),('accounts','user_id'),('tenant_memberships','user_id'),('platform_admins','user_id')]:
                rows = [dict(r) for r in await source.fetch(f'select * from {table} where {column}=any($1::text[])'
                        + (' and tenant_id=$2' if table=='tenant_memberships' else ''),
                        admin_ids, *([tenant] if table=='tenant_memberships' else []))]
                if table == 'platform_admins':
                    for row in rows:
                        if row['granted_by'] not in admin_ids:
                            row['granted_by'] = None
                counts[table] = await copy_rows(target, table, rows)
            for table in ('management_units','storage_locations','integration_clients','platform_connection_settings'):
                rows = await source.fetch(f'select * from {table} where tenant_id=$1', tenant)
                if table == 'platform_connection_settings' and any(r['updated_by'] not in admin_ids for r in rows):
                    raise SystemExit("Connection settings belong to a non-admin identity; review before reset.")
                counts[table] = await copy_rows(target, table, rows)
        await bootstrap(target_url)
        async with target.transaction():
            await target.execute("select set_config('app.tenant_id',$1,true)", TENANT)
            # Taxonomy describes enabled software capabilities, not a confirmed official service/fee catalog.
            await target.execute("update service_categories set name=case code when 'technical' then 'Kỹ thuật' when 'security' then 'An ninh' when 'sanitation' then 'Vệ sinh' else name end where tenant_id=$1", tenant)
            documents = [dict(r) for r in await source.fetch('select * from vh_knowledge_documents where tenant_id=$1', tenant)]
            quarantine = 0
            for row in documents:
                metadata = json.loads(row['metadata'])
                old_scope = {'zone_id':str(row['zone_id']) if row['zone_id'] else None,
                             'building_ids':[str(b) for b in row['building_ids'] or []]}
                sources = metadata.get('sources') or []
                front = metadata.get('frontMatter') or {}
                urls = []
                for value in [*sources, front.get('source_url','')]:
                    if isinstance(value,str):
                        urls.extend(re.findall(r'https?://[^\s<>"\]\)]+',value))
                metadata['sources'] = list(dict.fromkeys(urls))
                metadata['archived_scope'] = old_scope
                metadata['source_descriptions'] = sources
                metadata['operational_approval'] = 'pending'
                metadata['retrieval_status'] = 'quarantined' if row['zone_id'] or row['building_ids'] or not urls else 'reference'
                metadata['quarantine_reason'] = 'missing_confirmed_scope_or_source' if metadata['retrieval_status']=='quarantined' else None
                quarantine += metadata['retrieval_status']=='quarantined'
                # Scope-specific texts are retained verbatim but hidden until their real master data is supplied.
                row.update(site_id=OP1,zone_id=None,building_ids=None,unverified=True,metadata=json.dumps(metadata))
            counts['vh_knowledge_documents'] = await copy_rows(target,'vh_knowledge_documents',documents)
            chunks = await source.fetch('select * from vh_knowledge_chunks where tenant_id=$1',tenant)
            counts['vh_knowledge_chunks'] = await copy_rows(target,'vh_knowledge_chunks',chunks)
            def digest(rows):
                return hashlib.sha256(json.dumps(sorted((str(r['id']),r['text_content'],str(r['embedding'])) for r in rows),ensure_ascii=False).encode()).hexdigest()
            copied = await target.fetch('select * from vh_knowledge_chunks where tenant_id=$1 and id=any($2::uuid[])',tenant,[r['id'] for r in chunks])
            assert digest(chunks)==digest(copied), 'Knowledge text/vector preservation failed'
            counts['quarantined_documents'] = quarantine
            for table in ('tickets','work_orders','staff_profiles','units','unit_residents','sessions','scoped_user_roles','messages','invoices'):
                assert await target.fetchval(f'select count(*) from {table}')==0, f'{table} is not empty'
            assert await target.fetchval('select count(*) from users')==len(admin_ids)
        return {'target_database':target_database,'source_unchanged':True,'admins':len(admin_ids),
                'counts':counts,'sites':3,'knowledge_content_and_vectors_preserved':True,'activated':False}
    finally:
        if target:
            await target.close()
        await source.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url-env',default='DATABASE_URL')
    parser.add_argument('--target-database',required=True)
    args=parser.parse_args()
    print(json.dumps(asyncio.run(prepare(os.environ[args.url_env],args.target_database)),ensure_ascii=False))


if __name__=='__main__':
    main()
