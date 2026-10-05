"""Internal API for the Coordination runtime: the Supervisor of a management room.

Reception hands a ticket over as a schema_v2 message (v3_reception_supervisor). This module is
how the Supervisor runtime (agent-coordination) reaches that exchange without being a person:

  inbox      the durable V2 messages waiting for the Supervisor, in order
  verify     is this exact message the one stored for this team, and is the team still current?
  send       a V2 result, validated exactly like a result an operator would post
  view       what the backend currently holds about the session (the runtime's authority view)
  authorize  may this team still act? asked immediately before every dispatch
  results    was a result with this id stored? the runtime's reconciliation after a lost reply
  status     what the runtime is doing with the session, shown to management
  members    admit a published specialist to the session's room (the runtime's participant resolver)
  runs       the agent run of one turn of a member
  release    what the backend attests about a member's agent version before it is invoked
  room       the room's tasks, turns and specialist replies, mirrored for management to read
  mentions   questions management asked a specialist inside a session, waiting for the room
  plans      the plan the Supervisor proposes, stored for management to decide
  events     management's decisions on those plans, listed until the runtime has taken them

The service token only proves the caller is the runtime. Every call names a team and is checked
against it: the workspace has an active service identity, the Supervisor agent is an active
member, and the ticket is still in the generation the team was opened for. The backend binds
one runtime session and one agent run per team, so the ids the runtime works under are rows
here, not values it chose. The runtime never writes a business table.
"""

import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .v3_reception_runtime import append_agent_message
from .v3_room_files import for_agent
from .v3_reception_supervisor import (
    SupervisorToReceptionResult,
    _decode_cursor,
    _encode_cursor,
    accept_supervisor_result,
)

TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
RUNTIME_BACKEND = "coordination-agentscope"
POLICY_VERSION = "vinhomes-supervisor-policy-1"
FINAL = ("completed", "failed", "cancelled")
# How long a proposed plan waits for management before the Supervisor treats the request as expired.
# The backend itself never expires a plan; the Supervisor's flow needs a deadline to exist.
PLAN_APPROVAL_WINDOW = timedelta(days=30)
# Session status after a result of each kind. A final status is set only by management's
# closure approval (v3_session), a failure or a confirmed cancellation.
TEAM_STATUS = {"accepted": "running", "in_progress": "running", "information_requested": "waiting",
               "plan_approval_requested": "waiting", "failed": "failed", "cancelled": "cancelled"}
# What the resident is told in their own conversation. Progress notes stay in the management room.
RESIDENT_FACING = {"information_requested", "plan_approval_requested", "completed", "failed", "cancelled"}
router = APIRouter(prefix="/internal/coordination/v1", tags=["Coordination runtime"])


async def coordination_scope(request: Request):
    """Authenticate the runtime and open a tenant-scoped transaction with no acting user."""
    settings = request.app.state.settings
    token, offered = settings.coordination_service_token, request.headers.get("authorization", "")
    if not token:
        raise HTTPException(503, "Coordination runtime is not configured")
    if not offered.startswith("Bearer ") or not hmac.compare_digest(offered[7:].encode(), token.encode()):
        raise HTTPException(401, "Invalid Coordination service credential")
    engine = request.app.state.engine
    if engine is None:
        raise HTTPException(503, "Database unavailable")
    try:
        async with engine.begin() as db:
            await db.execute(text("select set_config('app.tenant_id',:tenant,true),set_config('app.user_id','',true)"),
                             {"tenant": str(settings.tenant_id)})
            yield db
    except IntegrityError as exc:
        raise HTTPException(409, "V3 constraint conflict; reload the resource and retry") from exc
    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(503, "V3 database is unavailable or missing required tables") from exc


Scope = Annotated[Any, Depends(coordination_scope, scope="function")]


async def team_authority(db, team_id: UUID, *, lock: bool = False) -> dict[str, Any]:
    """The team as the backend holds it now, or a refusal. Nothing here comes from the runtime."""
    row = (await db.execute(text(f"""
        select tm.id,tm.tenant_id,tm.workspace_id,tm.channel_id,tm.ticket_id,tm.ticket_generation,tm.status,
          tm.supervisor_agent_id,tm.requested_by_user_id,tm.shared_state,
          t.code as ticket_code,t.version as ticket_version,t.reopen_count,t.status as ticket_status,
          t.domain_id,t.channel_id as resident_channel_id,t.requester_user_id,w.management_unit_id,
          (select code from service_categories sc where sc.id=t.category_id and sc.tenant_id=t.tenant_id) as category_code,
          mem.id as member_id,mem.version_id as supervisor_version_id,
          p.id as principal_id,p.authz_version
        from agent_teams tm
        join workspaces w on w.id=tm.workspace_id and w.tenant_id=tm.tenant_id and w.status='active'
        join channels c on c.id=tm.channel_id and c.tenant_id=tm.tenant_id and c.kind='management'
          and c.workspace_id=tm.workspace_id
        join tickets t on t.id=tm.ticket_id and t.tenant_id=tm.tenant_id
        join agents a on a.id=tm.supervisor_agent_id and a.tenant_id=tm.tenant_id and a.status='active'
          and a.purpose='supervisor'
        join team_members mem on mem.team_id=tm.id and mem.tenant_id=tm.tenant_id
          and mem.agent_id=tm.supervisor_agent_id and mem.member_kind='supervisor' and mem.status='active'
          and not exists (select 1 from agent_releases sr where sr.version_id=mem.version_id
            and sr.tenant_id=mem.tenant_id and (sr.status<>'published' or sr.revoked_at is not null))
        join execution_principals p on p.tenant_id=tm.tenant_id and p.kind='workspace_service'
          and p.workspace_id=tm.workspace_id and p.status='active'
        where tm.id=:team and tm.tenant_id={TENANT} {"for update of tm" if lock else ""}
    """), {"team": team_id})).mappings().first()
    if row is None:
        raise HTTPException(403, "Supervisor team, workspace service identity or agent is inactive")
    if row["ticket_generation"] != row["reopen_count"]:
        raise HTTPException(409, "The ticket moved to a new generation; this team is no longer current")
    return dict(row)


async def member_binding(db, team: dict[str, Any], *, agent: str, version, member, key: str, namespace: str,
                         create: bool):
    """The runtime session of one team member: one active binding per member, allocated here."""
    backend = (await db.execute(text("select id from runtime_backends where code=:code and enabled"),
                                {"code": RUNTIME_BACKEND})).scalar_one_or_none()
    if backend is None:
        raise HTTPException(503, "Coordination runtime backend is not registered or is disabled")
    binding = (await db.execute(text(f"""
        select id from runtime_session_bindings where tenant_id={TENANT} and backend_id=:backend
          and runtime_session_key=:key and status='active'
    """), {"backend": backend, "key": key})).scalar_one_or_none()
    if binding is None and create:
        await db.execute(text(f"""
            insert into runtime_identities(tenant_id,backend_id,principal_id,runtime_user_key,status)
            values({TENANT},:backend,:principal,:key,'active') on conflict (backend_id,principal_id) do nothing
        """), {"backend": backend, "principal": team["principal_id"], "key": f"workspace:{team['workspace_id']}"})
        binding = (await db.execute(text(f"""
            insert into runtime_session_bindings(tenant_id,identity_id,backend_id,channel_id,agent_id,agent_version_id,
              team_member_id,audience_kind,started_by_user_id,runtime_session_key,checkpoint_namespace,status,policy_version)
            select {TENANT},i.id,i.backend_id,:channel,:agent,:version,:member,'team',:requester,:key,:namespace,'active',:policy
            from runtime_identities i where i.backend_id=:backend and i.principal_id=:principal
            returning id
        """), {"backend": backend, "principal": team["principal_id"], "channel": team["channel_id"],
               "agent": agent, "version": version, "member": member, "requester": team["requested_by_user_id"],
               "key": key, "namespace": namespace, "policy": POLICY_VERSION})).scalar_one()
        await db.execute(text("update team_members set binding_id=:binding,updated_at=now() where id=:member and binding_id is null"),
                         {"binding": binding, "member": member})
    return binding


async def session_context(db, team: dict[str, Any], *, create: bool) -> dict[str, Any] | None:
    """The runtime session and agent run of a team. Created once, on the first verified message."""
    binding = await member_binding(db, team, agent=team["supervisor_agent_id"], version=team["supervisor_version_id"],
                                   member=team["member_id"], key=f"coordination:{team['id']}",
                                   namespace="supervisor", create=create)
    if binding is None:
        return None
    run_key = f"supervisor-session:{team['id']}"
    await db.execute(text(f"""
        insert into agent_runs(tenant_id,channel_id,agent_id,version_id,team_member_id,idempotency_key,status,started_at,
          trace_id,binding_id,authority_principal_id,policy_version,authority_version)
        values({TENANT},:channel,:agent,:version,:member,:key,'running',now(),:trace,:binding,:principal,:policy,:authz)
        on conflict (tenant_id,idempotency_key) do nothing
    """), {"channel": team["channel_id"], "agent": team["supervisor_agent_id"], "version": team["supervisor_version_id"],
           "member": team["member_id"], "key": run_key, "trace": str(uuid4()), "binding": binding,
           "principal": team["principal_id"], "policy": POLICY_VERSION, "authz": team["authz_version"]})
    run = (await db.execute(text(f"select id from agent_runs where tenant_id={TENANT} and idempotency_key=:key"),
                            {"key": run_key})).scalar_one()
    return {"tenant_id": str(team["tenant_id"]), "principal_id": str(team["principal_id"]),
            **({"initiated_by_user_id": team["requested_by_user_id"]} if team["requested_by_user_id"] else {}),
            "domain_id": str(team["domain_id"]), "workspace_id": str(team["workspace_id"]),
            "ticket_id": str(team["ticket_id"]), "ticket_generation": team["ticket_generation"],
            "binding_id": str(binding), "run_id": str(run)}


def plan_for_resident(proposal: dict[str, Any]) -> str:
    """The plan as the resident reads it in the request's own conversation, so without the request code."""
    steps = "\n".join(f"{n}. {step}" for n, step in enumerate(proposal["steps"], 1))
    cost = proposal.get("cost")
    price = f"{Decimal(str(cost['amount'])):,.0f} {cost['currency']}".replace(",", ".") if cost else "chưa có"
    return (f"Ban quản lý đề xuất phương án xử lý cho yêu cầu của anh/chị:\n{proposal['summary']}\n\n"
            f"Các bước:\n{steps}\n\n"
            f"Người thực hiện: {proposal['performer_role']}\nThời gian dự kiến: {proposal['expected_duration']}\n"
            f"Điều kiện: {proposal['conditions']}\nChi phí dự kiến: {price}\n\n"
            "Anh/chị có đồng ý với phương án này không?")


async def specialists(db, team: dict[str, Any]) -> list[dict[str, Any]]:
    """The agents a Supervisor may invite for this ticket.

    An agent of the management room, active, whose published version declares the ticket's
    service category. A ticket without a category is offered nobody: management handles it.
    """
    if team["category_code"] is None:
        return []
    rows = (await db.execute(text(f"""
        select v.id as version_id,a.id as agent_id,a.name,v.config->>'description' as description,
          v.config->'service_categories' as categories,v.config->'mcp_tools' as tools
        from channel_agents ca
        join agents a on a.id=ca.agent_id and a.tenant_id=ca.tenant_id and a.status='active' and a.purpose='specialist'
        join agent_releases r on r.agent_id=a.id and r.tenant_id=a.tenant_id and r.status='published' and r.revoked_at is null
        join agent_versions v on v.id=r.version_id and v.tenant_id=r.tenant_id
        where ca.channel_id=:channel and ca.tenant_id={TENANT}
          and v.config->'service_categories' ? :category
          and v.version_no=(select max(v2.version_no) from agent_versions v2 where v2.agent_id=a.id and v2.tenant_id=a.tenant_id)
        order by a.name
    """), {"channel": team["channel_id"], "category": team["category_code"]})).mappings().all()
    return [{"agent_version_id": str(row["version_id"]), "agent_id": row["agent_id"], "name": row["name"],
             "role": team["category_code"], "description": row["description"],
             "service_categories": row["categories"],
             "tools": [tool["name"] for tool in row["tools"] or []]} for row in rows]


@router.get("/inbox", summary="V2 messages from Reception waiting for the Supervisor, oldest first")
async def inbox(db: Scope, cursor: str | None = Query(default=None, max_length=512),
                limit: int = Query(default=50, ge=1, le=100)) -> dict[str, Any]:
    after_at, after_id = _decode_cursor(cursor)
    rows = (await db.execute(text(f"""
        select id,team_id,payload,created_at from vh_reception_supervisor_messages
        where tenant_id={TENANT} and direction='reception_to_supervisor'
          and (cast(:after_at as timestamptz) is null or (created_at,id)>
            (cast(:after_at as timestamptz),cast(:after_id as uuid)))
        order by created_at,id limit :limit
    """), {"after_at": after_at, "after_id": after_id, "limit": limit})).mappings().all()
    return {"items": [{"team_id": str(row["team_id"]), "message": row["payload"]} for row in rows],
            "next_cursor": _encode_cursor(dict(rows[-1])) if rows else cursor}


class Verify(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_id: UUID
    message_id: str = Field(min_length=1, max_length=200)


@router.post("/reception/verify", summary="The stored V2 message and the session it belongs to")
async def verify(body: Verify, db: Scope) -> dict[str, Any]:
    team = await team_authority(db, body.team_id, lock=True)
    if team["status"] in FINAL:
        raise HTTPException(409, "This Supervisor team has finished")
    message = (await db.execute(text(f"""
        select payload from vh_reception_supervisor_messages where tenant_id={TENANT} and message_id=:message
          and team_id=:team and direction='reception_to_supervisor'
    """), {"message": body.message_id, "team": body.team_id})).scalar_one_or_none()
    if message is None:
        raise HTTPException(404, "No such Reception message for this team")
    context = await session_context(db, team, create=True)
    if message["message_type"] == "information_provided":
        requests = team["shared_state"].get("residentRequests", {})
        changed = False
        for question in requests.values():
            if question["ticket_version"] == message["ticket_version"] and not question.get("resolved"):
                question["resolved"], changed = True, True
        if changed:
            await db.execute(text("""update agent_teams set shared_state=shared_state||
                jsonb_build_object('residentRequests',cast(:requests as jsonb)) where id=:team"""), {
                "team": body.team_id, "requests": json.dumps(requests)})
    # The runtime compares this stored message with the one it was given: an old reply is never rebased.
    return {"message": message, "context": context, "supervisor_run_id": context["run_id"]}


async def _after_result(db, team: dict[str, Any], body: SupervisorToReceptionResult) -> None:
    """What a stored result changes: the session status and who is told."""
    status = TEAM_STATUS.get(body.message_type)
    if status:
        await db.execute(text("""
            update agent_teams set status=:status,state_version=state_version+1,updated_at=now(),
              finished_at=case when :status in ('failed','cancelled') then now() else finished_at end,
              shared_state=shared_state||jsonb_build_object('supervisor',
                coalesce(shared_state->'supervisor','{}'::jsonb)||cast(:note as jsonb))
            where id=:id and status not in ('completed','failed','cancelled')
        """), {"id": team["id"], "status": status, "note": json.dumps({
            "runId": body.supervisor_run_id, "lastMessageType": body.message_type,
            **({"acceptedAt": body.sent_at.isoformat()} if body.message_type == "accepted" else {})})})
    await append_agent_message(db, team["channel_id"], team["supervisor_agent_id"], "room", {
        "text": f"{team['ticket_code']}: {body.message}", "sessionId": str(team["id"]),
        "kind": "supervisor_" + body.message_type})
    if body.message_type in RESIDENT_FACING:
        from .reception_delegation import reception_agent
        await append_agent_message(db, team["resident_channel_id"], await reception_agent(db), "customer", {
            "text": body.message, "sessionId": str(team["id"]), "source": "supervisor",
            "supervisorMessageId": body.message_id})


class Send(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: SupervisorToReceptionResult


@router.post("/reception/send", summary="Store a V2 result from the Supervisor")
async def send(body: Send, db: Scope) -> dict[str, Any]:
    team = await team_authority(db, body.message.team_id, lock=True)
    stored = await accept_supervisor_result(db, body.message, team, agent_id=team["supervisor_agent_id"])
    replayed = bool(stored.get("replayed"))
    if not replayed:
        await _after_result(db, team, body.message)
        await db.execute(text(f"""
            insert into audit_events(tenant_id,initiator_kind,initiator_id,event_type,target_type,target_id,payload,correlation_id)
            values ({TENANT},'agent',:agent,'reception_supervisor.result_received','ticket',:ticket,cast(:payload as jsonb),:correlation)
        """), {"agent": team["supervisor_agent_id"], "ticket": str(team["ticket_id"]), "correlation": uuid4(),
               "payload": json.dumps({"messageId": body.message.message_id, "messageType": body.message.message_type})})
    return {"message_id": body.message.message_id, "status": "accepted", "replayed": replayed}


@router.get("/teams/{team_id}/view", summary="What the backend holds about a Supervisor session")
async def view(team_id: UUID, db: Scope) -> dict[str, Any]:
    team = await team_authority(db, team_id)
    context = await session_context(db, team, create=False)
    if context is None:
        raise HTTPException(409, "No Reception message was verified for this team yet")
    pending = (await db.execute(text(f"""
        select pending_kind from vh_reception_supervisor_pending
        where tenant_id={TENANT} and ticket_id=:ticket and ticket_generation=:generation
    """), {"ticket": team["ticket_id"], "generation": team["ticket_generation"]})).scalar_one_or_none()
    # The plan this session's Supervisor proposed, if any, and who decides it.
    plan = (await db.execute(text(f"""
        select id,status,created_at,proposal from vh_ticket_plans where tenant_id={TENANT} and ticket_id=:ticket
          and proposed_by_agent_id=:agent and created_at>=(select created_at from agent_teams where id=:team)
        order by created_at desc limit 1
    """), {"ticket": team["ticket_id"], "agent": team["supervisor_agent_id"], "team": team["id"]})).mappings().first()
    # Management approved: the resident is asked next, in these words and no others.
    asking = {} if plan is None or plan["status"] != "resident_pending" else {
        "resident_recipient": team["requester_user_id"], "resident_request_type": "plan_approval_requested",
        "resident_request_message": plan_for_resident(plan["proposal"])}
    questions = [q for q in team["shared_state"].get("residentRequests", {}).values() if not q.get("resolved")]
    question = questions[-1] if questions else None
    supervisor_instructions = (await db.execute(text('select instructions from agent_versions where id=:version'),
        {'version': team['supervisor_version_id']})).scalar_one()
    return {"context": context, "team_status": team["status"], "ticket_status": team["ticket_status"],
            "ticket_version": str(team["ticket_version"]), "ticket_code": team["ticket_code"],
            "supervisor_version_id": str(team["supervisor_version_id"]), "pending_resident": pending,
            "supervisor_instructions": supervisor_instructions,
            "resident_recipient": team["requester_user_id"],
            "resident_request_type": "information_requested" if question else None,
            "resident_request_message": question["message"] if question else None,
            "category": team["category_code"], "specialists": await specialists(db, team),
            "plan": None if plan is None else {
                "plan_id": plan["proposal"].get("root_plan_id", str(plan["id"])), "status": plan["status"],
                "management_recipient": f"management-unit:{team['management_unit_id']}",
                "approval_expires_at": (plan["created_at"] + PLAN_APPROVAL_WINDOW).isoformat(),
                # Every plan needs the resident's decision: the work orders are created by it.
                "resident_approval_required": True, **asking}}


class Authorize(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1, max_length=256)
    channel: Literal["room", "backend", "reception", "draft"]
    operation: str = Field(min_length=1, max_length=256)


@router.post("/teams/{team_id}/authorize", summary="May this team act now? Asked before every dispatch")
async def authorize(team_id: UUID, body: Authorize, db: Scope) -> dict[str, Any]:
    team = await team_authority(db, team_id)
    if team["status"] in FINAL:
        raise HTTPException(409, "This Supervisor team has finished")
    allowed = body.channel in ("reception", "room") or (body.channel, body.operation) in {
        ("draft", "plan"), ("draft", "question"), ("backend", "approval.requested")}
    if not allowed:
        # Assignments, questions, publications and cancellations have no producer contract yet.
        raise HTTPException(409, "This Supervisor action is not bound yet")
    return {"authorized": True}


@router.get("/teams/{team_id}/results/{message_id}", summary="Was this Supervisor result stored?")
async def result(team_id: UUID, message_id: str, db: Scope) -> dict[str, Any]:
    await team_authority(db, team_id)
    found = (await db.execute(text(f"""
        select 1 from vh_reception_supervisor_messages where tenant_id={TENANT} and message_id=:message
          and team_id=:team and direction='supervisor_to_reception'
    """), {"message": message_id, "team": team_id})).first() is not None
    return {"found": found, "message_id": message_id, **({"status": "accepted"} if found else {})}


class Status(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: str = Field(min_length=1, max_length=64)
    pause_reason: str | None = Field(default=None, max_length=200)
    state_version: int = Field(ge=0)


@router.post("/teams/{team_id}/status", summary="What the runtime is doing with this session")
async def status(team_id: UUID, body: Status, db: Scope) -> dict[str, Any]:
    team = await team_authority(db, team_id, lock=True)
    # Observability only: it does not change the session status or its version.
    await db.execute(text("""
        update agent_teams set shared_state=shared_state||jsonb_build_object('runtime',cast(:runtime as jsonb)),updated_at=now()
        where id=:id
    """), {"id": team["id"], "runtime": json.dumps({
        "phase": body.phase, "pauseReason": body.pause_reason, "stateVersion": body.state_version})})
    return {"ok": True}


class Admit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_version_id: UUID


async def specialist_member(db, team: dict[str, Any], member_id: UUID) -> dict[str, Any]:
    """A specialist of this team whose pinned version is still published."""
    row = (await db.execute(text(f"""
        select m.id,m.agent_id,m.version_id,m.binding_id,b.generation,b.runtime_session_key,
          v.instructions,v.config,v.config_hash,a.name,
          exists(select 1 from agent_releases r where r.version_id=m.version_id and r.tenant_id=m.tenant_id
                 and r.status='published' and r.revoked_at is null) as published,
          exists(select 1 from vh_agent_reviews rv where rv.agent_id=m.agent_id and rv.tenant_id=m.tenant_id
                 and rv.status='approved' and rv.config_hash=v.config_hash) as approved
        from team_members m
        join agents a on a.id=m.agent_id and a.tenant_id=m.tenant_id
        join agent_versions v on v.id=m.version_id and v.tenant_id=m.tenant_id
        join runtime_session_bindings b on b.id=m.binding_id and b.tenant_id=m.tenant_id and b.status='active'
        where m.id=:member and m.team_id=:team and m.tenant_id={TENANT}
          and m.member_kind='specialist' and m.status='active'
    """), {"member": member_id, "team": team["id"]})).mappings().first()
    if row is None:
        raise HTTPException(404, "No such specialist in this session")
    if not row["published"] or not row["approved"]:
        raise HTTPException(409, "This agent version was revoked or has no approved review")
    return dict(row)


@router.post("/teams/{team_id}/members", summary="Admit a published specialist to the session's room")
async def admit(team_id: UUID, body: Admit, db: Scope) -> dict[str, Any]:
    team = await team_authority(db, team_id, lock=True)
    if team["status"] in FINAL:
        raise HTTPException(409, "This Supervisor team has finished")
    if await session_context(db, team, create=False) is None:
        raise HTTPException(409, "No Reception message was verified for this team yet")
    offered = next((s for s in await specialists(db, team)
                    if s["agent_version_id"] == str(body.agent_version_id)), None)
    if offered is None:
        raise HTTPException(409, "This agent version is not offered to this session")
    member = (await db.execute(text(f"""
        select id,version_id from team_members where team_id=:team and agent_id=:agent and tenant_id={TENANT}
    """), {"team": team["id"], "agent": offered["agent_id"]})).mappings().first()
    if member is None:
        member = (await db.execute(text(f"""
            insert into team_members(tenant_id,team_id,agent_id,version_id,member_kind,status)
            values({TENANT},:team,:agent,:version,'specialist','active') returning id,version_id
        """), {"team": team["id"], "agent": offered["agent_id"], "version": body.agent_version_id})).mappings().one()
    elif member["version_id"] != body.agent_version_id:
        # A session keeps the version it admitted; a newer one is for the next session.
        raise HTTPException(409, "This agent is already a member with another version")
    binding = await member_binding(db, team, agent=offered["agent_id"], version=body.agent_version_id,
                                   member=member["id"], key=f"coordination:{team['id']}:{member['id']}",
                                   namespace="specialist", create=True)
    return {"agent_version_id": str(body.agent_version_id), "role": offered["role"],
            "platform_agent_id": offered["agent_id"], "member_id": str(member["id"]), "binding_id": str(binding),
            "binding_generation": 1, "framework_agent_id": offered["agent_id"],
            "framework_reference": f"openbot:{binding}"}


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str = Field(min_length=1, max_length=200)


@router.post("/teams/{team_id}/members/{member_id}/runs", summary="The agent run of one turn of a specialist")
async def turn_run(team_id: UUID, member_id: UUID, body: Turn, db: Scope) -> dict[str, Any]:
    team = await team_authority(db, team_id)
    if team["status"] in FINAL:
        raise HTTPException(409, "This Supervisor team has finished")
    member = await specialist_member(db, team, member_id)
    context = await session_context(db, team, create=False)
    key = f"turn:{team['id']}:{body.operation_id}"
    # The same operation asked twice gets the same run: a retried turn is not a second turn.
    await db.execute(text(f"""
        insert into agent_runs(tenant_id,channel_id,agent_id,version_id,team_member_id,parent_run_id,idempotency_key,status,
          started_at,trace_id,binding_id,authority_principal_id,policy_version,authority_version)
        values({TENANT},:channel,:agent,:version,:member,:parent,:key,'running',now(),:trace,:binding,:principal,:policy,:authz)
        on conflict (tenant_id,idempotency_key) do nothing
    """), {"channel": team["channel_id"], "agent": member["agent_id"], "version": member["version_id"],
           "member": member["id"], "parent": context["run_id"], "key": key, "trace": str(uuid4()),
           "binding": member["binding_id"], "principal": team["principal_id"], "policy": POLICY_VERSION,
           "authz": team["authz_version"]})
    run = (await db.execute(text(f"select id from agent_runs where tenant_id={TENANT} and idempotency_key=:key"),
                            {"key": key})).scalar_one()
    return {"run_id": str(run)}


@router.get("/teams/{team_id}/members/{member_id}/release",
            summary="What the backend attests about a member's agent version, asked before every invocation")
async def release(team_id: UUID, member_id: UUID, db: Scope) -> dict[str, Any]:
    team = await team_authority(db, team_id)
    if team["status"] in FINAL:
        raise HTTPException(409, "This Supervisor team has finished")
    member = await specialist_member(db, team, member_id)
    config = member["config"]
    # The tools this version was approved with, as the tenant's catalogue describes them now.
    # A model tool name cannot contain a dot, so `sop_kb.retrieve` is offered as `sop_kb__retrieve`.
    # Only read tools: the tool host keeps the others closed to sessions for now.
    descriptors = []
    for granted in config.get("mcp_tools", []):
        tool = (await db.execute(text(f"""
            select description,input_schema,effect from mcp_tools
            where tenant_id={TENANT} and server_id=:server and name=:name
        """), {"server": granted["server_id"], "name": granted["name"]})).mappings().first()
        if tool is None:
            raise HTTPException(409, "A tool this agent version was approved with is no longer in the catalogue")
        if tool["effect"] == "read":
            descriptors.append({"name": granted["name"].replace(".", "__"), "description": tool["description"],
                                "parameters": tool["input_schema"]})
    return {"tenant_id": str(team["tenant_id"]), "workspace_id": str(team["workspace_id"]),
            "ticket_id": str(team["ticket_id"]), "ticket_generation": team["ticket_generation"],
            "groupchat_version_id": str(team["supervisor_version_id"]),
            "agent_version_id": str(member["version_id"]), "member_id": str(member["id"]),
            "binding_id": str(member["binding_id"]), "binding_generation": member["generation"],
            "framework_reference": f"openbot:{member['binding_id']}", "thread_id": member["runtime_session_key"],
            # Both hold by construction: a version exists only from an approved review whose
            # evaluation passed every case, and specialist_member refused anything else.
            "evaluated": True, "admin_approved": True, "published": True, "revoked": False,
            "prompt_hash": hashlib.sha256(member["instructions"].encode()).hexdigest(),
            "config_hash": member["config_hash"],
            "knowledge_grants": [str(n) for n in config.get("knowledge_namespace_ids", [])],
            "capabilities": config.get("service_categories", []),
            "tool_descriptors": descriptors,
            "name": member["name"], "instructions": member["instructions"]}


class RoomTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=4000)
    assignee_agent_version_id: UUID
    status: Literal["pending", "in_progress", "blocked", "completed"]


class RoomMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1, max_length=256)
    sender_agent_version_id: UUID
    content: str = Field(min_length=1, max_length=20000)
    task_id: str | None = Field(default=None, max_length=256)


class RoomRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    status: Literal["succeeded", "failed"]


class Room(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasks: list[RoomTask] = Field(default_factory=list, max_length=200)
    messages: list[RoomMessage] = Field(default_factory=list, max_length=500)
    runs: list[RoomRun] = Field(default_factory=list, max_length=200)


TASK_STATUS = {"pending": "pending", "in_progress": "running", "blocked": "blocked", "completed": "done"}


@router.post("/teams/{team_id}/room", summary="Mirror the room's tasks, turns and specialist replies for management")
async def room(team_id: UUID, body: Room, db: Scope) -> dict[str, Any]:
    """Repeatable: a task is keyed by its id, a reply by its room message id, a run by its id."""
    team = await team_authority(db, team_id, lock=True)
    members = {str(row["version_id"]): row for row in (await db.execute(text(f"""
        select id,agent_id,version_id from team_members where team_id=:team and tenant_id={TENANT}
          and member_kind='specialist'
    """), {"team": team["id"]})).mappings()}
    for task in body.tasks:
        member = members.get(str(task.assignee_agent_version_id))
        if member is None:
            raise HTTPException(409, "A task is assigned to an agent that is not a member of this session")
        await db.execute(text(f"""
            insert into team_tasks(tenant_id,team_id,ticket_id,title,description,status,assigned_member_id,idempotency_key)
            values({TENANT},:team,:ticket,:title,:description,:status,:member,:key)
            on conflict (team_id,idempotency_key) do update
              set status=excluded.status,version=team_tasks.version+1,updated_at=now()
              where team_tasks.status<>excluded.status
        """), {"team": team["id"], "ticket": team["ticket_id"], "title": task.description[:120],
               "description": task.description, "status": TASK_STATUS[task.status], "member": member["id"],
               "key": task.task_id})
    stored = 0
    for message in body.messages:
        member = members.get(str(message.sender_agent_version_id))
        if member is None:
            raise HTTPException(409, "A reply comes from an agent that is not a member of this session")
        known = (await db.execute(text(f"""
            select 1 from messages where channel_id=:channel and tenant_id={TENANT}
              and body->>'sessionId'=:team and body->>'roomMessageId'=:message
        """), {"channel": team["channel_id"], "team": str(team["id"]), "message": message.message_id})).first()
        if known is None:
            await append_agent_message(db, team["channel_id"], member["agent_id"], "room", {
                "text": f"{team['ticket_code']}: {message.content}", "sessionId": str(team["id"]),
                "kind": "specialist_reply", "roomMessageId": message.message_id,
                **({"taskId": message.task_id} if message.task_id else {})})
            stored += 1
    for run in body.runs:
        await db.execute(text(f"""
            update agent_runs set status=:status,finished_at=now(),updated_at=now()
            where id=:run and tenant_id={TENANT} and status='running'
              and team_member_id in (select id from team_members where team_id=:team)
        """), {"run": run.run_id, "status": run.status, "team": team["id"]})
    return {"ok": True, "messages_stored": stored}


@router.get("/mentions", summary="Questions management asked a specialist inside a session, oldest first")
async def mentions(db: Scope, limit: int = Query(default=20, ge=1, le=50)) -> dict[str, Any]:
    """Queued questions only. One whose session is no longer current is refused here and not listed."""
    rows = (await db.execute(text(f"""
        select m.id as message_id,m.channel_id,cast(m.body->>'sessionId' as uuid) as team_id,mm.agent_id,
          substr(m.body->>'text',position(': ' in m.body->>'text')+2) as text,
          (select tm.version_id from team_members tm where tm.tenant_id=mm.tenant_id and tm.agent_id=mm.agent_id
             and tm.team_id=cast(m.body->>'sessionId' as uuid) and tm.member_kind='specialist' and tm.status='active'
          ) as version_id
        from message_mentions mm
        join messages m on m.id=mm.message_id and m.tenant_id=mm.tenant_id
        where mm.tenant_id={TENANT} and mm.status='queued' and m.body->>'kind'='session_question'
        order by m.created_at,m.id limit :limit
    """), {"limit": limit})).mappings().all()
    items = []
    for row in rows:
        try:
            team = await team_authority(db, row["team_id"])
            context = None if team["status"] in FINAL else await session_context(db, team, create=False)
        except HTTPException:
            context = None
        if context is None or row["version_id"] is None:
            await db.execute(text(f"""
                update message_mentions set status='refused' where tenant_id={TENANT} and message_id=:message
                  and agent_id=:agent and status='queued'
            """), {"message": row["message_id"], "agent": row["agent_id"]})
            continue
        # What was attached to the question: the text of text files, and its photos, which the runtime
        # hands to the specialist's model as pictures beside the text.
        attached, images = await for_agent(db, row["channel_id"], row["message_id"], pictures=True)
        items.append({"message_id": str(row["message_id"]), "team_id": str(row["team_id"]),
                      "agent_id": row["agent_id"], "agent_version_id": str(row["version_id"]),
                      "text": "\n\n".join(part for part in (row["text"], attached) if part), "context": context,
                      "images": images})
    return {"items": items}


class MentionOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["done", "failed"]
    run_id: UUID | None = None


@router.post("/teams/{team_id}/mentions/{message_id}", summary="What became of a question asked inside a session")
async def mention_outcome(team_id: UUID, message_id: UUID, body: MentionOutcome, db: Scope) -> dict[str, Any]:
    """Repeatable: only a question still waiting changes."""
    team = await team_authority(db, team_id)
    await db.execute(text(f"""
        update message_mentions mm set status=:status,resolved_run_id=:run
        from messages m where m.id=mm.message_id and m.tenant_id=mm.tenant_id and mm.tenant_id={TENANT}
          and mm.message_id=:message and m.body->>'sessionId'=:team and mm.status in ('queued','running')
    """), {"status": body.status, "run": body.run_id, "message": message_id, "team": str(team["id"])})
    return {"ok": True}


class ProposedCost(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    kind: str = Field(default="estimate", max_length=64)


class ProposedPlan(BaseModel):
    """The Supervisor's plan as its own flow describes one (agent-coordination, ProposedPlan)."""
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=4000)
    steps: list[str] = Field(min_length=1, max_length=20)
    performer_role: str = Field(min_length=1, max_length=500)
    expected_duration: str = Field(min_length=1, max_length=500)
    conditions: str = Field(min_length=1, max_length=2000)
    cost: ProposedCost | None
    result_refs: list[str] = Field(default_factory=list, max_length=50)
    attachment_ids: list[str] = Field(default_factory=list, max_length=50)


class PlanDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=160)
    payload_hash: str = Field(min_length=1, max_length=128)
    ticket_version: str = Field(pattern=r"^[0-9]+$", max_length=30)
    target_plan_version: int = Field(ge=1)
    plan: ProposedPlan


@router.post("/teams/{team_id}/plans", summary="Store the plan the Supervisor proposes, for management to decide")
async def propose_plan(team_id: UUID, body: PlanDraft, db: Scope) -> dict[str, Any]:
    """The plan enters the ordinary lifecycle as `management_pending`, with the Supervisor as its author.

    Storing it gives the ticket a new version, which is the version every later reply about this
    plan must carry. `payload_hash` is the runtime's fingerprint of its request: the same request
    again returns the stored plan, the same id with another fingerprint is refused. Nothing here
    approves the plan.
    """
    team = await team_authority(db, team_id, lock=True)
    if team["status"] in FINAL:
        raise HTTPException(409, "This Supervisor team has finished")
    # The ticket is locked so that its version and event sequence cannot move under this plan.
    team.update((await db.execute(text("""
        select version as ticket_version,status as ticket_status,last_event_seq,category_id
        from tickets where id=:id for update
    """), {"id": team["ticket_id"]})).mappings().one())
    stored = (await db.execute(text(f"""
        select id,request_hash,proposal from vh_ticket_plans where tenant_id={TENANT} and ticket_id=:ticket
          and idempotency_key=:key
    """), {"ticket": team["ticket_id"], "key": body.request_id})).mappings().first()
    if stored is None:
        if team["ticket_status"] in ("closed", "cancelled", "resolved"):
            raise HTTPException(409, "The ticket is final")
        if body.ticket_version != str(team["ticket_version"]):
            raise HTTPException(409, "The ticket changed since the Supervisor planned")
        if team["category_id"] is None:
            raise HTTPException(409, "A ticket without a service category cannot carry plan steps")
        if (await db.execute(text(f"""
            select 1 from vh_ticket_plans where tenant_id={TENANT} and ticket_id=:ticket
              and status in ('management_pending','resident_pending')
        """), {"ticket": team["ticket_id"]})).first():
            raise HTTPException(409, "Decide the existing plan first")
        # A plan step becomes a work order once the resident agrees. The Supervisor's steps are one
        # visit by one technician, so they are one work order; `proposal` keeps them as written.
        work = "\n".join(f"{n}. {step}" for n, step in enumerate(body.plan.steps, 1))[:2000]
        steps = [{"category_id": str(team["category_id"]), "description": work}]
        prior = (await db.execute(text(f"""
            select id,proposal from vh_ticket_plans where tenant_id={TENANT} and ticket_id=:ticket
              and proposed_by_agent_id=:agent and created_at>=(select created_at from agent_teams where id=:team)
            order by created_at desc limit 1
        """), {"ticket": team["ticket_id"], "agent": team["supervisor_agent_id"], "team": team_id})).mappings().first()
        expected = int(prior["proposal"]["plan_version"]) + 1 if prior else 1
        if body.target_plan_version != expected:
            raise HTTPException(409, "The proposed plan revision is out of order")
        proposal = {**body.plan.model_dump(mode="json"), "plan_version": body.target_plan_version}
        if prior:
            # The coordination core versions one plan aggregate. The ordinary UI keeps a row per
            # proposal so rejected text and both human decisions remain available for audit.
            proposal["root_plan_id"] = prior["proposal"].get("root_plan_id", str(prior["id"]))
        plan_id = (await db.execute(text(f"""
            insert into vh_ticket_plans(tenant_id,ticket_id,proposed_by_agent_id,title,steps,estimated_amount,status,
              idempotency_key,request_hash,proposal)
            values({TENANT},:ticket,:agent,:title,cast(:steps as jsonb),:amount,'management_pending',:key,:hash,
              cast(:proposal as jsonb)) returning id
        """), {"ticket": team["ticket_id"], "agent": team["supervisor_agent_id"], "title": body.plan.summary[:300],
               "steps": json.dumps(steps, ensure_ascii=False), "amount": body.plan.cost.amount if body.plan.cost else 0,
               "key": body.request_id, "hash": body.payload_hash,
               "proposal": json.dumps(proposal, ensure_ascii=False)})).scalar_one()
        seq = team["last_event_seq"] + 1
        await db.execute(text(f"""
            insert into ticket_events(tenant_id,ticket_id,seq,event_type,actor_kind,actor_agent_id,idempotency_key,
              correlation_id,payload,occurred_at,from_status)
            values({TENANT},:ticket,:seq,'plan.proposed','agent',:agent,:key,:correlation,cast(:payload as jsonb),now(),:status)
        """), {"ticket": team["ticket_id"], "seq": seq, "agent": team["supervisor_agent_id"], "key": body.request_id,
               "correlation": uuid4(), "payload": json.dumps({"planId": str(plan_id)}), "status": team["ticket_status"]})
        await db.execute(text("update tickets set last_event_seq=:seq,version=version+1,updated_at=now() where id=:id"),
                         {"seq": seq, "id": team["ticket_id"]})
        from .resident_cases import append_domain_event
        await append_domain_event(db, team["ticket_id"], "plan.proposed")
        await append_agent_message(db, team["channel_id"], team["supervisor_agent_id"], "room", {
            "text": f"{team['ticket_code']}: Supervisor đề xuất phương án, chờ Ban quản lý duyệt: {body.plan.summary}",
            "sessionId": str(team["id"]), "kind": "supervisor_plan", "planId": str(plan_id)})
        version = team["ticket_version"] + 1
    else:
        if stored["request_hash"] != body.payload_hash:
            raise HTTPException(409, "This request id was used for another plan")
        if stored["proposal"]["plan_version"] != body.target_plan_version:
            raise HTTPException(409, "This request id was used for another revision")
        proposal = stored["proposal"]
        plan_id, version = stored["id"], team["ticket_version"]
    return {"request_id": body.request_id, "status": "accepted", "payload_hash": body.payload_hash,
            "canonical_id": proposal.get("root_plan_id", str(plan_id)),
            "ticket_version": str(version), "plan_version": body.target_plan_version}


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str = Field(min_length=1, max_length=256)
    plan_version: int = Field(ge=1)


@router.post("/teams/{team_id}/plans/{plan_id}/approval-request",
             summary="Confirm that the proposed plan is waiting for management's decision")
async def plan_approval_request(team_id: UUID, plan_id: UUID, body: ApprovalRequest, db: Scope) -> dict[str, Any]:
    """The plan keeps the id the runtime gave its request, so management's decision can answer that request."""
    team = await team_authority(db, team_id, lock=True)
    plan = (await db.execute(text(f"""
        select id,status,proposal->>'management_approval_id' as approval,proposal->>'plan_version' as plan_version
        from vh_ticket_plans
        where tenant_id={TENANT} and (id=:plan or proposal->>'root_plan_id'=:root) and ticket_id=:ticket
          and proposed_by_agent_id=:agent order by created_at desc limit 1 for update
    """), {"plan": plan_id, "root": str(plan_id),
           "ticket": team["ticket_id"], "agent": team["supervisor_agent_id"]})).mappings().first()
    if plan is None:
        raise HTTPException(404, "No such plan of this session")
    if str(body.plan_version) != plan["plan_version"]:
        raise HTTPException(409, "The plan version does not match this request")
    if plan["approval"] != body.approval_id:
        if plan["approval"] is not None or plan["status"] != "management_pending":
            raise HTTPException(409, "This plan is no longer waiting for this request")
        await db.execute(text("update vh_ticket_plans set proposal=proposal||cast(:request as jsonb) where id=:plan"), {
            "plan": plan["id"], "request": json.dumps({"management_approval_id": body.approval_id,
                                                    "plan_version": body.plan_version})})
    return {"status": "accepted", "plan_id": str(plan_id)}


@router.get("/events", summary="Management's decisions on Supervisor plans, not yet taken by the runtime")
async def events(db: Scope) -> dict[str, Any]:
    rows = (await db.execute(text(f"""
        select p.id,p.status,p.management_note,p.management_at,p.resident_at,p.proposal,tm.id as team_id
        from vh_ticket_plans p
        join agent_teams tm on tm.tenant_id=p.tenant_id and tm.ticket_id=p.ticket_id
          and tm.supervisor_agent_id=p.proposed_by_agent_id and tm.created_at<=p.created_at
          and tm.status not in ('completed','failed','cancelled')
        where p.tenant_id={TENANT} and p.management_at is not null
          and p.proposal ? 'management_approval_id' and not (p.proposal ? 'management_decision_delivered')
        order by p.management_at limit 50
    """))).mappings().all()
    items = []
    for row in rows:
        try:
            team = await team_authority(db, row["team_id"])
        except HTTPException:
            continue  # the team is no longer current: nothing waits for this decision
        context = await session_context(db, team, create=False)
        if context is None:
            continue
        # A plan the resident later refused was still approved by management.
        decision = "reject" if row["status"] == "rejected" and row["resident_at"] is None else "approve"
        items.append({"team_id": str(row["team_id"]), "plan_id": str(row["id"]), "context": context, "event": {
            "event_id": f"plan-management-decision:{row['id']}", "event_type": "approval.responded",
            "schema_version": "1", "tenant_id": context["tenant_id"], "aggregate_id": str(row["id"]),
            "aggregate_version": 1, "occurred_at": row["management_at"].isoformat(),
            "correlation_id": str(row["team_id"]), "causation_id": row["proposal"]["management_approval_id"],
            "payload": {"approval_id": row["proposal"]["management_approval_id"],
                        "plan_id": row["proposal"].get("root_plan_id", str(row["id"])),
                        "plan_version": row["proposal"]["plan_version"], "stage": "management_plan",
                        "decision": decision, "comment": row["management_note"]}}})
    return {"items": items}


@router.get("/teams/{team_id}/plans/{plan_id}/management-event",
            summary="Verify a committed management decision, including after delivery")
async def management_event(team_id: UUID, plan_id: UUID, db: Scope) -> dict[str, Any]:
    team = await team_authority(db, team_id)
    row = (await db.execute(text(f"""
        select id,status,management_note,management_at,resident_at,proposal from vh_ticket_plans
        where tenant_id={TENANT} and id=:plan and ticket_id=:ticket and proposed_by_agent_id=:agent
          and created_at>=(select created_at from agent_teams where id=:team)
    """), {"plan": plan_id, "ticket": team["ticket_id"], "agent": team["supervisor_agent_id"],
           "team": team_id})).mappings().first()
    if row is None or row["management_at"] is None or "management_approval_id" not in row["proposal"]:
        raise HTTPException(404, "No committed management decision for this request")
    context = await session_context(db, team, create=False)
    if context is None:
        raise HTTPException(409, "The session has no runtime binding")
    decision = "reject" if row["status"] == "rejected" and row["resident_at"] is None else "approve"
    return {"context": context, "event": {
        "event_id": f"plan-management-decision:{row['id']}", "event_type": "approval.responded",
        "schema_version": "1", "tenant_id": context["tenant_id"], "aggregate_id": str(row["id"]),
        "aggregate_version": 1, "occurred_at": row["management_at"].isoformat(),
        "correlation_id": str(team_id), "causation_id": row["proposal"]["management_approval_id"],
        "payload": {"approval_id": row["proposal"]["management_approval_id"],
                    "plan_id": row["proposal"].get("root_plan_id", str(row["id"])),
                    "plan_version": row["proposal"]["plan_version"], "stage": "management_plan",
                    "decision": decision, "comment": row["management_note"]}}}


@router.post("/teams/{team_id}/plans/{plan_id}/decision-delivered",
             summary="The runtime holds management's decision on this plan; stop listing it")
async def plan_decision_delivered(team_id: UUID, plan_id: UUID, db: Scope) -> dict[str, Any]:
    team = await team_authority(db, team_id)
    marked = await db.execute(text(f"""
        update vh_ticket_plans set proposal=proposal||cast(:delivered as jsonb)
        where tenant_id={TENANT} and id=:plan and ticket_id=:ticket and proposed_by_agent_id=:agent
          and management_at is not null
    """), {"plan": plan_id, "ticket": team["ticket_id"], "agent": team["supervisor_agent_id"],
           "delivered": json.dumps({"management_decision_delivered": True})})
    if marked.rowcount != 1:
        raise HTTPException(404, "No decided plan of this session")
    return {"ok": True}


class QuestionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1, max_length=160)
    payload_hash: str = Field(min_length=1, max_length=128)
    ticket_version: str = Field(pattern=r"^[0-9]+$", max_length=30)
    question: str = Field(min_length=1, max_length=4000)


@router.post("/teams/{team_id}/questions", summary="Store and version a question before Reception asks the resident")
async def propose_question(team_id: UUID, body: QuestionDraft, db: Scope) -> dict[str, Any]:
    team = await team_authority(db, team_id, lock=True)
    requests = team["shared_state"].get("residentRequests", {})
    old = requests.get(body.request_id)
    if old:
        if old["payload_hash"] != body.payload_hash or old["message"] != body.question:
            raise HTTPException(409, "This request id was used for another question")
        return {"request_id": body.request_id, "status": "accepted", "payload_hash": body.payload_hash,
                "canonical_id": body.request_id, "ticket_version": old["ticket_version"]}
    ticket = (await db.execute(text("select version,status,last_event_seq from tickets where id=:id for update"),
                              {"id": team["ticket_id"]})).mappings().one()
    if (body.ticket_version != str(ticket["version"]) or ticket["status"] in ('closed','cancelled','resolved')
            or team["status"] in FINAL or any(not q.get("resolved") for q in requests.values())):
        raise HTTPException(409, "The ticket changed or a resident question is already pending")
    if (await db.execute(text(f"""select 1 from vh_ticket_plans where tenant_id={TENANT}
        and ticket_id=:ticket and status in ('management_pending','resident_pending')"""),
        {"ticket": team["ticket_id"]})).first():
        raise HTTPException(409, "Decide the pending plan before asking another question")
    version = str(ticket["version"] + 1)
    requests[body.request_id] = {"payload_hash": body.payload_hash, "message": body.question,
                                "ticket_version": version, "resolved": False}
    await db.execute(text("""update agent_teams set shared_state=shared_state||
        jsonb_build_object('residentRequests',cast(:requests as jsonb)) where id=:team"""),
        {"team": team_id, "requests": json.dumps(requests, ensure_ascii=False)})
    await db.execute(text(f"""insert into ticket_events(tenant_id,ticket_id,seq,event_type,actor_kind,
        actor_agent_id,idempotency_key,correlation_id,payload,occurred_at)
        values({TENANT},:ticket,:seq,'supervisor.information_requested','agent',:agent,:key,:correlation,
        cast(:payload as jsonb),now())"""), {"ticket": team["ticket_id"], "seq": ticket["last_event_seq"] + 1,
        "agent": team["supervisor_agent_id"], "key": body.request_id, "correlation": uuid4(),
        "payload": json.dumps({"requestId": body.request_id})})
    await db.execute(text("update tickets set version=version+1,last_event_seq=last_event_seq+1,updated_at=now() where id=:id"),
                     {"id": team["ticket_id"]})
    return {"request_id": body.request_id, "status": "accepted", "payload_hash": body.payload_hash,
            "canonical_id": body.request_id, "ticket_version": version}


@router.get('/controls', summary='Management session controls waiting for the runtime')
async def pending_controls(db: Scope):
    rows = (await db.execute(text(f"""select id,shared_state->'controlRequests' as controls from agent_teams
        where tenant_id={TENANT} and status not in ('completed','failed','cancelled')
        and shared_state ? 'controlRequests' order by created_at"""))).mappings().all()
    items = []
    for row in rows:
        for command in row['controls'].values():
            if command['status'] != 'queued':
                continue
            try:
                team = await team_authority(db, row['id'])
                context = await session_context(db, team, create=False)
            except HTTPException:
                continue
            if context:
                items.append({'team_id': str(row['id']), 'context': context, 'command': command})
                if len(items) >= 50:
                    return {'items': items}
    return {'items': items}


@router.get('/teams/{team_id}/controls/{request_id}')
async def verify_control(team_id: UUID, request_id: str, db: Scope):
    team = await team_authority(db, team_id)
    command = team['shared_state'].get('controlRequests', {}).get(request_id)
    if command is None:
        raise HTTPException(404, 'No such committed management control')
    # Check the requester's current room and ticket authority as well as the service identity.
    from .v3_team_board import access
    await access((db, command['actor']), team_id)
    return {'context': await session_context(db, team, create=False), 'command': command}


class ControlOutcome(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['applied','refused']
    reason: str | None = Field(default=None, max_length=200)
    phase: str = Field(max_length=64)
    state_version: int = Field(ge=0)


@router.post('/teams/{team_id}/controls/{request_id}')
async def finish_control(team_id: UUID, request_id: str, body: ControlOutcome, db: Scope):
    team = await team_authority(db, team_id, lock=True)
    controls = team['shared_state'].get('controlRequests', {})
    command = controls.get(request_id)
    if command is None:
        raise HTTPException(404, 'No such management control')
    result = body.model_dump()
    if command['status'] != 'queued':
        if command.get('result') != result:
            raise HTTPException(409, 'A different control outcome was already recorded')
        return {'ok': True}
    command['status'], command['result'] = body.status, result
    await db.execute(text("""update agent_teams set shared_state=shared_state||
        jsonb_build_object('controlRequests',cast(:controls as jsonb),'runtime',cast(:runtime as jsonb)),
        status=case when :stopped then 'cancelled' else status end,
        finished_at=case when :stopped then now() else finished_at end,updated_at=now() where id=:team"""), {
        'team': team_id, 'controls': json.dumps(controls),
        'runtime': json.dumps({'phase': body.phase, 'pauseReason': body.reason, 'stateVersion': body.state_version}),
        'stopped': body.status == 'applied' and command['operation'] == 'stop'})
    return {'ok': True}
