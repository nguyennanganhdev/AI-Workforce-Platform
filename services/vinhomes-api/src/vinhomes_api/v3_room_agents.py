"""Manage agent records in an authorized room; no tool or LLM execution."""

import json
from typing import Annotated, Literal
from uuid import uuid5, NAMESPACE_URL
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from .v3_auth import resident_connection
from .v3_rooms import _room
from .v3_audit import audit

router = APIRouter(tags=["Vinhomes V3 room agents"])
Scope = Annotated[tuple[AsyncConnection, str], Depends(resident_connection)]


async def managed_room(scope: Scope, room_id: str, *, lock: bool = True) -> dict[str, object]:
    await _room(scope, room_id, lock=lock)
    result = await scope[0].execute(
        text("""
        select c.workspace_id,w.management_unit_id from channels c
        join workspaces w on w.id=c.workspace_id and w.tenant_id=c.tenant_id and w.status='active'
        where c.id=:room and (exists (select 1 from platform_admins where user_id=:actor)
          or exists (select 1 from scoped_user_roles r
            join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
            join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
            where m.user_id=:actor and m.status='active' and r.role_code='management'
              and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
              and (s.kind='tenant' or (s.kind='management' and s.management_unit_id=w.management_unit_id))))
    """),
        {"room": room_id, "actor": scope[1]},
    )
    room = result.mappings().first()
    if room is None:
        raise HTTPException(403, "Room management permission required")
    return dict(room)


async def room_agents(room_id: str, scope: Scope) -> dict[str, object]:
    await _room(scope, room_id)
    result = await scope[0].execute(
        text("""
        select a.id,a.name,a.purpose,a.type,a.status,a.workspace_id,
          exists(select 1 from agent_releases rel join agent_versions v on v.id=rel.version_id and v.tenant_id=rel.tenant_id
            where rel.agent_id=a.id and rel.status='published' and rel.revoked_at is null
              and v.version_no=(select max(v2.version_no) from agent_versions v2 where v2.agent_id=a.id)) as published
        from channel_agents ca
        join agents a on a.id=ca.agent_id and a.tenant_id=ca.tenant_id
        where ca.channel_id=:room order by a.name
    """),
        {"room": room_id},
    )
    return {"items": [dict(row) for row in result.mappings()]}


@router.get("/rooms/{room_id}/available-agents")
async def available_agents(room_id: str, scope: Scope) -> dict[str, object]:
    room = await managed_room(scope, room_id)
    result = await scope[0].execute(
        text("""
        select id,name,purpose,type,status from agents a where a.workspace_id=:workspace and a.status='active'
          and not exists (select 1 from channel_agents ca where ca.agent_id=a.id and ca.channel_id=:room)
        order by name
    """),
        {"workspace": room["workspace_id"], "room": room_id},
    )
    return {"items": [dict(row) for row in result.mappings()]}


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    purpose: Literal["specialist", "supervisor"] = "specialist"
    instructions: str = Field(min_length=1, max_length=5000)
    idempotency_key: str = Field(min_length=1, max_length=160)


@router.post("/rooms/{room_id}/agents", status_code=201)
async def create_agent(
    room_id: str, body: AgentCreate, request: Request, scope: Scope
) -> dict[str, object]:
    room = await managed_room(scope, room_id)
    tenant = await scope[0].execute(text("select current_setting('app.tenant_id')"))
    agent_id = str(
        uuid5(
            NAMESPACE_URL,
            f"agent:{tenant.scalar_one()}:{room_id}:{scope[1]}:{body.idempotency_key}",
        )
    )
    configuration = {
        "instructions": body.instructions,
        "demo": request.app.state.settings.demo_mode,
    }
    prior = await scope[0].execute(
        text("select * from agents where id=:id"), {"id": agent_id}
    )
    existing = prior.mappings().first()
    if existing:
        if (
            existing["name"] != body.name
            or existing["purpose"] != body.purpose
            or existing["configuration"] != configuration
        ):
            raise HTTPException(409, "Agent key already used with different content")
    else:
        await scope[0].execute(
            text("""
            insert into agents(id,tenant_id,workspace_id,name,type,configuration,purpose,status)
            values (:id,nullif(current_setting('app.tenant_id',true),'')::uuid,:workspace,:name,'built_in',cast(:configuration as jsonb),:purpose,'draft')
        """),
            {
                "id": agent_id,
                "workspace": room["workspace_id"],
                "name": body.name,
                "configuration": json.dumps(configuration),
                "purpose": body.purpose,
            },
        )
        await audit(
            scope[0],
            scope[1],
            "room.agent_created",
            "agent",
            agent_id,
            {"roomId": room_id, "workspaceId": room["workspace_id"]},
        )
    await scope[0].execute(
        text("""
        insert into channel_agents(tenant_id,channel_id,agent_id)
        values (nullif(current_setting('app.tenant_id',true),'')::uuid,:room,:agent)
        on conflict (channel_id,agent_id) do nothing
    """),
        {"room": room_id, "agent": agent_id},
    )
    return {
        "id": agent_id,
        "name": body.name,
        "purpose": body.purpose,
        "roomId": room_id,
        "status": existing["status"] if existing else "draft",
        "execution": "record-only",
    }


@router.post("/rooms/{room_id}/agents/{agent_id}")
async def add_agent(room_id: str, agent_id: str, scope: Scope) -> dict[str, object]:
    room = await managed_room(scope, room_id)
    agent = await scope[0].execute(
        text(
            "select id from agents where id=:id and workspace_id=:workspace and status='active'"
        ),
        {"id": agent_id, "workspace": room["workspace_id"]},
    )
    if agent.first() is None:
        raise HTTPException(404, "Active agent in this workspace required")
    added = await scope[0].execute(
        text("""
        insert into channel_agents(tenant_id,channel_id,agent_id)
        values (nullif(current_setting('app.tenant_id',true),'')::uuid,:room,:agent)
        on conflict (channel_id,agent_id) do nothing returning agent_id
    """),
        {"room": room_id, "agent": agent_id},
    )
    if added.first():
        await audit(
            scope[0],
            scope[1],
            "room.agent_added",
            "agent",
            agent_id,
            {"roomId": room_id},
        )
    return {"roomId": room_id, "agentId": agent_id, "status": "added"}
