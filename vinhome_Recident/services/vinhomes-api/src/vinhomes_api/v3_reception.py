"""Resident context and structured ticket drafts; interpretation stays in runtime."""

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_agent_results import AgentBusinessResponse, agent_result
from .v3_auth import resident_connection
from .v3_reception_supervisor import Fact
from .v3_resident import ResidentTicketCreate, _owned_chat, create_resident_ticket

router = APIRouter(tags=["V3 reception data APIs"])
Scope = Annotated[tuple[AsyncConnection, str], Depends(resident_connection)]


@router.get("/resident/context", response_model=AgentBusinessResponse)
async def context(scope: Scope):
    user = (
        (
            await scope[0].execute(
                text("select id,name,phone_e164 from users where id=:actor"),
                {"actor": scope[1]},
            )
        )
        .mappings()
        .one()
    )
    rows = await scope[0].execute(
        text("""select u.id as unit_id,u.code as unit_code,b.id as building_id,b.name as building_name,b.code as building_code,s.domain_id,d.name as domain_name,s.id as site_id
      from unit_residents ur join units u on u.id=ur.unit_id and u.tenant_id=ur.tenant_id
      join buildings b on b.id=u.building_id and b.tenant_id=u.tenant_id join sites s on s.id=b.site_id and s.tenant_id=b.tenant_id
      join domains d on d.id=s.domain_id and d.tenant_id=s.tenant_id
      where ur.user_id=:actor and ur.verification_status='verified' and ur.valid_from<=now() and (ur.valid_to is null or ur.valid_to>now())
      and u.status='active' and b.status='active' and s.status='active'"""),
        {"actor": scope[1]},
    )
    return agent_result(
        "load_resident_context",
        {"resident": dict(user), "residences": [dict(r) for r in rows.mappings()]},
        {},
    )


class DraftFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, min_length=1, max_length=10000)
    domain_id: UUID | None = None
    building_id: UUID | None = None
    unit_id: UUID | None = None
    category_id: UUID | None = None
    contact_name: str | None = Field(default=None, min_length=1, max_length=200)
    contact_phone: str | None = Field(default=None, min_length=1, max_length=30)
    source_message_id: str | None = Field(default=None, min_length=1, max_length=200)
    facts: list[Fact] = Field(default_factory=list, max_length=100)
    file_ids: list[UUID] = Field(default_factory=list, max_length=100)
    request_kind: str = Field(
        default="incident", pattern="^(incident|service_request)$"
    )


class DraftCreate(BaseModel):
    incidents: list[DraftFields] = Field(min_length=1, max_length=10)
    client_message_id: str = Field(min_length=1, max_length=120)


def draft_result(row):
    incidents = row["body"]["incidents"]
    return {
        "draftId": row["id"],
        "channelId": row["channel_id"],
        "incidents": [
            {
                "index": i,
                "fields": fields,
                "missingFields": [k for k, v in fields.items() if v is None],
                "ready": all(v is not None for v in fields.values()),
            }
            for i, fields in enumerate(incidents)
        ],
    }


@router.post(
    "/resident/chats/{channel_id}/ticket-drafts",
    status_code=201,
    response_model=AgentBusinessResponse,
)
async def draft(channel_id: str, body: DraftCreate, scope: Scope):
    await _owned_chat(scope, channel_id, lock=True)
    content = {
        "type": "ticket_draft",
        "incidents": [r.model_dump(mode="json") for r in body.incidents],
    }
    old = (
        (
            await scope[0].execute(
                text(
                    "select id,channel_id,body from messages where channel_id=:channel and sender_user_id=:actor and client_message_id=:key"
                ),
                {
                    "channel": channel_id,
                    "actor": scope[1],
                    "key": body.client_message_id,
                },
            )
        )
        .mappings()
        .first()
    )
    if old:
        if old["body"] != content:
            raise HTTPException(409, "Draft key already used")
        return agent_result(
            "create_ticket_draft", draft_result(old), {"channel_id": channel_id}
        )
    seq = (
        await scope[0].execute(
            text(
                "update channels set next_message_seq=next_message_seq+1,last_message_at=now() where id=:id returning next_message_seq-1"
            ),
            {"id": channel_id},
        )
    ).scalar_one()
    row = await scope[0].execute(
        text(
            "insert into messages(tenant_id,channel_id,seq,sender_kind,sender_user_id,visibility,body,client_message_id) values(nullif(current_setting('app.tenant_id',true),'')::uuid,:channel,:seq,'user',:actor,'customer',cast(:body as jsonb),:key) returning id,channel_id,body"
        ),
        {
            "channel": channel_id,
            "seq": seq,
            "actor": scope[1],
            "body": json.dumps(content),
            "key": body.client_message_id,
        },
    )
    return agent_result(
        "create_ticket_draft",
        draft_result(row.mappings().one()),
        {"channel_id": channel_id},
    )


@router.get(
    "/resident/chats/{channel_id}/ticket-drafts", response_model=AgentBusinessResponse
)
async def drafts(channel_id: str, scope: Scope):
    await _owned_chat(scope, channel_id)
    rows = await scope[0].execute(
        text(
            "select id,channel_id,body from messages where channel_id=:channel and body->>'type'='ticket_draft' order by seq desc limit 50"
        ),
        {"channel": channel_id},
    )
    return agent_result(
        "list_ticket_drafts",
        {"items": [draft_result(r) for r in rows.mappings()]},
        {"channel_id": channel_id},
    )


@router.post(
    "/resident/chats/{channel_id}/ticket-drafts/{draft_id}/incidents/{index}/commit",
    status_code=201,
    response_model=AgentBusinessResponse,
)
async def commit(channel_id: str, draft_id: UUID, index: int, scope: Scope):
    return await commit_draft(channel_id, draft_id, index, scope)


async def commit_draft(channel_id: str, draft_id: UUID, index: int, scope: Scope, *, requires_plan: bool = True):
    await _owned_chat(scope, channel_id, lock=True)
    row = (
        (
            await scope[0].execute(
                text(
                    "select body from messages where id=:id and channel_id=:channel and sender_user_id=:actor and body->>'type'='ticket_draft'"
                ),
                {"id": draft_id, "channel": channel_id, "actor": scope[1]},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Draft not found")
    incidents = row["body"]["incidents"]
    if not 0 <= index < len(incidents):
        raise HTTPException(422, "Invalid incident index")
    fields = incidents[index]
    missing = [k for k, v in fields.items() if v is None]
    if missing:
        raise HTTPException(
            422,
            {
                "message": "Required incident fields are missing",
                "missingFields": missing,
                "agentContext": agent_result(
                    "create_ticket_draft",
                    {
                        "draftId": draft_id,
                        "channelId": channel_id,
                        "incidents": [
                            {
                                "index": index,
                                "fields": fields,
                                "missingFields": missing,
                                "ready": False,
                            }
                        ],
                    },
                )["agentContext"],
            },
        )
    body = ResidentTicketCreate(**{k: v for k, v in fields.items() if k in ResidentTicketCreate.model_fields},
                                idempotency_key=f"draft:{draft_id}:{index}")
    assessments = row["body"].get("assessments") or []
    assessment = assessments[index] if index < len(assessments) else None
    return agent_result(
        "create_ticket",
        await create_resident_ticket(channel_id, body, scope, assessment=assessment, requires_plan=requires_plan),
        {"channel_id": channel_id},
    )


class FeedbackCreate(BaseModel):
    score: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)


@router.post("/resident/assignments/{assignment_id}/review", status_code=201)
async def review(assignment_id: UUID, body: FeedbackCreate, scope: Scope):
    row = (
        (
            await scope[0].execute(
                text("""select a.id,a.staff_id,w.id as work_order_id,w.status,t.id as ticket_id
      from work_assignments a join work_orders w on w.id=a.work_order_id and w.tenant_id=a.tenant_id
      join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id where a.id=:id and t.requester_user_id=:actor"""),
                {"id": assignment_id, "actor": scope[1]},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Assignment not found")
    ticket = (
        (
            await scope[0].execute(
                text("select * from tickets where id=:id for update"),
                {"id": row["ticket_id"]},
            )
        )
        .mappings()
        .one()
    )
    if row["status"] != "completed":
        raise HTTPException(409, "Completed work required before feedback")
    approved = await scope[0].execute(
        text(
            "select 1 from work_approvals where work_order_id=:id and kind='customer_completion' and status='approved' and decided_by=:actor"
        ),
        {"id": row["work_order_id"], "actor": scope[1]},
    )
    if approved.first() is None:
        raise HTTPException(409, "Approve work completion before submitting feedback")
    old = (
        (
            await scope[0].execute(
                text(
                    "select * from ticket_reviews where assignment_id=:id and reviewer_user_id=:actor"
                ),
                {"id": assignment_id, "actor": scope[1]},
            )
        )
        .mappings()
        .first()
    )
    if old:
        if old["score"] != body.score or (old["comment"] or "") != body.comment:
            raise HTTPException(
                409, "Feedback already submitted with different content"
            )
        return dict(old)
    result = await scope[0].execute(
        text(
            "insert into ticket_reviews(tenant_id,ticket_id,assignment_id,reviewer_user_id,staff_id,score,comment,submitted_at) values(nullif(current_setting('app.tenant_id',true),'')::uuid,:ticket,:assignment,:actor,:staff,:score,:comment,now()) returning *"
        ),
        {
            "ticket": row["ticket_id"],
            "assignment": assignment_id,
            "actor": scope[1],
            "staff": row["staff_id"],
            "score": body.score,
            "comment": body.comment,
        },
    )
    from .v3_mutations import record_event

    await record_event(
        (scope[0], scope[1], False),
        dict(ticket),
        "work.reviewed",
        json.dumps({"assignmentId": str(assignment_id), "score": body.score}),
    )
    return dict(result.mappings().one())
