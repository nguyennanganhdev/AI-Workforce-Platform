"""Authenticated operation boundary for Reception; no agent/model execution."""

import json
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator
from sqlalchemy import text

from .resident_api import resident_scope
from .v3_agent_results import agent_result
from .v3_audit import audit
from .v3_conversation_images import AttachImages
from .v3_conversation_images import attach as attach_conversation_images
from .v3_reception import (
    DraftCreate,
    DraftFields,
    context,
    draft,
)
from .v3_reception import (
    commit as commit_draft,
)
from .v3_reception_supervisor import (
    Fact,
    ReceptionToSupervisorMessage,
    resident_results,
    submit_reception_message,
)
from .v3_resident import _owned_chat, get_my_ticket
from .v3_security import digest

router = APIRouter(tags=["Reception operation API"])
Scope = Annotated[tuple, Depends(resident_scope, scope="function")]
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"

Operation = Literal[
    "create_ticket_draft",
    "get_verified_resident_context",
    "update_ticket_incident",
    "submit_ticket_assessment",
    "resolve_management_destination",
    "handoff_ticket",
    "register_supervisor_wait",
    "get_supervisor_event",
    "append_ticket_information",
    "respond_supervisor_interaction",
    "request_ticket_cancellation",
    "get_ticket_status",
    "process_self_help",
    "escalate_emergency",
]


class OperationCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Operation
    input: dict[str, Any] = Field(default_factory=dict, max_length=100)
    context: dict[str, Any] = Field(default_factory=dict, max_length=30)
    idempotency_key: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def bound_serialized_input(self):
        encoded = json.dumps(
            {"input": self.input, "context": self.context},
            ensure_ascii=False,
            default=str,
        )
        if len(encoded) > 80_000:
            raise ValueError("input and context exceed 80 KB")
        for key in ("tenantId", "principalId", "bindingId", "runId", "requestId"):
            value = self.context.get(key)
            limit = 128 if key == "requestId" else 200
            if value is not None and (
                not isinstance(value, str) or not value or len(value) > limit
            ):
                raise ValueError(
                    f"context.{key} must be a non-empty string of at most {limit} characters"
                )
        return self


class TicketAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: Literal["low", "normal", "high", "critical"]
    severity: Literal[
        "unknown", "minor", "moderate", "major", "critical", "not_applicable"
    ]
    is_emergency: bool = False
    reason: StrictStr = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def emergency_is_critical(self):
        if self.is_emergency and self.priority != "critical":
            raise ValueError("Emergency assessment requires critical priority")
        return self


def _context_identity(scope, call: OperationCall) -> str:
    actor = scope[1]
    principal = call.context.get("principalId")
    if principal is not None and str(principal) != str(actor):
        raise HTTPException(
            403, "context.principalId does not match the authenticated resident"
        )
    return str(actor)


async def _tenant_id(db) -> str:
    value = await db.execute(text("select current_setting('app.tenant_id', true)"))
    tenant = value.scalar_one_or_none()
    if not tenant:
        raise HTTPException(503, "V3 tenant context is unavailable")
    return str(tenant)


def _uuid(value: Any, field: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(422, f"{field} must be a UUID") from exc


def _check_context_tenant(call: OperationCall, tenant: str) -> None:
    supplied = call.context.get("tenantId")
    if supplied is not None:
        try:
            matches = UUID(str(supplied)) == UUID(tenant)
        except ValueError:
            matches = False
        if not matches:
            raise HTTPException(
                403, "context.tenantId does not match the authenticated tenant"
            )


def _operation_hash(call: OperationCall) -> str:
    # Trace identifiers may change on a retry; only the business operation and input
    # participate in idempotency comparison.
    return digest({"operation": call.operation, "input": call.input})


async def _lock_idempotency(db, tenant: str, actor: str, call: OperationCall):
    command_type = f"reception:{call.operation}"
    await db.execute(
        text("select pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": f"{tenant}:{actor}:{command_type}:{call.idempotency_key}"},
    )
    old = (
        (
            await db.execute(
                text(f"""
                select payload_hash,response_json,status from vh_command_receipt
                where tenant_id={TENANT} and actor_type='user' and actor_id=:actor
                  and command_type=:command_type and idempotency_key=:key
                for update
            """),
                {
                    "actor": actor,
                    "command_type": command_type,
                    "key": call.idempotency_key,
                },
            )
        )
        .mappings()
        .first()
    )
    if old is not None:
        if old["payload_hash"] != _operation_hash(call):
            raise HTTPException(409, "IDEMPOTENCY_KEY_REUSED")
        if old["status"] != "COMPLETED" or old["response_json"] is None:
            raise HTTPException(409, "OPERATION_IN_PROGRESS")
        response = dict(old["response_json"])
        response["replayed"] = True
        return response
    await db.execute(
        text(f"""
            insert into vh_command_receipt
              (tenant_id,actor_type,actor_id,command_type,idempotency_key,payload_hash,
               subject_type,status)
            values ({TENANT},'user',:actor,:command_type,:key,:payload_hash,
               'reception_operation','IN_PROGRESS')
        """),
        {
            "actor": actor,
            "command_type": command_type,
            "key": call.idempotency_key,
            "payload_hash": _operation_hash(call),
        },
    )
    return None


async def _complete_idempotency(
    db, tenant: str, actor: str, call: OperationCall, response: dict
):
    encoded = json.dumps(jsonable_encoder(response), ensure_ascii=False)
    await db.execute(
        text(f"""
            update vh_command_receipt set subject_id=:subject_id,
              response_json=cast(:response as jsonb),status='COMPLETED',completed_at=now()
            where tenant_id={TENANT} and actor_type='user' and actor_id=:actor
              and command_type=:command_type and idempotency_key=:key
        """),
        {
            "subject_id": call.context.get("requestId") or call.idempotency_key,
            "response": encoded,
            "actor": actor,
            "command_type": f"reception:{call.operation}",
            "key": call.idempotency_key,
        },
    )


async def _draft_row(scope, channel_id: str, draft_id: UUID, *, lock: bool = False):
    await _owned_chat(scope, channel_id, lock=lock)
    row = (
        (
            await scope[0].execute(
                text(
                    """
                select id,channel_id,body from messages
                where id=:draft_id and channel_id=:channel_id and sender_user_id=:actor
                  and body->>'type'='ticket_draft'
            """
                    + (" for update" if lock else "")
                ),
                {"draft_id": draft_id, "channel_id": channel_id, "actor": scope[1]},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Ticket draft not found")
    return dict(row)


async def _save_draft(scope, row: dict[str, Any], body: dict[str, Any]):
    await scope[0].execute(
        text(
            "update messages set body=cast(:body as jsonb) where id=:id and channel_id=:channel"
        ),
        {
            "body": json.dumps(body, ensure_ascii=False),
            "id": row["id"],
            "channel": row["channel_id"],
        },
    )


async def _update_incident(scope, call: OperationCall):
    data = call.input
    channel_id = str(data.get("channel_id") or "")
    draft_id = _uuid(data.get("draft_id"), "draft_id")
    index = data.get("index", 0)
    patch = data.get("fields")
    if patch is None:
        patch = {
            key: value
            for key, value in data.items()
            if key
            in {
                "title",
                "description",
                "domain_id",
                "building_id",
                "unit_id",
                "category_id",
                "request_kind",
                "source_message_id",
                "facts",
                "file_ids",
            }
        }
    if (
        not channel_id
        or not isinstance(draft_id, UUID)
        or not isinstance(index, int)
        or index < 0
    ):
        raise HTTPException(
            422, "channel_id, draft_id and non-negative index are required"
        )
    if not isinstance(patch, dict):
        raise HTTPException(422, "fields must be an object")
    allowed = {
        "title",
        "description",
        "domain_id",
        "building_id",
        "unit_id",
        "category_id",
        "request_kind",
        "source_message_id",
        "facts",
        "file_ids",
    }
    unknown = set(patch) - allowed
    if unknown:
        raise HTTPException(
            422, {"message": "Unsupported incident fields", "fields": sorted(unknown)}
        )
    row = await _draft_row(scope, channel_id, draft_id, lock=True)
    value = dict(row["body"])
    incidents = list(value.get("incidents") or [])
    if index >= len(incidents):
        raise HTTPException(422, "Invalid incident index")
    try:
        incidents[index] = DraftFields.model_validate(
            {**incidents[index], **patch}
        ).model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(422, "Invalid incident fields") from exc
    value["incidents"] = incidents
    await _save_draft(scope, row, value)
    from .v3_reception import draft_result

    return agent_result(
        "update_ticket_incident",
        draft_result({**row, "body": value}),
        {"channel_id": channel_id},
    )


async def _submit_assessment(scope, call: OperationCall):
    data = call.input
    channel_id = str(data.get("channel_id") or "")
    draft_id = _uuid(data.get("draft_id"), "draft_id")
    index = data.get("index", 0)
    if (
        not channel_id
        or not isinstance(draft_id, UUID)
        or not isinstance(index, int)
        or index < 0
    ):
        raise HTTPException(
            422, "channel_id, draft_id and non-negative index are required"
        )
    try:
        assessment = TicketAssessment.model_validate(
            data.get("assessment", {})
        ).model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(422, "Invalid ticket assessment") from exc
    row = await _draft_row(scope, channel_id, draft_id, lock=True)
    value = dict(row["body"])
    incidents = value.get("incidents") or []
    if index >= len(incidents):
        raise HTTPException(422, "Invalid incident index")
    assessments = list(value.get("assessments") or [None] * len(incidents))
    assessments.extend([None] * (len(incidents) - len(assessments)))
    assessments[index] = assessment
    value["assessments"] = assessments
    await _save_draft(scope, row, value)
    return agent_result(
        "submit_ticket_assessment",
        {
            "draftId": str(draft_id),
            "index": index,
            "assessment": assessment,
            "status": "recorded",
        },
        {"channel_id": channel_id},
    )


async def _resolve_destination(scope, call: OperationCall):
    data = call.input
    channel_id = str(data.get("channel_id") or "")
    draft_id = _uuid(data.get("draft_id"), "draft_id")
    index = data.get("index", 0)
    if (
        not channel_id
        or not isinstance(draft_id, UUID)
        or not isinstance(index, int)
        or index < 0
    ):
        raise HTTPException(
            422, "channel_id, draft_id and non-negative index are required"
        )
    row = await _draft_row(scope, channel_id, draft_id)
    incidents = row["body"].get("incidents") or []
    if index >= len(incidents):
        raise HTTPException(422, "Invalid incident index")
    incident = incidents[index]
    required = [
        name
        for name in ("domain_id", "building_id", "unit_id", "category_id")
        if not incident.get(name)
    ]
    if required:
        return agent_result(
            "resolve_management_destination",
            {"available": False, "missingFields": required},
            {"channel_id": channel_id},
        )
    db, actor = scope
    place = (
        (
            await db.execute(
                text(
                    """
            select u.id as unit_id,b.id as building_id,b.site_id,b.zone_id,
                   si.domain_id,u.code as unit_code,b.code as building_code
            from unit_residents ur join units u on u.id=ur.unit_id and u.tenant_id=ur.tenant_id
            join buildings b on b.id=u.building_id and b.tenant_id=u.tenant_id
            join sites si on si.id=b.site_id and si.tenant_id=b.tenant_id
            where ur.user_id=:actor and ur.unit_id=cast(:unit_id as uuid)
              and ur.verification_status='verified' and ur.valid_from<=now()
              and (ur.valid_to is null or ur.valid_to>now())
              and b.id=cast(:building_id as uuid) and si.domain_id=cast(:domain_id as uuid)
              and ur.tenant_id="""
                    + TENANT
                    + """ and u.status='active' and b.status='active'
              and si.status='active'
        """
                ),
                {
                    "actor": actor,
                    "unit_id": incident["unit_id"],
                    "building_id": incident["building_id"],
                    "domain_id": incident["domain_id"],
                },
            )
        )
        .mappings()
        .first()
    )
    if place is None:
        raise HTTPException(
            403, "Verified residence in the selected building and domain is required"
        )
    coverage_rows = (
        (
            await db.execute(
                text(f"""
            select mc.management_unit_id,mc.scope_id,mc.priority,
              case s.kind when 'building' then 4 when 'zone' then 3 when 'site' then 2 else 1 end as specificity
            from management_coverage mc join access_scopes s on s.id=mc.scope_id and s.tenant_id=mc.tenant_id
            join management_units mu on mu.id=mc.management_unit_id and mu.tenant_id=mc.tenant_id
            join service_categories cat on cat.id=mc.service_category_id and cat.tenant_id=mc.tenant_id
            where mc.service_category_id=cast(:category_id as uuid) and cat.enabled and mu.status='active'
              and mc.valid_from<=now() and (mc.valid_to is null or mc.valid_to>now())
              and mc.tenant_id={TENANT}
              and (s.kind='tenant' or (s.kind='site' and s.site_id=:site_id)
                or (s.kind='zone' and s.zone_id=cast(:zone_id as uuid))
                or (s.kind='building' and s.building_id=:building_id))
            order by specificity desc,mc.priority desc,mc.id limit 2
        """),
                {
                    "category_id": incident["category_id"],
                    "site_id": place["site_id"],
                    "zone_id": place["zone_id"],
                    "building_id": place["building_id"],
                },
            )
        )
        .mappings()
        .all()
    )
    if not coverage_rows:
        return agent_result(
            "resolve_management_destination",
            {"available": False, "missingFields": ["management_coverage"]},
            {"channel_id": channel_id},
        )
    selected = coverage_rows[0]
    if (
        len(coverage_rows) > 1
        and (coverage_rows[1]["specificity"], coverage_rows[1]["priority"])
        == (selected["specificity"], selected["priority"])
        and coverage_rows[1]["management_unit_id"] != selected["management_unit_id"]
    ):
        raise HTTPException(409, "Ambiguous management coverage")
    management_unit = (
        (
            await db.execute(
                text(
                    f"select id,name from management_units where id=:id and tenant_id={TENANT}"
                ),
                {"id": selected["management_unit_id"]},
            )
        )
        .mappings()
        .first()
    )
    if management_unit is None:
        raise HTTPException(404, "Management destination is unavailable")
    workspaces = (
        (
            await db.execute(
                text(f"""
                select id from workspaces where management_unit_id=:management_unit_id
                  and tenant_id={TENANT} and status='active' order by id limit 2
            """),
                {"management_unit_id": selected["management_unit_id"]},
            )
        )
        .mappings()
        .all()
    )
    if len(workspaces) != 1:
        return agent_result(
            "resolve_management_destination",
            {
                "available": False,
                "managementUnitId": management_unit["id"],
                "managementUnitName": management_unit["name"],
                "buildingId": place["building_id"],
                "domainId": place["domain_id"],
                "serviceCategoryId": incident["category_id"],
                "missingFields": ["one active management workspace"],
            },
            {"channel_id": channel_id},
        )
    workspace_id = workspaces[0]["id"]
    channels = (
        (
            await db.execute(
                text(f"""
                select id,is_dispatch_default from channels where workspace_id=:workspace_id
                  and tenant_id={TENANT} and kind='management' order by id limit 20
            """),
                {"workspace_id": workspace_id},
            )
        )
        .mappings()
        .all()
    )
    default_channels = [
        channel for channel in channels if channel["is_dispatch_default"]
    ]
    destination_channels = default_channels if default_channels else channels
    if len(destination_channels) != 1:
        return agent_result(
            "resolve_management_destination",
            {
                "available": False,
                "managementUnitId": management_unit["id"],
                "workspaceId": workspace_id,
                "buildingId": place["building_id"],
                "domainId": place["domain_id"],
                "serviceCategoryId": incident["category_id"],
                "missingFields": ["one management group chat"],
            },
            {"channel_id": channel_id},
        )
    management_channel_id = destination_channels[0]["id"]
    supervisors = (
        (
            await db.execute(
                text(f"""
                select a.id,a.name,v.id as version_id from agents a
                join channel_agents ca on ca.agent_id=a.id and ca.tenant_id=a.tenant_id
                left join lateral (
                  select id from agent_versions where agent_id=a.id and tenant_id=a.tenant_id
                  order by version_no desc limit 1
                ) v on true
                where a.workspace_id=:workspace_id and a.tenant_id={TENANT}
                  and a.status='active' and a.purpose='supervisor'
                  and ca.channel_id=:channel_id order by a.id limit 2
            """),
                {"workspace_id": workspace_id, "channel_id": management_channel_id},
            )
        )
        .mappings()
        .all()
    )
    if len(supervisors) > 1:
        raise HTTPException(
            409, "Multiple active Supervisors are assigned to the management group"
        )
    supervisor = supervisors[0] if supervisors else None
    result = {
        "available": bool(
            supervisor is not None and supervisor["version_id"] is not None
        ),
        "managementUnitId": management_unit["id"],
        "managementUnitName": management_unit["name"],
        "workspaceId": workspace_id,
        "channelId": management_channel_id,
        "supervisorAgentId": supervisor["id"] if supervisor else None,
        "supervisorName": supervisor["name"] if supervisor else None,
        "supervisorVersionId": supervisor["version_id"] if supervisor else None,
        "buildingId": place["building_id"],
        "domainId": place["domain_id"],
        "serviceCategoryId": incident["category_id"],
    }
    if not result["available"]:
        result["missingFields"] = ["active Supervisor and version"]
    return agent_result(
        "resolve_management_destination", result, {"channel_id": channel_id}
    )


async def _register_wait(scope, call: OperationCall):
    ticket_id = _uuid(call.input.get("ticket_id"), "ticket_id")
    db, actor = scope
    row = (
        (
            await db.execute(
                text(f"""
            select t.id,t.code,t.reopen_count,tm.id as team_id,tm.ticket_generation
            from tickets t left join agent_teams tm on tm.ticket_id=t.id and tm.tenant_id=t.tenant_id
              and tm.ticket_generation=t.reopen_count and tm.status not in ('completed','failed','cancelled')
            where t.id=:ticket_id and t.requester_user_id=:actor and t.tenant_id={TENANT}
            order by tm.created_at desc limit 1
        """),
                {"ticket_id": ticket_id, "actor": actor},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Resident ticket not found")
    if row["team_id"] is None:
        return agent_result(
            "register_supervisor_wait",
            {
                "registered": False,
                "ticketId": ticket_id,
                "missingFields": ["current_supervisor_team"],
            },
        )
    return agent_result(
        "register_supervisor_wait",
        {
            "registered": True,
            "ticketId": ticket_id,
            "ticketCode": row["code"],
            "ticketGeneration": row["reopen_count"],
            "teamId": row["team_id"],
            "waitMode": "poll",
            "resultsPath": f"/api/domains/vinhomes/resident/reception-supervisor/tickets/{ticket_id}/results",
            "cursor": call.input.get("cursor"),
        },
    )


async def _supervisor_event(scope, call: OperationCall):
    ticket_id = _uuid(call.input.get("ticket_id"), "ticket_id")
    cursor = call.input.get("cursor")
    limit = call.input.get("limit", 50)
    if cursor is not None and not isinstance(cursor, str):
        raise HTTPException(422, "cursor must be a string")
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        raise HTTPException(422, "limit must be from 1 to 100")
    result = await resident_results(ticket_id, scope, cursor=cursor, limit=limit)
    return agent_result("get_supervisor_event", result, {"ticket_id": ticket_id})


async def _escalate_emergency(scope, call: OperationCall):
    ticket_id = _uuid(call.input.get("ticket_id"), "ticket_id")
    reason = call.input.get("reason")
    source_message_id = call.input.get("source_message_id")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise HTTPException(
            422, "reason is required and must not exceed 2000 characters"
        )
    if not isinstance(source_message_id, str) or not source_message_id:
        raise HTTPException(422, "source_message_id is required")
    db, actor = scope
    ticket = (
        (
            await db.execute(
                text(f"""
            select id,channel_id,status,priority,severity,is_emergency,last_event_seq,
                   management_unit_id,site_id,zone_id,building_id,version
            from tickets where id=:ticket_id and requester_user_id=:actor and tenant_id={TENANT}
            for update
        """),
                {"ticket_id": ticket_id, "actor": actor},
            )
        )
        .mappings()
        .first()
    )
    if ticket is None:
        raise HTTPException(404, "Resident ticket not found")
    if ticket["status"] in {"resolved", "closed", "cancelled"}:
        raise HTTPException(409, "A final ticket cannot be emergency-escalated")
    source = (
        await db.execute(
            text(f"""
            select 1 from messages where cast(id as text)=:message_id and channel_id=:channel_id
              and sender_kind='user' and sender_user_id=:actor and tenant_id={TENANT}
        """),
            {
                "message_id": source_message_id,
                "channel_id": ticket["channel_id"],
                "actor": actor,
            },
        )
    ).first()
    if source is None:
        raise HTTPException(
            422,
            "source_message_id must identify a resident message in this conversation",
        )
    if ticket["is_emergency"]:
        return agent_result(
            "escalate_emergency",
            {
                "ticketId": ticket_id,
                "status": ticket["status"],
                "priority": ticket["priority"],
                "severity": ticket["severity"],
                "isEmergency": True,
                "notificationQueued": False,
                "alreadyEscalated": True,
            },
        )
    await db.execute(
        text(f"""
        update tickets set priority='critical',severity='critical',is_emergency=true
        where id=:ticket_id and tenant_id={TENANT}
    """),
        {"ticket_id": ticket_id},
    )
    from .v3_mutations import record_event

    event_id = await record_event(
        (db, actor, False),
        dict(ticket),
        "ticket.emergency_escalated",
        json.dumps({"reason": reason.strip(), "sourceMessageId": source_message_id}),
    )
    deliveries = await db.execute(
        text(f"""
        insert into notification_deliveries
          (tenant_id,user_id,ticket_event_id,channel,dedupe_key,payload,status,available_at)
        select r.tenant_id,m.user_id,:event_id,'in_app',:dedupe_key,
          cast(:payload as jsonb),'pending',now()
        from scoped_user_roles r
        join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
        join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
        join users u on u.id=m.user_id and u.status='active'
        where r.tenant_id={TENANT} and r.role_code='management' and m.status='active'
          and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
          and (s.kind='tenant' or (s.kind='management' and s.management_unit_id=:management_unit_id)
            or (s.kind='site' and s.site_id=:site_id)
            or (s.kind='zone' and s.zone_id=cast(:zone_id as uuid))
            or (s.kind='building' and s.building_id=:building_id))
        on conflict (tenant_id,user_id,channel,dedupe_key) do nothing
        returning id
    """),
        {
            "event_id": event_id,
            "dedupe_key": f"ticket:{ticket_id}:emergency:{event_id}",
            "payload": json.dumps(
                {"type": "ticket.emergency_escalated", "ticketId": str(ticket_id)}
            ),
            "management_unit_id": ticket["management_unit_id"],
            "site_id": ticket["site_id"],
            "zone_id": ticket["zone_id"],
            "building_id": ticket["building_id"],
        },
    )
    return agent_result(
        "escalate_emergency",
        {
            "ticketId": ticket_id,
            "eventId": event_id,
            "priority": "critical",
            "severity": "critical",
            "isEmergency": True,
            "notificationQueued": deliveries.rowcount > 0,
            "notificationCount": max(deliveries.rowcount, 0),
            "deliveryStatus": "pending"
            if deliveries.rowcount > 0
            else "no_matching_bql_recipient",
        },
    )


async def _send_supervisor_message(
    scope, call: OperationCall, *, expected_type: str | None = None
):
    message = call.input.get("message") or call.input.get("schema_v2")
    if not isinstance(message, dict):
        raise HTTPException(
            422, "message must contain a schema_v2 Reception/Supervisor message"
        )
    try:
        body = ReceptionToSupervisorMessage.model_validate(message)
    except Exception as exc:
        raise HTTPException(
            422, "Invalid schema_v2 Reception/Supervisor message"
        ) from exc
    if expected_type and body.message_type != expected_type:
        raise HTTPException(422, f"message_type must be {expected_type}")
    return await submit_reception_message(body, scope)


async def _handoff_draft(scope, call: OperationCall):
    data = call.input
    channel_id = str(data.get("channel_id") or "")
    draft_id = _uuid(data.get("draft_id"), "draft_id")
    index = data.get("index", 0)
    if not channel_id or not isinstance(index, int) or index < 0:
        raise HTTPException(422, "channel_id and non-negative index are required")
    row = await _draft_row(scope, channel_id, draft_id, lock=True)
    draft_body = dict(row["body"])
    incidents = draft_body.get("incidents") or []
    if index >= len(incidents):
        raise HTTPException(422, "Invalid incident index")
    incident = incidents[index]
    required = [
        name
        for name in (
            "title",
            "description",
            "domain_id",
            "building_id",
            "unit_id",
            "category_id",
            "request_kind",
        )
        if incident.get(name) is None
    ]
    assessments = draft_body.get("assessments") or []
    assessment = assessments[index] if index < len(assessments) else None
    if assessment is None:
        required.append("assessment")
    if required:
        return agent_result(
            "handoff_ticket",
            {
                "accepted": False,
                "draftId": str(draft_id),
                "index": index,
                "missingFields": required,
            },
            {"channel_id": channel_id},
        )

    resident_context = await context(scope)
    resident = resident_context["resident"]
    if not resident.get("name") or not resident.get("phone_e164"):
        return agent_result(
            "handoff_ticket",
            {
                "accepted": False,
                "draftId": str(draft_id),
                "missingFields": ["verified_resident_name", "verified_resident_phone"],
            },
            {"channel_id": channel_id},
        )
    incident["contact_name"] = resident["name"]
    incident["contact_phone"] = resident["phone_e164"]
    draft_body["incidents"][index] = incident
    await _save_draft(scope, row, draft_body)

    destination = await _resolve_destination(
        scope, call.model_copy(update={"operation": "resolve_management_destination"})
    )
    if not destination.get("available"):
        return agent_result(
            "handoff_ticket",
            {
                "accepted": False,
                "draftId": str(draft_id),
                "destination": destination,
                "missingFields": destination.get(
                    "missingFields", ["management_destination"]
                ),
            },
            {"channel_id": channel_id},
        )

    try:
        facts = [Fact.model_validate(fact) for fact in (incident.get("facts") or [])]
    except Exception as exc:
        raise HTTPException(422, "Invalid Reception fact") from exc
    file_ids = [
        _uuid(file_id, "file_id") for file_id in (incident.get("file_ids") or [])
    ]
    handoff_reason = call.input.get("handoff_reason", "needs_staff")
    if handoff_reason not in {
        "needs_staff",
        "self_help_declined",
        "self_help_failed",
        "emergency",
    }:
        raise HTTPException(422, "Invalid handoff_reason")

    ticket_response = await commit_draft(channel_id, draft_id, index, scope)
    ticket_id = _uuid(ticket_response.get("id"), "created ticket id")
    db, actor = scope
    tenant = await _tenant_id(db)
    if file_ids:
        await attach_conversation_images(
            ticket_id, AttachImages(file_ids=file_ids), scope
        )
        from .v3_ticket_result import resident_ticket_result

        ticket_response = await resident_ticket_result(
            db,
            actor,
            ticket_id,
            replayed=ticket_response.get("creationOutcome") == "replayed",
        )
    snapshot = (
        (
            await db.execute(
                text(f"""
            select t.id,t.code,t.requester_user_id,t.channel_id,t.unit_id,t.building_id,t.domain_id,
              t.title,t.description,t.request_kind,t.category_id,t.priority,t.severity,t.is_emergency,
              t.current_triage_decision_id,t.version,t.reopen_count,t.created_at,t.management_unit_id,
              u.code as unit_number,b.code as building_code,b.name as building_name,d.name as domain_name,
              mc.scope_id as location_scope_id,coalesce(t.contact_name,u0.name) as resident_name,
              coalesce(t.contact_phone,u0.phone_e164) as resident_phone
            from tickets t join units u on u.id=t.unit_id and u.tenant_id=t.tenant_id
            join buildings b on b.id=t.building_id and b.tenant_id=t.tenant_id
            join domains d on d.id=t.domain_id and d.tenant_id=t.tenant_id
            left join management_coverage mc on mc.id=t.coverage_id and mc.tenant_id=t.tenant_id
            join users u0 on u0.id=t.requester_user_id
            where t.id=:ticket_id and t.requester_user_id=:actor and t.tenant_id={TENANT}
        """),
                {"ticket_id": ticket_id, "actor": actor},
            )
        )
        .mappings()
        .first()
    )
    if snapshot is None:
        raise HTTPException(404, "Created resident ticket not found")
    if str(snapshot["management_unit_id"]) != str(destination["managementUnitId"]):
        raise HTTPException(409, "Management coverage changed before handoff")

    team = (
        (
            await db.execute(
                text(f"""
            select id,workspace_id,channel_id,ticket_id,ticket_generation,supervisor_agent_id,status
            from agent_teams where ticket_id=:ticket_id and tenant_id={TENANT}
              and ticket_generation=:generation and status not in ('completed','failed','cancelled')
            order by created_at desc limit 1 for update
        """),
                {"ticket_id": ticket_id, "generation": snapshot["reopen_count"]},
            )
        )
        .mappings()
        .first()
    )
    supervisor_agent_id = destination["supervisorAgentId"]
    supervisor_version_id = destination["supervisorVersionId"]
    if team is not None:
        if str(team["workspace_id"]) != str(destination["workspaceId"]):
            raise HTTPException(
                409, "An active Supervisor team already exists in a different workspace"
            )
        if str(team["channel_id"]) != str(destination["channelId"]):
            raise HTTPException(
                409,
                "An active Supervisor team already exists in a different group chat",
            )
        team_id = team["id"]
        supervisor_agent_id = team["supervisor_agent_id"]
    else:
        team_id = uuid5(
            NAMESPACE_URL,
            f"reception-supervisor-team:{tenant}:{destination['channelId']}:{ticket_id}:{snapshot['reopen_count']}",
        )
        await db.execute(
            text(f"""
            insert into agent_teams
              (id,tenant_id,workspace_id,channel_id,ticket_id,ticket_generation,
               supervisor_agent_id,status,shared_state,requested_by_user_id)
            values (:id,{TENANT},:workspace_id,:channel_id,:ticket_id,:generation,
               :supervisor,'queued',cast(:state as jsonb),:actor)
        """),
            {
                "id": team_id,
                "workspace_id": destination["workspaceId"],
                "channel_id": destination["channelId"],
                "ticket_id": ticket_id,
                "generation": snapshot["reopen_count"],
                "supervisor": supervisor_agent_id,
                "state": json.dumps(
                    {
                        "request": {
                            "ticketId": str(ticket_id),
                            "supervisorVersionId": str(supervisor_version_id),
                            "source": "reception_handoff",
                        }
                    }
                ),
                "actor": actor,
            },
        )
        await db.execute(
            text(f"""
            insert into team_members(tenant_id,team_id,agent_id,version_id,member_kind,status)
            values ({TENANT},:team_id,:agent_id,:version_id,'supervisor','active')
            on conflict do nothing
        """),
            {
                "team_id": team_id,
                "agent_id": supervisor_agent_id,
                "version_id": supervisor_version_id,
            },
        )
        await audit(
            db,
            actor,
            "team.created",
            "agent_team",
            str(team_id),
            {"ticketId": str(ticket_id), "source": "reception_handoff"},
        )

    message_id = uuid5(
        NAMESPACE_URL,
        f"reception-ticket-submitted:{tenant}:{ticket_id}:{snapshot['reopen_count']}",
    )
    v2_message = ReceptionToSupervisorMessage(
        schema_version="2.0",
        message_id=str(message_id),
        correlation_id=str(
            call.context.get("runId")
            or call.input.get("correlation_id")
            or call.idempotency_key
        ),
        sent_at=datetime.now(UTC),
        message_type="ticket_submitted",
        message=str(call.input.get("handoff_message") or snapshot["description"]),
        source_message_id=incident.get("source_message_id"),
        tenant_id=UUID(tenant),
        domain_id=snapshot["domain_id"],
        domain_name=snapshot["domain_name"],
        workspace_id=destination["workspaceId"],
        team_id=team_id,
        ticket_id=ticket_id,
        ticket_code=snapshot["code"],
        ticket_generation=snapshot["reopen_count"],
        ticket_version=str(snapshot["version"]),
        resident={
            "resident_id": str(snapshot["requester_user_id"]),
            "resident_name": snapshot["resident_name"],
            "phone_number": snapshot["resident_phone"],
        },
        location={
            "location_scope_id": snapshot["location_scope_id"],
            "unit_id": snapshot["unit_id"],
            "unit_number": snapshot["unit_number"],
            "building_id": snapshot["building_id"],
            "building_code": snapshot["building_code"],
            "building_name": snapshot["building_name"],
        },
        request={
            "title": snapshot["title"],
            "description": snapshot["description"],
            "request_kind": snapshot["request_kind"],
            "category_id": snapshot["category_id"],
            "priority": snapshot["priority"],
            "severity": snapshot["severity"],
            "is_emergency": snapshot["is_emergency"],
            "triage_decision_id": snapshot["current_triage_decision_id"],
            "handoff_reason": handoff_reason,
        },
        facts=facts,
        file_ids=file_ids,
        created_at=snapshot["created_at"],
    )
    handoff = await submit_reception_message(v2_message, scope)
    draft_body["ticket_id"] = str(ticket_id)
    draft_body["ticket_code"] = snapshot["code"]
    draft_body["team_id"] = str(team_id)
    await _save_draft(scope, row, draft_body)
    return {
        "accepted": True,
        "ticket": ticket_response,
        "team": {
            "id": str(team_id),
            "workspaceId": str(destination["workspaceId"]),
            "channelId": str(destination["channelId"]),
            "supervisorAgentId": str(supervisor_agent_id),
        },
        "handoff": handoff,
    }


async def _dispatch(scope, call: OperationCall):
    if call.operation == "get_verified_resident_context":
        result = await context(scope)
        result["agentContext"]["operation"] = call.operation
        return result
    if call.operation == "create_ticket_draft":
        channel_id = str(call.input.get("channel_id") or "")
        if not channel_id:
            raise HTTPException(422, "channel_id is required")
        incidents = call.input.get("incidents")
        if incidents is None:
            flat = {
                key: value
                for key, value in call.input.items()
                if key
                not in {
                    "channel_id",
                    "client_message_id",
                    "handoff_reason",
                }
            }
            incidents = [call.input.get("incident", flat)]
        if not isinstance(incidents, list) or not incidents:
            raise HTTPException(422, "incidents must be a non-empty list")
        resident = (await context(scope))["resident"]
        verified_contact = {
            key: value
            for key, value in {
                "contact_name": resident.get("name"),
                "contact_phone": resident.get("phone_e164"),
            }.items()
            if value
        }
        incidents = [
            {**incident, **verified_contact} if isinstance(incident, dict) else incident
            for incident in incidents
        ]
        try:
            body = DraftCreate(
                incidents=incidents,
                client_message_id=str(
                    call.input.get("client_message_id")
                    or f"reception-draft:{digest(call.idempotency_key)}"
                ),
            )
        except Exception as exc:
            raise HTTPException(422, "Invalid ticket draft") from exc
        return await draft(channel_id, body, scope)
    if call.operation == "update_ticket_incident":
        return await _update_incident(scope, call)
    if call.operation == "submit_ticket_assessment":
        return await _submit_assessment(scope, call)
    if call.operation == "resolve_management_destination":
        return await _resolve_destination(scope, call)
    if call.operation == "handoff_ticket":
        if call.input.get("draft_id") is not None:
            return await _handoff_draft(scope, call)
        return await _send_supervisor_message(
            scope, call, expected_type="ticket_submitted"
        )
    if call.operation == "register_supervisor_wait":
        return await _register_wait(scope, call)
    if call.operation == "get_supervisor_event":
        return await _supervisor_event(scope, call)
    if call.operation == "append_ticket_information":
        return await _send_supervisor_message(
            scope, call, expected_type="information_provided"
        )
    if call.operation == "respond_supervisor_interaction":
        return await _send_supervisor_message(scope, call)
    if call.operation == "request_ticket_cancellation":
        return await _send_supervisor_message(
            scope, call, expected_type="cancel_requested"
        )
    if call.operation == "get_ticket_status":
        ticket_id = _uuid(call.input.get("ticket_id"), "ticket_id")
        return agent_result(
            "get_ticket_status",
            await get_my_ticket(ticket_id, scope),
            {"ticket_id": ticket_id},
        )
    if call.operation == "escalate_emergency":
        if call.input.get("draft_id") is not None:
            assessment = dict(call.input.get("assessment") or {})
            assessment.setdefault("priority", "critical")
            assessment.setdefault("severity", "critical")
            assessment["is_emergency"] = True
            nested = call.model_copy(
                update={
                    "operation": "submit_ticket_assessment",
                    "input": {**call.input, "assessment": assessment},
                }
            )
            return await _submit_assessment(scope, nested)
        return await _escalate_emergency(scope, call)
    if call.operation == "process_self_help":
        raise HTTPException(
            501,
            "Reception self-help requires the separately configured resident knowledge/RAG service",
        )
    raise HTTPException(422, "Unsupported Reception operation")


@router.post("/internal/reception/operations/execute")
async def execute(call: OperationCall, scope: Scope):
    actor = _context_identity(scope, call)
    tenant = await _tenant_id(scope[0])
    _check_context_tenant(call, tenant)
    replay = await _lock_idempotency(scope[0], tenant, actor, call)
    if replay is not None:
        return replay
    result = await _dispatch(scope, call)
    if not isinstance(result, dict):
        result = jsonable_encoder(result)
    response = {
        **result,
        "replayed": False,
        "agentContext": {
            **dict(result.get("agentContext") or {}),
            "operation": call.operation,
            "source": "business_api",
            "resourceContext": {
                **dict((result.get("agentContext") or {}).get("resourceContext") or {}),
                "tenantId": tenant,
                "principalId": actor,
                "bindingId": call.context.get("bindingId"),
                "runId": call.context.get("runId"),
                "requestId": call.context.get("requestId"),
            },
        },
    }
    await _complete_idempotency(scope[0], tenant, actor, call, response)
    return response


@router.post("/internal/reception/operations/reconcile")
async def reconcile(call: OperationCall, scope: Scope):
    actor = _context_identity(scope, call)
    db = scope[0]
    _check_context_tenant(call, await _tenant_id(db))
    receipt = (
        (
            await db.execute(
                text(f"""
            select payload_hash,response_json,status,created_at,completed_at
            from vh_command_receipt where tenant_id={TENANT} and actor_type='user'
              and actor_id=:actor and command_type=:command_type and idempotency_key=:key
        """),
                {
                    "actor": actor,
                    "command_type": f"reception:{call.operation}",
                    "key": call.idempotency_key,
                },
            )
        )
        .mappings()
        .first()
    )
    if receipt is None:
        return {
            "operation": call.operation,
            "found": False,
            "status": "not_found",
            "result": None,
        }
    if receipt["payload_hash"] != _operation_hash(call):
        raise HTTPException(409, "IDEMPOTENCY_KEY_REUSED")
    if receipt["status"] != "COMPLETED" or receipt["response_json"] is None:
        return {
            "operation": call.operation,
            "found": True,
            "status": "in_progress",
            "result": None,
        }
    return {
        "operation": call.operation,
        "found": True,
        "status": "completed",
        "result": receipt["response_json"],
    }
