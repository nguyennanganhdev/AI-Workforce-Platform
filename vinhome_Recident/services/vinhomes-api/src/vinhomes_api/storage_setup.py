"""Prepare the bucket a deployment stores its files in, and move the files already on disk into it.

    DATABASE_URL=<owner> VINHOMES_API_TENANT_ID=<tenant> \\
    VINHOMES_API_S3_ENDPOINT=http://minio:9000 VINHOMES_API_S3_ACCESS_KEY=... VINHOMES_API_S3_SECRET_KEY=... \\
    python -m vinhomes_api.storage_setup [--allow-missing]

Creates the bucket when it is missing (private, as a new bucket is). A stored object's record cannot
be pointed elsewhere (the database keeps an object's location and key immutable), so what moves is
the location itself: every object of a disk location is copied from the file root
(VINHOMES_RESIDENT_FILE_ROOT) into the bucket under the same key, and the location's own record then
names the bucket. A tenant without a location gets one.

With the storage server's administrator account in VINHOMES_API_S3_ADMIN_ACCESS_KEY / _SECRET_KEY
(MinIO), the bucket is created with it and the API's own key (VINHOMES_API_S3_ACCESS_KEY) is made a
user that may read and write this bucket and nothing else. Without them the API's key must already
exist and be allowed to create or use the bucket.

A record whose file is not on disk stops the move, so a wrong file root cannot turn every photo into
"not found"; --allow-missing moves the rest anyway. Files on disk are not deleted: remove them once
the deployment has been checked. Repeatable; needs the database owner, which no running service is given.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from urllib.parse import urlsplit

import asyncpg

from . import storage


def service_key(bucket: str) -> bool:
    """Make the API's key a user of this bucket only. Returns False when no administrator account was given."""
    get = lambda name: os.getenv(name, '').strip()
    admin_key, admin_secret = get('VINHOMES_API_S3_ADMIN_ACCESS_KEY'), get('VINHOMES_API_S3_ADMIN_SECRET_KEY')
    access, secret = get('VINHOMES_API_S3_ACCESS_KEY'), get('VINHOMES_API_S3_SECRET_KEY')
    if not admin_key or admin_key == access:
        return False
    from minio import Minio, MinioAdmin
    from minio.credentials import StaticProvider
    address = urlsplit(get('VINHOMES_API_S3_ENDPOINT'))
    secure = address.scheme == 'https'
    root = Minio(address.netloc, access_key=admin_key, secret_key=admin_secret, secure=secure)
    if not root.bucket_exists(bucket):
        root.make_bucket(bucket)
    admin = MinioAdmin(endpoint=address.netloc, credentials=StaticProvider(admin_key, admin_secret), secure=secure)
    policy = 'files-' + bucket
    admin.policy_add(policy, policy={'Version': '2012-10-17', 'Statement': [
        {'Effect': 'Allow', 'Action': ['s3:GetBucketLocation', 's3:ListBucket'], 'Resource': [f'arn:aws:s3:::{bucket}']},
        {'Effect': 'Allow', 'Action': ['s3:GetObject', 's3:PutObject', 's3:DeleteObject'], 'Resource': [f'arn:aws:s3:::{bucket}/*']}]})
    admin.user_add(access, secret)
    admin.policy_set(policy, user=access)
    return True


async def setup(db: asyncpg.Connection, tenant: str, *, root: Path, allow_missing: bool = False) -> dict:
    """Runs in the caller's transaction: a location's record changes only after its objects were copied."""
    if storage.provider() != 's3':
        raise RuntimeError('VINHOMES_API_S3_ENDPOINT is required')
    bucket = storage.bucket()
    scoped = service_key(bucket)
    client = storage.client()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    moved = missing = 0
    for location in await db.fetch("select id from storage_locations where tenant_id=$1 and provider='local_fs' order by created_at", tenant):
        for row in await db.fetch('select object_key from file_objects where tenant_id=$1 and location_id=$2', tenant, location['id']):
            path = (root / row['object_key']).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file():
                missing += 1
                continue
            client.fput_object(bucket, row['object_key'], str(path))
            moved += 1
        if missing and not allow_missing:
            raise RuntimeError(f'{missing} recorded files are not under {root}; check VINHOMES_RESIDENT_FILE_ROOT, or pass --allow-missing')
        # The credentials stay in the service's settings; the record only says where they are taken from.
        await db.execute("""update storage_locations set provider='s3',endpoint_ref='s3',bucket_name=$2,
            credential_secret_ref='env:VINHOMES_API_S3',versioning_required=false where id=$1""", location['id'], bucket)
    if not await db.fetchval("select 1 from storage_locations where tenant_id=$1 and provider='s3' and purpose='evidence' and status='active'", tenant):
        await db.execute("""insert into storage_locations(tenant_id,provider,endpoint_ref,bucket_name,tenant_prefix,
              credential_secret_ref,versioning_required,encryption_mode,purpose,status)
            values($1,'s3','s3',$2,'evidence/','env:VINHOMES_API_S3',false,'none','evidence','active')""", tenant, bucket)
    return {'type': 'object-storage-ready', 'bucket': bucket, 'moved': moved, 'missingOnDisk': missing, 'scopedKey': scoped}


async def main() -> None:
    url, tenant = os.environ.get('DATABASE_URL', ''), os.environ.get('VINHOMES_API_TENANT_ID', '')
    if not url or not tenant:
        raise SystemExit('DATABASE_URL (owner) and VINHOMES_API_TENANT_ID are required')
    from .v3_files import FILE_ROOT
    db = await asyncpg.connect(url)
    try:
        async with db.transaction():
            await db.execute("select set_config('app.tenant_id',$1,true)", tenant)
            print(json.dumps(await setup(db, tenant, root=FILE_ROOT, allow_missing='--allow-missing' in sys.argv[1:])))
    finally:
        await db.close()


if __name__ == '__main__':
    asyncio.run(main())
