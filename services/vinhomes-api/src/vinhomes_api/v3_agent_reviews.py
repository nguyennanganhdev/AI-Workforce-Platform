"""Accept evaluation records and admin decisions; no evaluator or model runtime."""

import json
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from .v3_auth import scoped_connection, resident_connection
from .v3_room_agents import managed_room
from .v3_security import digest
from .v3_audit import audit

router = APIRouter(tags=["V3 agent evaluation approval records"])
Member = Annotated[tuple[AsyncConnection, str], Depends(resident_connection)]
Admin = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection)]
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"


async def room_agent(scope: Member, room_id: str, agent_id: str):
    room = await managed_room(scope, room_id)
    agent = (
        (
            await scope[0].execute(
                text(
                    "select a.* from agents a join channel_agents ca on ca.agent_id=a.id and ca.tenant_id=a.tenant_id where a.id=:id and a.workspace_id=:workspace and ca.channel_id=:room for update of a"
                ),
                {"id": agent_id, "workspace": room["workspace_id"], "room": room_id},
            )
        )
        .mappings()
        .first()
    )
    if agent is None:
        raise HTTPException(404, "Agent in this managed room required")
    return dict(agent)


class ToolReference(BaseModel):
    server_id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=160)


class AgentConfiguration(BaseModel):
    instructions: str = Field(min_length=1, max_length=10000)
    description: str = Field(min_length=1, max_length=2000)
    mcp_tools: list[ToolReference] = Field(default_factory=list, max_length=50)
    knowledge_namespace_ids: list[UUID] = Field(default_factory=list, max_length=20)
    # Ticket categories this agent serves. A Supervisor is offered it only for those tickets.
    service_categories: list[str] = Field(default_factory=list, max_length=10)
    framework_version: str = Field(
        default="demo-record-only", min_length=1, max_length=120
    )


@router.put("/rooms/{room_id}/agents/{agent_id}/configuration")
async def configure(
    room_id: str, agent_id: str, body: AgentConfiguration, scope: Member
):
    agent = await room_agent(scope, room_id, agent_id)
    if agent["status"] != "draft":
        raise HTTPException(409, "Only draft agents can be configured")
    pending = await scope[0].execute(
        text("select 1 from vh_agent_reviews where agent_id=:id and status='pending'"),
        {"id": agent_id},
    )
    if pending.first():
        raise HTTPException(409, "Wait for the current admin review")
    for tool in body.mcp_tools:
        available = await scope[0].execute(
            text("select 1 from mcp_tools where server_id=:server and name=:name"),
            {"server": tool.server_id, "name": tool.name},
        )
        if available.first() is None:
            raise HTTPException(422, "Unknown tenant MCP tool")
    for nid in body.knowledge_namespace_ids:
        available = await scope[0].execute(
            text(
                "select 1 from memory_namespaces where id=:id and workspace_id=:workspace and status='active'"
            ),
            {"id": nid, "workspace": agent["workspace_id"]},
        )
        if available.first() is None:
            raise HTTPException(422, "Namespace outside the agent workspace")
    for code in body.service_categories:
        available = await scope[0].execute(
            text("select 1 from service_categories where code=:code and enabled"),
            {"code": code},
        )
        if available.first() is None:
            raise HTTPException(422, "Unknown service category")
    config = body.model_dump(mode="json")
    await scope[0].execute(
        text("update agents set configuration=cast(:config as jsonb) where id=:id"),
        {"config": json.dumps(config), "id": agent_id},
    )
    await audit(
        scope[0],
        scope[1],
        "agent.configured",
        "agent",
        agent_id,
        {"configHash": digest(config)},
    )
    return {"agentId": agent_id, "status": "draft", "configurationHash": digest(config)}


class EvaluationCase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    input: str = Field(min_length=1, max_length=5000)
    expected: str = Field(min_length=1, max_length=5000)
    actual: str = Field(min_length=1, max_length=5000)
    passed: bool
    explanation: str = Field(min_length=1, max_length=2000)


class EvaluationRecord(BaseModel):
    configuration_hash: str = Field(pattern="^[a-f0-9]{64}$")
    evaluator: str = Field(min_length=1, max_length=160)
    round: int = Field(ge=1, le=20)
    cases: list[EvaluationCase] = Field(min_length=6, max_length=30)


@router.post("/rooms/{room_id}/agents/{agent_id}/review-submissions", status_code=201)
async def submit(room_id: str, agent_id: str, body: EvaluationRecord, scope: Member):
    agent = await room_agent(scope, room_id, agent_id)
    if agent["status"] != "draft":
        raise HTTPException(409, "Draft agent required")
    if digest(agent["configuration"]) != body.configuration_hash:
        raise HTTPException(409, "Evaluation belongs to a different configuration")
    if not all(c.passed for c in body.cases):
        raise HTTPException(
            409, "All evaluation cases must pass before admin submission"
        )
    if len({c.name for c in body.cases}) != len(body.cases):
        raise HTTPException(422, "Evaluation cases must have distinct names")
    data = body.model_dump(mode="json")
    old = (
        (
            await scope[0].execute(
                text(
                    "select * from vh_agent_reviews where agent_id=:id and status='pending'"
                ),
                {"id": agent_id},
            )
        )
        .mappings()
        .first()
    )
    if old:
        if old["evaluation"] != data or old["submitted_by"] != scope[1]:
            raise HTTPException(409, "Another submission is pending")
        return dict(old)
    row = await scope[0].execute(
        text(
            f"insert into vh_agent_reviews(tenant_id,agent_id,submitted_by,config_hash,evaluation,status) values({TENANT},:agent,:actor,:hash,cast(:evaluation as jsonb),'pending') returning *"
        ),
        {
            "agent": agent_id,
            "actor": scope[1],
            "hash": body.configuration_hash,
            "evaluation": json.dumps(data),
        },
    )
    await audit(
        scope[0],
        scope[1],
        "agent.review_submitted",
        "agent",
        agent_id,
        {"configurationHash": body.configuration_hash},
    )
    return dict(row.mappings().one())


@router.get("/admin/agent-reviews")
async def reviews(
    scope: Admin,
    status: Literal["pending", "approved", "rejected"] = "pending",
    limit: int = Query(50, ge=1, le=100),
):
    if not scope[2]:
        raise HTTPException(403, "Platform admin required")
    rows = await scope[0].execute(
        text(
            "select r.*,a.name from vh_agent_reviews r join agents a on a.id=r.agent_id and a.tenant_id=r.tenant_id where r.status=:status order by r.created_at limit :limit"
        ),
        {"status": status, "limit": limit},
    )
    return {"items": [dict(r) for r in rows.mappings()]}


class ReviewDecision(BaseModel):
    decision: Literal["approve", "reject"]
    version: int = Field(ge=0)
    note: str = Field(min_length=1, max_length=2000)


@router.post("/admin/agent-reviews/{review_id}/decision")
async def decide(review_id: UUID, body: ReviewDecision, scope: Admin):
    if not scope[2]:
        raise HTTPException(403, "Platform admin required")
    ref = (
        (
            await scope[0].execute(
                text("select agent_id from vh_agent_reviews where id=:id"),
                {"id": review_id},
            )
        )
        .mappings()
        .first()
    )
    if ref is None:
        raise HTTPException(404, "Review not found")
    agent = (
        (
            await scope[0].execute(
                text("select configuration,status from agents where id=:id for update"),
                {"id": ref["agent_id"]},
            )
        )
        .mappings()
        .one()
    )
    row = (
        (
            await scope[0].execute(
                text("select * from vh_agent_reviews where id=:id for update"),
                {"id": review_id},
            )
        )
        .mappings()
        .one()
    )
    if row["status"] != "pending" or row["version"] != body.version:
        raise HTTPException(409, "Review already decided")
    if (
        agent["status"] != "draft"
        or digest(agent["configuration"]) != row["config_hash"]
    ):
        raise HTTPException(409, "Agent configuration changed")
    status = "approved" if body.decision == "approve" else "rejected"
    result = await scope[0].execute(
        text(
            "update vh_agent_reviews set status=:status,version=version+1,decided_by=:actor,decision_note=:note,decided_at=now(),updated_at=now() where id=:id returning *"
        ),
        {"status": status, "actor": scope[1], "note": body.note, "id": review_id},
    )
    version_id = None
    if status == "approved":
        version_no = (
            await scope[0].execute(
                text(
                    "select coalesce(max(version_no),0)+1 from agent_versions where agent_id=:id"
                ),
                {"id": ref["agent_id"]},
            )
        ).scalar_one()
        version_id = (
            await scope[0].execute(
                text(f"""insert into agent_versions(tenant_id,agent_id,version_no,runtime,framework_version,instructions,config,config_hash,created_by)
          values({TENANT},:agent,:number,'agentscope',:framework,:instructions,cast(:config as jsonb),:hash,:actor) returning id"""),
                {
                    "agent": ref["agent_id"],
                    "number": version_no,
                    "framework": agent["configuration"].get(
                        "framework_version", "demo-record-only"
                    ),
                    "instructions": agent["configuration"].get("instructions", ""),
                    "config": json.dumps(agent["configuration"]),
                    "hash": row["config_hash"],
                    "actor": scope[1],
                },
            )
        ).scalar_one()
        # Approval is the publication: only a published version may enter a Supervisor's room.
        await scope[0].execute(
            text(f"""insert into agent_releases(tenant_id,agent_id,version_id,status,published_by,published_at)
          values({TENANT},:agent,:version,'published',:actor,now())"""),
            {"agent": ref["agent_id"], "version": version_id, "actor": scope[1]},
        )
        await scope[0].execute(
            text("update agents set status='active' where id=:id"),
            {"id": ref["agent_id"]},
        )
    await audit(
        scope[0],
        scope[1],
        "agent.review_decided",
        "agent",
        ref["agent_id"],
        {"reviewId": review_id, "status": status},
    )
    return {
        **dict(result.mappings().one()),
        "agentStatus": "active" if status == "approved" else "draft",
        "versionId": version_id,
        "execution": "not performed by this API",
    }


class Revocation(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


@router.post("/admin/agents/{agent_id}/release/revoke")
async def revoke(agent_id: str, body: Revocation, scope: Admin):
    """Withdraw the published version: no new room admits it and running turns are refused."""
    if not scope[2]:
        raise HTTPException(403, "Platform admin required")
    release = (
        (
            await scope[0].execute(
                text(
                    "update agent_releases set status='revoked',revoked_at=now(),updated_at=now() "
                    "where agent_id=:id and status='published' and revoked_at is null returning id,version_id"
                ),
                {"id": agent_id},
            )
        )
        .mappings()
        .first()
    )
    if release is None:
        raise HTTPException(404, "No published version of this agent")
    await audit(
        scope[0],
        scope[1],
        "agent.release_revoked",
        "agent",
        agent_id,
        {"releaseId": release["id"], "versionId": release["version_id"], "note": body.note},
    )
    return {"agentId": agent_id, "versionId": release["version_id"], "status": "revoked"}


@router.get("/rooms/{room_id}/agents/{agent_id}/versions")
async def versions(room_id: str, agent_id: str, scope: Member):
    await room_agent(scope, room_id, agent_id)
    rows = await scope[0].execute(
        text(
            "select id,version_no,runtime,framework_version,config_hash,created_at from agent_versions where agent_id=:id order by version_no desc"
        ),
        {"id": agent_id},
    )
    return {"items": [dict(r) for r in rows.mappings()]}
