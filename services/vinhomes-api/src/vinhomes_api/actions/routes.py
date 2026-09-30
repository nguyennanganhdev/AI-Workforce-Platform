"""Field Operations ActionRequest submission and authorized WorkOrder gate."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..concurrency import require_expected_version
from ..commands import CommandReceiptRepository
from ..commands.hashing import command_payload_hash
from ..db.action_request import (
    ActionRequest,
    ActionRequestStatus,
    RequestedByType,
)
from ..db.approval import ActionApproval, ApprovalStatus
from ..db.command_receipt import CommandReceiptStatus
from ..db.dependencies import get_db_session
from ..db.rule_evaluation import RuleDecisionValue, RuleEvaluationRecord
from ..db.task import TaskStatus
from ..db.work_order import WorkOrder, WorkOrderStatus
from ..events import BusinessEventRepository
from ..request_context import (
    DomainScope,
    RequestContext,
    get_domain_scope,
    get_request_context,
    scope_contains_subject,
)
from ..rules import A5RuleEngine, RuleDecision
from ..work_orders.authority import (
    FieldOperationsAuthority,
    FieldOperationsRole,
    get_field_operations_authority,
)
from ..work_orders.repository import WorkOrderRepository
from ..work_orders.schemas import WorkOrderRead
from ..tasks.repository import TaskRepository
from .hashing import action_payload_hash
from .repository import ActionRequestRepository
from .schemas import ActionRequestCreate, ActionSubmissionRead, action_submission_read


router = APIRouter(tags=["actions"])


class AuthorizedWorkOrderCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    expected_version: int = Field(alias="expectedVersion", ge=1, strict=True)


def _tenant_uuid(context: RequestContext) -> UUID:
    try:
        return UUID(context.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Authenticated tenant identifier is invalid") from exc


def _requester_type(context: RequestContext) -> RequestedByType:
    # The platform context has one trusted service actor kind; service principals
    # use the ERD's SYSTEM requester code until a more specific claim is supplied.
    return {
        "user": RequestedByType.HUMAN,
        "agent": RequestedByType.AGENT,
        "service": RequestedByType.SYSTEM,
    }[context.actor.kind]


def _require_incident_scope(scope: DomainScope, incident_id: UUID) -> None:
    if not scope_contains_subject(
        scope,
        namespace="vinhomes",
        subject_type="incident",
        subject_id=str(incident_id),
    ):
        raise HTTPException(status_code=403, detail="Incident is outside the effective domain scope")


def _require_coordinator(authority: FieldOperationsAuthority) -> None:
    if authority.actor_type != "user" or FieldOperationsRole.BQL_COORDINATOR not in authority.roles:
        raise HTTPException(status_code=403, detail="BQL coordinator role required")


async def _latest_rule_evaluation(
    session: AsyncSession, action_request_id: UUID
) -> RuleEvaluationRecord | None:
    return await session.scalar(
        select(RuleEvaluationRecord)
        .where(RuleEvaluationRecord.action_request_id == action_request_id)
        .order_by(RuleEvaluationRecord.evaluated_at.desc(), RuleEvaluationRecord.id.desc())
        .limit(1)
    )


@router.post(
    "/tasks/{task_id}/actions",
    operation_id="submitActionRequest",
    response_model=ActionSubmissionRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_action_request(
    task_id: UUID,
    payload: ActionRequestCreate,
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    _authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> ActionSubmissionRead:
    tenant_id = _tenant_uuid(context)
    command_type = "SUBMIT_ACTION_REQUEST"
    request_hash = command_payload_hash(
        {
            "taskId": str(task_id),
            "expectedTaskVersion": payload.expected_task_version,
            "actionType": payload.action_type,
            "payload": payload.payload,
        }
    )
    async with session.begin():
        receipt_repository = CommandReceiptRepository(session)
        receipt = await receipt_repository.get(
            tenant_id=tenant_id,
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            command_type=command_type,
            idempotency_key=idempotency_key,
            for_update=True,
        )
        if receipt is not None:
            if receipt.payload_hash != request_hash:
                raise HTTPException(status_code=409, detail="IDEMPOTENCY_KEY_REUSED")
            if receipt.status is not CommandReceiptStatus.COMPLETED or receipt.response_json is None:
                raise HTTPException(status_code=409, detail="Command with this Idempotency-Key is still in progress")
            if receipt.subject_id is None:
                raise HTTPException(status_code=409, detail="Completed command receipt has no subject")
            original = await ActionRequestRepository(session).get_by_id(
                tenant_id=tenant_id, action_request_id=UUID(receipt.subject_id)
            )
            if original is None or original.task_id != task_id:
                raise HTTPException(status_code=404, detail="ActionRequest not found")
            _require_incident_scope(scope, original.incident_id)
            return ActionSubmissionRead.model_validate(receipt.response_json)

        task = await TaskRepository(session).get_by_id_for_update(
            tenant_id=tenant_id, task_id=task_id
        )
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        _require_incident_scope(scope, task.incident_id)
        require_expected_version(task.version, payload.expected_task_version)
        if task.status in {TaskStatus.DONE, TaskStatus.CANCELLED}:
            raise HTTPException(status_code=409, detail="A completed or cancelled Task cannot accept a new action")

        target_type = "TASK"
        target_id = str(task.id)
        payload_hash = action_payload_hash(
            action_type=payload.action_type,
            target_type=target_type,
            target_id=target_id,
            payload=payload.payload,
        )
        engine: A5RuleEngine = request.app.state.field_operations_rule_engine
        evaluation = engine.evaluate(
            action_type=payload.action_type,
            requested_by_type=_requester_type(context),
            correlation_id=context.correlation_id,
            payload=payload.payload,
        )
        ttl_seconds: int | None = request.app.state.approval_ttl_seconds
        if evaluation.decision is RuleDecision.REQUIRE_APPROVAL and ttl_seconds is None:
            raise HTTPException(
                status_code=503,
                detail="Approval expiry policy is not configured",
            )

        receipt = receipt_repository.add(
            tenant_id=tenant_id,
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            command_type=command_type,
            idempotency_key=idempotency_key,
            payload_hash=request_hash,
            subject_type="ActionRequest",
        )
        await session.flush()

        status_by_decision = {
            RuleDecision.ALLOW: ActionRequestStatus.AUTHORIZED,
            RuleDecision.REQUIRE_APPROVAL: ActionRequestStatus.AWAITING_APPROVAL,
            RuleDecision.DENY: ActionRequestStatus.DENIED,
        }
        action_request = ActionRequest(
            incident_id=task.incident_id,
            task_id=task.id,
            requested_by_type=_requester_type(context),
            requested_by_id=context.actor.id,
            requested_by_version=None,
            action_type=payload.action_type,
            target_type=target_type,
            target_id=target_id,
            payload=payload.payload,
            payload_hash=payload_hash,
            status=status_by_decision[evaluation.decision].value,
            correlation_id=context.correlation_id,
        )
        stored = await ActionRequestRepository(session).add(
            action_request, tenant_id=tenant_id
        )
        if stored is None:
            raise HTTPException(status_code=404, detail="Task not found")

        evaluation_record = RuleEvaluationRecord(
            action_request_id=stored.id,
            decision=RuleDecisionValue(evaluation.decision.value),
            reason_code=evaluation.reason_code,
            rule_version=evaluation.rule_version,
            evaluated_at=evaluation.evaluated_at,
            correlation_id=evaluation.correlation_id,
        )
        session.add(evaluation_record)
        approval: ActionApproval | None = None
        if evaluation.decision is RuleDecision.REQUIRE_APPROVAL:
            approval = ActionApproval(
                action_request_id=stored.id,
                action_payload_hash=stored.payload_hash,
                status=ApprovalStatus.PENDING,
                requested_by_id=context.actor.id,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
            )
            session.add(approval)
        await session.flush()
        await session.refresh(stored)
        await session.refresh(evaluation_record)
        if approval is not None:
            await session.refresh(approval)
        result = action_submission_read(stored, evaluation_record, approval)
        event_repository = BusinessEventRepository(session)
        await event_repository.append(
            tenant_id=tenant_id,
            incident_id=stored.incident_id,
            subject_type="ActionRequest",
            subject_id=str(stored.id),
            event_type="ACTION_REQUESTED",
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            actor_version=None,
            data={
                "taskId": str(stored.task_id),
                "actionType": stored.action_type,
                "decision": evaluation.decision.value,
                "reasonCode": evaluation.reason_code,
                "ruleVersion": evaluation.rule_version,
            },
            correlation_id=context.correlation_id,
        )
        if approval is not None:
            await event_repository.append(
                tenant_id=tenant_id,
                incident_id=stored.incident_id,
                subject_type="ActionApproval",
                subject_id=str(approval.id),
                event_type="APPROVAL_REQUESTED",
                actor_type=context.actor.kind,
                actor_id=context.actor.id,
                actor_version=None,
                data={
                    "actionRequestId": str(stored.id),
                    "actionPayloadHash": stored.payload_hash,
                    "expiresAt": approval.expires_at.isoformat(),
                },
                correlation_id=context.correlation_id,
            )
        await receipt_repository.complete(
            receipt,
            subject_id=str(stored.id),
            response_json=result.model_dump(mode="json", by_alias=True),
        )
        return result


@router.post(
    "/actions/{action_request_id}/work-orders",
    operation_id="createWorkOrderFromAction",
    response_model=WorkOrderRead,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"model": WorkOrderRead, "description": "An identical first attempt already exists."}},
)
async def create_work_order_from_action(
    action_request_id: UUID,
    payload: AuthorizedWorkOrderCommand,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> WorkOrderRead:
    _require_coordinator(authority)
    tenant_id = _tenant_uuid(context)
    command_type = "CREATE_WORK_ORDER_FROM_ACTION"
    request_hash = command_payload_hash(
        {"actionRequestId": str(action_request_id), "expectedVersion": payload.expected_version}
    )
    response_status = status.HTTP_201_CREATED
    try:
        async with session.begin():
            action_request = await ActionRequestRepository(session).get_by_id_for_update(
                tenant_id=tenant_id, action_request_id=action_request_id
            )
            if action_request is None:
                raise HTTPException(status_code=404, detail="ActionRequest not found")
            _require_incident_scope(scope, action_request.incident_id)
            receipt_repository = CommandReceiptRepository(session)
            receipt = await receipt_repository.get(
                tenant_id=tenant_id,
                actor_type=context.actor.kind,
                actor_id=context.actor.id,
                command_type=command_type,
                idempotency_key=idempotency_key,
                for_update=True,
            )
            if receipt is not None:
                if receipt.payload_hash != request_hash:
                    raise HTTPException(status_code=409, detail="IDEMPOTENCY_KEY_REUSED")
                if receipt.status is not CommandReceiptStatus.COMPLETED or receipt.response_json is None:
                    raise HTTPException(status_code=409, detail="Command with this Idempotency-Key is still in progress")
                if receipt.subject_id is None:
                    raise HTTPException(status_code=409, detail="Completed command receipt has no subject")
                original_order = await WorkOrderRepository(session).get_by_id(
                    tenant_id=tenant_id, work_order_id=UUID(receipt.subject_id)
                )
                if original_order is None or original_order.action_request_id != action_request.id:
                    raise HTTPException(status_code=404, detail="WorkOrder not found")
                response_status = status.HTTP_200_OK
                response.status_code = status.HTTP_200_OK
                result = WorkOrderRead.model_validate(receipt.response_json)
                return result

            require_expected_version(action_request.version, payload.expected_version)
            expected_hash = action_payload_hash(
                action_type=action_request.action_type,
                target_type=action_request.target_type,
                target_id=action_request.target_id,
                payload=action_request.payload,
            )
            if expected_hash != action_request.payload_hash:
                raise HTTPException(status_code=409, detail="ActionRequest payload hash no longer matches its contents")
            if action_request.status != ActionRequestStatus.AUTHORIZED.value:
                raise HTTPException(status_code=409, detail="ActionRequest is not authorized")

            evaluation = await _latest_rule_evaluation(session, action_request.id)
            if evaluation is None or evaluation.decision is RuleDecisionValue.DENY:
                raise HTTPException(status_code=409, detail="A denied or unevaluated ActionRequest cannot create a WorkOrder")
            if evaluation.decision is RuleDecisionValue.REQUIRE_APPROVAL:
                approved = await session.scalar(
                    select(ActionApproval.id).where(
                        ActionApproval.action_request_id == action_request.id,
                        ActionApproval.action_payload_hash == expected_hash,
                        ActionApproval.status == ApprovalStatus.APPROVED,
                    )
                )
                if approved is None:
                    raise HTTPException(status_code=409, detail="A current matching approval is required")

            task = await TaskRepository(session).get_by_id_for_update(
                tenant_id=tenant_id, task_id=action_request.task_id
            )
            if task is None or task.incident_id != action_request.incident_id:
                raise HTTPException(status_code=404, detail="Task not found")
            if task.status in {TaskStatus.DONE, TaskStatus.CANCELLED}:
                raise HTTPException(status_code=409, detail="A completed or cancelled Task cannot create a WorkOrder")

            receipt = receipt_repository.add(
                tenant_id=tenant_id,
                actor_type=context.actor.kind,
                actor_id=context.actor.id,
                command_type=command_type,
                idempotency_key=idempotency_key,
                payload_hash=request_hash,
                subject_type="WorkOrder",
            )
            await session.flush()

            attempts = await WorkOrderRepository(session).list_attempts(
                tenant_id=tenant_id, task_id=task.id
            )
            if attempts:
                existing = next((row for row in attempts if row.attempt_no == 1), None)
                if existing is not None and existing.action_request_id == action_request.id:
                    response.status_code = status.HTTP_200_OK
                    result = WorkOrderRead.model_validate(existing)
                    await receipt_repository.complete(
                        receipt,
                        subject_id=str(existing.id),
                        response_json=result.model_dump(mode="json", by_alias=True),
                    )
                    response_status = status.HTTP_200_OK
                    return result
                raise HTTPException(status_code=409, detail="Task already has a first WorkOrder attempt")

            order = WorkOrder(
                incident_id=task.incident_id,
                task_id=task.id,
                action_request_id=action_request.id,
                executor_type=task.assignee_type,
                executor_id=None,
                status=WorkOrderStatus.OPEN,
                attempt_no=1,
                redo_of_work_order_id=None,
                checklist_version_id=None,
                execution_started_at=None,
                execution_completed_at=None,
                result={},
            )
            session.add(order)
            await session.flush()
            await session.refresh(order)
            result = WorkOrderRead.model_validate(order)
            event = await BusinessEventRepository(session).append(
                tenant_id=tenant_id,
                incident_id=order.incident_id,
                subject_type="WorkOrder",
                subject_id=str(order.id),
                event_type="WORK_ORDER_CREATED",
                actor_type=context.actor.kind,
                actor_id=context.actor.id,
                actor_version=None,
                data={
                    "taskId": str(order.task_id),
                    "actionRequestId": str(action_request.id),
                    "attemptNo": order.attempt_no,
                },
                correlation_id=context.correlation_id,
            )
            if event is None:
                raise HTTPException(status_code=404, detail="Incident not found")
            await receipt_repository.complete(
                receipt,
                subject_id=str(order.id),
                response_json=result.model_dump(mode="json", by_alias=True),
            )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Concurrent duplicate command or first WorkOrder attempt conflict; retry with the same Idempotency-Key",
        ) from exc

    response.status_code = response_status
    return result
