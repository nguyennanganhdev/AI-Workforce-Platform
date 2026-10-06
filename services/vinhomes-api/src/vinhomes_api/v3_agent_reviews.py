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


async def room_agent(scope: Member, room_id: str, agent_id: str, *, lock: bool = True):
    room = await managed_room(scope, room_id, lock=lock)
    agent = (
        (
            await scope[0].execute(
                text(
                    "select a.* from agents a join channel_agents ca on ca.agent_id=a.id and ca.tenant_id=a.tenant_id where a.id=:id and a.workspace_id=:workspace and ca.channel_id=:room" + (" for update of a" if lock else "")
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
    instructions: str = Field(min_length=1, max_length=50000)
    description: str = Field(min_length=1, max_length=2000)
    mcp_tools: list[ToolReference] = Field(default_factory=list, max_length=50)
    knowledge_namespace_ids: list[UUID] = Field(default_factory=list, max_length=20)
    # Ticket categories this agent serves. A Supervisor is offered it only for those tickets.
    service_categories: list[str] = Field(default_factory=list, max_length=10)
    model_id: str | None = Field(default=None, max_length=160)
    skill_ids: list[UUID] = Field(default_factory=list, max_length=30)
    revision_of: UUID | None = None
    framework_version: str = Field(
        default="demo-record-only", min_length=1, max_length=120
    )


@router.put("/rooms/{room_id}/agents/{agent_id}/configuration")
async def configure(
    room_id: str, agent_id: str, body: AgentConfiguration, scope: Member
):
    agent = await room_agent(scope, room_id, agent_id)
    if not await can_author_unit(scope[0], scope[1], agent["workspace_id"]):
        raise HTTPException(403, "Only management of this unit can edit its agent")
    if agent["status"] != "draft" and not (agent["status"] == "active" and body.revision_of):
        raise HTTPException(409, "Only draft agents can be configured")
    if body.revision_of:
        latest = (await scope[0].execute(text("select id from agent_versions where agent_id=:id order by version_no desc limit 1"),
                                        {"id": agent_id})).scalar_one_or_none()
        if latest != body.revision_of:
            raise HTTPException(409, "Revision must be based on the latest version of this agent")
    pending = await scope[0].execute(
        text("select 1 from vh_agent_reviews where agent_id=:id and status='pending'"),
        {"id": agent_id},
    )
    if pending.first():
        raise HTTPException(409, "Wait for the current admin review")
    for tool in body.mcp_tools:
        available = await scope[0].execute(
            # A connection set up for one group is not offered to another group's agents.
            text("select 1 from mcp_tools t join mcp_servers s on s.id=t.server_id and s.tenant_id=t.tenant_id "
                 "where t.server_id=:server and t.name=:name and (t.effect='read' or (s.provenance='custom' and t.effect='write')) and not t.destructive and s.status='active' "
                 "and (s.workspace_id is null or s.workspace_id=:workspace)"),
            {"server": tool.server_id, "name": tool.name, "workspace": agent["workspace_id"]},
        )
        if available.first() is None:
            raise HTTPException(422, "A registered read tool is required; actions require separate human approval")
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
    if body.model_id:
        from .v3_models import resolve_model
        if not await resolve_model(scope[0], 'specialist', body.model_id):
            raise HTTPException(422, 'Model is not available for this unit')
    skill_snapshots = []
    for skill_id in body.skill_ids:
        skill = (await scope[0].execute(text('select id,name,instructions from vh_agent_skills where id=:id and (workspace_id is null or workspace_id=:workspace)'), {'id': skill_id, 'workspace': agent['workspace_id']})).mappings().first()
        if not skill:
            raise HTTPException(422, 'Skill outside this unit')
        skill_snapshots.append({'id': str(skill['id']), 'name': skill['name'], 'instructions': skill['instructions']})
    config = {**body.model_dump(mode="json"), "skill_snapshots": skill_snapshots}
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
    if agent["status"] != "draft" and not (agent["status"] == "active" and agent["configuration"].get("revision_of")):
        raise HTTPException(409, "Draft agent required")
    if digest(agent["configuration"]) != body.configuration_hash:
        raise HTTPException(409, "Evaluation belongs to a different configuration")
    if agent['status'] == 'active':
        latest = (await scope[0].execute(text('select id,config_hash from agent_versions where agent_id=:id order by version_no desc limit 1'), {'id': agent_id})).mappings().one()
        if str(latest['id']) != agent['configuration'].get('revision_of') or latest['config_hash'] == body.configuration_hash:
            raise HTTPException(409, 'Start a new revision from the current published version')
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
        evidence = {k: v for k, v in old['evaluation'].items() if not k.startswith('_')}
        if evidence != data or old["submitted_by"] != scope[1]:
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
            # With the configuration under review: an admin approves what the agent is told and granted.
            "select r.*,a.name,a.configuration from vh_agent_reviews r join agents a on a.id=r.agent_id and a.tenant_id=r.tenant_id where r.status=:status order by r.created_at limit :limit"
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
        agent["status"] not in ("draft", "active")
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
        "agentStatus": "active" if status == "approved" else agent["status"],
        "versionId": version_id,
        "execution": "not performed by this API",
    }


@router.get("/admin/agent-releases")
async def releases(scope: Admin):
    """The agent versions a Supervisor may invite now: published and not revoked."""
    if not scope[2]:
        raise HTTPException(403, "Platform admin required")
    rows = await scope[0].execute(
        text(
            "select a.id as agent_id,a.name,v.version_no,r.published_at,w.name as workspace,"
            "v.config->'service_categories' as service_categories,v.config->'mcp_tools' as tools "
            "from agent_releases r join agents a on a.id=r.agent_id and a.tenant_id=r.tenant_id "
            "join agent_versions v on v.id=r.version_id and v.tenant_id=r.tenant_id "
            "left join workspaces w on w.id=a.workspace_id and w.tenant_id=a.tenant_id "
            "where r.status='published' and r.revoked_at is null order by r.published_at desc"
        )
    )
    return {"items": [dict(r) for r in rows.mappings()]}


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
    # Withdrawing an agent also stops pre-governance system Supervisor pins.
    # A later approved revision reactivates the agent in decide().
    await scope[0].execute(text("update agents set status='draft',updated_at=now() where id=:id"), {'id': agent_id})
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


@router.get('/rooms/{room_id}/agent-management')
async def management_agents(room_id: str, scope: Member):
    return await room_catalogue(room_id, scope)


async def room_catalogue(room_id: str, scope: Member, *, lock: bool = True):
    """The room's agents, read tools and categories. `lock=False` for a caller that waits on another service."""
    room = await managed_room(scope, room_id, lock=lock)
    rows = await scope[0].execute(text("""select a.id,a.name,a.purpose,a.status,a.configuration,a.updated_at,
        (select jsonb_build_object('id',v.id,'number',v.version_no,'hash',v.config_hash,'config',v.config)
          from agent_versions v where v.agent_id=a.id order by v.version_no desc limit 1) as latest_version,
        (select row_to_json(rv) from vh_agent_reviews rv where rv.agent_id=a.id order by rv.created_at desc limit 1) as review,
        exists(select 1 from agent_releases rel join agent_versions v on v.id=rel.version_id
          where rel.agent_id=a.id and rel.status='published' and rel.revoked_at is null
          and v.version_no=(select max(last.version_no) from agent_versions last where last.agent_id=a.id)) as published
        from agents a join channel_agents ca on ca.agent_id=a.id and ca.tenant_id=a.tenant_id
        where ca.channel_id=:room and a.workspace_id=:workspace order by a.name"""), {'room': room_id, 'workspace': room['workspace_id']})
    tools = await scope[0].execute(text("select t.server_id,s.title as server_title,s.provenance='custom' as external,s.added_by,s.added_by=:actor as own,t.name,t.description,t.input_schema,t.effect "
        "from mcp_tools t join mcp_servers s on s.id=t.server_id and s.tenant_id=t.tenant_id "
        "where (t.effect='read' or (s.provenance='custom' and t.effect='write')) and not t.destructive and s.status='active' and (s.workspace_id is null or s.workspace_id=:workspace) order by t.name"), {'workspace': room['workspace_id'], 'actor': scope[1]})
    skills = await scope[0].execute(text('select id,name,description,instructions,workspace_id,created_by=:actor as own from vh_agent_skills where workspace_id is null or workspace_id=:workspace order by name'), {'workspace': room['workspace_id'], 'actor': scope[1]})
    is_admin = (await scope[0].execute(text('select 1 from platform_admins where user_id=:actor'), {'actor': scope[1]})).first() is not None
    categories = await scope[0].execute(text('select code,name from service_categories where enabled order by name'))
    return {'isAdmin': is_admin, 'canManage': await can_author_unit(scope[0], scope[1], room['workspace_id']), 'skills': [dict(s) for s in skills.mappings()], 'items': [{**dict(r), 'configurationHash': digest(r['configuration'])} for r in rows.mappings()], 'tools': [dict(t) for t in tools.mappings()],
            'categories': [dict(c) for c in categories.mappings()]}


@router.post('/rooms/{room_id}/agent-reviews/{review_id}/decision')
async def management_decide(room_id: str, review_id: UUID, body: ReviewDecision, scope: Member):
    agent_id = (await scope[0].execute(text('select agent_id from vh_agent_reviews where id=:id'), {'id': review_id})).scalar_one_or_none()
    if agent_id is None:
        raise HTTPException(404, 'Review not found')
    await room_agent(scope, room_id, agent_id)
    evidence = (await scope[0].execute(text('select evaluation from vh_agent_reviews where id=:id'), {'id': review_id})).scalar_one()
    is_admin = (await scope[0].execute(text('select 1 from platform_admins where user_id=:actor'), {'actor': scope[1]})).first() is not None
    if body.decision == 'approve' and not is_admin and evidence.get('_runtime_verified') is not True:
        raise HTTPException(409, 'Run the server evaluation before BQL publication')
    return await decide(review_id, body, (scope[0], scope[1], True))


@router.post('/rooms/{room_id}/agents/{agent_id}/release/revoke')
async def management_revoke(room_id: str, agent_id: str, body: Revocation, scope: Member):
    await room_agent(scope, room_id, agent_id)
    return await revoke(agent_id, body, (scope[0], scope[1], True))


async def can_author_unit(db, actor, workspace_id):
    return (await db.execute(text("""select 1 from scoped_user_roles r join tenant_memberships m on m.id=r.membership_id and m.status='active' join access_scopes s on s.id=r.scope_id join workspaces w on w.id=:workspace where m.user_id=:actor and r.role_code='management' and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now()) and (s.kind='tenant' or (s.kind='management' and s.management_unit_id=w.management_unit_id)) limit 1"""), {'actor': actor, 'workspace': workspace_id})).first() is not None
