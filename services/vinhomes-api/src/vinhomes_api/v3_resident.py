"""Resident chat, ticket tracking, and in-app notification endpoints."""


import json
import hashlib
from typing import Annotated
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_auth import resident_connection
from .v3_mutations import UNRESOLVED_QC, record_event, requires_plan

router = APIRouter(tags=["Vinhomes V3 resident"])
ResidentScope = Annotated[tuple[AsyncConnection, str], Depends(resident_connection, scope="function")]


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
    file_ids: list[UUID] = Field(default_factory=list, max_length=20)

    @field_validator("text", "client_message_id")
    @classmethod
    def nonempty_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class ResidentApprovalDecision(BaseModel):
    version: int = Field(ge=0)
    approved: bool
    note: str = Field(min_length=1, max_length=2000)


class ResidentTicketCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    domain_id: UUID
    building_id: UUID
    unit_id: UUID
    category_id: UUID
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=10000)
    contact_name: str = Field(min_length=1, max_length=200)
    contact_phone: str = Field(min_length=1, max_length=30)
    request_kind: str = Field(pattern="^(incident|service_request)$")
    file_ids: list[UUID] = Field(default_factory=list, max_length=3)
    location: str | None = Field(default=None, min_length=3, max_length=500)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=160)


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
               t.id as ticket_id, t.code as ticket_code, t.status as ticket_status,
               (select count(*) from messages msg where msg.channel_id=c.id and msg.seq>m.last_read_seq
                 and msg.visibility in ('room','customer') and msg.sender_user_id is distinct from :actor_id) as unread_count
        from channels c
        join channel_memberships m on m.channel_id=c.id and m.tenant_id=c.tenant_id
        left join lateral (select t.id,t.code,t.status from tickets t where t.channel_id=c.id and t.tenant_id=c.tenant_id order by t.created_at desc,t.id limit 1) t on true
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
async def send_message(channel_id: str, body: SendMessage, request: Request, scope: ResidentScope) -> dict[str, object]:
    db, actor_id = scope
    await _owned_chat(scope, channel_id, lock=True)
    content = {"text": body.text}
    if body.file_ids:
        content['fileIds'] = [str(fid) for fid in dict.fromkeys(body.file_ids)]
        for fid in body.file_ids:
            image = await db.execute(text("select 1 from files where id=:id and channel_id=:channel and uploaded_by=:actor and status='ready'"), {'id':fid,'channel':channel_id,'actor':actor_id})
            if image.first() is None:
                raise HTTPException(422, 'Ready image from this conversation required')
    existing = await db.execute(text("""
        select id, seq, body, created_at from messages
        where channel_id=:channel_id and sender_user_id=:actor_id
          and client_message_id=:client_message_id
    """), {"channel_id": channel_id, "actor_id": actor_id,
           "client_message_id": body.client_message_id})
    previous = existing.mappings().first()
    if previous is not None:
        if previous["body"] != content:
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
           "actor_id": actor_id, "body": json.dumps(content),
           "client_message_id": body.client_message_id})
    created = dict(result.mappings().one())
    if request.app.state.settings.demo_mode:
        response_text = "Reception demo đã tiếp nhận. Hãy tạo ticket trong chat để chuyển BQL."
        seq = await db.execute(text("update channels set next_message_seq=next_message_seq+1,last_message=:preview,last_message_at=now() where id=:id returning next_message_seq-1"), {"id": channel_id, "preview": response_text})
        response_message = await db.execute(text("""
            insert into messages(tenant_id,channel_id,seq,sender_kind,sender_agent_id,visibility,body,reply_to_id)
            values(nullif(current_setting('app.tenant_id',true),'')::uuid,:channel_id,:seq,'agent','demo-reception','customer',cast(:body as jsonb),:reply)
            returning id
        """), {"channel_id": channel_id, "seq": seq.scalar_one(), "body": json.dumps({"text": response_text, "mode": "faker"}), "reply": created["id"]})
        message_id=response_message.scalar_one()
        await db.execute(text("""insert into notification_deliveries(tenant_id,user_id,message_id,channel,dedupe_key,payload,status,available_at)
          values(nullif(current_setting('app.tenant_id',true),'')::uuid,:actor,:message,'in_app',:key,cast(:payload as jsonb),'pending',now())
          on conflict(tenant_id,user_id,channel,dedupe_key) do nothing"""),{'actor':actor_id,'message':message_id,'key':f'reception:{message_id}','payload':json.dumps({'type':'reception.message','channelId':channel_id,'message':'Reception demo đã phản hồi'})})
    return created


@router.post("/resident/chats/{channel_id}/tickets", status_code=201,
             summary="Create a ticket for my verified unit in this chat")
async def create_chat_ticket(channel_id: str, body: ResidentTicketCreate, request: Request,
                             scope: ResidentScope) -> dict[str, object]:
    # The resident app sends an Idempotency-Key header and gets the stored receipt back;
    # agent callers use body.idempotency_key and get the AgentBusinessResponse snapshot.
    return await create_resident_ticket(channel_id, body, scope,
                                        receipt_key=request.headers.get("Idempotency-Key"))


async def create_resident_ticket(channel_id: str, body: ResidentTicketCreate,
                                 scope: ResidentScope, *, acting_user_id: str | None = None,
                                 assessment: dict[str, object] | None = None,
                                 receipt_key: str | None = None) -> dict[str, object]:
    """Shared intake service; staff callers must authorize the Case before calling.

    Residence/chat ownership belong to the requester. Audit belongs to the actual
    actor performing intake, including management materializing a resident Case.
    """
    db, actor_id = scope
    await _owned_chat(scope, channel_id, lock=True)
    from .v3_security import digest
    if receipt_key is not None:
        if not 8 <= len(receipt_key) <= 120:
            raise HTTPException(422, "Idempotency-Key must contain 8 to 120 characters")
        if body.location is None:
            raise HTTPException(422, "location is required")
        fingerprint = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
        receipt = await db.execute(text("""
            select e.payload from ticket_events e join tickets t on t.id=e.ticket_id and t.tenant_id=e.tenant_id
            where t.channel_id=:channel_id and t.requester_user_id=:actor_id
              and e.idempotency_key=:key and e.actor_user_id=:actor_id
        """), {"channel_id": channel_id, "actor_id": actor_id, "key": receipt_key})
        previous = receipt.scalar_one_or_none()
        if previous is not None:
            if previous.get("requestHash") != fingerprint:
                raise HTTPException(409, "Idempotency-Key already used with different content")
            return previous["receipt"]
        exists = await db.execute(text("""
            select 1 from tickets where channel_id=:channel_id
              and tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        """), {"channel_id": channel_id})
        if exists.first() is not None:
            raise HTTPException(409, "This chat already has a ticket")
        ticket_id = uuid4()
    if assessment is not None:
        priority = assessment.get("priority")
        severity = assessment.get("severity")
        is_emergency = assessment.get("is_emergency")
        reason = assessment.get("reason")
        if priority not in {"low", "normal", "high", "critical"}:
            raise HTTPException(422, "Invalid assessed priority")
        if severity not in {"unknown", "minor", "moderate", "major", "critical", "not_applicable"}:
            raise HTTPException(422, "Invalid assessed severity")
        if not isinstance(is_emergency, bool) or (is_emergency and priority != "critical"):
            raise HTTPException(422, "Emergency assessment requires critical priority")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
            raise HTTPException(422, "Assessment reason is required")
    if receipt_key is None:
        fingerprint = (
            digest(body.model_dump(exclude={"idempotency_key"}))
            if assessment is None
            else digest({"ticket": body.model_dump(exclude={"idempotency_key"}), "assessment": assessment})
        )
        tenant = (await db.execute(text("select current_setting('app.tenant_id')"))).scalar_one()
        ticket_id = uuid5(NAMESPACE_URL, f'ticket:{tenant}:{channel_id}:{actor_id}:{body.idempotency_key}') if body.idempotency_key else uuid4()
        old = (await db.execute(text('select id,code,channel_id,status,version from tickets where id=:id and requester_user_id=:actor'), {'id':ticket_id,'actor':actor_id})).mappings().first()
        if old:
            stored = (await db.execute(text("select payload->>'requestHash' from ticket_events where ticket_id=:id and event_type='ticket.created' order by seq limit 1"), {'id':ticket_id})).scalar_one_or_none()
            if stored != fingerprint:
                raise HTTPException(409, 'Ticket key already used with different content')
            from .v3_ticket_result import resident_ticket_result
            return await resident_ticket_result(db, actor_id, ticket_id, replayed=True)
    location = await db.execute(text("""
        select u.id, u.code as unit_code, b.id as building_id,
               b.name as building_name, b.site_id, b.zone_id
        from unit_residents ur
        join units u on u.id=ur.unit_id and u.tenant_id=ur.tenant_id
        join buildings b on b.id=u.building_id and b.tenant_id=u.tenant_id
        join sites si on si.id=b.site_id and si.tenant_id=b.tenant_id
        join domains d on d.id=si.domain_id and d.tenant_id=si.tenant_id
        where ur.user_id=:actor_id and ur.unit_id=:unit_id
          and ur.verification_status='verified'
          and ur.valid_from<=now() and (ur.valid_to is null or ur.valid_to>now())
          and b.id=:building_id and d.id=:domain_id
          and u.status='active' and b.status='active'
          and si.status='active' and d.status='active'
          and ur.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        limit 1
    """), {"actor_id": actor_id, "unit_id": body.unit_id,
           "building_id": body.building_id, "domain_id": body.domain_id})
    place = location.mappings().first()
    if place is None:
        raise HTTPException(403, "Verified residence in this building required")
    coverage = await db.execute(text("""
        select mc.management_unit_id, mc.id as coverage_id, mc.priority,
               case s.kind when 'building' then 4 when 'zone' then 3
                   when 'site' then 2 else 1 end as specificity
        from management_coverage mc
        join access_scopes s on s.id=mc.scope_id and s.tenant_id=mc.tenant_id
        join management_units mu on mu.id=mc.management_unit_id and mu.tenant_id=mc.tenant_id
        join service_categories cat on cat.id=mc.service_category_id and cat.tenant_id=mc.tenant_id
        where mc.service_category_id=:category_id and cat.enabled and mu.status='active'
          and mc.valid_from<=now() and (mc.valid_to is null or mc.valid_to>now())
          and mc.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
          and (s.kind='tenant'
            or (s.kind='site' and s.site_id=:site_id)
            or (s.kind='zone' and s.zone_id=cast(:zone_id as uuid))
            or (s.kind='building' and s.building_id=:building_id))
        order by specificity desc, mc.priority desc, mc.id
        limit 2
    """), {"category_id": body.category_id, "site_id": place["site_id"],
           "zone_id": place["zone_id"], "building_id": body.building_id})
    choices = coverage.mappings().all()
    if not choices:
        raise HTTPException(404, "No management coverage for this category")
    selected = choices[0]
    if (len(choices) > 1 and choices[1]["specificity"] == selected["specificity"]
            and choices[1]["priority"] == selected["priority"]
            and choices[1]["management_unit_id"] != selected["management_unit_id"]):
        raise HTTPException(409, "Ambiguous management coverage")
    assessment_columns = ", priority, severity, is_emergency" if assessment is not None else ", priority"
    assessment_values = ", :priority, :severity, :is_emergency" if assessment is not None else ", 'normal'"
    ticket = await db.execute(text(f"""
        insert into tickets
           (id, tenant_id, code, requester_user_id, channel_id, unit_id,
           domain_id, site_id, zone_id, building_id, management_unit_id,
           coverage_id, category_id, title, description, status,
           contact_name, contact_phone, address_snapshot, request_kind{assessment_columns})
        values (:id, nullif(current_setting('app.tenant_id', true), '')::uuid,
                :code, :actor_id, :channel_id, :unit_id, :domain_id,
                :site_id, :zone_id, :building_id, :management_unit_id,
                :coverage_id, :category_id, :title, :description,
                'open', :contact_name, :contact_phone,
                cast(:address as jsonb), :request_kind{assessment_values})
        returning id, code, channel_id, status, version
    """), {"id": ticket_id, "code": f"VH-{ticket_id.hex[:12].upper()}",
           "actor_id": actor_id, "channel_id": channel_id, "unit_id": body.unit_id,
           "domain_id": body.domain_id, "site_id": place["site_id"],
           "zone_id": place["zone_id"], "building_id": body.building_id,
           "management_unit_id": selected["management_unit_id"],
           "coverage_id": selected["coverage_id"], "category_id": body.category_id,
           "title": body.title, "description": body.description,
           "contact_name": body.contact_name, "contact_phone": body.contact_phone,
           "address": json.dumps({"building": place["building_name"],
                                  "unit": place["unit_code"],
                                  **({"location": body.location} if body.location is not None else {})}),
           "request_kind": body.request_kind,
           **({"priority": assessment["priority"], "severity": assessment["severity"],
               "is_emergency": assessment["is_emergency"]} if assessment is not None else {})})
    created = dict(ticket.mappings().one())
    event_payload = ({"receipt": {**created, "version": 1}} if receipt_key is not None
                     else {"requiresPlan": True, **({"assessment": assessment} if assessment is not None else {})})
    event_id = await record_event((db, acting_user_id or actor_id, False),
                                  {**created, "last_event_seq": 0}, "ticket.created",
                                  json.dumps({"source": "resident_chat", "requestHash": fingerprint, **event_payload}, default=str),
                                  to_status="open", idempotency_key=receipt_key)
    await db.execute(text("""
        insert into ticket_routing_history
          (tenant_id, ticket_id, to_management_id, status, reason, requested_at)
        values (nullif(current_setting('app.tenant_id', true), '')::uuid,
                :ticket_id, :management_unit_id, 'requested',
                'initial_reception_handoff', now())
    """), {"ticket_id": ticket_id,
           "management_unit_id": selected["management_unit_id"]})
    await db.execute(text("""
        insert into notification_deliveries
          (tenant_id, user_id, ticket_event_id, channel, dedupe_key,
           payload, status, available_at)
        select r.tenant_id, m.user_id, :event_id, 'in_app', :dedupe_key,
               cast(:payload as jsonb), 'pending', now()
        from scoped_user_roles r
        join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
        join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
        join users u on u.id=m.user_id and u.status='active'
        where r.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
          and r.role_code='management' and m.status='active'
          and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
          and (s.kind='tenant'
            or (s.kind='management' and s.management_unit_id=:management_unit_id)
            or (s.kind='site' and s.site_id=:site_id)
            or (s.kind='zone' and s.zone_id=cast(:zone_id as uuid))
            or (s.kind='building' and s.building_id=:building_id))
        on conflict (tenant_id, user_id, channel, dedupe_key) do nothing
    """), {"event_id": event_id, "dedupe_key": f"ticket:{ticket_id}:created",
           "payload": json.dumps({"type": "ticket.created", "ticketId": str(ticket_id)}),
           "management_unit_id": selected["management_unit_id"],
           "site_id": place["site_id"], "zone_id": place["zone_id"],
           "building_id": body.building_id})
    if len(set(body.file_ids)) != len(body.file_ids):
        raise HTTPException(422, "Duplicate file IDs")
    for file_id in body.file_ids:
        linked = await db.execute(text("""
            update files set retention_until=null
            where id=:file_id and channel_id=:channel_id and uploaded_by=:actor_id and status='ready'
            returning id
        """), {"file_id": file_id, "ticket_id": ticket_id, "channel_id": channel_id, "actor_id": actor_id})
        if linked.first() is None:
            raise HTTPException(422, "File must be ready and belong to this chat")
        await db.execute(text("""
            insert into ticket_files(tenant_id,ticket_id,file_id,purpose,uploaded_by)
            values(nullif(current_setting('app.tenant_id',true),'')::uuid,:ticket,:file,'issue',:actor)
        """), {"ticket": ticket_id, "file": file_id, "actor": actor_id})
    if receipt_key is not None:
        created["version"] = 1
        return created
    from .v3_ticket_result import resident_ticket_result
    return await resident_ticket_result(db, actor_id, ticket_id, replayed=False)


@router.get("/resident/tickets", summary="List my tickets")
async def list_my_tickets(scope: ResidentScope, limit: int = Query(50, ge=1, le=100),
                          offset: int = Query(0, ge=0, le=100000)) -> dict[str, object]:
    db, actor_id = scope
    result = await db.execute(text("""
        select id, code, channel_id, title, description, address_snapshot, version, status, priority, created_at, updated_at
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
        select id, code, channel_id, title, description, status, priority, severity, version, address_snapshot,
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
          and event_type in ('ticket.created', 'ticket.routing_accepted',
                             'ticket.status_changed',
                             'work_order.status_changed', 'work_order.offered',
                             'work_assignment.responded', 'ticket.resolution_published', 'work_approval.decided')
        order by seq desc limit 100
    """), {"ticket_id": ticket_id})
    photos = await db.execute(text("""
        select f.id,f.original_name as name from files f join ticket_files tf on tf.file_id=f.id and tf.tenant_id=f.tenant_id
        where tf.ticket_id=:id and f.uploaded_by=:actor and f.status='ready' order by tf.created_at
    """), {"id": ticket_id, "actor": actor_id})
    return {"ticket": dict(ticket), "events": _rows(timeline), "photos": [dict(r) for r in photos.mappings()]}


@router.post("/resident/approvals/{approval_id}/decision",
             summary="Confirm or reject a repair assigned to me")
async def decide_resident_approval(approval_id: UUID, body: ResidentApprovalDecision, request: Request,
                                   scope: ResidentScope) -> dict[str, object]:
    db, actor_id = scope
    found = await db.execute(text("""
        select a.work_order_id, a.kind, w.ticket_id from work_approvals a
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
        select id, status, version, last_event_seq from tickets
        where id=:ticket_id and requester_user_id=:actor_id for update
    """), {"ticket_id": approval["ticket_id"], "actor_id": actor_id})
    ticket = dict(ticket_result.mappings().one())
    key = request.headers.get("Idempotency-Key", "")
    if not 8 <= len(key) <= 120:
        raise HTTPException(422, "Idempotency-Key must contain 8 to 120 characters")
    digest = hashlib.sha256((str(approval_id) + body.model_dump_json()).encode()).hexdigest()
    receipt = await db.execute(text("select payload from ticket_events where ticket_id=:id and idempotency_key=:key and actor_user_id=:actor"),
        {"id": ticket["id"], "key": key, "actor": actor_id})
    previous = receipt.scalar_one_or_none()
    if previous is not None:
        if previous.get("requestHash") != digest:
            raise HTTPException(409, "Idempotency-Key already used with different content")
        return previous["receipt"]
    if ticket["version"] != body.version:
        raise HTTPException(409, "Ticket version changed; reload before deciding")
    if not body.approved and len(body.note.strip()) < 8:
        raise HTTPException(422, "Please explain the requested rework in at least 8 characters")
    current = await db.execute(text("""
        select status, expires_at is null or expires_at>now() as unexpired
        from work_approvals
        where id=:approval_id for update
    """), {"approval_id": approval_id})
    row = current.mappings().one()
    if row["status"] != "pending" or not row["unexpired"]:
        raise HTTPException(409, "Approval is no longer pending")
    status = "approved" if body.approved else "rejected"
    target_status = None
    if approval["kind"] == "customer_repair" and not body.approved:
        await db.execute(text("update work_orders set status='arrived',version=version+1,updated_at=now() where id=:id and status='awaiting_approval'"), {"id": approval["work_order_id"]})
    if approval["kind"] == "customer_completion":
        planned = await requires_plan((db, actor_id, False), ticket["id"])
        if planned:
            work = (await db.execute(text('select status from work_orders where id=:id for update'), {'id':approval['work_order_id']})).scalar_one()
            if work != 'completed' or ticket['status'] in {'closed','cancelled'}:
                raise HTTPException(409, 'Completed work and active ticket required')
            unfinished = await db.execute(text(f"""select 1 from work_orders w where w.ticket_id=:ticket and w.required and w.status not in ('cancelled','rejected')
              and (w.status!='completed' or (w.id!=:work and not exists(select 1 from work_approvals a where a.work_order_id=w.id and a.tenant_id=w.tenant_id and a.kind='customer_completion' and a.status='approved'))
                or {UNRESOLVED_QC})
              limit 1"""), {'ticket':ticket['id'],'work':approval['work_order_id']})
            if body.approved:
                target_status = 'closed' if unfinished.first() is None else ticket['status']
            else:
                target_status = 'in_progress'
        else:
            if ticket["status"] != "resolved":
                raise HTTPException(409, "Ticket must be resolved before completion confirmation")
            eligible = await db.execute(text("""
                select w.id from work_orders w where w.ticket_id=:id
                  and w.status not in ('cancelled','rejected')
                  and not exists (select 1 from vh_qc_redo_orders r where r.source_work_order_id=w.id)
                  and (w.status<>'completed' or coalesce((select outcome from vh_qc_results q
                    where q.work_order_id=w.id order by checked_at desc,id desc limit 1),'missing')<>'pass')
            """), {"id": ticket["id"]})
            if eligible.first() is not None:
                raise HTTPException(409, "All work orders must pass QC before confirmation")
            target_status = "closed" if body.approved else "in_progress"
        await db.execute(text("""
            update tickets set status=:status, closed_at=case when :status='closed' then now() else null end,
              resolved_at=case when :status='closed' then resolved_at else null end where id=:id
        """), {"id": ticket["id"], "status": target_status})
        if not body.approved and not planned:
            # Re-open intake, preserving all work orders, evidence and QC history.
            await db.execute(text("update tickets set status='triaging',reopen_count=reopen_count+1 where id=:id"), {"id": ticket["id"]})
            target_status = "triaging"
    updated = await db.execute(text("""
        update work_approvals set status=:status, decided_by=:actor_id,
            decided_at=now(), decision_note=:note, updated_at=now()
        where id=:approval_id
        returning id, kind, status, decided_at
    """), {"status": status, "actor_id": actor_id, "note": body.note,
           "approval_id": approval_id})
    decision = jsonable_encoder(dict(updated.mappings().one()))
    event_id = await record_event((db, actor_id, False), ticket, "work_approval.decided",
                                  json.dumps({"approvalId": str(approval_id), "status": status, "requestHash": digest, "receipt": decision}, default=str), to_status=target_status, idempotency_key=key)
    await db.execute(text("""
        update work_approvals set decided_event_id=:event_id where id=:approval_id
    """), {"event_id": event_id, "approval_id": approval_id})
    return decision


@router.get("/resident/approvals", summary="List repair approvals assigned to me")
async def my_approvals(scope: ResidentScope,
                       limit: int = Query(50, ge=1, le=100)) -> dict[str, object]:
    db, actor_id = scope
    result = await db.execute(text("""
        select a.id, a.work_order_id, a.kind, a.status, a.request_detail, a.expires_at,
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
