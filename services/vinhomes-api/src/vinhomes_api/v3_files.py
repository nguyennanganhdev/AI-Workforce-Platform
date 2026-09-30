"""Loopback development file store for V3 evidence.

Production storage needs the deployment's verified object-store workflow. This
route deliberately refuses uploads outside the local development configuration.
"""

import hashlib
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_auth import scoped_connection
from .v3_mutations import record_event, visible_ticket

router = APIRouter(tags=["Vinhomes V3 files"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection)]
FILE_ROOT = Path(__file__).resolve().parents[2] / ".local-v3-files"
MAX_FILE_BYTES = 10 * 1024 * 1024
MAGIC = {"image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG\r\n\x1a\n",
         "image/webp": b"RIFF"}
EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def local_only(request: Request) -> None:
    settings = request.app.state.settings
    if not settings.dev_user_id or settings.host not in {"127.0.0.1", "localhost", "::1"}:
        raise HTTPException(503, "Local file storage is available only in loopback development")


@router.post("/tickets/{ticket_id}/files", status_code=201,
             summary="Upload a local development image for ticket evidence")
async def upload_ticket_file(
    ticket_id: UUID,
    request: Request,
    scope: Scope,
    data: bytes = Body(..., media_type="application/octet-stream"),
    filename: str = Query(..., min_length=1, max_length=255),
    mime_type: Literal["image/jpeg", "image/png", "image/webp"] = Query(..., alias="mimeType"),
    purpose: Literal["issue", "before", "after", "other"] = "issue",
) -> dict[str, object]:
    local_only(request)
    if filename != Path(filename).name or any(ord(ch) < 32 for ch in filename):
        raise HTTPException(422, "filename must be a plain file name")
    ticket = await visible_ticket(scope, ticket_id, lock=True)
    location = await scope[0].execute(text("""
        select id from storage_locations where provider='local_fs'
          and purpose='evidence' and status='active'
        order by created_at limit 1
    """))
    location_id = location.scalar_one_or_none()
    if location_id is None:
        raise HTTPException(503, "Local V3 evidence storage is not configured")
    file_id = uuid4()
    object_id = uuid4()
    object_key = f"{file_id.hex}{EXT[mime_type]}"
    FILE_ROOT.mkdir(parents=True, exist_ok=True)
    file_path = FILE_ROOT / object_key
    size = len(data)
    header = data[:12]
    if size > MAX_FILE_BYTES:
        raise HTTPException(413, "Image exceeds the 10 MB local limit")
    if size == 0 or not header.startswith(MAGIC[mime_type]):
        raise HTTPException(422, "Image content does not match mimeType")
    if mime_type == "image/webp" and header[8:12] != b"WEBP":
        raise HTTPException(422, "Image content does not match mimeType")
    digest = hashlib.sha256(data)
    try:
        with file_path.open("xb") as output:
            output.write(data)
    except BaseException:
        file_path.unlink(missing_ok=True)
        raise
    principal = await scope[0].execute(text("""
        select id from execution_principals
        where kind='user' and user_id=:user_id and status='active' limit 1
    """), {"user_id": scope[1]})
    principal_id = principal.scalar_one_or_none()
    if principal_id is None:
        result = await scope[0].execute(text("""
            insert into execution_principals
              (tenant_id,kind,user_id,status)
            values (nullif(current_setting('app.tenant_id',true),'')::uuid,
              'user',:user_id,'active') returning id
        """), {"user_id": scope[1]})
        principal_id = result.scalar_one()
    await scope[0].execute(text("""
        insert into files
          (id,tenant_id,uploaded_by,original_name,owner_principal_id,
           scope_kind,ticket_id,status,declared_mime_type)
        values (:id,nullif(current_setting('app.tenant_id',true),'')::uuid,
          :user_id,:filename,:principal_id,'ticket',:ticket_id,'staged',:mime_type)
    """), {"id": file_id, "user_id": scope[1], "filename": filename,
           "principal_id": principal_id, "ticket_id": ticket_id,
           "mime_type": mime_type})
    await scope[0].execute(text("""
        insert into file_objects
          (id,tenant_id,file_id,location_id,object_key,version_id,variant,
           mime_type,size_bytes,sha256,scan_status,verified_at,
           encryption_mode,status)
        values (:id,nullif(current_setting('app.tenant_id',true),'')::uuid,
          :file_id,:location_id,:object_key,:version_id,'original',
          :mime_type,:size_bytes,:sha256,'clean',now(),'none','ready')
    """), {"id": object_id, "file_id": file_id, "location_id": location_id,
           "object_key": object_key, "version_id": str(uuid4()),
           "mime_type": mime_type, "size_bytes": size, "sha256": digest.hexdigest()})
    await scope[0].execute(text("""
        update files set status='ready',accepted_object_id=:object_id,
          updated_at=now() where id=:file_id
    """), {"object_id": object_id, "file_id": file_id})
    await scope[0].execute(text("""
        insert into ticket_files
          (tenant_id,ticket_id,file_id,purpose,uploaded_by)
        values (nullif(current_setting('app.tenant_id',true),'')::uuid,
          :ticket_id,:file_id,:purpose,:user_id)
    """), {"ticket_id": ticket_id, "file_id": file_id,
           "purpose": purpose, "user_id": scope[1]})
    await record_event(scope, ticket, "ticket.file_uploaded",
                       __import__("json").dumps({"fileId": str(file_id), "purpose": purpose}))
    return {"fileId": file_id, "ticketId": ticket_id, "sizeBytes": size,
            "mimeType": mime_type, "status": "ready"}


@router.get("/files/{file_id}/content", summary="Download a local development evidence image")
async def download_file(file_id: UUID, request: Request, scope: Scope) -> FileResponse:
    local_only(request)
    found = await scope[0].execute(text("""
        select f.ticket_id, f.original_name, o.object_key, o.sha256
        from files f join file_objects o on o.id=f.accepted_object_id and o.tenant_id=f.tenant_id
        where f.id=:id and f.status='ready' and o.status='ready'
          and o.location_id in (select id from storage_locations
                                where provider='local_fs' and purpose='evidence')
    """), {"id": file_id})
    file = found.mappings().first()
    if file is None or file["ticket_id"] is None:
        raise HTTPException(404, "Local evidence image not found")
    await visible_ticket(scope, file["ticket_id"])
    object_key = file["object_key"]
    if object_key != Path(object_key).name:
        raise HTTPException(503, "Invalid local evidence object key")
    file_path = (FILE_ROOT / object_key).resolve()
    if not file_path.is_relative_to(FILE_ROOT.resolve()) or not file_path.is_file():
        raise HTTPException(404, "Local evidence image is missing")
    return FileResponse(file_path, media_type="application/octet-stream",
                        filename=file["original_name"], content_disposition_type="attachment")


@router.get("/tickets/{ticket_id}/files", summary="List files attached to a ticket")
async def list_ticket_files(ticket_id: UUID, scope: Scope) -> dict[str, object]:
    await visible_ticket(scope, ticket_id)
    result = await scope[0].execute(text("""
        select f.id, f.original_name, f.declared_mime_type, f.status,
               tf.purpose, tf.created_at
        from ticket_files tf
        join files f on f.id=tf.file_id and f.tenant_id=tf.tenant_id
        where tf.ticket_id=:ticket_id order by tf.created_at desc
    """), {"ticket_id": ticket_id})
    return {"items": [dict(row) for row in result.mappings().all()]}
