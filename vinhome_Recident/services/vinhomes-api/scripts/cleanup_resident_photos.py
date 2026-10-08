"""Clean expired, unbound local resident images. Defaults to a dry run.

Uses the configured tenant/runtime role and row locks shared with Case intake.
Never removes bound, referenced or legally held files. Receipts/history stay.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.concurrency import run_in_threadpool
from vinhomes_api.v3_config import V3Settings
from vinhomes_api.resident_photos import object_path

async def cleanup(apply=False, limit=100):
    settings = V3Settings.from_env()
    if not settings.database_url or not settings.tenant_id:
        raise RuntimeError('Configure the runtime database URL and tenant')
    if settings.host not in {'127.0.0.1', 'localhost', '::1'} or not (settings.resident_local_storage or settings.dev_user_id or settings.demo_mode):
        raise RuntimeError('This command supports only configured loopback local storage')
    engine = create_async_engine(settings.database_url)
    count = 0
    try:
        async with engine.begin() as db:
            await db.execute(text("select set_config('app.tenant_id',:tenant,true)"), {'tenant': str(settings.tenant_id)})
            rows = (await db.execute(text('''select f.id,o.object_key from vh_resident_photos p
              join files f on f.id=p.file_id and f.tenant_id=p.tenant_id
              join file_objects o on o.id=f.accepted_object_id and o.tenant_id=f.tenant_id
              join storage_locations s on s.id=o.location_id and s.tenant_id=o.tenant_id
              where p.case_id is null and p.expires_at<=now() and not f.legal_hold
                and f.status in ('ready','deletion_pending') and s.provider='local_fs'
                and not exists(select 1 from evidence_items e where e.file_id=f.id and e.tenant_id=f.tenant_id)
                and not exists(select 1 from message_files m where m.file_id=f.id and m.tenant_id=f.tenant_id)
                and not exists(select 1 from ticket_files t where t.file_id=f.id and t.tenant_id=f.tenant_id)
                and not exists(select 1 from vh_resident_resolution_photos r where r.file_id=f.id and r.tenant_id=f.tenant_id)
              order by p.file_id limit :limit for update of p,f skip locked'''), {'limit': limit})).mappings().all()
            for row in rows:
                path = object_path(row['object_key'])  # Checks resolved path stays inside FILE_ROOT.
                if apply:
                    await run_in_threadpool(path.unlink, missing_ok=True)
                    await db.execute(text("update files set status='deleted',deleted_at=now() where id=:id"), {'id': row['id']})
                count += 1
    finally:
        await engine.dispose()
    print(json.dumps({'dryRun': not apply, 'eligibleFiles': count}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--limit', type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000: parser.error('--limit must be 1..1000')
    asyncio.run(cleanup(args.apply, args.limit))
