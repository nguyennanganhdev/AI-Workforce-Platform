"""Verify real signed S3 upload, integrity and isolation with restricted PostgreSQL."""
import asyncio
import hashlib
import os
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
from test_resident_contract import TENANT, image, sql
from test_resident_contract import database as database
from test_v3_agent_database import demo_client
from vinhomes_api import storage
from vinhomes_api.storage_setup import setup
from vinhomes_api.v3_files import FILE_ROOT

ENDPOINT = os.getenv('VINHOMES_TEST_S3_ENDPOINT', '')


@pytest.mark.skipif(not ENDPOINT, reason='Real MinIO endpoint required')
def test_direct_browser_upload_integrity_replay_and_no_ready_overwrite(database, monkeypatch):
    bucket = 'direct-' + uuid4().hex[:12]
    for name, value in {'VINHOMES_API_S3_ENDPOINT': ENDPOINT, 'VINHOMES_API_S3_PUBLIC_ENDPOINT': ENDPOINT,
                        'VINHOMES_API_S3_BUCKET': bucket, 'VINHOMES_API_S3_ACCESS_KEY': os.environ['VINHOMES_TEST_S3_ACCESS_KEY'],
                        'VINHOMES_API_S3_SECRET_KEY': os.environ['VINHOMES_TEST_S3_SECRET_KEY']}.items():
        monkeypatch.setenv(name, value)
    async def prepare():
        db = await asyncpg.connect(database['admin'])
        try:
            async with db.transaction():
                await db.execute("select set_config('app.tenant_id',$1,true)", str(TENANT))
                await setup(db, str(TENANT), root=FILE_ROOT, allow_missing=True)
        finally:
            await db.close()
    asyncio.run(prepare())
    data = image()
    try:
        with demo_client(database, 'resident') as c:
            chat = c.post('/resident/chats', json={'title': 'Direct image'}).json()['id']
            path = f'/resident/chats/{chat}/direct-uploads'
            body = {'filename': 'image.png', 'mime_type': 'image/png', 'size_bytes': len(data),
                    'sha256': hashlib.sha256(data).hexdigest(), 'idempotency_key': str(uuid4())}
            response = c.post(path, json=body)
            assert response.status_code == 201, response.text
            upload = response.json()
            assert upload['storage'] == 's3' and upload['method'] == 'POST'
            assert c.post(path, json=body).json()['uploadId'] == upload['uploadId']
            assert c.post(path, json={**body, 'sha256': '0' * 64}).status_code == 409
            complete = f"/direct-uploads/{upload['uploadId']}/complete"
            assert c.post(complete).status_code == 409
            with demo_client(database, 'management') as other:
                assert other.post(complete).status_code == 404
            # Bytes go to the object store URL, never the business API.
            with httpx.Client() as browser:
                too_large = browser.post(upload['uploadUrl'], data=upload['fields'], files={'file': ('image.png', data + b'x', 'image/png')})
                assert too_large.status_code == 400
                signed = browser.post(upload['uploadUrl'], data=upload['fields'], files={'file': ('image.png', data, 'image/png')})
                assert signed.status_code == 204, signed.text
            ready = c.post(complete)
            assert ready.status_code == 200, ready.text
            assert c.post(complete).json()['fileId'] == ready.json()['fileId']
            assert c.get(f"/resident/photos/{ready.json()['fileId']}").content == data
            stored = sql(database, 'select object_key from file_objects where file_id=$1', UUID(ready.json()['fileId']))[0]['object_key']
            assert '/accepted/' in stored
            with httpx.Client() as browser:
                assert browser.post(upload['uploadUrl'], data=upload['fields'], files={'file': ('image.png', b'x' * len(data), 'image/png')}).status_code == 204
            assert c.get(f"/resident/photos/{ready.json()['fileId']}").content == data
            # A correct declared checksum cannot make non-image content accepted.
            invalid_data = b'x' * len(data)
            invalid = c.post(path, json={**body, 'idempotency_key': str(uuid4()), 'sha256': hashlib.sha256(invalid_data).hexdigest()}).json()
            with httpx.Client() as browser:
                assert browser.post(invalid['uploadUrl'], data=invalid['fields'], files={'file': ('image.png', invalid_data, 'image/png')}).status_code == 204
            assert c.post(f"/direct-uploads/{invalid['uploadId']}/complete").status_code == 422
    finally:
        client = storage.client()
        for obj in client.list_objects(bucket, recursive=True):
            client.remove_object(bucket, obj.object_name)
        client.remove_bucket(bucket)
