"""Coordination session of a ticket: the Supervisor team in the management group chat.

The session is persistence only; no agent runs here. It is opened when the ticket
reaches a management unit that has one workspace, one group chat and one versioned
Supervisor, and it stays open after the resident confirms until management approves.
"""

import json
from typing import Annotated
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .reception_delegation import DelegatedScope, reception_agent
from .v3_audit import audit
from .v3_auth import TICKET_VISIBILITY, scoped_connection
from .v3_learning import curate, propose_from_answer
from .v3_mutations import management_access, visible_ticket
from .v3_reception_runtime import append_agent_message
from .v3_rooms import attach_files

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
          and a.purpose='supervisor' and ca.channel_id=:channel
          and not exists(select 1 from agent_releases sr where sr.version_id=v.id and sr.tenant_id=a.tenant_id
            and (sr.status<>'published' or sr.revoked_at is not null)) order by a.id limit 2
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
          tm.shared_state->'closure' as closure,a.name as supervisor_name,
          tm.shared_state->'supervisor' as supervisor,tm.shared_state->'runtime' as runtime
        from agent_teams tm join agents a on a.id=tm.supervisor_agent_id and a.tenant_id=tm.tenant_id
        where tm.ticket_id=:ticket and tm.tenant_id={TENANT}
        order by tm.created_at desc limit 1 {"for update of tm" if lock else ""}
    """), {"ticket": ticket_id})
    return row.mappings().first()


@router.get("/tickets/{ticket_id}/conversation", summary="What the resident and Reception said about a ticket")
async def ticket_conversation(ticket_id: UUID, scope: Scope) -> dict[str, object]:
    await visible_ticket(scope, ticket_id)
    rows = await scope[0].execute(text(f"""
        select m.id,m.seq,m.sender_kind,m.body->>'text' as text,m.created_at from messages m
        where m.channel_id=(select channel_id from tickets where id=:ticket) and m.tenant_id={TENANT} and m.visibility in ('room','customer')
          and m.body->>'text'<>'' order by m.seq desc limit 100
    """), {"ticket": ticket_id})
    return {"items": [dict(row) for row in rows.mappings()][::-1]}


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
    from .supervised_flow import supervisor_approves
    return {"session": dict(session), "room": await _room(scope[0], session["id"]),
            "supervisorApprovesPlans": supervisor_approves(),
            "awaitingManagementApproval": ticket["status"] == "closed" and session["status"] != "completed"}


async def _room(db: AsyncConnection, team_id: UUID) -> dict[str, object]:
    """What the Supervisor's room did for this session: who was invited, their tasks and their replies."""
    members = await db.execute(text(f"""
        select a.name from team_members m join agents a on a.id=m.agent_id and a.tenant_id=m.tenant_id
        where m.team_id=:team and m.tenant_id={TENANT} and m.member_kind='specialist' order by m.created_at
    """), {"team": team_id})
    tasks = await db.execute(text(f"""
        select k.description,k.status,a.name as agent from team_tasks k
        join team_members m on m.id=k.assigned_member_id and m.tenant_id=k.tenant_id
        join agents a on a.id=m.agent_id and a.tenant_id=m.tenant_id
        where k.team_id=:team and k.tenant_id={TENANT} order by k.created_at
    """), {"team": team_id})
    # A mirrored reply is stored as "<ticket code>: <reply>"; the ticket is already on screen.
    replies = await db.execute(text(f"""
        select m.id,a.name as agent,substr(m.body->>'text',position(': ' in m.body->>'text')+2) as text,m.created_at
        from messages m join agents a on a.id=m.sender_agent_id and a.tenant_id=m.tenant_id
        where m.tenant_id={TENANT} and m.body->>'sessionId'=:team and m.body->>'kind'='specialist_reply'
        order by m.seq
    """), {"team": str(team_id)})
    # What management asked an agent inside this session, and whether it was answered yet.
    questions = await db.execute(text(f"""
        select m.id,a.name as agent,substr(m.body->>'text',position(': ' in m.body->>'text')+2) as text,
          mm.status,m.created_at
        from messages m
        join message_mentions mm on mm.message_id=m.id and mm.tenant_id=m.tenant_id
        join agents a on a.id=mm.agent_id and a.tenant_id=mm.tenant_id
        where m.tenant_id={TENANT} and m.body->>'sessionId'=:team and m.body->>'kind'='session_question'
        order by m.seq
    """), {"team": str(team_id)})
    # The plan the Supervisor proposed in this session, which management decides like any other plan.
    plan = (await db.execute(text(f"""
        select p.id,p.title,p.status,p.version,p.proposal,p.management_note,p.created_at
        from vh_ticket_plans p join agent_teams tm on tm.ticket_id=p.ticket_id and tm.tenant_id=p.tenant_id
        where tm.id=:team and p.tenant_id={TENANT} and p.proposed_by_agent_id=tm.supervisor_agent_id
          and p.created_at>=tm.created_at
        order by p.created_at desc limit 1
    """), {"team": team_id})).mappings().first()
    return {"members": [row[0] for row in members], "tasks": [dict(row) for row in tasks.mappings()],
            "replies": [dict(row) for row in replies.mappings()],
            "questions": [dict(row) for row in questions.mappings()],
            "plan": dict(plan) if plan else None}


class SessionQuestion(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    client_message_id: str = Field(min_length=1, max_length=160)
    # Needed only when the session has more than one specialist.
    agent_id: str | None = Field(default=None, max_length=160)
    # Photos and text files uploaded to the session's room beforehand (v3_room_files.py), at most 8.
    file_ids: list[UUID] = Field(default_factory=list, max_length=8)

    @field_validator("file_ids")
    @classmethod
    def once(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("a file is attached once")
        return value


@router.post("/tickets/{ticket_id}/session/questions", status_code=201,
             summary="Management asks a specialist of this ticket's session a question")
async def ask_session_agent(ticket_id: UUID, body: SessionQuestion, scope: Scope) -> dict[str, object]:
    """Stored as a message of the management room and queued for the Supervisor's room of this session.

    The agent answers inside the session, with the ticket and the room's exchange as its context.
    The backend never runs the agent; the Coordination runtime picks the question up.
    """
    db, actor, _ = scope
    ticket = await visible_ticket(scope, ticket_id, lock=True)
    if not await management_access(scope, ticket):
        raise HTTPException(403, "Management grant for this ticket is required")
    session = await _session(db, ticket_id, lock=True)
    if session is None:
        raise HTTPException(404, "This ticket has no coordination session")
    if session["status"] in ("completed", "failed", "cancelled"):
        raise HTTPException(409, "This session has finished")
    specialists = (await db.execute(text(f"""
        select m.agent_id from team_members m where m.team_id=:team and m.tenant_id={TENANT}
          and m.member_kind='specialist' and m.status='active' order by m.created_at
    """), {"team": session["id"]})).scalars().all()
    agent = body.agent_id or (specialists[0] if len(specialists) == 1 else None)
    if agent is None or agent not in specialists:
        raise HTTPException(422, "Name a specialist that takes part in this session")
    code = (await db.execute(text("select code from tickets where id=:id"), {"id": ticket_id})).scalar_one()
    content = {"text": f"{code}: {body.text}", "sessionId": str(session["id"]),
               "kind": "session_question", "mentionAgentId": agent}
    previous = (await db.execute(text("""
        select id,body from messages where channel_id=:room and sender_user_id=:actor and client_message_id=:client
    """), {"room": session["channel_id"], "actor": actor, "client": body.client_message_id})).mappings().first()
    if previous is not None:
        if previous["body"] != content:
            raise HTTPException(409, "client_message_id already used with different content")
        return {"id": str(previous["id"]), "status": "queued", "replayed": True}
    if (await db.execute(text(f"""
        select 1 from messages m join message_mentions mm on mm.message_id=m.id and mm.tenant_id=m.tenant_id
        where m.tenant_id={TENANT} and m.body->>'sessionId'=:team and m.body->>'kind'='session_question'
          and mm.status in ('queued','running')
    """), {"team": str(session["id"])})).first():
        # The room runs one turn at a time; a second question waits for the first answer.
        raise HTTPException(409, "A question of this session is still waiting for its answer")
    seq = (await db.execute(text("""
        update channels set next_message_seq=next_message_seq+1,last_message=:preview,last_message_at=now(),updated_at=now()
        where id=:room returning next_message_seq-1
    """), {"room": session["channel_id"], "preview": content["text"][:200]})).scalar_one()
    message = (await db.execute(text(f"""
        insert into messages(tenant_id,channel_id,seq,sender_kind,sender_user_id,visibility,body,client_message_id)
        values({TENANT},:room,:seq,'user',:actor,'room',cast(:body as jsonb),:client) returning id
    """), {"room": session["channel_id"], "seq": seq, "actor": actor, "body": json.dumps(content, ensure_ascii=False),
           "client": body.client_message_id})).scalar_one()
    await attach_files(db, actor, session["channel_id"], message, body.file_ids)
    await db.execute(text(f"""
        insert into message_mentions(tenant_id,message_id,agent_id,requested_by,status)
        values({TENANT},:message,:agent,:actor,'queued')
    """), {"message": message, "agent": agent, "actor": actor})
    await audit(db, actor, "team.agent_asked", "agent_team", str(session["id"]), {"messageId": str(message), "agentId": agent})
    return {"id": str(message), "status": "queued", "replayed": False}


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
        select distinct mc.management_unit_id,u.code as unit_code,b.name as building_name,
          b.id as building_id,b.zone_id
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
    # What management answers applies to the resident's area: its zone, else its building.
    area = (await db.execute(text(f"""
        select id from access_scopes where tenant_id={TENANT} and ((kind='zone' and zone_id=:zone)
          or (kind='building' and building_id=:building)) order by kind desc limit 1
    """), {"zone": homes[0]["zone_id"], "building": homes[0]["building_id"]})).scalar_one_or_none()
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
               "scopeId": str(area) if area else None,
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
async def answer_inquiry(session_id: UUID, body: InquiryAnswer, scope: Scope, request: Request,
                         background: BackgroundTasks) -> dict[str, object]:
    db = scope[0]
    session = (await db.execute(text(f"""
        select tm.id,tm.status,tm.state_version,tm.shared_state,tm.workspace_id,{MANAGES_SESSION} as allowed
        from agent_teams tm join workspaces w on w.id=tm.workspace_id and w.tenant_id=tm.tenant_id
        where tm.id=:id and tm.tenant_id={TENANT} and tm.request_message_id is not null for update of tm
    """), {"id": session_id, "user_id": scope[1], "is_admin": scope[2]})).mappings().first()
    if session is None or not session["allowed"]:
        raise HTTPException(403, "Management grant for this session is required")
    request_state = session["shared_state"].get("request", {})
    answer = body.text.strip()
    if session["status"] == "completed":
        if session["shared_state"].get("closure", {}).get("answer") != answer:
            raise HTTPException(409, "This question was already answered")
        return {"id": str(session["id"]), "status": "completed", "state_version": session["state_version"]}
    if session["state_version"] != body.version or session["status"] in {"failed", "cancelled"}:
        raise HTTPException(409, "Session state or version changed")
    await append_agent_message(db, request_state["residentChannelId"], await reception_agent(db), "customer", {
        "text": f"Ban quản lý trả lời câu hỏi của bạn: {answer}", "sessionId": str(session_id), "source": "management"})
    await db.execute(text("""
        update agent_teams set status='completed',state_version=state_version+1,finished_at=now(),
          shared_state=shared_state||jsonb_build_object('closure',cast(:closure as jsonb)) where id=:id
    """), {"id": session_id, "closure": json.dumps({"answeredBy": scope[1], "answer": answer}, ensure_ascii=False)})
    await audit(db, scope[1], "team.inquiry_answered", "agent_team", str(session_id), {})
    # The answer is also a piece of knowledge the next resident may need.
    candidate = await propose_from_answer(db, session_id, session["workspace_id"], request_state.get("scopeId"),
                                          request_state["question"], answer, scope[1])
    if candidate:
        background.add_task(curate, request.app, scope[1], candidate, request_state["question"], answer)
    return {"id": str(session_id), "status": "completed", "state_version": session["state_version"] + 1}
