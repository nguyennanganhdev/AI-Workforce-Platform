"""Coordination session of a ticket: the Supervisor team in the management group chat.

The session is persistence only; no agent runs here. It is opened when the ticket
reaches a management unit that has one workspace, one group chat and one versioned
Supervisor, and it stays open after the resident confirms until management approves.
"""

import json
from typing import Annotated
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .reception_delegation import DelegatedScope, reception_agent
from .v3_audit import audit
from .v3_auth import TICKET_VISIBILITY, scoped_connection
from .v3_mutations import management_access, visible_ticket
from .v3_reception_runtime import append_agent_message

router = APIRouter(tags=["Vinhomes V3 coordination session"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection, scope="function")]
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"


async def session_destination(db: AsyncConnection, management_unit_id: object) -> dict[str, object]:
    """Same rule as the Reception handoff: exactly one workspace, group chat and Supervisor."""
    workspaces = (await db.execute(text(f"""
        select id from workspaces where management_unit_id=:unit and tenant_id={TENANT}
          and status='active' order by id limit 2
    """), {"unit": management_unit_id})).scalars().all()
    if len(workspaces) != 1:
        return {"missing": "workspace"}
    channels = (await db.execute(text(f"""
        select id,is_dispatch_default from channels where workspace_id=:workspace
          and tenant_id={TENANT} and kind='management' order by id limit 20
    """), {"workspace": workspaces[0]})).mappings().all()
    channels = [c for c in channels if c["is_dispatch_default"]] or channels
    if len(channels) != 1:
        return {"missing": "group_chat"}
    supervisors = (await db.execute(text(f"""
        select a.id,a.name,v.id as version_id from agents a
        join channel_agents ca on ca.agent_id=a.id and ca.tenant_id=a.tenant_id
        left join lateral (select id from agent_versions where agent_id=a.id and tenant_id=a.tenant_id
          order by version_no desc limit 1) v on true
        where a.workspace_id=:workspace and a.tenant_id={TENANT} and a.status='active'
          and a.purpose='supervisor' and ca.channel_id=:channel order by a.id limit 2
    """), {"workspace": workspaces[0], "channel": channels[0]["id"]})).mappings().all()
    if len(supervisors) != 1 or supervisors[0]["version_id"] is None:
        return {"missing": "supervisor"}
    return {"workspace_id": workspaces[0], "channel_id": channels[0]["id"],
            "supervisor_id": supervisors[0]["id"], "supervisor_version_id": supervisors[0]["version_id"]}


async def ensure_session(db: AsyncConnection, actor: str, ticket_id: UUID) -> None:
    """Open the session for a new ticket; an unconfigured management unit keeps the manual flow."""
    ticket = (await db.execute(text(
        "select management_unit_id,reopen_count from tickets where id=:id"), {"id": ticket_id})).mappings().one()
    destination = await session_destination(db, ticket["management_unit_id"])
    if "missing" in destination:
        return
    tenant = (await db.execute(text("select current_setting('app.tenant_id')"))).scalar_one()
    # Same identifier as the Reception handoff, so a later handoff joins this team.
    team_id = uuid5(NAMESPACE_URL, f"reception-supervisor-team:{tenant}:{destination['channel_id']}:{ticket_id}:{ticket['reopen_count']}")
    created = await db.execute(text(f"""
        insert into agent_teams(id,tenant_id,workspace_id,channel_id,ticket_id,ticket_generation,
          supervisor_agent_id,status,shared_state,requested_by_user_id)
        values (:id,{TENANT},:workspace,:channel,:ticket,:generation,:supervisor,'queued',cast(:state as jsonb),:actor)
        on conflict do nothing returning id
    """), {"id": team_id, "workspace": destination["workspace_id"], "channel": destination["channel_id"],
           "ticket": ticket_id, "generation": ticket["reopen_count"], "supervisor": destination["supervisor_id"],
           "actor": actor, "state": json.dumps({"request": {
               "ticketId": str(ticket_id), "supervisorVersionId": str(destination["supervisor_version_id"]),
               "source": "ticket_created"}})})
    if created.first() is None:
        return
    await db.execute(text(f"""
        insert into team_members(tenant_id,team_id,agent_id,version_id,member_kind,status)
        values ({TENANT},:team,:agent,:version,'supervisor','active') on conflict do nothing
    """), {"team": team_id, "agent": destination["supervisor_id"], "version": destination["supervisor_version_id"]})
    await audit(db, actor, "team.created", "agent_team", str(team_id),
                {"ticketId": str(ticket_id), "source": "ticket_created"})


async def _session(db: AsyncConnection, ticket_id: UUID, *, lock: bool = False):
    row = await db.execute(text(f"""
        select tm.id,tm.status,tm.state_version,tm.channel_id,tm.created_at,tm.finished_at,
          tm.shared_state->'closure' as closure,a.name as supervisor_name
        from agent_teams tm join agents a on a.id=tm.supervisor_agent_id and a.tenant_id=tm.tenant_id
        where tm.ticket_id=:ticket and tm.tenant_id={TENANT}
        order by tm.created_at desc limit 1 {"for update of tm" if lock else ""}
    """), {"ticket": ticket_id})
    return row.mappings().first()


@router.get("/sessions/awaiting-approval", summary="Closed tickets whose session still waits for management")
async def sessions_awaiting_approval(scope: Scope) -> dict[str, object]:
    rows = await scope[0].execute(text(f"""
        select t.id from tickets t
        join lateral (select status from agent_teams tm where tm.ticket_id=t.id and tm.tenant_id=t.tenant_id
                      order by tm.created_at desc limit 1) s on true
        where t.status='closed' and s.status not in ('completed','failed','cancelled') and {TICKET_VISIBILITY}
        order by t.updated_at desc limit 200
    """), {"user_id": scope[1], "is_admin": scope[2]})
    return {"ticketIds": [str(row[0]) for row in rows]}


@router.get("/tickets/{ticket_id}/session", summary="Coordination session of a ticket")
async def ticket_session(ticket_id: UUID, scope: Scope) -> dict[str, object]:
    ticket = await visible_ticket(scope, ticket_id)
    session = await _session(scope[0], ticket_id)
    if session is None:
        destination = await session_destination(scope[0], ticket["management_unit_id"])
        return {"session": None, "missing": destination.get("missing")}
    return {"session": dict(session),
            "awaitingManagementApproval": ticket["status"] == "closed" and session["status"] != "completed"}


class SessionClosure(BaseModel):
    version: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=2000)


@router.post("/tickets/{ticket_id}/session/close-approval",
             summary="Management approves and closes the session after the resident confirmed")
async def approve_session_closure(ticket_id: UUID, body: SessionClosure, scope: Scope) -> dict[str, object]:
    ticket = await visible_ticket(scope, ticket_id, lock=True)
    if not await management_access(scope, ticket):
        raise HTTPException(403, "Management grant for this ticket is required")
    session = await _session(scope[0], ticket_id, lock=True)
    if session is None:
        raise HTTPException(404, "This ticket has no coordination session")
    if session["status"] == "completed":
        return {"session": dict(session), "awaitingManagementApproval": False}
    if ticket["status"] != "closed":
        raise HTTPException(409, "The resident must confirm the result before the session is closed")
    if session["state_version"] != body.version or session["status"] in {"failed", "cancelled"}:
        raise HTTPException(409, "Session state or version changed")
    await scope[0].execute(text("""
        update agent_teams set status='completed',state_version=state_version+1,finished_at=now(),
          shared_state=shared_state||jsonb_build_object('closure',cast(:closure as jsonb)) where id=:id
    """), {"id": session["id"], "closure": json.dumps({"approvedBy": scope[1], "note": body.note})})
    await audit(scope[0], scope[1], "team.closure_approved", "agent_team", str(session["id"]),
                {"ticketId": str(ticket_id)})
    return {"session": dict(await _session(scope[0], ticket_id)), "awaitingManagementApproval": False}


# --- Inquiries: a question Reception has no source for becomes a session without a ticket.
# The Supervisor of the resident's management unit owns it; until a Supervisor runtime answers,
# management answers in the same session and Reception relays the answer to the resident.

CURRENT_HOME = """ur.verification_status='verified' and ur.valid_from<=now()
    and (ur.valid_to is null or ur.valid_to>now())"""
# Management of the unit that owns the session's workspace (or of the whole tenant).
MANAGES_SESSION = """(:is_admin or exists (
    select 1 from scoped_user_roles r
    join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
    join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
    where m.user_id=:user_id and m.status='active' and r.role_code='management' and r.tenant_id=tm.tenant_id
      and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
      and (s.kind='tenant' or (s.kind='management' and s.management_unit_id=w.management_unit_id))))"""


class InquiryCreate(BaseModel):
    message_id: UUID


@router.post("/internal/reception/chats/{channel_id}/inquiries", status_code=201,
             summary="Reception hands a question it has no source for to the management session")
async def open_inquiry(channel_id: str, body: InquiryCreate, scope: DelegatedScope) -> dict[str, object]:
    db, run = scope
    if channel_id != run["channel_id"]:
        raise HTTPException(403, "Channel differs from delegated binding")
    actor = run["user_id"]
    message = (await db.execute(text("""
        select m.body->>'text' as text,u.name from messages m join users u on u.id=m.sender_user_id
        where m.id=:id and m.channel_id=:channel and m.sender_kind='user' and m.sender_user_id=:actor
    """), {"id": body.message_id, "channel": channel_id, "actor": actor})).mappings().first()
    if message is None or not (message["text"] or "").strip():
        raise HTTPException(422, "message_id must be a resident message with text in this conversation")
    homes = (await db.execute(text(f"""
        select distinct mc.management_unit_id,u.code as unit_code,b.name as building_name
        from unit_residents ur
        join units u on u.id=ur.unit_id and u.tenant_id=ur.tenant_id
        join buildings b on b.id=u.building_id and b.tenant_id=u.tenant_id
        join access_scopes s on s.tenant_id=b.tenant_id and (s.kind='tenant'
          or (s.kind='building' and s.building_id=b.id) or (s.kind='zone' and s.zone_id=b.zone_id)
          or (s.kind='site' and s.site_id=b.site_id))
        join management_coverage mc on mc.scope_id=s.id and mc.tenant_id=s.tenant_id
          and mc.valid_from<=now() and (mc.valid_to is null or mc.valid_to>now())
        where ur.user_id=:actor and ur.tenant_id={TENANT} and {CURRENT_HOME}
    """), {"actor": actor})).mappings().all()
    if len({home["management_unit_id"] for home in homes}) != 1:
        # No home, or homes under different management units: Reception cannot pick one.
        return {"accepted": False, "missing": "management_unit"}
    destination = await session_destination(db, homes[0]["management_unit_id"])
    if "missing" in destination:
        return {"accepted": False, "missing": destination["missing"]}
    tenant = (await db.execute(text("select current_setting('app.tenant_id')"))).scalar_one()
    team_id = uuid5(NAMESPACE_URL, f"reception-inquiry:{tenant}:{body.message_id}")
    resident = f"{message['name'] or 'Cư dân'} (căn {homes[0]['unit_code']}, {homes[0]['building_name']})"
    created = await db.execute(text(f"""
        insert into agent_teams(id,tenant_id,workspace_id,channel_id,request_message_id,
          supervisor_agent_id,status,shared_state,requested_by_user_id)
        values (:id,{TENANT},:workspace,:channel,:message,:supervisor,'queued',cast(:state as jsonb),:actor)
        on conflict do nothing returning id
    """), {"id": team_id, "workspace": destination["workspace_id"], "channel": destination["channel_id"],
           "message": body.message_id, "supervisor": destination["supervisor_id"], "actor": actor,
           "state": json.dumps({"request": {
               "kind": "inquiry", "question": message["text"].strip(), "resident": resident,
               "residentChannelId": channel_id, "unitCode": homes[0]["unit_code"],
               "supervisorVersionId": str(destination["supervisor_version_id"])}}, ensure_ascii=False)})
    if created.first() is not None:
        await db.execute(text(f"""
            insert into team_members(tenant_id,team_id,agent_id,version_id,member_kind,status)
            values ({TENANT},:team,:agent,:version,'supervisor','active') on conflict do nothing
        """), {"team": team_id, "agent": destination["supervisor_id"], "version": destination["supervisor_version_id"]})
        # The group chat is where the Supervisor and management see the session.
        await append_agent_message(db, destination["channel_id"], await reception_agent(db), "room", {
            "text": f"{resident} hỏi: {message['text'].strip()}", "sessionId": str(team_id), "kind": "inquiry"})
        await audit(db, actor, "team.created", "agent_team", str(team_id), {"source": "reception_inquiry"})
    return {"accepted": True, "sessionId": str(team_id)}


@router.get("/sessions/inquiries", summary="Resident questions waiting for management")
async def list_inquiries(scope: Scope) -> dict[str, object]:
    rows = await scope[0].execute(text(f"""
        select tm.id,tm.status,tm.state_version,tm.created_at,
          tm.shared_state->'request'->>'question' as question,
          tm.shared_state->'request'->>'resident' as resident,
          tm.shared_state->'request'->>'unitCode' as unit_code
        from agent_teams tm join workspaces w on w.id=tm.workspace_id and w.tenant_id=tm.tenant_id
        where tm.tenant_id={TENANT} and tm.request_message_id is not null
          and tm.shared_state->'request'->>'kind'='inquiry'
          and tm.status in ('queued','running','waiting') and {MANAGES_SESSION}
        order by tm.created_at limit 200
    """), {"user_id": scope[1], "is_admin": scope[2]})
    return {"items": [dict(row) for row in rows.mappings()]}


class InquiryAnswer(BaseModel):
    version: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=4000)


@router.post("/sessions/{session_id}/answer", summary="Management answers a resident question; Reception relays it")
async def answer_inquiry(session_id: UUID, body: InquiryAnswer, scope: Scope) -> dict[str, object]:
    db = scope[0]
    session = (await db.execute(text(f"""
        select tm.id,tm.status,tm.state_version,tm.shared_state,{MANAGES_SESSION} as allowed
        from agent_teams tm join workspaces w on w.id=tm.workspace_id and w.tenant_id=tm.tenant_id
        where tm.id=:id and tm.tenant_id={TENANT} and tm.request_message_id is not null for update of tm
    """), {"id": session_id, "user_id": scope[1], "is_admin": scope[2]})).mappings().first()
    if session is None or not session["allowed"]:
        raise HTTPException(403, "Management grant for this session is required")
    request = session["shared_state"].get("request", {})
    answer = body.text.strip()
    if session["status"] == "completed":
        if session["shared_state"].get("closure", {}).get("answer") != answer:
            raise HTTPException(409, "This question was already answered")
        return {"id": str(session["id"]), "status": "completed", "state_version": session["state_version"]}
    if session["state_version"] != body.version or session["status"] in {"failed", "cancelled"}:
        raise HTTPException(409, "Session state or version changed")
    await append_agent_message(db, request["residentChannelId"], await reception_agent(db), "customer", {
        "text": f"Ban quản lý trả lời câu hỏi của bạn: {answer}", "sessionId": str(session_id), "source": "management"})
    await db.execute(text("""
        update agent_teams set status='completed',state_version=state_version+1,finished_at=now(),
          shared_state=shared_state||jsonb_build_object('closure',cast(:closure as jsonb)) where id=:id
    """), {"id": session_id, "closure": json.dumps({"answeredBy": scope[1], "answer": answer}, ensure_ascii=False)})
    await audit(db, scope[1], "team.inquiry_answered", "agent_team", str(session_id), {})
    return {"id": str(session_id), "status": "completed", "state_version": session["state_version"] + 1}
