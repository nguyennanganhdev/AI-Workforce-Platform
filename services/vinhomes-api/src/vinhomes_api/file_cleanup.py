"""Remove stored files nothing refers to any more.

    DATABASE_URL=<the API's own role> VINHOMES_API_TENANT_ID=<tenant> python -m vinhomes_api.file_cleanup

Two kinds are left behind in normal use:

- A file uploaded to a management room for a message that was never sent (v3_room_files.py). After a
  day it is removed: its bytes from storage first, then its record is marked deleted.
- The staging copy of a photo a browser sent straight to the bucket (direct_uploads.py). An accepted
  upload removes its own; what stays is an upload nobody completed, and anything sent to a staging
  address after its upload was decided. After an hour such an object is removed, and an upload
  session that ran out is marked expired.

If bytes cannot be removed the record stays as it was and the next run tries again. Needs no more
than the API's own database role and storage key. Repeatable; run it once a day from the host's scheduler.
"""
import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg

from . import storage

# Long enough that nobody is still writing the message the file was meant for.
KEEP = timedelta(hours=24)
# An upload session lasts five minutes; an hour later nothing can still be on its way.
SETTLED = timedelta(hours=1)


async def clean(db: asyncpg.Connection, tenant: str, root: Path, keep: timedelta = KEEP) -> int:
    """Room files nobody sent. Returns how many were removed."""
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
                return removed
            storage.at(root, file['object_key']).unlink(missing_ok=True)
            await db.execute("update file_objects set status='deleted' where id=$1", file['object_id'])
            await db.execute("update files set status='deleted',deleted_at=now() where id=$1", file['id'])
            removed += 1


async def clean_staging(db: asyncpg.Connection, tenant: str, settled: timedelta = SETTLED) -> int:
    """Staging copies of direct uploads that are decided or ran out. Returns how many objects were removed."""
    if storage.provider() != 's3':
        return 0  # a browser only uploads straight to a bucket
    async with db.transaction():
        await db.execute("select set_config('app.tenant_id',$1,true)", tenant)
        await db.execute("update file_uploads set status='expired' where status='issued' and expires_at<now()-$1::interval", settled)
        waiting = {row['staging_key'] for row in await db.fetch("select staging_key from file_uploads where status='issued'")}
        prefixes = [row['tenant_prefix'] for row in await db.fetch(
            "select tenant_prefix from storage_locations where provider='s3' and status='active'")]
    client, bucket, removed = storage.client(), storage.bucket(), 0
    before = datetime.now(UTC) - settled
    for prefix in prefixes:
        for stored in client.list_objects(bucket, prefix=prefix + 'staging/', recursive=True):
            # Old enough that its session is over, and no session still waits for it.
            if stored.object_name not in waiting and stored.last_modified <= before:
                client.remove_object(bucket, stored.object_name)
                removed += 1
    return removed


async def main() -> None:
    url, tenant = os.environ.get('DATABASE_URL', ''), os.environ.get('VINHOMES_API_TENANT_ID', '')
    if not url or not tenant:
        raise SystemExit('DATABASE_URL (the API role) and VINHOMES_API_TENANT_ID are required')
    from .v3_files import FILE_ROOT
    db = await asyncpg.connect(url.replace('postgresql+asyncpg://', 'postgresql://'))
    try:
        print(json.dumps({'type': 'files-cleaned', 'roomFiles': await clean(db, tenant, FILE_ROOT),
                          'stagedUploads': await clean_staging(db, tenant)}))
    finally:
        await db.close()


if __name__ == '__main__':
    asyncio.run(main())
