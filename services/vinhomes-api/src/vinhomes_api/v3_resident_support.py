"""Resident bootstrap, durable read cursors and private intake photographs."""
import hashlib
import io
import os
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_auth import resident_connection
from .v3_resident import _owned_chat

router = APIRouter(tags=["Vinhomes V3 resident"])
Scope = Annotated[tuple[AsyncConnection, str], Depends(resident_connection, scope="function")]
FILE_ROOT = Path(os.getenv("VINHOMES_RESIDENT_FILE_ROOT", str(Path(__file__).resolve().parents[2] / ".local-v3-files"))).resolve()
MAX_BYTES = 10 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 20_000_000


@router.get("/resident/me")
async def me(request: Request, scope: Scope):
    db, actor = scope
    user = (await db.execute(text("select id,name,email from users where id=:id"), {"id": actor})).mappings().one()
    units = await db.execute(text("""
        select u.id,u.code,b.id as building_id,b.name as building_name,s.name as site_name,s.domain_id
        from unit_residents ur join units u on u.id=ur.unit_id and u.tenant_id=ur.tenant_id
        join buildings b on b.id=u.building_id and b.tenant_id=u.tenant_id
        join sites s on s.id=b.site_id and s.tenant_id=b.tenant_id
        join domains d on d.id=s.domain_id and d.tenant_id=s.tenant_id
        where ur.user_id=:actor and ur.verification_status='verified'
          and ur.valid_from<=now() and (ur.valid_to is null or ur.valid_to>now())
          and u.status='active' and b.status='active' and s.status='active' and d.status='active'
        order by b.name,u.code
    """), {"actor": actor})
    categories = await db.execute(text("select id,code,name from service_categories where enabled order by name"))
    return {"user": dict(user), "units": [dict(r) for r in units.mappings()],
            "categories": [dict(r) for r in categories.mappings()],
            "dataMode": "local-database" if request.app.state.settings.demo_mode or request.app.state.settings.dev_user_id else "database"}


class ReadCursor(BaseModel):
    sequence: int = Field(ge=0)


@router.post("/resident/chats/{channel_id}/read")
async def read_chat(channel_id: str, body: ReadCursor, scope: Scope):
    await _owned_chat(scope, channel_id)
    result = await scope[0].execute(text("""
        update channel_memberships set last_read_seq=greatest(last_read_seq,
          least(:seq,(select next_message_seq-1 from channels where id=:id))),last_read_at=now()
        where channel_id=:id and user_id=:actor returning last_read_seq
    """), {"id": channel_id, "actor": scope[1], "seq": body.sequence})
    return {"sequence": result.scalar_one()}


@router.post("/resident/chats/{channel_id}/photos", status_code=201)
async def upload_photo(channel_id: str, request: Request, scope: Scope,
                       filename: str = Query(min_length=1, max_length=255),
                       mime_type: Literal["image/jpeg", "image/png", "image/webp"] = Query(alias="mimeType")):
    await _owned_chat(scope, channel_id, lock=True)
    key = request.headers.get("Idempotency-Key", "")
    if not 8 <= len(key) <= 120 or filename != Path(filename).name or any(ord(c) < 32 for c in filename):
        raise HTTPException(422, "Invalid file name or Idempotency-Key")
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "Image exceeds 10 MiB")
    try:
        with Image.open(io.BytesIO(data)) as photo:
            if photo.format != {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}[mime_type]:
                raise ValueError("Image type mismatch")
            photo.verify()
        with Image.open(io.BytesIO(data)) as photo:
            photo.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise HTTPException(422, "Invalid or oversized image") from exc
    db, actor = scope
    file_id = uuid5(NAMESPACE_URL, f"{request.app.state.settings.tenant_id}:{actor}:{channel_id}:{key}")
    digest = hashlib.sha256(data).hexdigest()
    previous = await db.execute(text("""
        select f.original_name,o.sha256,f.declared_mime_type from files f
        join file_objects o on o.id=f.accepted_object_id and o.tenant_id=f.tenant_id
        where f.id=:id and f.uploaded_by=:actor
    """), {"id": file_id, "actor": actor})
    old = previous.mappings().first()
    if old:
        if old["sha256"] != digest or old["original_name"] != filename or old["declared_mime_type"] != mime_type:
            raise HTTPException(409, "Idempotency-Key already used for a different file")
        return {"id": file_id, "name": filename, "url": f"/api/business/resident/photos/{file_id}"}
    storage = (await db.execute(text("select id,tenant_prefix from storage_locations where provider='local_fs' and purpose='evidence' and status='active' order by created_at limit 1"))).mappings().first()
    if not storage:
        raise HTTPException(503, "Private evidence storage has not been configured")
    object_key = f"{storage['tenant_prefix']}{file_id.hex}"
    path = (FILE_ROOT / object_key).resolve()
    if not path.is_relative_to(FILE_ROOT):
        raise HTTPException(503, "Invalid storage prefix")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Deterministic key also recovers a file left by a rolled-back database transaction.
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise HTTPException(409, "Upload key already contains another image")
    path.write_bytes(data)
    principal = await db.execute(text("select id from execution_principals where kind='user' and user_id=:actor and status='active'"), {"actor": actor})
    principal_id = principal.scalar_one_or_none()
    if principal_id is None:
        principal_id = (await db.execute(text("insert into execution_principals(tenant_id,kind,user_id,status) values(nullif(current_setting('app.tenant_id',true),'')::uuid,'user',:actor,'active') returning id"), {"actor": actor})).scalar_one()
    object_id = uuid4()
    await db.execute(text("""
        insert into files(id,tenant_id,uploaded_by,original_name,owner_principal_id,scope_kind,channel_id,status,declared_mime_type,retention_until)
        values(:id,nullif(current_setting('app.tenant_id',true),'')::uuid,:actor,:name,:principal,'channel',:channel,'staged',:mime,now()+interval '24 hours')
    """), {"id": file_id, "actor": actor, "name": filename, "principal": principal_id, "channel": channel_id, "mime": mime_type})
    await db.execute(text("""
        insert into file_objects(id,tenant_id,file_id,location_id,object_key,version_id,variant,mime_type,size_bytes,sha256,scan_status,verified_at,encryption_mode,status)
        values(:id,nullif(current_setting('app.tenant_id',true),'')::uuid,:file,:location,:key,:version,'original',:mime,:size,:hash,'clean',now(),'none','ready')
    """), {"id": object_id, "file": file_id, "location": storage["id"], "key": object_key, "version": str(uuid4()), "mime": mime_type, "size": len(data), "hash": digest})
    await db.execute(text("update files set status='ready',accepted_object_id=:object where id=:id"), {"object": object_id, "id": file_id})
    return {"id": file_id, "name": filename, "url": f"/api/business/resident/photos/{file_id}"}


@router.get("/resident/photos/{file_id}")
async def photo_content(file_id: UUID, scope: Scope):
    result = await scope[0].execute(text("""
        select o.object_key,o.mime_type,f.original_name from files f
        join file_objects o on o.id=f.accepted_object_id and o.tenant_id=f.tenant_id
        where f.id=:id and f.status='ready' and o.status='ready' and f.uploaded_by=:actor
          and (exists(select 1 from channels c where c.id=f.channel_id and c.created_by=:actor)
            or exists(select 1 from tickets t where t.id=f.ticket_id and t.requester_user_id=:actor))
    """), {"id": file_id, "actor": scope[1]})
    file = result.mappings().first()
    if file is None:
        raise HTTPException(404, "Photo not found")
    path = (FILE_ROOT / file["object_key"]).resolve()
    if not path.is_relative_to(FILE_ROOT) or not path.is_file():
        raise HTTPException(404, "Photo not found")
    return FileResponse(path, media_type=file["mime_type"], headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
