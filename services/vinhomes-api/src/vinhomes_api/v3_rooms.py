"""Management room messages and mention requests; agent execution is separate."""

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_auth import resident_connection


router = APIRouter(tags=["Vinhomes V3 rooms"])
MemberScope = Annotated[tuple[AsyncConnection, str], Depends(resident_connection, scope="function")]


async def _room(scope: MemberScope, room_id: str, *, lock: bool = False) -> None:
    db, actor_id = scope
    result = await db.execute(text("""
        select c.id from channels c
        left join channel_memberships m on m.channel_id=c.id and m.tenant_id=c.tenant_id and m.user_id=:actor_id
        where c.id=:room_id and c.kind='management' and c.deleted_at is null
          and (m.user_id=:actor_id or exists(select 1 from platform_admins where user_id=:actor_id))
          and c.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
    """ + (" for update of c" if lock else "")), {"room_id": room_id, "actor_id": actor_id})
    if result.first() is None:
        raise HTTPException(404, "Room not found")


class RoomMessage(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    client_message_id: str = Field(min_length=1, max_length=120)
    mention_agent_id: str | None = Field(default=None, max_length=160)

    @field_validator("text", "client_message_id")
    @classmethod
    def nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


@router.get("/rooms", summary="List my management rooms")
async def list_rooms(scope: MemberScope, limit: int = Query(50, ge=1, le=100)) -> dict[str, object]:
    db, actor_id = scope
    result = await db.execute(text("""
        select c.id, c.name, c.description, c.workspace_id,
               c.last_message_at, m.last_read_seq
        from channels c
        left join channel_memberships m on m.channel_id=c.id and m.tenant_id=c.tenant_id and m.user_id=:actor_id
        where (m.user_id=:actor_id or exists(select 1 from platform_admins where user_id=:actor_id)) and c.kind='management' and c.deleted_at is null
          and c.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        order by coalesce(c.last_message_at, c.created_at) desc limit :limit
    """), {"actor_id": actor_id, "limit": limit})
    return {"items": [dict(row) for row in result.mappings()]}


@router.get("/rooms/{room_id}/messages", summary="Read messages in my management room")
async def room_messages(room_id: str, scope: MemberScope,
                        after_seq: int = Query(0, ge=0, alias="afterSeq"),
                        limit: int = Query(50, ge=1, le=100)) -> dict[str, object]:
    await _room(scope, room_id)
    result = await scope[0].execute(text("""
        select id, seq, sender_kind, sender_user_id, sender_agent_id, body, created_at,
               (select name from users where users.id=messages.sender_user_id) as sender_name,
               (select mm.status from message_mentions mm where mm.message_id=messages.id
                 and mm.tenant_id=messages.tenant_id order by mm.created_at limit 1) as mention_status
        from messages where channel_id=:room_id and visibility='room'
          and seq>:after_seq
          and tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        order by seq limit :limit
    """), {"room_id": room_id, "after_seq": after_seq, "limit": limit})
    return {"items": [dict(row) for row in result.mappings()]}


@router.get("/rooms/{room_id}/agents", summary="Agents configured in my management room")
async def room_agents(room_id: str, scope: MemberScope) -> dict[str, object]:
    await _room(scope, room_id)
    result = await scope[0].execute(text("""
        select a.id,a.name,a.status,a.purpose,
          exists(select 1 from agent_releases rel join agent_versions v on v.id=rel.version_id and v.tenant_id=rel.tenant_id
            where rel.agent_id=a.id and rel.status='published' and rel.revoked_at is null
              and v.version_no=(select max(v2.version_no) from agent_versions v2 where v2.agent_id=a.id)) as published
        from channel_agents ca join agents a
          on a.id=ca.agent_id and a.tenant_id=ca.tenant_id
        where ca.channel_id=:id
          and ca.tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
        order by a.name,a.id
    """), {"id": room_id})
    return {"items": [dict(row) for row in result.mappings()]}


@router.get("/rooms/{room_id}/mentions/{message_id}",
            summary="Read the status of an agent mention in my room")
async def mention_status(room_id: str, message_id: UUID,
                         scope: MemberScope) -> dict[str, object]:
    await _room(scope, room_id)
    result = await scope[0].execute(text("""
        select mm.agent_id, mm.status, mm.resolved_run_id, mm.created_at
        from message_mentions mm
        join messages msg on msg.id=mm.message_id and msg.tenant_id=mm.tenant_id
        where mm.message_id=:message_id and msg.channel_id=:room_id
          and mm.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
    """), {"message_id": message_id, "room_id": room_id})
    items = [dict(row) for row in result.mappings()]
    if not items:
        raise HTTPException(404, "Mention not found")
    return {"items": items}


@router.post("/rooms/{room_id}/messages", status_code=201,
             summary="Post to my room, optionally requesting an agent mention")
async def post_room_message(room_id: str, body: RoomMessage,
                            request: Request, scope: MemberScope) -> dict[str, object]:
    db, actor_id = scope
    await _room(scope, room_id, lock=True)
    previous = await db.execute(text("""
        select id, seq, body, created_at from messages
        where channel_id=:room_id and sender_user_id=:actor_id
          and client_message_id=:client_message_id
    """), {"room_id": room_id, "actor_id": actor_id,
           "client_message_id": body.client_message_id})
    row = previous.mappings().first()
    content = {"text": body.text, "mentionAgentId": body.mention_agent_id}
    if row is not None:
        if row["body"] != content:
            raise HTTPException(409, "clientMessageId already used with different content")
        return dict(row)
    if body.mention_agent_id:
        allowed = await db.execute(text("""
            select 1 from channel_agents ca join agents a on a.id=ca.agent_id
            where ca.channel_id=:room_id and ca.agent_id=:agent_id
              and ca.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
              and a.tenant_id=ca.tenant_id and a.status='active' limit 1
        """), {"room_id": room_id, "agent_id": body.mention_agent_id})
        if allowed.first() is None:
            raise HTTPException(422, "Mentioned agent is not in this room")
    sequence = await db.execute(text("""
        update channels set next_message_seq=next_message_seq+1,
            last_message=:preview, last_message_at=now(), updated_at=now()
        where id=:room_id returning next_message_seq-1
    """), {"room_id": room_id, "preview": body.text[:200]})
    message = await db.execute(text("""
        insert into messages (tenant_id, channel_id, seq, sender_kind, sender_user_id,
                              visibility, body, client_message_id)
        values (nullif(current_setting('app.tenant_id', true), '')::uuid,
                :room_id, :seq, 'user', :actor_id, 'room', cast(:content as jsonb),
                :client_message_id)
        returning id, seq, body, created_at
    """), {"room_id": room_id, "seq": sequence.scalar_one(), "actor_id": actor_id,
           "content": json.dumps(content), "client_message_id": body.client_message_id})
    created = dict(message.mappings().one())
    if body.mention_agent_id:
        await db.execute(text("""
            insert into message_mentions (tenant_id, message_id, agent_id, requested_by, status)
            values (nullif(current_setting('app.tenant_id', true), '')::uuid,
                    :message_id, :agent_id, :actor_id, 'queued')
        """), {"message_id": created["id"], "agent_id": body.mention_agent_id,
               "actor_id": actor_id})
        if request.app.state.settings.demo_mode and not request.app.state.settings.coordination_service_token:
            seq = await db.execute(text("update channels set next_message_seq=next_message_seq+1 where id=:id returning next_message_seq-1"), {"id": room_id})
            await db.execute(text("""
                insert into messages(tenant_id,channel_id,seq,sender_kind,sender_agent_id,visibility,body,reply_to_id)
                values(nullif(current_setting('app.tenant_id',true),'')::uuid,:room_id,:seq,'agent',:agent,'room',cast(:body as jsonb),:reply)
            """), {"room_id": room_id, "seq": seq.scalar_one(), "agent": body.mention_agent_id,
                   "body": json.dumps({"text": "Agent demo đã nhận context room. Dùng API báo cáo để lấy dữ liệu trong database.", "mode": "faker"}), "reply": created["id"]})
            await db.execute(text("update message_mentions set status='done' where message_id=:id and agent_id=:agent"), {"id": created["id"], "agent": body.mention_agent_id})
    return created
