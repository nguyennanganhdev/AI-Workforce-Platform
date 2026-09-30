"""Resident chat, ticket tracking, and in-app notification endpoints."""

import json
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_auth import resident_connection
from .v3_mutations import record_event


router = APIRouter(tags=["Vinhomes V3 resident"])
ResidentScope = Annotated[tuple[AsyncConnection, str], Depends(resident_connection)]


def _rows(result: object) -> list[dict[str, object]]:
    return [dict(row) for row in result.mappings().all()]


async def _owned_chat(scope: ResidentScope, channel_id: str, *, lock: bool = False) -> dict[str, object]:
    db, actor_id = scope
    result = await db.execute(text("""
        select c.id, c.name, c.description, c.created_at, c.last_message_at
        from channels c
        join channel_memberships m on m.channel_id=c.id and m.tenant_id=c.tenant_id
        where c.id=:channel_id and c.kind='reception' and c.deleted_at is null
          and c.created_by=:actor_id and m.user_id=:actor_id
          and c.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
    """ + (" for update of c" if lock else "")), {"channel_id": channel_id, "actor_id": actor_id})
    row = result.mappings().first()
    if row is None:
        raise HTTPException(404, "Chat not found")
    return dict(row)


class CreateChat(BaseModel):
    title: str = Field(min_length=1, max_length=160)

    @field_validator("title")
    @classmethod
    def nonempty_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value


class SendMessage(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    client_message_id: str = Field(min_length=1, max_length=120)

    @field_validator("text", "client_message_id")
    @classmethod
    def nonempty_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class ResidentApprovalDecision(BaseModel):
    approved: bool
    note: str = Field(min_length=1, max_length=2000)


@router.post("/resident/chats", status_code=201, summary="Create a resident chat")
async def create_chat(body: CreateChat, scope: ResidentScope) -> dict[str, object]:
    db, actor_id = scope
    channel_id = str(uuid4())
    result = await db.execute(text("""
        insert into channels (id, name, description, tenant_id, kind, created_by)
        values (:id, :name, '', nullif(current_setting('app.tenant_id', true), '')::uuid,
                'reception', :actor_id)
        returning id, name, description, created_at
    """), {"id": channel_id, "name": body.title.strip(), "actor_id": actor_id})
    await db.execute(text("""
        insert into channel_memberships (channel_id, user_id, tenant_id)
        values (:id, :actor_id, nullif(current_setting('app.tenant_id', true), '')::uuid)
    """), {"id": channel_id, "actor_id": actor_id})
    return dict(result.mappings().one())


@router.get("/resident/chats", summary="List my resident chats")
async def list_chats(scope: ResidentScope, limit: int = Query(50, ge=1, le=100),
                     offset: int = Query(0, ge=0, le=100000)) -> dict[str, object]:
    db, actor_id = scope
    result = await db.execute(text("""
        select c.id, c.name, c.description, c.last_message_at, c.created_at,
               t.id as ticket_id, t.code as ticket_code, t.status as ticket_status
        from channels c
        join channel_memberships m on m.channel_id=c.id and m.tenant_id=c.tenant_id
        left join tickets t on t.channel_id=c.id and t.tenant_id=c.tenant_id
        where c.kind='reception' and c.deleted_at is null
          and c.created_by=:actor_id and m.user_id=:actor_id
          and c.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        order by coalesce(c.last_message_at, c.created_at) desc, c.id desc
        limit :limit offset :offset
    """), {"actor_id": actor_id, "limit": limit, "offset": offset})
    items = _rows(result)
    return {"items": items, "nextOffset": offset + len(items) if len(items) == limit else None}


@router.get("/resident/chats/{channel_id}/messages", summary="Read messages in my chat")
async def list_messages(channel_id: str, scope: ResidentScope,
                        after_seq: int = Query(0, ge=0, alias="afterSeq"),
                        limit: int = Query(50, ge=1, le=100)) -> dict[str, object]:
    await _owned_chat(scope, channel_id)
    result = await scope[0].execute(text("""
        select id, seq, sender_kind, sender_user_id, sender_agent_id, body, created_at
        from messages where channel_id=:channel_id and seq>:after_seq
          and visibility in ('room','customer')
          and tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        order by seq limit :limit
    """), {"channel_id": channel_id, "after_seq": after_seq, "limit": limit})
    return {"items": _rows(result)}


@router.post("/resident/chats/{channel_id}/messages", status_code=201,
             summary="Send a message in my chat")
async def send_message(channel_id: str, body: SendMessage, scope: ResidentScope) -> dict[str, object]:
    db, actor_id = scope
    await _owned_chat(scope, channel_id, lock=True)
    existing = await db.execute(text("""
        select id, seq, body, created_at from messages
        where channel_id=:channel_id and sender_user_id=:actor_id
          and client_message_id=:client_message_id
    """), {"channel_id": channel_id, "actor_id": actor_id,
           "client_message_id": body.client_message_id})
    previous = existing.mappings().first()
    if previous is not None:
        if previous["body"] != {"text": body.text}:
            raise HTTPException(409, "clientMessageId already used with different content")
        return dict(previous)
    sequence = await db.execute(text("""
        update channels set next_message_seq=next_message_seq+1,
            last_message=:preview, last_message_at=now(), updated_at=now()
        where id=:channel_id returning next_message_seq-1
    """), {"channel_id": channel_id, "preview": body.text[:200]})
    result = await db.execute(text("""
        insert into messages (tenant_id, channel_id, seq, sender_kind, sender_user_id,
                              visibility, body, client_message_id)
        values (nullif(current_setting('app.tenant_id', true), '')::uuid,
                :channel_id, :seq, 'user', :actor_id, 'customer', cast(:body as jsonb),
                :client_message_id)
        returning id, seq, body, created_at
    """), {"channel_id": channel_id, "seq": sequence.scalar_one(),
           "actor_id": actor_id, "body": json.dumps({"text": body.text}),
           "client_message_id": body.client_message_id})
    return dict(result.mappings().one())


@router.get("/resident/tickets", summary="List my tickets")
async def list_my_tickets(scope: ResidentScope, limit: int = Query(50, ge=1, le=100),
                          offset: int = Query(0, ge=0, le=100000)) -> dict[str, object]:
    db, actor_id = scope
    result = await db.execute(text("""
        select id, code, channel_id, title, status, priority, created_at, updated_at
        from tickets where requester_user_id=:actor_id
          and tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        order by created_at desc, id desc limit :limit offset :offset
    """), {"actor_id": actor_id, "limit": limit, "offset": offset})
    items = _rows(result)
    return {"items": items, "nextOffset": offset + len(items) if len(items) == limit else None}


@router.get("/resident/tickets/{ticket_id}", summary="Read my ticket and timeline")
async def get_my_ticket(ticket_id: UUID, scope: ResidentScope) -> dict[str, object]:
    db, actor_id = scope
    result = await db.execute(text("""
        select id, code, channel_id, title, description, status, priority, severity,
               response_due_at, resolution_due_at, created_at, updated_at
        from tickets where id=:ticket_id and requester_user_id=:actor_id
          and tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
    """), {"ticket_id": ticket_id, "actor_id": actor_id})
    ticket = result.mappings().first()
    if ticket is None:
        raise HTTPException(404, "Ticket not found")
    timeline = await db.execute(text("""
        select id, seq, event_type, from_status, to_status, occurred_at
        from ticket_events
        where ticket_id=:ticket_id and tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
          and event_type in ('ticket.created', 'ticket.status_changed',
                             'work_order.status_changed', 'work_order.offered',
                             'work_assignment.responded')
        order by seq desc limit 100
    """), {"ticket_id": ticket_id})
    return {"ticket": dict(ticket), "events": _rows(timeline)}


@router.post("/resident/approvals/{approval_id}/decision",
             summary="Confirm or reject a repair assigned to me")
async def decide_resident_approval(approval_id: UUID, body: ResidentApprovalDecision,
                                   scope: ResidentScope) -> dict[str, object]:
    db, actor_id = scope
    found = await db.execute(text("""
        select a.work_order_id, w.ticket_id from work_approvals a
        join work_orders w on w.id=a.work_order_id and w.tenant_id=a.tenant_id
        join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id
        where a.id=:approval_id and a.requested_to_user_id=:actor_id
          and a.kind in ('customer_repair','customer_completion')
          and t.requester_user_id=:actor_id
          and a.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
    """), {"approval_id": approval_id, "actor_id": actor_id})
    approval = found.mappings().first()
    if approval is None:
        raise HTTPException(404, "Approval not found")
    ticket_result = await db.execute(text("""
        select id, status, last_event_seq from tickets
        where id=:ticket_id and requester_user_id=:actor_id for update
    """), {"ticket_id": approval["ticket_id"], "actor_id": actor_id})
    ticket = dict(ticket_result.mappings().one())
    current = await db.execute(text("""
        select status, expires_at is null or expires_at>now() as unexpired
        from work_approvals
        where id=:approval_id for update
    """), {"approval_id": approval_id})
    row = current.mappings().one()
    if row["status"] != "pending" or not row["unexpired"]:
        raise HTTPException(409, "Approval is no longer pending")
    status = "approved" if body.approved else "rejected"
    updated = await db.execute(text("""
        update work_approvals set status=:status, decided_by=:actor_id,
            decided_at=now(), decision_note=:note, updated_at=now()
        where id=:approval_id
        returning id, kind, status, decided_at
    """), {"status": status, "actor_id": actor_id, "note": body.note,
           "approval_id": approval_id})
    event_id = await record_event((db, actor_id, False), ticket, "work_approval.decided",
                                  json.dumps({"approvalId": str(approval_id), "status": status}))
    await db.execute(text("""
        update work_approvals set decided_event_id=:event_id where id=:approval_id
    """), {"event_id": event_id, "approval_id": approval_id})
    return dict(updated.mappings().one())


@router.get("/resident/approvals", summary="List repair approvals assigned to me")
async def my_approvals(scope: ResidentScope,
                       limit: int = Query(50, ge=1, le=100)) -> dict[str, object]:
    db, actor_id = scope
    result = await db.execute(text("""
        select a.id, a.kind, a.status, a.request_detail, a.expires_at,
               a.created_at, w.ticket_id, t.code as ticket_code
        from work_approvals a
        join work_orders w on w.id=a.work_order_id and w.tenant_id=a.tenant_id
        join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id
        where a.requested_to_user_id=:actor_id and t.requester_user_id=:actor_id
          and a.kind in ('customer_repair','customer_completion')
          and a.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        order by a.created_at desc limit :limit
    """), {"actor_id": actor_id, "limit": limit})
    return {"items": _rows(result)}


@router.get("/my/notifications", summary="List my in-app notifications")
async def my_notifications(scope: ResidentScope, limit: int = Query(50, ge=1, le=100),
                           offset: int = Query(0, ge=0, le=100000)) -> dict[str, object]:
    db, actor_id = scope
    result = await db.execute(text("""
        select id, ticket_event_id, message_id, interruption_id, payload, status,
               sent_at, read_at, created_at
        from notification_deliveries where user_id=:actor_id and channel='in_app'
          and tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        order by created_at desc, id desc limit :limit offset :offset
    """), {"actor_id": actor_id, "limit": limit, "offset": offset})
    items = _rows(result)
    return {"items": items, "nextOffset": offset + len(items) if len(items) == limit else None}


@router.post("/my/notifications/{notification_id}/read", summary="Mark my notification read")
async def mark_notification_read(notification_id: UUID, scope: ResidentScope) -> dict[str, object]:
    db, actor_id = scope
    result = await db.execute(text("""
        update notification_deliveries set read_at=coalesce(read_at, now()), updated_at=now()
        where id=:id and user_id=:actor_id and channel='in_app'
          and tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        returning id, read_at
    """), {"id": notification_id, "actor_id": actor_id})
    row = result.mappings().first()
    if row is None:
        raise HTTPException(404, "Notification not found")
    return dict(row)
