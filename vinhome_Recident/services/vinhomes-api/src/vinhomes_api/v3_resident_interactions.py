"""Explicit resident responses to Supervisor requests, through the existing V2 boundary.

The browser supplies a decision or answer. Tenant, team, ticket version and the V2
identity are derived from the owned ticket and persisted request, never from the model.
"""
import json
from datetime import datetime, UTC
from uuid import UUID, NAMESPACE_URL, uuid5
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from typing import Literal
from .v3_reception_supervisor import RESIDENT, TENANT, WIRE_TICKET, ReceptionToSupervisorMessage, current_wire, submit_reception_message
from .v3_security import digest

router = APIRouter(tags=['Resident Supervisor interactions'])


@router.get('/resident/supervisor-interactions')
async def interactions(scope: RESIDENT):
    rows = await scope[0].execute(text(f'''select p.ticket_id,p.pending_kind,t.version as ticket_version,
        m.payload->>'message' as question,p.plan_id,p.plan_version,plan.title,plan.proposal
        from vh_reception_supervisor_pending p join tickets t on t.id=p.ticket_id and t.tenant_id=p.tenant_id
        join vh_reception_supervisor_messages m on m.message_id=p.supervisor_message_id and m.tenant_id=p.tenant_id
        left join vh_ticket_plans plan on plan.id=p.plan_id and plan.tenant_id=p.tenant_id
        where p.tenant_id={TENANT} and t.requester_user_id=:actor and p.ticket_generation=t.reopen_count
          and t.status not in ('closed','cancelled','resolved') order by p.created_at'''), {'actor': scope[1]})
    return {'items': [dict(r) for r in rows.mappings()]}


class Response(BaseModel):
    decision: Literal['information', 'approve', 'reject', 'request_changes']
    note: str = Field(min_length=1, max_length=2000)
    ticket_version: int = Field(ge=1)
    request_id: UUID


@router.post('/resident/tickets/{ticket_id}/supervisor-response')
async def respond(ticket_id: UUID, body: Response, scope: RESIDENT):
    db, actor = scope
    ticket = (await db.execute(text(f'''select t.id,t.channel_id,t.reopen_count,{WIRE_TICKET} from tickets t
        where t.id=:ticket and t.tenant_id={TENANT} and t.requester_user_id=:actor for update'''),
        {'ticket': ticket_id, 'actor': actor})).mappings().first()
    if not ticket:
        raise HTTPException(404, 'Resident ticket not found')
    message_id = uuid5(NAMESPACE_URL, f'resident-supervisor:{actor}:{ticket_id}:{body.request_id}')
    fingerprint = digest(body.model_dump(mode='json'))
    prior = (await db.execute(text('select body from messages where id=:id and channel_id=:channel'),
        {'id': message_id, 'channel': ticket['channel_id']})).mappings().first()
    if prior:
        if prior['body'].get('responseHash') != fingerprint:
            raise HTTPException(409, 'Response id already used with different content')
        return await submit_reception_message(ReceptionToSupervisorMessage.model_validate(prior['body']['supervisorResponse']), scope)
    pending = (await db.execute(text(f'''select * from vh_reception_supervisor_pending
        where tenant_id={TENANT} and ticket_id=:ticket and ticket_generation=:generation for update'''),
        {'ticket': ticket_id, 'generation': ticket['reopen_count']})).mappings().first()
    if not pending or ticket['version'] != body.ticket_version:
        raise HTTPException(409, 'Supervisor request or ticket changed; reload before replying')
    if (pending['pending_kind'] == 'information') != (body.decision == 'information'):
        raise HTTPException(422, 'Response does not match the pending request')
    original = (await db.execute(text(f'''select payload from vh_reception_supervisor_messages
        where tenant_id={TENANT} and ticket_id=:ticket and ticket_generation=:generation
          and direction='reception_to_supervisor' and message_type='ticket_submitted' order by created_at limit 1'''),
        {'ticket': ticket_id, 'generation': ticket['reopen_count']})).scalar_one_or_none()
    if not original:
        raise HTTPException(409, 'Supervisor handoff is unavailable')
    kinds = {'information': 'information_provided', 'approve': 'plan_approved', 'reject': 'plan_rejected', 'request_changes': 'plan_change_requested'}
    wire = {**current_wire(original, ticket), 'message_id': str(message_id), 'message_type': kinds[body.decision],
        'message': body.note.strip(), 'sent_at': datetime.now(UTC).isoformat(), 'source_message_id': str(message_id),
        'facts': [], 'file_ids': []}
    parsed = ReceptionToSupervisorMessage.model_validate(wire)
    seq = (await db.execute(text('''update channels set next_message_seq=next_message_seq+1,
        last_message=:preview,last_message_at=now() where id=:channel returning next_message_seq-1'''),
        {'channel': ticket['channel_id'], 'preview': body.note[:200]})).scalar_one()
    await db.execute(text(f'''insert into messages(id,tenant_id,channel_id,seq,sender_kind,sender_user_id,visibility,body)
        values(:id,{TENANT},:channel,:seq,'user',:actor,'customer',cast(:body as jsonb))'''),
        {'id': message_id, 'channel': ticket['channel_id'], 'seq': seq, 'actor': actor,
         'body': json.dumps({'text': body.note.strip(), 'responseHash': fingerprint, 'supervisorResponse': parsed.model_dump(mode='json')})})
    # Answering the question is reading it: it must not stay unread in the resident's chat.
    await db.execute(text('''update channel_memberships set last_read_seq=greatest(last_read_seq,:seq),last_read_at=now()
        where channel_id=:channel and user_id=:actor'''), {'seq': seq, 'channel': ticket['channel_id'], 'actor': actor})
    return await submit_reception_message(parsed, scope)
