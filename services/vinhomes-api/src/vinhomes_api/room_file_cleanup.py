"""Remove files that were uploaded to a management room and never attached to a message.

    DATABASE_URL=<the API's own role> VINHOMES_API_TENANT_ID=<tenant> python -m vinhomes_api.room_file_cleanup

A file is uploaded before its message is posted (v3_room_files.py), so a message that was never sent
leaves its files behind. After a day such a file is removed: its bytes from storage first, then its
record is marked deleted. If the bytes cannot be removed the record stays as it was and the next run
tries again. Needs no more than the API's own database role and storage key. Repeatable; run it once a
day from the host's scheduler.
"""
import asyncio
import json
import os
from datetime import timedelta
from pathlib import Path

import asyncpg

from . import storage

# Long enough that nobody is still writing the message the file was meant for.
KEEP = timedelta(hours=24)


async def clean(db: asyncpg.Connection, tenant: str, root: Path, keep: timedelta = KEEP) -> dict:
    removed = 0
    while True:
        # One file at a time, locked: a message being posted with it either gets there first, or finds it gone.
        async with db.transaction():
            await db.execute("select set_config('app.tenant_id',$1,true)", tenant)
            file = await db.fetchrow("""select f.id,o.id as object_id,o.object_key from files f
                join channels c on c.id=f.channel_id and c.tenant_id=f.tenant_id and c.kind='management'
                join file_objects o on o.id=f.accepted_object_id and o.tenant_id=f.tenant_id
                where f.scope_kind='channel' and f.status='ready' and f.created_at<now()-$1::interval
                  and not exists(select 1 from message_files mf where mf.file_id=f.id and mf.tenant_id=f.tenant_id)
                order by f.created_at limit 1 for update of f skip locked""", keep)
            if file is None:
                break
            storage.at(root, file['object_key']).unlink(missing_ok=True)
            await db.execute("update file_objects set status='deleted' where id=$1", file['object_id'])
            await db.execute("update files set status='deleted',deleted_at=now() where id=$1", file['id'])
            removed += 1
    return {'type': 'room-files-cleaned', 'removed': removed}


async def main() -> None:
    url, tenant = os.environ.get('DATABASE_URL', ''), os.environ.get('VINHOMES_API_TENANT_ID', '')
    if not url or not tenant:
        raise SystemExit('DATABASE_URL (the API role) and VINHOMES_API_TENANT_ID are required')
    from .v3_files import FILE_ROOT
    db = await asyncpg.connect(url.replace('postgresql+asyncpg://', 'postgresql://'))
    try:
        print(json.dumps(await clean(db, tenant, FILE_ROOT)))
    finally:
        await db.close()


if __name__ == '__main__':
    asyncio.run(main())
