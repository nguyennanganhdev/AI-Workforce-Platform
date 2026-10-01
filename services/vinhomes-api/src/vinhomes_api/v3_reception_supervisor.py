"""Durable, authenticated API exchange for the schema_v2 Reception/Supervisor contract."""

import base64
import binascii
import json
from datetime import datetime, timezone
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)
from sqlalchemy import text

from .resident_api import OPERATIONS_BASE, BASE, operations_scope, resident_scope
from .v3_audit import audit
from .v3_mutations import record_event, visible_ticket
from .v3_security import digest

TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
RESIDENT = Annotated[tuple, Depends(resident_scope, scope="function")]
OPERATIONS = Annotated[tuple, Depends(operations_scope, scope="function")]
router = APIRouter(
    prefix=BASE + "/reception-supervisor",
    tags=["Reception/Supervisor schema_v2"],
)
operations_router = APIRouter(
    prefix=OPERATIONS_BASE + "/reception-supervisor",
    tags=["Reception/Supervisor schema_v2"],
)


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Fact(StrictPayload):
    key: str = Field(min_length=1, max_length=200)
    value: StrictStr | StrictInt | StrictFloat | StrictBool | None
    source: Literal["customer_report", "staff_verified", "agent_inference"]
    source_message_id: str = Field(min_length=1, max_length=200)

    @field_validator("value")
    @classmethod
    def string_fact_value_is_bounded(cls, value):
        if isinstance(value, str) and len(value) > 4000:
            raise ValueError("string fact values cannot exceed 4000 characters")
        return value


class ResidentSnapshot(StrictPayload):
    resident_id: str = Field(min_length=1, max_length=200)
    resident_name: str = Field(min_length=1, max_length=200)
    phone_number: str = Field(min_length=1, max_length=30)


class LocationSnapshot(StrictPayload):
    location_scope_id: UUID
    unit_id: UUID
    unit_number: str = Field(min_length=1, max_length=100)
    building_id: UUID
    building_code: str = Field(min_length=1, max_length=100)
    building_name: str = Field(min_length=1, max_length=200)


class RequestSnapshot(StrictPayload):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=10000)
    request_kind: Literal["incident", "service_request"]
    category_id: UUID = Field(default=None)
    priority: Literal["low", "normal", "high", "critical"]
    severity: Literal[
        "unknown", "minor", "moderate", "major", "critical", "not_applicable"
    ]
    is_emergency: bool
    triage_decision_id: UUID = Field(default=None)
    handoff_reason: Literal[
        "needs_staff", "self_help_declined", "self_help_failed", "emergency"
    ]


class ReceptionToSupervisorMessage(StrictPayload):
    schema_version: Literal["2.0"]
    message_id: str = Field(min_length=1, max_length=200)
    correlation_id: str = Field(min_length=1, max_length=200)
    sent_at: datetime
    message_type: Literal[
        "ticket_submitted",
        "information_provided",
        "plan_approved",
        "plan_rejected",
        "plan_change_requested",
        "cancel_requested",
    ]
    message: str = Field(min_length=1, max_length=10000)
    source_message_id: str = Field(default=None, min_length=1, max_length=200)
    tenant_id: UUID
    domain_id: UUID
    domain_name: str = Field(min_length=1, max_length=200)
    workspace_id: UUID
    team_id: UUID
    ticket_id: UUID
    ticket_code: str = Field(min_length=1, max_length=100)
    ticket_generation: int = Field(ge=0)
    ticket_version: str = Field(pattern=r"^[0-9]+$", max_length=30)
    resident: ResidentSnapshot
    location: LocationSnapshot
    request: RequestSnapshot
    facts: list[Fact] = Field(max_length=100)
    file_ids: list[UUID] = Field(max_length=100)
    created_at: datetime

    @field_validator("sent_at", "created_at")
    @classmethod
    def timestamps_require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @field_validator("file_ids")
    @classmethod
    def file_ids_are_unique(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("file_ids must not contain duplicates")
        return value

    @model_validator(mode="after")
    def message_source_is_present_when_required(self):
        if self.message_type != "ticket_submitted" and not self.source_message_id:
            raise ValueError("source_message_id is required for this message_type")
        return self


class ResultError(StrictPayload):
    code: str = Field(min_length=1, max_length=100)
    retryable: bool
    message: str = Field(min_length=1, max_length=2000)


class ResultData(StrictPayload):
    outcome: Literal["work_completed", "needs_human_review", "unable_to_resolve"]
    summary: str = Field(min_length=1, max_length=5000)
    work_order_ids: list[UUID] = Field(max_length=100)
    evidence_ids: list[UUID] = Field(max_length=200)

    @field_validator("work_order_ids", "evidence_ids")
    @classmethod
    def result_ids_are_unique(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("result ids must not contain duplicates")
        return value


class SupervisorToReceptionResult(StrictPayload):
    schema_version: Literal["2.0"]
    message_id: str = Field(min_length=1, max_length=200)
    correlation_id: str = Field(min_length=1, max_length=200)
    sent_at: datetime
    message_type: Literal[
        "accepted",
        "in_progress",
        "information_requested",
        "plan_approval_requested",
        "completed",
        "failed",
        "cancelled",
    ]
    message: str = Field(min_length=1, max_length=10000)
    tenant_id: UUID
    workspace_id: UUID
    team_id: UUID
    ticket_id: UUID
    ticket_code: str = Field(min_length=1, max_length=100)
    ticket_generation: int = Field(ge=0)
    ticket_version: str = Field(pattern=r"^[0-9]+$", max_length=30)
    supervisor_run_id: str = Field(min_length=1, max_length=200)
    result: ResultData = Field(default=None)
    error: ResultError = Field(default=None)

    @field_validator("sent_at")
    @classmethod
    def sent_at_requires_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def result_matches_message_type(self):
        if self.message_type == "completed":
            if self.result is None or self.result.outcome != "work_completed":
                raise ValueError("completed requires a work_completed result")
        if self.message_type == "failed" and self.error is None:
            raise ValueError("failed requires an error object")
        if self.message_type == "cancelled" and self.result is not None:
            raise ValueError("cancelled cannot report work_completed")
        return self


class MessageAcceptance(StrictPayload):
    message: ReceptionToSupervisorMessage
    replayed: bool
    business_effect: dict[str, Any]


class ResultAcceptance(StrictPayload):
    result: SupervisorToReceptionResult
    replayed: bool
    verification: dict[str, Any]


class MessagePage(StrictPayload):
    items: list[ReceptionToSupervisorMessage]
    next_cursor: str | None


class ResultPage(StrictPayload):
    items: list[SupervisorToReceptionResult]
    next_cursor: str | None


def _payload_hash(payload: dict[str, Any]) -> str:
    return digest(payload)


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


def _encode_cursor(row: dict[str, Any]) -> str:
    raw = f"{row['created_at'].isoformat()}|{row['id']}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(value: str | None) -> tuple[datetime | None, UUID | None]:
    if value is None:
        return None, None
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode("utf-8")
        timestamp, row_id = raw.split("|", 1)
        at = datetime.fromisoformat(timestamp)
        if at.utcoffset() is None:
            raise ValueError("cursor timestamp has no timezone")
        return at, UUID(row_id)
    except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise HTTPException(422, "Invalid message cursor") from exc


async def _authorized_team(scope, team_id: UUID, *, lock: bool = False) -> dict[str, Any]:
    result = await scope[0].execute(text(f"""
        select tm.*,w.management_unit_id as workspace_management_unit_id,
          c.workspace_id as channel_workspace_id
        from agent_teams tm
        join workspaces w on w.id=tm.workspace_id and w.tenant_id=tm.tenant_id and w.status='active'
        join channels c on c.id=tm.channel_id and c.tenant_id=tm.tenant_id
          and c.kind='management'
        where tm.id=:team_id and tm.tenant_id={TENANT}
          and c.workspace_id=tm.workspace_id
        {"for update of tm" if lock else ""}
    """), {"team_id": team_id})
    row = result.mappings().first()
    if row is None:
        raise HTTPException(404, "Supervisor team not found")
    team = dict(row)
    ticket = await visible_ticket(scope, team["ticket_id"])
    if team["workspace_management_unit_id"] != ticket["management_unit_id"]:
        raise HTTPException(404, "Supervisor team is outside this ticket workspace")
    return team


def _check_snapshot(body: ReceptionToSupervisorMessage, row: dict[str, Any]) -> None:
    expected = {
        "tenant_id": str(row["tenant_id"]),
        "domain_id": str(row["domain_id"]),
        "domain_name": row["domain_name"],
        "workspace_id": str(row["workspace_id"]),
        "team_id": str(row["team_id"]),
        "ticket_id": str(row["ticket_id"]),
        "ticket_code": row["ticket_code"],
        "ticket_generation": row["ticket_generation"],
        "ticket_version": str(row["ticket_version"]),
        "resident.resident_id": row["requester_user_id"],
        "resident.resident_name": row["contact_name"],
        "resident.phone_number": row["contact_phone"],
        "location.location_scope_id": str(row["location_scope_id"]),
        "location.unit_id": str(row["unit_id"]),
        "location.unit_number": row["unit_number"],
        "location.building_id": str(row["building_id"]),
        "location.building_code": row["building_code"],
        "location.building_name": row["building_name"],
        "request.title": row["title"],
        "request.description": row["description"],
        "request.request_kind": row["request_kind"],
        "request.priority": row["priority"],
        "request.severity": row["severity"],
        "request.is_emergency": row["is_emergency"],
    }
    actual = body.model_dump(mode="python")
    for path, value in expected.items():
        current: Any = actual
        for segment in path.split("."):
            current = current[segment]
        if str(current) != str(value):
            raise HTTPException(409, f"V2 ticket snapshot is stale or mismatched: {path}")
    if body.request.category_id is not None and str(body.request.category_id) != str(row["category_id"]):
        raise HTTPException(409, "V2 ticket snapshot is stale or mismatched: request.category_id")
    if body.request.triage_decision_id is not None and str(body.request.triage_decision_id) != str(row["triage_decision_id"]):
        raise HTTPException(409, "V2 ticket snapshot is stale or mismatched: request.triage_decision_id")
    if _utc(body.created_at) != _utc(row["created_at"]):
        raise HTTPException(409, "V2 ticket snapshot is stale or mismatched: created_at")


async def _resident_ticket_snapshot(scope, body: ReceptionToSupervisorMessage) -> dict[str, Any]:
    db, actor = scope
    row = (
        await db.execute(
            text(f"""
            select t.id as ticket_id,t.tenant_id,t.code as ticket_code,t.requester_user_id,
              t.channel_id,t.unit_id,t.building_id,t.domain_id,t.title,t.description,
              t.priority,t.severity,t.request_kind,t.is_emergency,t.version as ticket_version,
              t.reopen_count as ticket_generation,t.current_triage_decision_id as triage_decision_id,
              t.category_id,t.status,t.created_at,t.last_event_seq,t.assigned_team_id,
              t.management_unit_id,t.site_id,t.zone_id,t.contact_name,t.contact_phone,
              d.name as domain_name,u.code as unit_number,b.code as building_code,
              b.name as building_name,mc.scope_id as location_scope_id,
              tm.id as team_id,tm.ticket_id as team_ticket_id,
              tm.ticket_generation as team_generation,tm.status as team_status,
              tm.workspace_id,tm.channel_id as team_channel_id,
              w.management_unit_id as workspace_management_unit_id,
              c.workspace_id as channel_workspace_id
            from tickets t
            join domains d on d.id=t.domain_id and d.tenant_id=t.tenant_id
            join units u on u.id=t.unit_id and u.tenant_id=t.tenant_id
            join buildings b on b.id=t.building_id and b.tenant_id=t.tenant_id
            left join management_coverage mc on mc.id=t.coverage_id and mc.tenant_id=t.tenant_id
            left join agent_teams tm on tm.id=:team_id and tm.tenant_id=t.tenant_id
            left join workspaces w on w.id=tm.workspace_id and w.tenant_id=tm.tenant_id
            left join channels c on c.id=tm.channel_id and c.tenant_id=tm.tenant_id
              and c.kind='management'
            where t.id=:ticket_id and t.requester_user_id=:actor and t.tenant_id={TENANT}
            for update of t
            """),
            {"ticket_id": body.ticket_id, "team_id": body.team_id, "actor": actor},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(404, "Resident ticket not found")
    row = dict(row)
    if (
        row["team_id"] is None
        or row["team_ticket_id"] != row["ticket_id"]
        or row["team_generation"] != row["ticket_generation"]
        or row["team_status"] in {"completed", "failed", "cancelled"}
        or row["channel_workspace_id"] != row["workspace_id"]
        or row["workspace_management_unit_id"] != row["management_unit_id"]
        or row["location_scope_id"] is None
    ):
        raise HTTPException(409, "A current Supervisor team and ticket scope are required")
    _check_snapshot(body, row)
    final_ticket = row["status"] in {"resolved", "closed", "cancelled"}
    if body.message_type != "cancel_requested" and final_ticket:
        raise HTTPException(409, "A final ticket cannot accept this Reception message")
    row["source_message_at"] = await _validate_source_message(
        db, row, actor, body.source_message_id, source="customer_report"
    )
    for fact in body.facts:
        await _validate_source_message(
            db,
            row,
            actor,
            fact.source_message_id,
            source=fact.source,
        )
    for file_id in body.file_ids:
        linked = await db.execute(text(f"""
            select 1 from files f
            where f.id=:file_id and f.tenant_id={TENANT} and f.status='ready'
              and ((f.channel_id=:channel_id and f.uploaded_by=:actor)
                or exists(select 1 from ticket_files tf where tf.tenant_id=f.tenant_id
                  and tf.ticket_id=:ticket_id and tf.file_id=f.id))
            limit 1
        """), {"file_id": file_id, "channel_id": row["channel_id"], "actor": actor,
               "ticket_id": row["ticket_id"]})
        if linked.first() is None:
            raise HTTPException(422, "A file_id is not attached to this resident request")
    return row


async def _validate_source_message(db, ticket: dict[str, Any], actor: str,
                                   message_id: str | None, *, source: str):
    if message_id is None:
        return None
    result = await db.execute(text(f"""
        select sender_kind,sender_user_id,sender_agent_id,created_at from messages
        where cast(id as text)=:message_id and channel_id=:channel_id and tenant_id={TENANT}
    """), {"message_id": message_id, "channel_id": ticket["channel_id"]})
    row = result.mappings().first()
    if row is None:
        raise HTTPException(422, "source_message_id does not belong to this conversation")
    if source == "customer_report" and (row["sender_kind"] != "user" or row["sender_user_id"] != actor):
        raise HTTPException(422, "customer_report facts must cite a resident message")
    if source == "staff_verified":
        sender = row["sender_user_id"]
        if row["sender_kind"] != "user" or sender is None:
            raise HTTPException(422, "staff_verified facts must cite an authenticated staff message")
        admin = await db.execute(
            text("select exists(select 1 from platform_admins where user_id=:user_id)"),
            {"user_id": sender},
        )
        try:
            await visible_ticket((db, sender, admin.scalar_one()), ticket["ticket_id"])
        except HTTPException as exc:
            raise HTTPException(422, "staff_verified source is outside this ticket scope") from exc
    if source == "agent_inference" and row["sender_kind"] != "agent":
        raise HTTPException(422, "agent_inference facts must cite an agent message")
    return row["created_at"]


async def _previous_message(
    db,
    message_id: str,
    expected_hash: str,
    *,
    actor: str | None,
    ticket_id: UUID,
    team_id: UUID,
    direction: str,
):
    previous = (
        await db.execute(text(f"""
            select payload_hash,response_body,created_by,ticket_id,team_id,direction
            from vh_reception_supervisor_messages
            where tenant_id={TENANT} and message_id=:message_id
        """), {"message_id": message_id})
    ).mappings().first()
    if previous is None:
        return None
    if (
        (actor is not None and previous["created_by"] != actor)
        or previous["ticket_id"] != ticket_id
        or previous["team_id"] != team_id
        or previous["direction"] != direction
    ):
        raise HTTPException(409, "message_id belongs to a different authenticated operation")
    if previous["payload_hash"] != expected_hash:
        raise HTTPException(409, "message_id was already used for a different payload")
    response = dict(previous["response_body"])
    response["replayed"] = True
    return response


async def _lock_message_id(db, message_id: str) -> None:
    await db.execute(
        text("""
            select pg_advisory_xact_lock(
              hashtextextended(current_setting('app.tenant_id',true)||':'||:message_id,0)
            )
        """),
        {"message_id": message_id},
    )


async def _pending(db, ticket_id: UUID, generation: int):
    return (
        await db.execute(text(f"""
            select * from vh_reception_supervisor_pending
            where tenant_id={TENANT} and ticket_id=:ticket_id and ticket_generation=:generation
            for update
        """), {"ticket_id": ticket_id, "generation": generation})
    ).mappings().first()


@router.post("/messages", response_model=MessageAcceptance, response_model_exclude_unset=True, status_code=201)
async def submit_reception_message(body: ReceptionToSupervisorMessage, scope: RESIDENT):
    db, actor = scope
    payload = body.model_dump(mode="json", exclude_unset=True)
    payload_hash = _payload_hash({key: value for key, value in payload.items() if key != "sent_at"})
    owner = await db.execute(text(f"""
        select 1 from tickets where id=:ticket_id and requester_user_id=:actor and tenant_id={TENANT}
    """), {"ticket_id": body.ticket_id, "actor": actor})
    if owner.first() is None:
        raise HTTPException(404, "Resident ticket not found")
    await _lock_message_id(db, body.message_id)
    previous = await _previous_message(
        db, body.message_id, payload_hash, actor=actor, ticket_id=body.ticket_id,
        team_id=body.team_id, direction="reception_to_supervisor",
    )
    if previous is not None:
        return previous

    ticket = await _resident_ticket_snapshot(scope, body)
    payload["sent_at"] = datetime.now(timezone.utc).isoformat()
    pending = await _pending(db, ticket["ticket_id"], ticket["ticket_generation"])
    effect: dict[str, Any]
    if body.message_type == "ticket_submitted":
        existing = await db.execute(text(f"""
            select 1 from vh_reception_supervisor_messages
            where tenant_id={TENANT} and ticket_id=:ticket_id
              and ticket_generation=:generation and direction='reception_to_supervisor'
              and message_type='ticket_submitted'
            limit 1
        """), {"ticket_id": ticket["ticket_id"], "generation": ticket["ticket_generation"]})
        if existing.first() is not None:
            raise HTTPException(409, "This ticket generation was already submitted to Supervisor")
        effect = {"ticket_status": ticket["status"], "ticket_version": str(ticket["ticket_version"])}
    elif body.message_type == "information_provided":
        if pending is None or pending["pending_kind"] != "information":
            raise HTTPException(409, "No matching Supervisor information request is pending")
        if ticket["source_message_at"] <= pending["created_at"]:
            raise HTTPException(409, "source_message_id predates the pending information request")
        await db.execute(text(f"""
            delete from vh_reception_supervisor_pending
            where tenant_id={TENANT} and ticket_id=:ticket_id and ticket_generation=:generation
        """), {"ticket_id": ticket["ticket_id"], "generation": ticket["ticket_generation"]})
        effect = {"pending_request_resolved": "information"}
    elif body.message_type in {"plan_approved", "plan_rejected", "plan_change_requested"}:
        if pending is None or pending["pending_kind"] != "plan_approval":
            raise HTTPException(409, "No matching resident plan approval is pending")
        if ticket["source_message_at"] <= pending["created_at"]:
            raise HTTPException(409, "source_message_id predates the pending plan request")
        if body.ticket_version != str(ticket["ticket_version"]):
            raise HTTPException(409, "Ticket changed since the plan was sent to the resident")
        plan_id = pending["plan_id"]
        plan_version = pending["plan_version"]
        if body.message_type in {"plan_approved", "plan_rejected"}:
            if len(body.message) > 2000:
                raise HTTPException(422, "Plan decision message cannot exceed 2000 characters")
            from .v3_plans import PlanDecision, resident_decision

            decision = "approve" if body.message_type == "plan_approved" else "reject"
            decided = await resident_decision(
                plan_id,
                PlanDecision(decision=decision, version=plan_version, note=body.message),
                scope,
            )
            effect = {
                "plan_id": str(plan_id),
                "plan_status": decided["status"],
                "work_order_ids": decided.get("workOrderIds", []),
                "ticket_version_after": str(ticket["ticket_version"] + 1),
            }
        else:
            changed = await db.execute(text(f"""
                update vh_ticket_plans
                set status='revision_requested',version=version+1,resident_by=:actor,
                resident_note=:note,resident_at=now(),updated_at=now()
                where tenant_id={TENANT} and id=:plan_id and status='resident_pending'
                  and version=:plan_version
            """), {"actor": actor, "note": body.message, "plan_id": plan_id,
                   "plan_version": plan_version})
            if changed.rowcount != 1:
                raise HTTPException(409, "Plan changed before the revision request was recorded")
            await record_event(
                (db, actor, False),
                ticket,
                "plan.resident_change_requested",
                json.dumps({"planId": str(plan_id), "messageId": body.message_id}),
            )
            effect = {
                "plan_id": str(plan_id),
                "plan_status": "revision_requested",
                "resident_decision": "plan_change_requested",
                "ticket_version_after": str(ticket["ticket_version"] + 1),
            }
        await db.execute(text(f"""
            delete from vh_reception_supervisor_pending
            where tenant_id={TENANT} and ticket_id=:ticket_id and ticket_generation=:generation
        """), {"ticket_id": ticket["ticket_id"], "generation": ticket["ticket_generation"]})
    else:
        effect = {"cancel_requested": True, "ticket_status": ticket["status"]}

    response_body = {"message": payload, "replayed": False, "business_effect": effect}
    await db.execute(text(f"""
        insert into vh_reception_supervisor_messages
          (tenant_id,direction,message_id,correlation_id,ticket_id,team_id,ticket_generation,
           message_type,payload,payload_hash,response_body,created_by)
        values ({TENANT},'reception_to_supervisor',:message_id,:correlation_id,:ticket_id,
          :team_id,:generation,:message_type,cast(:payload as jsonb),:payload_hash,
          cast(:response as jsonb),:actor)
    """), {"message_id": body.message_id, "correlation_id": body.correlation_id,
           "ticket_id": ticket["ticket_id"], "team_id": body.team_id,
           "generation": ticket["ticket_generation"], "message_type": body.message_type,
           "payload": json.dumps(payload), "payload_hash": payload_hash,
           "response": json.dumps(response_body), "actor": actor})
    await audit(db, actor, "reception_supervisor.input_received", "ticket",
                str(ticket["ticket_id"]), {"messageId": body.message_id, "messageType": body.message_type})
    return response_body


@operations_router.get("/teams/{team_id}/inbox", response_model=MessagePage, response_model_exclude_unset=True)
async def supervisor_inbox(
    team_id: UUID,
    scope: OPERATIONS,
    cursor: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=50, ge=1, le=100),
):
    await _authorized_team(scope, team_id)
    after_at, after_id = _decode_cursor(cursor)
    rows = (
        await scope[0].execute(text(f"""
            select id,payload,created_at from vh_reception_supervisor_messages
            where tenant_id={TENANT} and team_id=:team_id and direction='reception_to_supervisor'
              and (:after_at is null or (created_at,id)>
                (cast(:after_at as timestamptz),cast(:after_id as uuid)))
            order by created_at,id limit :limit
        """), {"team_id": team_id, "after_at": after_at, "after_id": after_id,
               "limit": limit + 1})
    ).mappings().all()
    selected = rows[:limit]
    return {
        "items": [ReceptionToSupervisorMessage.model_validate(row["payload"]) for row in selected],
        "next_cursor": _encode_cursor(dict(selected[-1])) if selected else cursor,
    }


@operations_router.post("/results", response_model=ResultAcceptance, response_model_exclude_unset=True, status_code=201)
async def submit_supervisor_result(body: SupervisorToReceptionResult, scope: OPERATIONS):
    db, actor, _ = scope
    payload = body.model_dump(mode="json", exclude_unset=True)
    payload_hash = _payload_hash({key: value for key, value in payload.items() if key != "sent_at"})
    team = await _authorized_team(scope, body.team_id, lock=True)
    if str(team["ticket_id"]) != str(body.ticket_id):
        raise HTTPException(409, "Result ticket does not belong to this team")
    await _lock_message_id(db, body.message_id)
    previous = await _previous_message(
        db, body.message_id, payload_hash, actor=None, ticket_id=body.ticket_id,
        team_id=body.team_id, direction="supervisor_to_reception",
    )
    if previous is not None:
        return previous
    payload["sent_at"] = datetime.now(timezone.utc).isoformat()
    ticket_row = (
        await db.execute(text(f"""
            select t.id,t.tenant_id,t.code,t.version,t.reopen_count,t.status,t.last_event_seq,
              t.assigned_team_id,t.management_unit_id,tm.workspace_id,tm.ticket_generation
            from tickets t join agent_teams tm on tm.ticket_id=t.id and tm.tenant_id=t.tenant_id
            where t.id=:ticket_id and tm.id=:team_id and t.tenant_id={TENANT}
            for update of t
        """), {"ticket_id": body.ticket_id, "team_id": body.team_id})
    ).mappings().first()
    if ticket_row is None:
        raise HTTPException(404, "Ticket or Supervisor team not found")
    ticket = dict(ticket_row)
    if (
        body.tenant_id != ticket["tenant_id"]
        or body.workspace_id != ticket["workspace_id"]
        or body.ticket_code != ticket["code"]
        or body.ticket_generation != ticket["reopen_count"]
        or body.ticket_generation != ticket["ticket_generation"]
        or body.ticket_version != str(ticket["version"])
    ):
        raise HTTPException(409, "Supervisor result is stale or targets a different ticket scope")
    if body.message_type in {
        "accepted", "in_progress", "information_requested", "plan_approval_requested"
    } and ticket["status"] in {"resolved", "closed", "cancelled"}:
        raise HTTPException(409, "A final ticket cannot receive a new Supervisor request")

    pending = await _pending(db, body.ticket_id, body.ticket_generation)
    if body.message_type in {"information_requested", "plan_approval_requested"} and pending is not None:
        raise HTTPException(409, "A resident-facing request is already pending for this ticket generation")
    if body.message_type == "completed" and pending is not None:
        raise HTTPException(409, "Resolve the pending resident request before finishing this team")

    verification: dict[str, Any] = {
        "ticket_status": ticket["status"],
        "ticket_version": str(ticket["version"]),
        "ticket_generation": ticket["reopen_count"],
    }
    if body.message_type == "completed":
        if ticket["status"] not in {"resolved", "closed"}:
            raise HTTPException(409, "Backend has not accepted ticket completion")
        work_rows = (
            await db.execute(text(f"""
                select id,status,required from work_orders
                where tenant_id={TENANT} and ticket_id=:ticket_id
            """), {"ticket_id": body.ticket_id})
        ).mappings().all()
        work_by_id = {str(row["id"]): row for row in work_rows}
        if any(row["required"] and row["status"] != "completed" for row in work_rows):
            raise HTTPException(409, "One or more backend work orders are not complete")
        if any(
            str(work_id) not in work_by_id or work_by_id[str(work_id)]["status"] != "completed"
            for work_id in body.result.work_order_ids
        ):
            raise HTTPException(422, "A result work_order_id does not belong to this ticket")
        evidence_rows = (
            await db.execute(text(f"""
                select id,work_order_id from evidence_items
                where tenant_id={TENANT} and ticket_id=:ticket_id and status='active'
            """), {"ticket_id": body.ticket_id})
        ).mappings().all()
        valid_evidence = {
            str(row["id"])
            for row in evidence_rows
            if row["work_order_id"] is None or str(row["work_order_id"]) in body.result.work_order_ids
        }
        if any(str(evidence_id) not in valid_evidence for evidence_id in body.result.evidence_ids):
            raise HTTPException(422, "A result evidence_id is not active evidence for this ticket")
        verification["verified_work_order_ids"] = sorted(
            work_id for work_id, row in work_by_id.items() if row["status"] == "completed"
        )
        verification["verified_evidence_ids"] = sorted(valid_evidence)
    elif body.message_type == "cancelled":
        if ticket["status"] != "cancelled":
            raise HTTPException(409, "Backend has not confirmed ticket cancellation")
        if pending is not None:
            await db.execute(text(f"""
                delete from vh_reception_supervisor_pending
                where tenant_id={TENANT} and ticket_id=:ticket_id and ticket_generation=:generation
            """), {"ticket_id": body.ticket_id, "generation": body.ticket_generation})
        verification["cancellation_confirmed"] = True
    elif body.message_type == "information_requested":
        await db.execute(text(f"""
            insert into vh_reception_supervisor_pending
              (tenant_id,ticket_id,team_id,ticket_generation,correlation_id,pending_kind,
               supervisor_message_id)
            values ({TENANT},:ticket_id,:team_id,:generation,:correlation_id,'information',:message_id)
        """), {"ticket_id": body.ticket_id, "team_id": body.team_id,
               "generation": body.ticket_generation, "correlation_id": body.correlation_id,
               "message_id": body.message_id})
        verification["pending_request"] = "information"
    elif body.message_type == "plan_approval_requested":
        plans = (
            await db.execute(text(f"""
                select id,version from vh_ticket_plans where tenant_id={TENANT}
                  and ticket_id=:ticket_id and status='resident_pending' order by created_at desc,id limit 2
                for update
            """), {"ticket_id": body.ticket_id})
        ).mappings().all()
        if len(plans) != 1:
            raise HTTPException(409, "Exactly one resident-pending plan is required")
        plan = plans[0]
        await db.execute(text(f"""
            insert into vh_reception_supervisor_pending
              (tenant_id,ticket_id,team_id,ticket_generation,correlation_id,pending_kind,
               supervisor_message_id,plan_id,plan_version)
            values ({TENANT},:ticket_id,:team_id,:generation,:correlation_id,'plan_approval',
              :message_id,:plan_id,:plan_version)
        """), {"ticket_id": body.ticket_id, "team_id": body.team_id,
               "generation": body.ticket_generation, "correlation_id": body.correlation_id,
               "message_id": body.message_id, "plan_id": plan["id"],
               "plan_version": plan["version"]})
        verification["pending_request"] = "plan_approval"
        verification["plan_id"] = str(plan["id"])
        verification["plan_version"] = plan["version"]
    elif body.message_type == "failed" and pending is not None:
        await db.execute(text(f"""
            delete from vh_reception_supervisor_pending
            where tenant_id={TENANT} and ticket_id=:ticket_id and ticket_generation=:generation
        """), {"ticket_id": body.ticket_id, "generation": body.ticket_generation})
        verification["pending_request_cleared"] = True

    response_body = {"result": payload, "replayed": False, "verification": verification}
    await db.execute(text(f"""
        insert into vh_reception_supervisor_messages
          (tenant_id,direction,message_id,correlation_id,ticket_id,team_id,ticket_generation,
           message_type,payload,payload_hash,response_body,created_by)
        values ({TENANT},'supervisor_to_reception',:message_id,:correlation_id,:ticket_id,
          :team_id,:generation,:message_type,cast(:payload as jsonb),:payload_hash,
          cast(:response as jsonb),:actor)
    """), {"message_id": body.message_id, "correlation_id": body.correlation_id,
           "ticket_id": body.ticket_id, "team_id": body.team_id,
           "generation": body.ticket_generation, "message_type": body.message_type,
           "payload": json.dumps(payload), "payload_hash": payload_hash,
           "response": json.dumps(response_body), "actor": actor})
    await audit(db, actor, "reception_supervisor.result_received", "ticket",
                str(body.ticket_id), {"messageId": body.message_id, "messageType": body.message_type})
    return response_body


@router.get("/tickets/{ticket_id}/results", response_model=ResultPage, response_model_exclude_unset=True)
async def resident_results(
    ticket_id: UUID,
    scope: RESIDENT,
    cursor: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=50, ge=1, le=100),
):
    db, actor = scope
    owner = await db.execute(text(f"""
        select 1 from tickets where id=:ticket_id and requester_user_id=:actor and tenant_id={TENANT}
    """), {"ticket_id": ticket_id, "actor": actor})
    if owner.first() is None:
        raise HTTPException(404, "Resident ticket not found")
    after_at, after_id = _decode_cursor(cursor)
    rows = (
        await db.execute(text(f"""
            select id,payload,created_at from vh_reception_supervisor_messages
            where tenant_id={TENANT} and ticket_id=:ticket_id and direction='supervisor_to_reception'
              and (:after_at is null or (created_at,id)>
                (cast(:after_at as timestamptz),cast(:after_id as uuid)))
            order by created_at,id limit :limit
        """), {"ticket_id": ticket_id, "after_at": after_at, "after_id": after_id,
               "limit": limit + 1})
    ).mappings().all()
    selected = rows[:limit]
    return {
        "items": [SupervisorToReceptionResult.model_validate(row["payload"]) for row in selected],
        "next_cursor": _encode_cursor(dict(selected[-1])) if selected else cursor,
    }
