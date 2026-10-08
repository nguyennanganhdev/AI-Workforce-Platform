"""Mock-contract Field Operations progress commands.

Pause, arrival, blocker and support records live under WorkOrder.result until the
shared platform contract defines normalized resources. They do not add canonical
WorkOrder statuses or alter SLA semantics.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..commands import CommandReceiptRepository
from ..commands.hashing import command_payload_hash
from ..concurrency import require_expected_version
from ..db.command_receipt import CommandReceiptStatus
from ..db.dependencies import get_db_session
from ..events import BusinessEventRepository
from ..request_context import DomainScope, RequestContext, get_domain_scope, get_request_context
from ..tasks.repository import TaskRepository
from .authority import FieldOperationsAuthority, FieldOperationsRole, get_field_operations_authority
from .field_operations_schemas import (
    ContractorArrivalPlanInput,
    ContractorResponseInput,
    EscalateWorkOrderInput,
    FieldOperationsStateRead,
    FieldOperationsVersionCommand,
    HandoverInput,
    PauseExecutionInput,
    ReportBlockerInput,
    RequestFieldSupportInput,
    SecurityAreaActionInput,
    SecurityIncidentReportInput,
)
from .field_operations_state import (
    FieldOperationsState,
    InvalidFieldOperationsState,
    check_in,
    check_out,
    escalate_work_order,
    add_security_report,
    pause_execution,
    plan_arrival,
    read_field_operations_state,
    record_handover,
    record_security_area_action,
    report_blocker,
    request_support,
    respond_to_contractor_work,
    resolve_blocker,
    resume_execution,
)
from .repository import WorkOrderRepository

router = APIRouter(tags=["field-operations-progress"])


def _tenant_id(context: RequestContext) -> UUID:
    try:
        return UUID(context.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Authenticated tenant identifier is invalid") from exc


def _require_scope(scope: DomainScope, incident_id: UUID) -> None:
    if scope.namespace != "vinhomes" or not any(
        subject.namespace == "vinhomes"
        and subject.subject_type == "incident"
        and subject.subject_id == str(incident_id)
        for subject in scope.subjects
    ):
        raise HTTPException(status_code=404, detail="WorkOrder not found")


async def _mutate(
    *,
    work_order_id: UUID,
    command_name: str,
    event_type: str,
    payload: BaseCommand,
    idempotency_key: str,
    apply: Callable[[Any], FieldOperationsState],
    context: RequestContext,
    scope: DomainScope,
    authority: FieldOperationsAuthority,
    session: AsyncSession,
    executor_only: bool = True,
    required_domain: str | None = None,
) -> FieldOperationsStateRead:
    tenant_id = _tenant_id(context)
    command_hash = command_payload_hash(
        {
            "workOrderId": str(work_order_id),
            "command": command_name,
            "payload": payload.model_dump(mode="json", by_alias=True),
        }
    )
    async with session.begin():
        receipts = CommandReceiptRepository(session)
        receipt = await receipts.get(
            tenant_id=tenant_id,
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            command_type=command_name,
            idempotency_key=idempotency_key,
            for_update=True,
        )
        repository = WorkOrderRepository(session)
        order = await repository.get_by_id_for_update(tenant_id=tenant_id, work_order_id=work_order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="WorkOrder not found")
        _require_scope(scope, order.incident_id)
        if not authority.can_read(order, scope):
            raise HTTPException(status_code=404, detail="WorkOrder not found")
        if required_domain is not None:
            task = await TaskRepository(session).get_by_id(tenant_id=tenant_id, task_id=order.task_id)
            if task is None or task.domain_type.value != required_domain:
                raise HTTPException(status_code=404, detail="WorkOrder not found")

        if receipt is not None:
            if receipt.payload_hash != command_hash:
                raise HTTPException(status_code=409, detail="IDEMPOTENCY_KEY_REUSED")
            if receipt.status is not CommandReceiptStatus.COMPLETED or receipt.response_json is None:
                raise HTTPException(status_code=409, detail="Command with this Idempotency-Key is still in progress")
            return FieldOperationsStateRead.model_validate(receipt.response_json)

        if executor_only:
            authority.require_execute(order)
        require_expected_version(order.version, payload.expected_version)
        try:
            state = apply(order)
        except InvalidFieldOperationsState as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        await session.flush()
        await session.refresh(order)
        await BusinessEventRepository(session).append(
            tenant_id=tenant_id,
            incident_id=order.incident_id,
            subject_type="WorkOrder",
            subject_id=str(order.id),
            event_type=event_type,
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            actor_version=None,
            data={"workOrderVersion": order.version, "fieldOperations": state.model_dump(mode="json", by_alias=True)},
            correlation_id=context.correlation_id,
        )
        receipt = receipts.add(
            tenant_id=tenant_id,
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            command_type=command_name,
            idempotency_key=idempotency_key,
            payload_hash=command_hash,
            subject_type="WorkOrder",
            subject_id=str(order.id),
        )
        response = FieldOperationsStateRead.model_validate(state.model_dump(mode="python", by_alias=True))
        await receipts.complete(
            receipt,
            subject_id=str(order.id),
            response_json=response.model_dump(mode="json", by_alias=True),
        )
        return response


BaseCommand = (
    FieldOperationsVersionCommand
    | PauseExecutionInput
    | ReportBlockerInput
    | RequestFieldSupportInput
    | ContractorResponseInput
    | ContractorArrivalPlanInput
    | EscalateWorkOrderInput
    | SecurityIncidentReportInput
    | SecurityAreaActionInput
    | HandoverInput
)


@router.get("/work-orders/{work_order_id}/field-operations", response_model=FieldOperationsStateRead)
async def get_field_operations_state(
    work_order_id: UUID,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> FieldOperationsStateRead:
    order = await WorkOrderRepository(session).get_by_id(tenant_id=_tenant_id(context), work_order_id=work_order_id)
    if order is None or not authority.can_read(order, scope):
        raise HTTPException(status_code=404, detail="WorkOrder not found")
    try:
        state = read_field_operations_state(order)
        return FieldOperationsStateRead.model_validate(state.model_dump(mode="python", by_alias=True))
    except InvalidFieldOperationsState as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/work-orders/{work_order_id}/pause", response_model=FieldOperationsStateRead)
async def pause_work_order(
    work_order_id: UUID,
    payload: PauseExecutionInput,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context), scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority), session: AsyncSession = Depends(get_db_session),
) -> FieldOperationsStateRead:
    return await _mutate(work_order_id=work_order_id, command_name="WO_PAUSE", event_type="WORK_ORDER_PAUSED", payload=payload, idempotency_key=idempotency_key, apply=lambda order: pause_execution(order, actor_id=context.actor.id, reason=payload.reason), context=context, scope=scope, authority=authority, session=session)


@router.post("/work-orders/{work_order_id}/resume", response_model=FieldOperationsStateRead)
async def resume_work_order(
    work_order_id: UUID,
    payload: FieldOperationsVersionCommand,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context), scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority), session: AsyncSession = Depends(get_db_session),
) -> FieldOperationsStateRead:
    return await _mutate(work_order_id=work_order_id, command_name="WO_RESUME", event_type="WORK_ORDER_RESUMED", payload=payload, idempotency_key=idempotency_key, apply=lambda order: resume_execution(order, actor_id=context.actor.id), context=context, scope=scope, authority=authority, session=session)


@router.post("/work-orders/{work_order_id}/check-in", response_model=FieldOperationsStateRead)
async def check_in_work_order(
    work_order_id: UUID,
    payload: FieldOperationsVersionCommand,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context), scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority), session: AsyncSession = Depends(get_db_session),
) -> FieldOperationsStateRead:
    return await _mutate(work_order_id=work_order_id, command_name="WO_CHECK_IN", event_type="WORK_ORDER_CHECKED_IN", payload=payload, idempotency_key=idempotency_key, apply=lambda order: check_in(order, actor_id=context.actor.id), context=context, scope=scope, authority=authority, session=session)


def _require_security_worker(context: RequestContext, authority: FieldOperationsAuthority) -> None:
    if context.actor.kind != "user" or FieldOperationsRole.SECURITY_WORKER not in authority.roles:
        raise HTTPException(status_code=403, detail="Security field role required")


@router.post("/work-orders/{work_order_id}/security/check-out", response_model=FieldOperationsStateRead)
async def check_out_security_work_order(
    work_order_id: UUID,
    payload: FieldOperationsVersionCommand,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context), scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority), session: AsyncSession = Depends(get_db_session),
) -> FieldOperationsStateRead:
    _require_security_worker(context, authority)
    return await _mutate(
        work_order_id=work_order_id, command_name="SECURITY_CHECK_OUT", event_type="SECURITY_CHECKED_OUT",
        payload=payload, idempotency_key=idempotency_key,
        apply=lambda order: check_out(order, actor_id=context.actor.id), context=context, scope=scope,
        authority=authority, session=session, required_domain="SECURITY",
    )


@router.post("/work-orders/{work_order_id}/security/reports", response_model=FieldOperationsStateRead)
async def submit_security_report(
    work_order_id: UUID,
    payload: SecurityIncidentReportInput,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context), scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority), session: AsyncSession = Depends(get_db_session),
) -> FieldOperationsStateRead:
    _require_security_worker(context, authority)
    return await _mutate(
        work_order_id=work_order_id, command_name="SECURITY_REPORT", event_type="SECURITY_INCIDENT_REPORTED",
        payload=payload, idempotency_key=idempotency_key,
        apply=lambda order: add_security_report(
            order, severity=payload.severity, summary=payload.summary, people_refs=payload.people_refs,
            vehicle_refs=payload.vehicle_refs, asset_refs=payload.asset_refs, actor_id=context.actor.id,
        ), context=context, scope=scope, authority=authority, session=session, required_domain="SECURITY",
    )


@router.post("/work-orders/{work_order_id}/security/area-actions", response_model=FieldOperationsStateRead)
async def record_security_area_action_route(
    work_order_id: UUID,
    payload: SecurityAreaActionInput,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context), scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority), session: AsyncSession = Depends(get_db_session),
) -> FieldOperationsStateRead:
    _require_security_worker(context, authority)
    return await _mutate(
        work_order_id=work_order_id, command_name="SECURITY_AREA_ACTION", event_type="SECURITY_AREA_ACTION_RECORDED",
        payload=payload, idempotency_key=idempotency_key,
        apply=lambda order: record_security_area_action(
            order, area_id=payload.area_id, action=payload.action, note=payload.note, actor_id=context.actor.id,
        ), context=context, scope=scope, authority=authority, session=session, required_domain="SECURITY",
    )


@router.post("/work-orders/{work_order_id}/security/handover", response_model=FieldOperationsStateRead)
async def handover_security_work_order(
    work_order_id: UUID,
    payload: HandoverInput,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context), scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority), session: AsyncSession = Depends(get_db_session),
) -> FieldOperationsStateRead:
    _require_security_worker(context, authority)
    return await _mutate(
        work_order_id=work_order_id, command_name="SECURITY_HANDOVER", event_type="SECURITY_HANDOVER_RECORDED",
        payload=payload, idempotency_key=idempotency_key,
        apply=lambda order: record_handover(
            order, recipient=payload.recipient, note=payload.note, actor_id=context.actor.id,
        ), context=context, scope=scope, authority=authority, session=session, required_domain="SECURITY",
    )


@router.post("/work-orders/{work_order_id}/contractor-response", response_model=FieldOperationsStateRead)
async def respond_to_work_order_assignment(
    work_order_id: UUID,
    payload: ContractorResponseInput,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context), scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority), session: AsyncSession = Depends(get_db_session),
) -> FieldOperationsStateRead:
    if context.actor.kind != "user" or FieldOperationsRole.CONTRACTOR_WORKER not in authority.roles:
        raise HTTPException(status_code=403, detail="Contractor worker role required")
    return await _mutate(
        work_order_id=work_order_id,
        command_name="WO_CONTRACTOR_RESPONSE",
        event_type="CONTRACTOR_ASSIGNMENT_ACCEPTED" if payload.decision == "ACCEPTED" else "CONTRACTOR_ASSIGNMENT_REJECTED",
        payload=payload,
        idempotency_key=idempotency_key,
        apply=lambda order: respond_to_contractor_work(
            order, actor_id=context.actor.id, decision=payload.decision, reason=payload.reason
        ),
        context=context,
        scope=scope,
        authority=authority,
        session=session,
    )


@router.post("/work-orders/{work_order_id}/arrival-plan", response_model=FieldOperationsStateRead)
async def plan_contractor_arrival(
    work_order_id: UUID,
    payload: ContractorArrivalPlanInput,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context), scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority), session: AsyncSession = Depends(get_db_session),
) -> FieldOperationsStateRead:
    if context.actor.kind != "user" or not authority.roles.intersection({FieldOperationsRole.SUPERVISOR, FieldOperationsRole.BQL_COORDINATOR}):
        raise HTTPException(status_code=403, detail="Supervisor or BQL coordinator role required")
    return await _mutate(
        work_order_id=work_order_id,
        command_name="WO_PLAN_CONTRACTOR_ARRIVAL",
        event_type="CONTRACTOR_ARRIVAL_PLANNED",
        payload=payload,
        idempotency_key=idempotency_key,
        apply=lambda order: plan_arrival(
            order,
            actor_id=context.actor.id,
            planned_start_at=payload.planned_start_at,
            planned_end_at=payload.planned_end_at,
        ),
        context=context,
        scope=scope,
        authority=authority,
        session=session,
        executor_only=False,
    )


@router.post("/work-orders/{work_order_id}/escalations", response_model=FieldOperationsStateRead)
async def escalate_work_order_to_bql(
    work_order_id: UUID,
    payload: EscalateWorkOrderInput,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context), scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority), session: AsyncSession = Depends(get_db_session),
) -> FieldOperationsStateRead:
    if context.actor.kind != "user" or FieldOperationsRole.SUPERVISOR not in authority.roles:
        raise HTTPException(status_code=403, detail="Supervisor role required")
    return await _mutate(
        work_order_id=work_order_id,
        command_name="WO_ESCALATE",
        event_type="WORK_ORDER_ESCALATED",
        payload=payload,
        idempotency_key=idempotency_key,
        apply=lambda order: escalate_work_order(
            order, actor_id=context.actor.id, urgency=payload.urgency, reason=payload.reason
        ),
        context=context,
        scope=scope,
        authority=authority,
        session=session,
        executor_only=False,
    )


@router.post("/work-orders/{work_order_id}/blockers", response_model=FieldOperationsStateRead)
async def report_work_order_blocker(
    work_order_id: UUID,
    payload: ReportBlockerInput,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context), scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority), session: AsyncSession = Depends(get_db_session),
) -> FieldOperationsStateRead:
    return await _mutate(work_order_id=work_order_id, command_name="WO_REPORT_BLOCKER", event_type="WORK_ORDER_BLOCKED", payload=payload, idempotency_key=idempotency_key, apply=lambda order: report_blocker(order, actor_id=context.actor.id, code=payload.code, note=payload.note), context=context, scope=scope, authority=authority, session=session)


@router.post("/work-orders/{work_order_id}/blockers/resolve", response_model=FieldOperationsStateRead)
async def resolve_work_order_blocker(
    work_order_id: UUID,
    payload: FieldOperationsVersionCommand,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context), scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority), session: AsyncSession = Depends(get_db_session),
) -> FieldOperationsStateRead:
    if context.actor.kind != "user" or not authority.roles.intersection({FieldOperationsRole.SUPERVISOR, FieldOperationsRole.BQL_COORDINATOR}):
        raise HTTPException(status_code=403, detail="Supervisor or BQL coordinator role required")
    return await _mutate(work_order_id=work_order_id, command_name="WO_RESOLVE_BLOCKER", event_type="WORK_ORDER_BLOCKER_RESOLVED", payload=payload, idempotency_key=idempotency_key, apply=lambda order: resolve_blocker(order, actor_id=context.actor.id), context=context, scope=scope, authority=authority, session=session, executor_only=False)


@router.post("/work-orders/{work_order_id}/support-requests", response_model=FieldOperationsStateRead)
async def request_work_order_support(
    work_order_id: UUID,
    payload: RequestFieldSupportInput,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context), scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority), session: AsyncSession = Depends(get_db_session),
) -> FieldOperationsStateRead:
    return await _mutate(work_order_id=work_order_id, command_name="WO_REQUEST_SUPPORT", event_type="WORK_ORDER_SUPPORT_REQUESTED", payload=payload, idempotency_key=idempotency_key, apply=lambda order: (request_support(order, actor_id=context.actor.id, support_type=payload.support_type, note=payload.note), read_field_operations_state(order))[1], context=context, scope=scope, authority=authority, session=session)
