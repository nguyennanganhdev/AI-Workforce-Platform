"""Short-lived direct browser uploads using the existing file_uploads contract.

Signed POSTs reach the private bucket directly. Completion verifies the bytes and promotes
them to a different key, so reusing a staging credential cannot overwrite a ready file.
"""
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from . import storage
from .v3_auth import resident_connection, scoped_connection
from .v3_files import EXT, FILE_ROOT, MAX_FILE_BYTES, validate_image
from .v3_mutations import visible_ticket, record_event
from .v3_resident import _owned_chat

router = APIRouter(tags=['Direct image uploads'])
Resident = Annotated[tuple, Depends(resident_connection)]
Staff = Annotated[tuple, Depends(scoped_connection)]
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"


class ImageUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: Literal['image/jpeg', 'image/png', 'image/webp']
    size_bytes: int = Field(gt=0, le=MAX_FILE_BYTES)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    idempotency_key: str = Field(min_length=1, max_length=160)
    purpose: Literal['issue', 'before', 'after', 'other'] = 'issue'


def upload_result(row):
    if row['status'] == 'accepted':
        return {'uploadId': row['id'], 'fileId': row['file_id'], 'storage': 's3', 'status': 'ready'}
    if row['status'] != 'issued' or row['expires_at'] <= datetime.now(UTC):
        raise HTTPException(409, 'Upload session is no longer usable; start a new upload.')
    url, fields = storage.signed_upload(row['staging_key'], row['expected_size_bytes'],
                                        row['allowed_mime_types'][0], row['expires_at'])
    return {'uploadId': row['id'], 'fileId': row['file_id'], 'storage': 's3', 'status': 'issued',
            'uploadUrl': url, 'method': 'POST', 'fields': fields, 'expiresAt': row['expires_at']}


async def issue(body, scope, *, channel=None, ticket=None):
    if not storage.direct_enabled():
        return {'storage': 'api'}
    if Path(body.filename).name != body.filename or any(c in body.filename for c in '/\\') or any(ord(c) < 32 for c in body.filename):
        raise HTTPException(422, 'Plain filename required')
    db, actor = scope[:2]
    await db.execute(text("select pg_advisory_xact_lock(hashtext(:key))"), {'key': f'{actor}:{body.idempotency_key}'})
    prior = (await db.execute(text('''select u.*,f.original_name,f.channel_id,f.ticket_id,f.declared_mime_type
        from file_uploads u join files f on f.id=u.file_id and f.tenant_id=u.tenant_id
        where u.requested_by=:actor and u.idempotency_key=:key'''), {'actor': actor, 'key': body.idempotency_key})).mappings().first()
    if prior:
        if (prior['original_name'], prior['channel_id'], prior['ticket_id'], prior['expected_size_bytes'],
            prior['expected_sha256'], prior['declared_mime_type']) != (body.filename, channel, ticket, body.size_bytes, body.sha256, body.mime_type):
            raise HTTPException(409, 'Upload key already used for different content')
        if ticket:
            purpose = (await db.execute(text('select purpose from ticket_files where ticket_id=:ticket and file_id=:file'),
                                       {'ticket': ticket, 'file': prior['file_id']})).scalar_one()
            if purpose != body.purpose:
                raise HTTPException(409, 'Upload key already used for a different purpose')
        return upload_result(prior)
    location = (await db.execute(text("select id,tenant_prefix from storage_locations where provider='s3' and purpose='evidence' and status='active' order by created_at limit 1"))).mappings().first()
    if not location:
        raise HTTPException(503, 'Object storage is not configured')
    principal = (await db.execute(text("select id from execution_principals where kind='user' and user_id=:actor and status='active'"), {'actor': actor})).scalar_one_or_none()
    if not principal:
        principal = (await db.execute(text(f"insert into execution_principals(tenant_id,kind,user_id,status) values({TENANT},'user',:actor,'active') returning id"), {'actor': actor})).scalar_one()
    file = uuid4()
    key = f"{location['tenant_prefix']}staging/{file.hex}{EXT[body.mime_type]}"
    storage.at(FILE_ROOT, key)
    await db.execute(text(f'''insert into files(id,tenant_id,uploaded_by,original_name,owner_principal_id,scope_kind,channel_id,ticket_id,status,declared_mime_type)
        values(:id,{TENANT},:actor,:name,:principal,:kind,:channel,:ticket,'staged',:mime)'''),
        {'id': file, 'actor': actor, 'name': body.filename, 'principal': principal, 'kind': 'channel' if channel else 'ticket',
         'channel': channel, 'ticket': ticket, 'mime': body.mime_type})
    if ticket:
        await db.execute(text(f"insert into ticket_files(tenant_id,ticket_id,file_id,purpose,uploaded_by) values({TENANT},:ticket,:file,:purpose,:actor)"),
                         {'ticket': ticket, 'file': file, 'purpose': body.purpose, 'actor': actor})
    row = (await db.execute(text(f'''insert into file_uploads(tenant_id,file_id,requested_by,location_id,staging_key,upload_mode,
        expected_size_bytes,expected_sha256,allowed_mime_types,max_size_bytes,status,idempotency_key,expires_at)
        values({TENANT},:file,:actor,:location,:key,'single',:size,:sha,:mime,:max,'issued',:idempotency_key,now()+interval '5 minutes') returning *'''),
        {'file': file, 'actor': actor, 'location': location['id'], 'key': key, 'size': body.size_bytes,
         'sha': body.sha256, 'mime': [body.mime_type], 'max': MAX_FILE_BYTES,
         'idempotency_key': body.idempotency_key})).mappings().one()
    return upload_result(row)


@router.post('/resident/chats/{channel}/direct-uploads', status_code=201)
async def resident_issue(channel: str, body: ImageUpload, scope: Resident):
    await _owned_chat(scope, channel, lock=True)
    return await issue(body, scope, channel=channel)


@router.post('/tickets/{ticket}/direct-uploads', status_code=201)
async def staff_issue(ticket: UUID, body: ImageUpload, scope: Staff):
    await visible_ticket(scope, ticket, lock=True)
    return await issue(body, scope, ticket=ticket)


@router.post('/direct-uploads/{upload}/complete')
async def complete(upload: UUID, scope: Resident):
    if not storage.direct_enabled():
        raise HTTPException(503, 'Direct object storage is not configured')
    db, actor = scope
    row = (await db.execute(text('''select u.*,f.original_name,f.channel_id,f.ticket_id,f.declared_mime_type
        from file_uploads u join files f on f.id=u.file_id and f.tenant_id=u.tenant_id
        where u.id=:id and u.requested_by=:actor for update of u,f'''), {'id': upload, 'actor': actor})).mappings().first()
    if not row:
        raise HTTPException(404, 'Upload not found')
    ticket = None
    if row['channel_id']:
        await _owned_chat(scope, row['channel_id'])
    else:
        admin = bool((await db.execute(text('select 1 from platform_admins where user_id=:actor'), {'actor': actor})).first())
        ticket = await visible_ticket((db, actor, admin), row['ticket_id'])
    if row['status'] == 'accepted':
        return upload_result(row)
    if row['status'] != 'issued' or row['expires_at'] <= datetime.now(UTC):
        raise HTTPException(409, 'Upload session expired')
    staged = storage.at(FILE_ROOT, row['staging_key'])
    if not staged.exists() or staged.stat().st_size != row['expected_size_bytes']:
        raise HTTPException(409, 'Uploaded object is missing or size differs')
    data = staged.read_bytes()
    if len(data) != row['expected_size_bytes'] or hashlib.sha256(data).hexdigest() != row['expected_sha256']:
        raise HTTPException(409, 'Uploaded object checksum differs')
    validate_image(data, row['declared_mime_type'])
    # Validate a snapshot, then store exactly those verified bytes under an unguessable final key.
    final_key = row['staging_key'].replace('/staging/', '/accepted/', 1)
    stored = storage.at(FILE_ROOT, final_key)
    stored.write_bytes(data)
    obj = uuid4()
    await db.execute(text(f'''insert into file_objects(id,tenant_id,file_id,location_id,object_key,version_id,variant,
        mime_type,size_bytes,sha256,scan_status,verified_at,encryption_mode,status)
        values(:id,{TENANT},:file,:location,:key,:version,'original',:mime,:size,:sha,'clean',now(),'none','ready')'''),
        {'id': obj, 'file': row['file_id'], 'location': row['location_id'], 'key': final_key, 'version': str(uuid4()),
         'mime': row['declared_mime_type'], 'size': row['expected_size_bytes'], 'sha': row['expected_sha256']})
    await db.execute(text("update files set status='ready',accepted_object_id=:object,updated_at=now() where id=:file"), {'object': obj, 'file': row['file_id']})
    await db.execute(text("update file_uploads set status='accepted',result_object_id=:object,finalized_at=now() where id=:id"), {'object': obj, 'id': upload})
    if ticket:
        await record_event((db, actor, admin), ticket, 'ticket.file_uploaded', json.dumps({'fileId': str(row['file_id']), 'storage': 's3-direct'}))
    return {**upload_result({**row, 'status': 'accepted'}), 'mimeType': row['declared_mime_type'], 'sizeBytes': len(data)}
