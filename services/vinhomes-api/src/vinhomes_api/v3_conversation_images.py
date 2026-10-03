"""Persist images before a ticket exists, using verified local objects for demo."""


import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from .v3_agent_results import AgentBusinessResponse, agent_result
from .v3_auth import resident_connection
from .v3_resident import _owned_chat
from .v3_files import local_only, FILE_ROOT, EXT, MAGIC, MAX_FILE_BYTES
from .v3_security import digest
from .v3_mutations import visible_ticket, record_event

router = APIRouter(tags=["V3 conversation images"])
Scope = Annotated[tuple[AsyncConnection, str], Depends(resident_connection)]
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"


class ImageInitiate(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: Literal["image/jpeg", "image/png", "image/webp"]
    size_bytes: int = Field(gt=0, le=MAX_FILE_BYTES)
    sha256: str = Field(pattern="^[a-f0-9]{64}$")
    idempotency_key: str = Field(min_length=1, max_length=160)


def session_result(row):
    return {
        "uploadId": row["id"],
        "fileId": row["file_id"],
        "channelId": row["channel_id"],
        "status": row["status"],
        "uploadUrl": f"/image-uploads/{row['id']}/content",
        "method": "PUT",
        "storage": "local-demo",
    }


@router.post(
    "/resident/chats/{channel_id}/image-uploads",
    status_code=201,
    response_model=AgentBusinessResponse,
)
async def initiate(
    channel_id: str, body: ImageInitiate, request: Request, scope: Scope
):
    local_only(request)
    await _owned_chat(scope, channel_id, lock=True)
    if (
        Path(body.filename).name != body.filename
        or any(c in body.filename for c in ["\\", "/"])
        or any(ord(c) < 32 for c in body.filename)
    ):
        raise HTTPException(422, "Plain filename required")
    fp = digest(body.model_dump(exclude={"idempotency_key"}))
    prior = (
        (
            await scope[0].execute(
                text(
                    "select * from vh_conversation_uploads where channel_id=:channel and requested_by=:actor and idempotency_key=:key"
                ),
                {"channel": channel_id, "actor": scope[1], "key": body.idempotency_key},
            )
        )
        .mappings()
        .first()
    )
    if prior:
        if prior["request_hash"] != fp:
            raise HTTPException(409, "Upload key already used")
        return agent_result(
            "initiate_image_upload", session_result(prior), {"channel_id": channel_id}
        )
    storage = (
        (
            await scope[0].execute(
                text(
                    "select id,tenant_prefix from storage_locations where provider='local_fs' and purpose='evidence' and status='active' order by created_at limit 1"
                )
            )
        )
        .mappings()
        .first()
    )
    if storage is None:
        raise HTTPException(503, "Local storage is not configured")
    principal = await scope[0].execute(
        text(
            "select id from execution_principals where kind='user' and user_id=:actor and status='active'"
        ),
        {"actor": scope[1]},
    )
    pid = principal.scalar_one_or_none()
    if pid is None:
        pid = (
            await scope[0].execute(
                text(
                    f"insert into execution_principals(tenant_id,kind,user_id,status) values({TENANT},'user',:actor,'active') returning id"
                ),
                {"actor": scope[1]},
            )
        ).scalar_one()
    fid = uuid4()
    key = f"{storage['tenant_prefix']}{fid.hex}{EXT[body.mime_type]}"
    path = (FILE_ROOT / key).resolve()
    if not path.is_relative_to(FILE_ROOT.resolve()):
        raise HTTPException(503, "Invalid storage prefix")
    await scope[0].execute(
        text(
            f"insert into files(id,tenant_id,uploaded_by,original_name,owner_principal_id,scope_kind,channel_id,status,declared_mime_type) values(:id,{TENANT},:actor,:name,:principal,'channel',:channel,'staged',:mime)"
        ),
        {
            "id": fid,
            "actor": scope[1],
            "name": body.filename,
            "principal": pid,
            "channel": channel_id,
            "mime": body.mime_type,
        },
    )
    row = await scope[0].execute(
        text(
            f"insert into vh_conversation_uploads(tenant_id,file_id,channel_id,requested_by,location_id,object_key,expected_size,expected_sha256,mime_type,status,idempotency_key,request_hash) values({TENANT},:file,:channel,:actor,:location,:object,:size,:sha,:mime,'issued',:key,:hash) returning *"
        ),
        {
            "file": fid,
            "channel": channel_id,
            "actor": scope[1],
            "location": storage["id"],
            "object": key,
            "size": body.size_bytes,
            "sha": body.sha256,
            "mime": body.mime_type,
            "key": body.idempotency_key,
            "hash": fp,
        },
    )
    return agent_result(
        "initiate_image_upload",
        session_result(row.mappings().one()),
        {"channel_id": channel_id},
    )


async def upload_session(scope: Scope, upload_id: UUID):
    ref = (
        (
            await scope[0].execute(
                text(
                    "select channel_id from vh_conversation_uploads where id=:id and requested_by=:actor"
                ),
                {"id": upload_id, "actor": scope[1]},
            )
        )
        .mappings()
        .first()
    )
    if ref is None:
        raise HTTPException(404, "Upload not found")
    await _owned_chat(scope, ref["channel_id"], lock=True)
    return (
        (
            await scope[0].execute(
                text("select * from vh_conversation_uploads where id=:id for update"),
                {"id": upload_id},
            )
        )
        .mappings()
        .one()
    )


def object_path(row):
    path = (FILE_ROOT / row["object_key"]).resolve()
    if not path.is_relative_to(FILE_ROOT.resolve()):
        raise HTTPException(503, "Invalid object path")
    return path


@router.put("/image-uploads/{upload_id}/content", response_model=AgentBusinessResponse)
async def put_image(upload_id: UUID, request: Request, scope: Scope):
    local_only(request)
    row = await upload_session(scope, upload_id)
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > row["expected_size"]:
            raise HTTPException(413, "Image exceeds declared size")
    if (
        len(data) != row["expected_size"]
        or hashlib.sha256(data).hexdigest() != row["expected_sha256"]
    ):
        raise HTTPException(422, "Size or checksum mismatch")
    if not data.startswith(MAGIC[row["mime_type"]]) or (
        row["mime_type"] == "image/webp" and data[8:12] != b"WEBP"
    ):
        raise HTTPException(422, "Image signature mismatch")
    path = object_path(row)
    if row["status"] == "ready":
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != row["expected_sha256"]
        ):
            raise HTTPException(409, "Ready object is missing or corrupt")
        return agent_result(
            "upload_image", session_result(row), {"upload_id": upload_id}
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    # A stable object key makes retry after transaction failure recoverable.
    temporary = path.with_suffix(path.suffix + ".upload")
    temporary.write_bytes(data)
    temporary.replace(path)
    await scope[0].execute(
        text("update vh_conversation_uploads set status='uploaded' where id=:id"),
        {"id": upload_id},
    )
    return agent_result(
        "upload_image",
        {**session_result(row), "status": "uploaded"},
        {"upload_id": upload_id},
    )


@router.post(
    "/image-uploads/{upload_id}/complete", response_model=AgentBusinessResponse
)
async def complete(upload_id: UUID, request: Request, scope: Scope):
    local_only(request)
    row = await upload_session(scope, upload_id)
    path = object_path(row)
    if (
        not path.is_file()
        or path.stat().st_size != row["expected_size"]
        or hashlib.sha256(path.read_bytes()).hexdigest() != row["expected_sha256"]
    ):
        raise HTTPException(
            409, "Uploaded object is missing or does not match expected checksum"
        )
    if row["status"] == "ready":
        return agent_result(
            "complete_image_upload", session_result(row), {"upload_id": upload_id}
        )
    if row["status"] != "uploaded":
        raise HTTPException(409, "Upload content first")
    oid = uuid4()
    await scope[0].execute(
        text(f"""insert into file_objects(id,tenant_id,file_id,location_id,object_key,version_id,variant,mime_type,size_bytes,sha256,scan_status,verified_at,encryption_mode,status)
       values(:id,{TENANT},:file,:location,:object,:version,'original',:mime,:size,:sha,'clean',now(),'none','ready')"""),
        {
            "id": oid,
            "file": row["file_id"],
            "location": row["location_id"],
            "object": row["object_key"],
            "version": str(uuid4()),
            "mime": row["mime_type"],
            "size": row["expected_size"],
            "sha": row["expected_sha256"],
        },
    )
    await scope[0].execute(
        text(
            "update files set status='ready',accepted_object_id=:object,updated_at=now() where id=:id"
        ),
        {"object": oid, "id": row["file_id"]},
    )
    await scope[0].execute(
        text("update vh_conversation_uploads set status='ready' where id=:id"),
        {"id": upload_id},
    )
    return agent_result(
        "complete_image_upload",
        {**session_result(row), "status": "ready"},
        {"upload_id": upload_id},
    )


@router.get("/resident/chats/{channel_id}/images", response_model=AgentBusinessResponse)
async def images(channel_id: str, scope: Scope):
    await _owned_chat(scope, channel_id)
    rows = await scope[0].execute(
        text("""select f.id,f.original_name,f.status,f.created_at,m.id as message_id,m.seq from files f
      join messages m on m.channel_id=f.channel_id and m.tenant_id=f.tenant_id and m.body->'fileIds' ? f.id::text
      where f.channel_id=:channel and f.status='ready' order by m.seq,f.created_at"""),
        {"channel": channel_id},
    )
    return agent_result(
        "get_conversation_images",
        {"items": [dict(r) for r in rows.mappings()]},
        {"channel_id": channel_id},
    )


class AttachImages(BaseModel):
    file_ids: list[UUID] = Field(min_length=1, max_length=20)


@router.post(
    "/tickets/{ticket_id}/conversation-images", response_model=AgentBusinessResponse
)
async def attach(ticket_id: UUID, body: AttachImages, scope: Scope):
    db, actor = scope
    ticket = (
        (
            await db.execute(
                text("select * from tickets where id=:id for update"), {"id": ticket_id}
            )
        )
        .mappings()
        .first()
    )
    if ticket is None:
        raise HTTPException(404, "Ticket not found")
    if ticket["requester_user_id"] != actor:
        admin = (
            await db.execute(
                text(
                    "select exists(select 1 from platform_admins where user_id=:actor)"
                ),
                {"actor": actor},
            )
        ).scalar_one()
        await visible_ticket((db, actor, admin), ticket_id)
    attached = []
    for fid in dict.fromkeys(body.file_ids):
        valid = await db.execute(
            text(
                "select 1 from files f where f.id=:id and f.channel_id=:channel and f.uploaded_by=:requester and f.status='ready' and exists(select 1 from messages m where m.channel_id=f.channel_id and m.tenant_id=f.tenant_id and m.body->'fileIds' ? f.id::text)"
            ),
            {
                "id": fid,
                "channel": ticket["channel_id"],
                "requester": ticket["requester_user_id"],
            },
        )
        if valid.first() is None:
            raise HTTPException(
                422, "Ready image from the source conversation required"
            )
        row = await db.execute(
            text(
                f"insert into ticket_files(tenant_id,ticket_id,file_id,purpose,uploaded_by) values({TENANT},:ticket,:file,'issue',:actor) on conflict do nothing returning file_id"
            ),
            {"ticket": ticket_id, "file": fid, "actor": actor},
        )
        if row.first():
            attached.append(str(fid))
    if attached:
        await record_event(
            (db, actor, False),
            dict(ticket),
            "ticket.conversation_images_attached",
            json.dumps({"fileIds": attached}),
        )
    return agent_result(
        "attach_images_to_ticket",
        {
            "ticketId": ticket_id,
            "fileIds": [str(f) for f in body.file_ids],
            "added": len(attached),
        },
        {"ticket_id": ticket_id},
    )


@router.get("/conversation-images/{file_id}/content")
async def read_image(file_id: UUID, request: Request, scope: Scope):
    local_only(request)
    token = request.query_params.get("access")
    if token:
        try:
            expires, signature = token.split(".", 1)
            expires = int(expires)
        except (ValueError, TypeError):
            raise HTTPException(403, "Invalid image access link")
        tenant = (
            await scope[0].execute(text("select current_setting('app.tenant_id')"))
        ).scalar_one()
        message = f"{tenant}:{scope[1]}:{file_id}:{expires}".encode()
        expected = hmac.new(
            request.app.state.image_access_key, message, hashlib.sha256
        ).hexdigest()
        if expires <= int(time.time()) or not hmac.compare_digest(signature, expected):
            raise HTTPException(403, "Image access link expired or invalid")
    row = (
        (
            await scope[0].execute(
                text(
                    "select f.original_name,f.channel_id,u.* from files f join vh_conversation_uploads u on u.file_id=f.id and u.tenant_id=f.tenant_id where f.id=:id and f.status='ready'"
                ),
                {"id": file_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Image not found")
    if row["requested_by"] != scope[1]:
        tickets = (
            (
                await scope[0].execute(
                    text("select ticket_id from ticket_files where file_id=:id"),
                    {"id": file_id},
                )
            )
            .scalars()
            .all()
        )
        permitted = False
        admin = (
            await scope[0].execute(
                text(
                    "select exists(select 1 from platform_admins where user_id=:actor)"
                ),
                {"actor": scope[1]},
            )
        ).scalar_one()
        for tid in tickets:
            try:
                await visible_ticket((scope[0], scope[1], admin), tid)
                permitted = True
                break
            except HTTPException as exc:
                if exc.status_code != 404:
                    raise
        if not permitted:
            raise HTTPException(404, "Image not found")
    else:
        await _owned_chat(scope, row["channel_id"])
    path = object_path(row)
    if not path.is_file():
        raise HTTPException(404, "Image object is missing")
    return FileResponse(
        path, media_type=row["mime_type"], filename=row["original_name"]
    )


@router.get(
    "/conversation-images/{file_id}/read-access", response_model=AgentBusinessResponse
)
async def read_access(file_id: UUID, request: Request, scope: Scope):
    await read_image(file_id, request, scope)
    expires = int(time.time()) + 300
    tenant = (
        await scope[0].execute(text("select current_setting('app.tenant_id')"))
    ).scalar_one()
    message = f"{tenant}:{scope[1]}:{file_id}:{expires}".encode()
    signature = hmac.new(
        request.app.state.image_access_key, message, hashlib.sha256
    ).hexdigest()
    return agent_result(
        "get_image_read_access",
        {
            "fileId": file_id,
            "readUrl": f"/conversation-images/{file_id}/content?access={expires}.{signature}",
            "expiresAtEpoch": expires,
            "authenticationRequired": True,
            "boundToRequester": True,
        },
        {"file_id": file_id},
    )
