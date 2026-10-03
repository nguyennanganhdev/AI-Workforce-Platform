"""Tenant and scope protected approval inbox and decision commands."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..actions.hashing import action_payload_hash
from ..commands import CommandReceiptRepository
from ..commands.hashing import command_payload_hash
from ..concurrency import require_expected_version
from ..db.action_request import ActionRequest, ActionRequestStatus
from ..db.approval import ActionApproval, ApprovalStatus
from ..db.command_receipt import CommandReceiptStatus
from ..db.dependencies import get_db_session
from ..db.incident import Incident
from ..db.rule_evaluation import RuleEvaluationRecord
from ..events import BusinessEventRepository
from ..request_context import (
    DomainScope,
    RequestContext,
    get_domain_scope,
    get_request_context,
    scope_contains_subject,
)
from ..work_orders.authority import (
    FieldOperationsAuthority,
    FieldOperationsRole,
    get_field_operations_authority,
)
from .repository import ActionApprovalRepository
from .schemas import (
    ApprovalDecisionInput,
    ApprovalDetailRead,
    ApprovalPage,
    ApprovalRejectInput,
    approval_detail_read,
)


router = APIRouter(tags=["approvals"])


def _tenant_uuid(context: RequestContext) -> UUID:
    try:
        return UUID(context.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Authenticated tenant identifier is invalid") from exc


def _scoped_incident_ids(scope: DomainScope) -> list[UUID]:
    incident_ids: list[UUID] = []
    if scope.namespace != "vinhomes":
        return incident_ids
    for subject in scope.subjects:
        if subject.namespace == "vinhomes" and subject.subject_type == "incident":
            try:
                incident_ids.append(UUID(subject.subject_id))
            except ValueError:
                continue
    return incident_ids


def _require_bql(authority: FieldOperationsAuthority) -> None:
    if authority.actor_type != "user" or FieldOperationsRole.BQL_COORDINATOR not in authority.roles:
        raise HTTPException(status_code=403, detail="BQL coordinator role required")


async def _approval_detail(
    session: AsyncSession, approval: ActionApproval, action_request
) -> ApprovalDetailRead:
    evaluation = await session.scalar(
        select(RuleEvaluationRecord)
        .where(RuleEvaluationRecord.action_request_id == action_request.id)
        .order_by(RuleEvaluationRecord.evaluated_at.desc(), RuleEvaluationRecord.id.desc())
        .limit(1)
    )
    if evaluation is None:
        raise HTTPException(status_code=409, detail="Approval has no persisted rule evaluation")
    return approval_detail_read(approval, action_request, evaluation)


async def _expire_due_approvals(
    session: AsyncSession, *, tenant_id: UUID, incident_ids: list[UUID]
) -> None:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(ActionApproval, ActionRequest)
        .join(ActionRequest, ActionApproval.action_request_id == ActionRequest.id)
        .join(Incident, ActionRequest.incident_id == Incident.id)
        .where(
            Incident.tenant_id == tenant_id,
            Incident.id.in_(incident_ids),
            ActionApproval.status == ApprovalStatus.PENDING,
            ActionApproval.expires_at <= now,
        )
        .with_for_update(of=(ActionApproval, ActionRequest))
    )
    for approval, action_request in result.all():
        approval.status = ApprovalStatus.EXPIRED
        approval.decided_at = now
        if action_request.status == ActionRequestStatus.AWAITING_APPROVAL.value:
            action_request.status = ActionRequestStatus.EXPIRED.value
        await BusinessEventRepository(session).append(
            tenant_id=tenant_id,
            incident_id=action_request.incident_id,
            subject_type="ActionApproval",
            subject_id=str(approval.id),
            event_type="APPROVAL_EXPIRED",
            actor_type="system",
            actor_id="vinhomes-api",
            actor_version=None,
            data={"actionRequestId": str(action_request.id), "expiredAt": now.isoformat()},
            correlation_id=action_request.correlation_id,
        )
    await session.flush()


@router.get("/approvals", operation_id="listApprovals", response_model=ApprovalPage)
async def list_approvals(
    approval_status: ApprovalStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> ApprovalPage:
    _require_bql(authority)
    tenant_id = _tenant_uuid(context)
    incident_ids = _scoped_incident_ids(scope)
    async with session.begin():
        await _expire_due_approvals(
            session, tenant_id=tenant_id, incident_ids=incident_ids
        )
        rows, total = await ActionApprovalRepository(session).list_by_scope(
            tenant_id=tenant_id,
            incident_ids=incident_ids,
            status=approval_status,
            limit=limit,
            offset=offset,
        )
        items = [
            await _approval_detail(session, approval, action_request)
            for approval, action_request in rows
        ]
    return ApprovalPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/approvals/{approval_id}", operation_id="getApproval", response_model=ApprovalDetailRead)
async def get_approval(
    approval_id: UUID,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> ApprovalDetailRead:
    _require_bql(authority)
    tenant_id = _tenant_uuid(context)
    incident_ids = _scoped_incident_ids(scope)
    async with session.begin():
        await _expire_due_approvals(
            session, tenant_id=tenant_id, incident_ids=incident_ids
        )
        found = await ActionApprovalRepository(session).get_by_id(
            tenant_id=tenant_id,
            incident_ids=incident_ids,
            approval_id=approval_id,
        )
        if found is None:
            raise HTTPException(status_code=404, detail="Approval not found")
        result = await _approval_detail(session, *found)
    return result


async def _decide_approval(
    *,
    approval_id: UUID,
    payload: ApprovalDecisionInput,
    approve: bool,
    reason: str | None,
    idempotency_key: str,
    context: RequestContext,
    scope: DomainScope,
    authority: FieldOperationsAuthority,
    session: AsyncSession,
) -> tuple[ApprovalDetailRead, bool]:
    _require_bql(authority)
    tenant_id = _tenant_uuid(context)
    scope_ids = _scoped_incident_ids(scope)
    expired = False
    transitioned = False
    result: ApprovalDetailRead | None = None
    desired_status = ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED
    command_type = "APPROVE_ACTION" if approve else "REJECT_ACTION"
    command_hash = command_payload_hash(
        {
            "approvalId": str(approval_id),
            "expectedVersion": payload.expected_version,
            "actionPayloadHash": payload.action_payload_hash,
            "reason": reason,
        }
    )
    async with session.begin():
        receipts = CommandReceiptRepository(session)
        receipt = await receipts.get(
            tenant_id=tenant_id,
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            command_type=command_type,
            idempotency_key=idempotency_key,
            for_update=True,
        )
        if receipt is not None:
            if receipt.payload_hash != command_hash:
                raise HTTPException(status_code=409, detail="IDEMPOTENCY_KEY_REUSED")
            if receipt.status is not CommandReceiptStatus.COMPLETED or receipt.response_json is None:
                raise HTTPException(status_code=409, detail="Command with this Idempotency-Key is still in progress")
            current = await ActionApprovalRepository(session).get_by_id(
                tenant_id=tenant_id,
                incident_ids=scope_ids,
                approval_id=approval_id,
            )
            if current is None:
                raise HTTPException(status_code=404, detail="Approval not found")
            return ApprovalDetailRead.model_validate(receipt.response_json), False

        found = await ActionApprovalRepository(session).get_by_id(
            tenant_id=tenant_id,
            incident_ids=scope_ids,
            approval_id=approval_id,
            for_update=True,
        )
        if found is None:
            raise HTTPException(status_code=404, detail="Approval not found")
        approval, action_request = found
        if not scope_contains_subject(
            scope,
            namespace="vinhomes",
            subject_type="incident",
            subject_id=str(action_request.incident_id),
        ):
            raise HTTPException(status_code=404, detail="Approval not found")

        current_hash = action_payload_hash(
            action_type=action_request.action_type,
            target_type=action_request.target_type,
            target_id=action_request.target_id,
            payload=action_request.payload,
        )
        if (
            current_hash != action_request.payload_hash
            or approval.action_payload_hash != action_request.payload_hash
            or payload.action_payload_hash != action_request.payload_hash
        ):
            raise HTTPException(status_code=409, detail="Approval is bound to a different ActionRequest payload")

        if approval.status is desired_status and approval.reviewer_id == context.actor.id and approval.reason == reason:
            result = await _approval_detail(session, approval, action_request)
        elif approval.status is not ApprovalStatus.PENDING:
            raise HTTPException(status_code=409, detail="Approval has already been decided or expired")
        else:
            now = datetime.now(timezone.utc)
            if _utc(approval.expires_at) <= now:
                approval.status = ApprovalStatus.EXPIRED
                approval.decided_at = now
                if action_request.status == ActionRequestStatus.AWAITING_APPROVAL.value:
                    action_request.status = ActionRequestStatus.EXPIRED.value
                expired = True
                transitioned = True
            else:
                require_expected_version(approval.version, payload.expected_version)
                approval.status = desired_status
                approval.reviewer_id = context.actor.id
                approval.decided_at = now
                approval.reason = reason
                action_request.status = (
                    ActionRequestStatus.AUTHORIZED.value
                    if approve
                    else ActionRequestStatus.REJECTED.value
                )
                transitioned = True
            await session.flush()
            await session.refresh(approval)
            await session.refresh(action_request)
            result = await _approval_detail(session, approval, action_request)

        if transitioned:
            await BusinessEventRepository(session).append(
                tenant_id=tenant_id,
                incident_id=action_request.incident_id,
                subject_type="ActionApproval",
                subject_id=str(approval.id),
                event_type=(
                    "APPROVAL_EXPIRED"
                    if approval.status is ApprovalStatus.EXPIRED
                    else "APPROVAL_APPROVED"
                    if approval.status is ApprovalStatus.APPROVED
                    else "APPROVAL_REJECTED"
                ),
                actor_type=("system" if expired else context.actor.kind),
                actor_id=("vinhomes-api" if expired else context.actor.id),
                actor_version=None,
                data={
                    "actionRequestId": str(action_request.id),
                    "actionPayloadHash": approval.action_payload_hash,
                    "status": approval.status.value,
                    "reason": approval.reason,
                },
                correlation_id=action_request.correlation_id,
            )

        if not expired:
            receipt = receipts.add(
                tenant_id=tenant_id,
                actor_type=context.actor.kind,
                actor_id=context.actor.id,
                command_type=command_type,
                idempotency_key=idempotency_key,
                payload_hash=command_hash,
                subject_type="ActionApproval",
                subject_id=str(approval.id),
            )
            await session.flush()
            await receipts.complete(
                receipt,
                subject_id=str(approval.id),
                response_json=result.model_dump(mode="json", by_alias=True),
            )

    if result is None:
        raise HTTPException(status_code=500, detail="Approval decision failed")
    return result, expired


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@router.post("/approvals/{approval_id}/approve", operation_id="approveAction", response_model=ApprovalDetailRead)
async def approve_action(
    approval_id: UUID,
    payload: ApprovalDecisionInput,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> ApprovalDetailRead:
    result, expired = await _decide_approval(
        approval_id=approval_id,
        payload=payload,
        approve=True,
        reason=None,
        idempotency_key=idempotency_key,
        context=context,
        scope=scope,
        authority=authority,
        session=session,
    )
    if expired:
        raise HTTPException(status_code=409, detail="Approval expired before it could be approved")
    return result


@router.post("/approvals/{approval_id}/reject", operation_id="rejectAction", response_model=ApprovalDetailRead)
async def reject_action(
    approval_id: UUID,
    payload: ApprovalRejectInput,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> ApprovalDetailRead:
    result, expired = await _decide_approval(
        approval_id=approval_id,
        payload=payload,
        approve=False,
        reason=payload.reason,
        idempotency_key=idempotency_key,
        context=context,
        scope=scope,
        authority=authority,
        session=session,
    )
    if expired:
        raise HTTPException(status_code=409, detail="Approval expired before it could be rejected")
    return result
