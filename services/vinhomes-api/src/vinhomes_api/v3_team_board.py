"""Shared task board and mailbox persistence; this service does not execute teams."""

import json
from typing import Annotated, Literal
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from .v3_auth import resident_connection
from .v3_room_agents import managed_room
from .v3_mutations import visible_ticket
from .v3_audit import audit

router = APIRouter(tags=["V3 shared task board and mailbox"])
Scope = Annotated[tuple[AsyncConnection, str], Depends(resident_connection)]
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"


async def ticket_scope(scope: Scope):
    admin = (
        await scope[0].execute(
            text("select exists(select 1 from platform_admins where user_id=:actor)"),
            {"actor": scope[1]},
        )
    ).scalar_one()
    return (scope[0], scope[1], admin)


async def access(scope: Scope, team_id: UUID, lock=False):
    ref = (
        (
            await scope[0].execute(
                text("select channel_id from agent_teams where id=:id"), {"id": team_id}
            )
        )
        .mappings()
        .first()
    )
    if ref is None:
        raise HTTPException(404, "Team not found")
    room = await managed_room(scope, ref["channel_id"])
    row = (
        (
            await scope[0].execute(
                text(
                    "select * from agent_teams where id=:id"
                    + (" for update" if lock else "")
                ),
                {"id": team_id},
            )
        )
        .mappings()
        .one()
    )
    if row["workspace_id"] != room["workspace_id"]:
        raise HTTPException(404, "Team workspace mismatch")
    await visible_ticket(await ticket_scope(scope), row["ticket_id"])
    return dict(row)


class TeamCreate(BaseModel):
    ticket_id: UUID
    supervisor_version_id: UUID
    member_version_ids: list[UUID] = Field(default_factory=list, max_length=20)
    idempotency_key: str = Field(min_length=1, max_length=160)


@router.post("/rooms/{room_id}/teams", status_code=201)
async def create(room_id: str, body: TeamCreate, scope: Scope):
    room = await managed_room(scope, room_id)
    ticket = await visible_ticket(await ticket_scope(scope), body.ticket_id, lock=True)
    if ticket["management_unit_id"] != room["management_unit_id"]:
        raise HTTPException(422, "Ticket must belong to room management")
    tenant = (
        await scope[0].execute(text("select current_setting('app.tenant_id')"))
    ).scalar_one()
    team_id = uuid5(
        NAMESPACE_URL,
        f"team:{tenant}:{room_id}:{body.ticket_id}:{ticket['reopen_count']}:{scope[1]}:{body.idempotency_key}",
    )
    data = body.model_dump(mode="json", exclude={"idempotency_key"})
    old = (
        (
            await scope[0].execute(
                text("select shared_state from agent_teams where id=:id"),
                {"id": team_id},
            )
        )
        .mappings()
        .first()
    )
    if old:
        if old["shared_state"].get("request") != data:
            raise HTTPException(409, "Team key already used")
        return await detail(team_id, scope)
    members = []
    for version_id in dict.fromkeys(
        [body.supervisor_version_id, *body.member_version_ids]
    ):
        row = (
            (
                await scope[0].execute(
                    text(
                        "select a.id,a.purpose from agent_versions v join agents a on a.id=v.agent_id and a.tenant_id=v.tenant_id join channel_agents ca on ca.agent_id=a.id and ca.tenant_id=a.tenant_id where v.id=:version and a.workspace_id=:workspace and a.status='active' and ca.channel_id=:room"
                    ),
                    {
                        "version": version_id,
                        "workspace": room["workspace_id"],
                        "room": room_id,
                    },
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise HTTPException(422, "Approved agent version in this room required")
        if version_id == body.supervisor_version_id and row["purpose"] != "supervisor":
            raise HTTPException(422, "Supervisor version required")
        if any(m[0] == row["id"] for m in members):
            raise HTTPException(422, "Use one version per agent")
        members.append((row["id"], version_id))
    await scope[0].execute(
        text(
            f"insert into agent_teams(id,tenant_id,workspace_id,channel_id,ticket_id,ticket_generation,supervisor_agent_id,status,shared_state,requested_by_user_id) values(:id,{TENANT},:workspace,:room,:ticket,:generation,:supervisor,'queued',cast(:state as jsonb),:actor)"
        ),
        {
            "id": team_id,
            "workspace": room["workspace_id"],
            "room": room_id,
            "ticket": body.ticket_id,
            "generation": ticket["reopen_count"],
            "supervisor": members[0][0],
            "state": json.dumps({"request": data}),
            "actor": scope[1],
        },
    )
    for agent, version in members:
        await scope[0].execute(
            text(
                f"insert into team_members(tenant_id,team_id,agent_id,version_id,member_kind,status) values({TENANT},:team,:agent,:version,:kind,'active')"
            ),
            {
                "team": team_id,
                "agent": agent,
                "version": version,
                "kind": "supervisor"
                if version == body.supervisor_version_id
                else "specialist",
            },
        )
    await audit(
        scope[0],
        scope[1],
        "team.created",
        "agent_team",
        str(team_id),
        {"ticketId": body.ticket_id},
    )
    return await detail(team_id, scope)


@router.get("/rooms/{room_id}/teams")
async def teams(room_id: str, scope: Scope):
    await managed_room(scope, room_id)
    rows = await scope[0].execute(
        text(
            # With the ticket's code and what the Supervisor runtime last reported, for the room's session list.
            "select tm.id,tm.ticket_id,tm.status,tm.state_version,tm.created_at,t.code as ticket_code,t.title as ticket_title,"
            "tm.shared_state->'runtime' as runtime from agent_teams tm join tickets t on t.id=tm.ticket_id and t.tenant_id=tm.tenant_id "
            "where tm.channel_id=:room order by tm.created_at desc limit 100"
        ),
        {"room": room_id},
    )
    items = []
    for row in rows.mappings():
        try:
            await visible_ticket(await ticket_scope(scope), row["ticket_id"])
            items.append(dict(row))
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
    return {"items": items}


@router.get("/teams/{team_id}")
async def detail(team_id: UUID, scope: Scope):
    team = await access(scope, team_id)
    members = await scope[0].execute(
        text(
            "select id,agent_id,version_id,member_kind,status from team_members where team_id=:id"
        ),
        {"id": team_id},
    )
    return {
        "team": team,
        "members": [dict(r) for r in members.mappings()],
        "execution": "record-only; runtime integration separate",
    }


async def member(scope: Scope, team_id: UUID, member_id: UUID):
    row = await scope[0].execute(
        text(
            "select 1 from team_members where id=:id and team_id=:team and status='active'"
        ),
        {"id": member_id, "team": team_id},
    )
    if row.first() is None:
        raise HTTPException(422, "Active member of this team required")


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=5000)
    assigned_member_id: UUID | None = None
    parent_task_id: UUID | None = None
    priority: int = Field(default=0, ge=0, le=100)
    idempotency_key: str = Field(min_length=1, max_length=160)


@router.post("/teams/{team_id}/tasks", status_code=201)
async def create_task(team_id: UUID, body: TaskCreate, scope: Scope):
    team = await access(scope, team_id, True)
    if team["status"] in {"completed", "failed", "cancelled"}:
        raise HTTPException(409, "Team is final")
    if body.assigned_member_id:
        await member(scope, team_id, body.assigned_member_id)
    if body.parent_task_id:
        parent = await scope[0].execute(
            text("select 1 from team_tasks where id=:id and team_id=:team"),
            {"id": body.parent_task_id, "team": team_id},
        )
        if parent.first() is None:
            raise HTTPException(422, "Parent task must belong to this team")
    old = (
        (
            await scope[0].execute(
                text(
                    "select * from team_tasks where team_id=:team and idempotency_key=:key"
                ),
                {"team": team_id, "key": body.idempotency_key},
            )
        )
        .mappings()
        .first()
    )
    if old:
        if any(
            old[k] != getattr(body, k)
            for k in [
                "title",
                "description",
                "assigned_member_id",
                "parent_task_id",
                "priority",
            ]
        ):
            raise HTTPException(409, "Task key already used")
        return dict(old)
    row = await scope[0].execute(
        text(
            f"insert into team_tasks(tenant_id,team_id,ticket_id,parent_task_id,title,description,status,priority,assigned_member_id,idempotency_key) values({TENANT},:team,:ticket,:parent,:title,:description,'ready',:priority,:member,:key) returning *"
        ),
        {
            "team": team_id,
            "ticket": team["ticket_id"],
            "parent": body.parent_task_id,
            "title": body.title,
            "description": body.description,
            "priority": body.priority,
            "member": body.assigned_member_id,
            "key": body.idempotency_key,
        },
    )
    return dict(row.mappings().one())


@router.get("/teams/{team_id}/tasks")
async def tasks(team_id: UUID, scope: Scope):
    await access(scope, team_id)
    rows = await scope[0].execute(
        text(
            "select * from team_tasks where team_id=:id order by priority desc,created_at limit 200"
        ),
        {"id": team_id},
    )
    return {"items": [dict(r) for r in rows.mappings()]}


class TaskUpdate(BaseModel):
    status: Literal["running", "blocked", "done", "failed", "cancelled", "ready"]
    version: int = Field(ge=0)
    result: dict[str, str | int | bool] = Field(default_factory=dict, max_length=30)


@router.patch("/teams/{team_id}/tasks/{task_id}")
async def update_task(team_id: UUID, task_id: UUID, body: TaskUpdate, scope: Scope):
    team = await access(scope, team_id, True)
    if team["status"] in {"completed", "failed", "cancelled"}:
        raise HTTPException(409, "Team is final")
    row = (
        (
            await scope[0].execute(
                text(
                    "select * from team_tasks where id=:id and team_id=:team for update"
                ),
                {"id": task_id, "team": team_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Task not found")
    allowed = {
        "ready": {"running", "cancelled"},
        "running": {"blocked", "done", "failed", "cancelled"},
        "blocked": {"ready", "running", "cancelled"},
        "failed": {"ready", "cancelled"},
    }
    if row["version"] != body.version or body.status not in allowed.get(
        row["status"], set()
    ):
        raise HTTPException(409, "Task state or version changed")
    if body.status == "done" and not body.result:
        raise HTTPException(422, "Task result required")
    result = await scope[0].execute(
        text(
            "update team_tasks set status=:status,result=cast(:result as jsonb),version=version+1,updated_at=now() where id=:id returning *"
        ),
        {"id": task_id, "status": body.status, "result": json.dumps(body.result)},
    )
    return dict(result.mappings().one())


class MailCreate(BaseModel):
    sender_member_id: UUID
    recipient_member_id: UUID | None = None
    task_id: UUID | None = None
    message_kind: Literal["direct", "broadcast", "result"]
    text: str = Field(min_length=1, max_length=5000)
    idempotency_key: str = Field(min_length=1, max_length=160)


@router.post("/teams/{team_id}/mailbox", status_code=201)
async def send_mail(team_id: UUID, body: MailCreate, scope: Scope):
    team = await access(scope, team_id, True)
    if team["status"] in {"completed", "failed", "cancelled"}:
        raise HTTPException(409, "Team is final")
    await member(scope, team_id, body.sender_member_id)
    if body.recipient_member_id:
        await member(scope, team_id, body.recipient_member_id)
    if (body.message_kind == "direct" and not body.recipient_member_id) or (
        body.message_kind == "broadcast" and body.recipient_member_id
    ):
        raise HTTPException(
            422, "Direct requires recipient; broadcast requires no recipient"
        )
    if body.task_id:
        task = await scope[0].execute(
            text("select 1 from team_tasks where id=:id and team_id=:team"),
            {"id": body.task_id, "team": team_id},
        )
        if task.first() is None:
            raise HTTPException(422, "Task must belong to team")
    old = (
        (
            await scope[0].execute(
                text(
                    "select * from team_mailbox where team_id=:team and idempotency_key=:key"
                ),
                {"team": team_id, "key": body.idempotency_key},
            )
        )
        .mappings()
        .first()
    )
    content = {"text": body.text, "requestedByUserId": scope[1]}
    if old:
        if old["content"] != content or any(
            old[k] != getattr(body, k)
            for k in [
                "sender_member_id",
                "recipient_member_id",
                "task_id",
                "message_kind",
            ]
        ):
            raise HTTPException(409, "Mailbox key already used")
        return dict(old)
    row = await scope[0].execute(
        text(
            f"insert into team_mailbox(tenant_id,team_id,sender_member_id,recipient_member_id,task_id,message_kind,content,correlation_id,idempotency_key) values({TENANT},:team,:sender,:recipient,:task,:kind,cast(:content as jsonb),:correlation,:key) returning *"
        ),
        {
            "team": team_id,
            "sender": body.sender_member_id,
            "recipient": body.recipient_member_id,
            "task": body.task_id,
            "kind": body.message_kind,
            "content": json.dumps(content),
            "correlation": uuid4(),
            "key": body.idempotency_key,
        },
    )
    return dict(row.mappings().one())


@router.get("/teams/{team_id}/mailbox")
async def mailbox(
    team_id: UUID,
    scope: Scope,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    await access(scope, team_id)
    rows = await scope[0].execute(
        text(
            "select * from team_mailbox where team_id=:id order by created_at,id limit :limit offset :offset"
        ),
        {"id": team_id, "limit": limit, "offset": offset},
    )
    return {"items": [dict(r) for r in rows.mappings()]}


class TeamState(BaseModel):
    version: int = Field(ge=0)
    status: Literal["running", "waiting", "completed", "failed", "cancelled"]
    state: dict[str, str | int | bool] = Field(default_factory=dict, max_length=30)


@router.patch("/teams/{team_id}/state")
async def state(team_id: UUID, body: TeamState, scope: Scope):
    team = await access(scope, team_id, True)
    transitions = {
        "queued": {"running", "cancelled"},
        "running": {"waiting", "completed", "failed", "cancelled"},
        "waiting": {"running", "failed", "cancelled"},
    }
    if team["state_version"] != body.version or body.status not in transitions.get(
        team["status"], set()
    ):
        raise HTTPException(409, "Team state or version changed")
    if body.status == "completed":
        remaining = await scope[0].execute(
            text(
                "select 1 from team_tasks where team_id=:id and status not in ('done','cancelled') limit 1"
            ),
            {"id": team_id},
        )
        if remaining.first():
            raise HTTPException(409, "Finish tasks before marking team complete")
    shared = {**team["shared_state"], "context": body.state}
    row = await scope[0].execute(
        text(
            "update agent_teams set status=:status,shared_state=cast(:state as jsonb),state_version=state_version+1,finished_at=case when :status in ('completed','failed','cancelled') then now() else null end,updated_at=now() where id=:id returning *"
        ),
        {"id": team_id, "status": body.status, "state": json.dumps(shared)},
    )
    await audit(
        scope[0],
        scope[1],
        "team.state_changed",
        "agent_team",
        str(team_id),
        {"status": body.status},
    )
    return {"team": dict(row.mappings().one()), "ticketStateChanged": False}


@router.get("/rooms/{room_id}/context")
async def context(
    room_id: str,
    scope: Scope,
    ticket_id: UUID = Query(..., alias="ticketId"),
    message_limit: int = Query(20, ge=1, le=50),
):
    room = await managed_room(scope, room_id)
    ticket = await visible_ticket(await ticket_scope(scope), ticket_id)
    if ticket["management_unit_id"] != room["management_unit_id"]:
        raise HTTPException(422, "Ticket outside room management")
    messages = await scope[0].execute(
        text(
            "select id,seq,sender_kind,sender_user_id,sender_agent_id,body,created_at from messages where channel_id=:room and visibility='room' order by seq desc limit :limit"
        ),
        {"room": room_id, "limit": message_limit},
    )
    tasks = await scope[0].execute(
        text(
            "select t.id,t.title,t.status,t.result,t.assigned_member_id from team_tasks t join agent_teams team on team.id=t.team_id and team.tenant_id=t.tenant_id where team.channel_id=:room and t.ticket_id=:ticket order by t.created_at limit 100"
        ),
        {"room": room_id, "ticket": ticket_id},
    )
    return {
        "ticket": ticket,
        "messages": list(reversed([dict(r) for r in messages.mappings()])),
        "tasks": [dict(r) for r in tasks.mappings()],
        "contextSelection": "bounded API data; runtime constructs the model prompt",
    }
