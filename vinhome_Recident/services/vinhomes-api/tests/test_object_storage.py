"""Files in a bucket: a real S3 server (MinIO) is needed, named by VINHOMES_TEST_S3_ENDPOINT.

    VINHOMES_TEST_S3_ENDPOINT=http://127.0.0.1:9599 VINHOMES_TEST_S3_ACCESS_KEY=... VINHOMES_TEST_S3_SECRET_KEY=... pytest tests/test_object_storage.py
"""

import pytest

import asyncio
import os
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from test_resident_contract import TENANT, image, sql
from test_resident_contract import (
    database as database,  # noqa: PLC0414 -- pytest fixture export
)
from test_domain_database import demo_client

from vinhomes_api import storage, v3_files
from vinhomes_api.storage_setup import setup

ENDPOINT = os.getenv('VINHOMES_TEST_S3_ENDPOINT', '')


def test_a_key_that_would_leave_the_storage_is_refused(tmp_path, monkeypatch):
    monkeypatch.delenv('VINHOMES_API_S3_ENDPOINT', raising=False)
    assert storage.provider() == 'local_fs' and storage.at(tmp_path, 'evidence/a.png') == (tmp_path / 'evidence/a.png').resolve()
    for key in ('../outside.png', str(tmp_path.parent / 'outside.png')):
        with pytest.raises(ValueError):
            storage.at(tmp_path, key)
    monkeypatch.setenv('VINHOMES_API_S3_ENDPOINT', 'http://bucket.test:9000')
    assert storage.provider() == 's3' and storage.at(tmp_path, 'evidence/a.png').key == 'evidence/a.png'
    for key in ('../outside.png', '/absolute.png', 'a/../../b.png', ''):
        with pytest.raises(ValueError):
            storage.at(tmp_path, key)


@pytest.mark.skipif(not ENDPOINT, reason='VINHOMES_TEST_S3_ENDPOINT names no S3 server')
def test_files_on_disk_move_to_the_bucket_and_new_ones_are_stored_there(database, monkeypatch, tmp_path):
    upload = lambda client, ticket, name: client.post(f'/tickets/{ticket}/files', content=image(), params={
        'filename': name, 'mimeType': 'image/png', 'purpose': 'issue'}, headers={'Content-Type': 'application/octet-stream'})
    ticket = sql(database, 'select id from tickets order by created_at limit 1')[0]['id']
    monkeypatch.delenv('VINHOMES_API_S3_ENDPOINT', raising=False)
    with demo_client(database, 'admin') as admin:
        old = upload(admin, ticket, 'truoc.png')
        assert old.status_code == 201, old.text
    key = sql(database, 'select object_key from file_objects where file_id=$1', old.json()['fileId'])[0]['object_key']
    assert (Path(v3_files.FILE_ROOT) / key).is_file()

    bucket = 'test-' + uuid4().hex[:12]
    for name, value in {'VINHOMES_API_S3_ENDPOINT': ENDPOINT, 'VINHOMES_API_S3_BUCKET': bucket,
                        'VINHOMES_API_S3_ACCESS_KEY': os.environ['VINHOMES_TEST_S3_ACCESS_KEY'],
                        'VINHOMES_API_S3_SECRET_KEY': os.environ['VINHOMES_TEST_S3_SECRET_KEY']}.items():
        monkeypatch.setenv(name, value)
    with demo_client(database, 'admin') as admin:
        # The bucket is not prepared yet: no upload is accepted and nothing on disk is served as if it were there.
        assert upload(admin, ticket, 'chua-co-bucket.png').status_code == 503
        assert admin.get(f"/files/{old.json()['fileId']}/content").status_code == 404

    async def prepare(root, **options):
        db = await asyncpg.connect(database['admin'])
        try:
            async with db.transaction():
                await db.execute("select set_config('app.tenant_id',$1,true)", str(TENANT))
                return await setup(db, str(TENANT), root=root, **options)
        finally:
            await db.close()

    # A wrong file root would record every photo as moved while none was: the move stops and nothing changes.
    with pytest.raises(RuntimeError, match='not under'):
        asyncio.run(prepare(tmp_path / 'wrong-root'))
    assert sql(database, "select count(*) as n from storage_locations where provider='s3'")[0]['n'] == 0
    report = asyncio.run(prepare(Path(v3_files.FILE_ROOT)))
    assert report['bucket'] == bucket and report['moved'] >= 1 and report['missingOnDisk'] == 0
    assert asyncio.run(prepare(Path(v3_files.FILE_ROOT)))['moved'] == 0  # repeatable: no disk location is left
    client = storage.client()
    assert client.stat_object(bucket, key).size == len(image())
    assert sql(database, "select count(*) as n from storage_locations where provider='local_fs'")[0]['n'] == 0
    with demo_client(database, 'admin') as admin:
        moved = admin.get(f"/files/{old.json()['fileId']}/content?inline=true")
        assert moved.status_code == 200 and moved.content == image() and moved.headers['content-type'] == 'image/png'
        new = upload(admin, ticket, 'ảnh sau sửa.png')
        assert new.status_code == 201, new.text
        new_key = sql(database, """select o.object_key,s.provider,s.bucket_name from file_objects o join storage_locations s on s.id=o.location_id
            where o.file_id=$1""", new.json()['fileId'])[0]
        assert (new_key['provider'], new_key['bucket_name']) == ('s3', bucket) and client.stat_object(bucket, new_key['object_key']).size == len(image())
        assert not (Path(v3_files.FILE_ROOT) / new_key['object_key']).exists()
        served = admin.get(f"/files/{new.json()['fileId']}/content")
        assert served.status_code == 200 and served.content == image()
        assert "filename*=utf-8''" in served.headers['content-disposition'] and served.headers['cache-control'] == 'private, no-store'
        # The object is gone from the bucket: the route says so instead of failing.
        client.remove_object(bucket, new_key['object_key'])
        assert admin.get(f"/files/{new.json()['fileId']}/content").status_code == 404
    with demo_client(database, 'resident') as resident:
        assert resident.get(f"/files/{old.json()['fileId']}/content").status_code in (403, 404)
    for item in client.list_objects(bucket, recursive=True):
        client.remove_object(bucket, item.object_name)
    client.remove_bucket(bucket)


@pytest.mark.skipif(not ENDPOINT, reason='VINHOMES_TEST_S3_ENDPOINT names no S3 server')
def test_a_bucket_object_behaves_as_the_file_routes_expect_a_path_to(monkeypatch, tmp_path):
    bucket = 'test-' + uuid4().hex[:12]
    for name, value in {'VINHOMES_API_S3_ENDPOINT': ENDPOINT, 'VINHOMES_API_S3_BUCKET': bucket,
                        'VINHOMES_API_S3_ACCESS_KEY': os.environ['VINHOMES_TEST_S3_ACCESS_KEY'],
                        'VINHOMES_API_S3_SECRET_KEY': os.environ['VINHOMES_TEST_S3_SECRET_KEY']}.items():
        monkeypatch.setenv(name, value)
    storage.client().make_bucket(bucket)
    stored = storage.at(tmp_path, 'evidence/resident/photo.png')
    assert not stored.exists() and not stored.is_file()
    with pytest.raises(FileNotFoundError):
        stored.stat()
    stored.parent.mkdir(parents=True, exist_ok=True)
    with stored.open('xb') as output:
        output.write(b'first')
    assert stored.is_file() and stored.stat().st_size == 5 and stored.read_bytes() == b'first'
    # Creating is exclusive, as "xb" is on disk: a second upload under the same key does not replace the first.
    with pytest.raises(FileExistsError):
        stored.open('xb')
    # The conversation upload writes beside the object and then puts it in place.
    temporary = stored.with_suffix(stored.suffix + '.upload')
    assert temporary.key == 'evidence/resident/photo.png.upload'
    temporary.write_bytes(bytearray(b'second!'))
    temporary.replace(stored)
    assert stored.read_bytes() == b'second!' and not temporary.exists()
    answer = storage.respond(stored, media_type='image/png', filename='ảnh.png', content_disposition_type='inline',
                             headers={'Cache-Control': 'private, no-store'})
    assert answer.body == b'second!' and answer.headers['content-disposition'].startswith("inline; filename*=utf-8''")
    stored.unlink(missing_ok=True)
    stored.unlink(missing_ok=True)
    with pytest.raises(FileNotFoundError):
        stored.unlink()
    storage.client().remove_bucket(bucket)


@pytest.mark.skipif(not ENDPOINT, reason='VINHOMES_TEST_S3_ENDPOINT names no S3 server')
def test_the_api_gets_a_key_of_its_own_that_only_reaches_its_bucket(monkeypatch):
    from minio.error import S3Error
    from vinhomes_api.storage_setup import service_key
    bucket, other = 'test-' + uuid4().hex[:12], 'test-' + uuid4().hex[:12]
    access, secret = 'api' + uuid4().hex[:10], uuid4().hex + uuid4().hex[:8]
    root = {'VINHOMES_API_S3_ENDPOINT': ENDPOINT, 'VINHOMES_API_S3_BUCKET': bucket,
            'VINHOMES_API_S3_ACCESS_KEY': os.environ['VINHOMES_TEST_S3_ACCESS_KEY'],
            'VINHOMES_API_S3_SECRET_KEY': os.environ['VINHOMES_TEST_S3_SECRET_KEY']}
    for name, value in root.items():
        monkeypatch.setenv(name, value)
    # The administrator's own key as the API's key: nothing to scope, as with any other S3 service.
    assert service_key(bucket) is False
    administrator = storage.client()
    administrator.make_bucket(other)
    administrator.put_object(other, 'secret.txt', __import__('io').BytesIO(b'x'), 1)
    for name, value in {'VINHOMES_API_S3_ADMIN_ACCESS_KEY': root['VINHOMES_API_S3_ACCESS_KEY'],
                        'VINHOMES_API_S3_ADMIN_SECRET_KEY': root['VINHOMES_API_S3_SECRET_KEY'],
                        'VINHOMES_API_S3_ACCESS_KEY': access, 'VINHOMES_API_S3_SECRET_KEY': secret}.items():
        monkeypatch.setenv(name, value)
    assert service_key(bucket) is True and service_key(bucket) is True  # repeatable
    api = storage.client()
    assert api.bucket_exists(bucket)
    stored = storage.BucketObject('evidence/a.png')
    stored.write_bytes(b'photo')
    assert stored.read_bytes() == b'photo'
    stored.unlink()
    for refused in (lambda: api.get_object(other, 'secret.txt'), lambda: api.put_object(other, 'b.txt', __import__('io').BytesIO(b'x'), 1),
                    lambda: api.make_bucket('test-' + uuid4().hex[:12]), lambda: api.remove_bucket(bucket)):
        with pytest.raises(S3Error) as denied:
            refused()
        assert denied.value.code == 'AccessDenied'
    administrator.remove_object(other, 'secret.txt')
    administrator.remove_bucket(other)
    administrator.remove_bucket(bucket)
