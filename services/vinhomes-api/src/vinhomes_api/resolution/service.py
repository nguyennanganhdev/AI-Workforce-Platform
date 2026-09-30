"""Field Operations resolution readiness calculation."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.action_request import ActionRequest, ActionRequestStatus
from ..db.approval import ActionApproval, ApprovalStatus
from ..db.incident import Incident, IncidentStatus
from ..db.qc_result import QCOutcome, QCResult
from ..db.task import TaskDomainType, TaskStatus
from ..db.work_order import WorkOrderStatus
from ..evidence.repository import EvidenceRepository
from ..evidence.service import work_order_evidence_read
from ..qc.repository import QCRepository
from ..tasks.repository import TaskRepository
from ..work_orders.a5_execution import a5_execution_read, task_for_execution
from ..work_orders.a5_execution import InvalidA5Execution
from ..work_orders.checklist_execution import checklist_execution_read
from ..work_orders.checklist_repository import ChecklistRepository
from ..work_orders.repository import WorkOrderRepository
from ..work_orders.checklist_execution import InvalidChecklistContract

from .schemas import IncidentResolutionRead, ResolutionBlocker


class ResolutionBlockedError(RuntimeError):
    def __init__(self, blockers: list[ResolutionBlocker]) -> None:
        super().__init__("Incident has unresolved Field Operations blockers")
        self.blockers = blockers


async def _execution_blockers(session, tenant_id, task, work_order):
    evidence_repository = EvidenceRepository(session)
    rows = await evidence_repository.list_work_order_evidence(
        tenant_id=tenant_id,
        work_order=work_order,
    )
    execution_task = task_for_execution(work_order, task)
    checklist = None
    checklist_version = None
    if work_order.checklist_version_id is not None:
        pair = await ChecklistRepository(session).get_version_for_tenant(
            tenant_id=tenant_id,
            checklist_version_id=work_order.checklist_version_id,
        )
        if pair is not None:
            checklist, checklist_version = pair
    checklist_read = checklist_execution_read(
        work_order,
        task=execution_task,
        checklist=checklist,
        checklist_version=checklist_version,
    )
    evidence_read = work_order_evidence_read(
        work_order,
        task=execution_task,
        rows=rows,
        checklist=checklist_read,
    )
    if task.domain_type in {TaskDomainType.SANITATION, TaskDomainType.LANDSCAPE}:
        a5_read = a5_execution_read(
            work_order,
            execution_task,
            satisfied_required_evidence=evidence_read.satisfied_required_evidence,
            missing_required_evidence=evidence_read.missing_required_evidence,
            unsupported_required_evidence=evidence_read.unsupported_required_evidence,
            evidence_blockers=evidence_read.blockers,
        )
        return a5_read.blockers
    return evidence_read.blockers


async def check_incident_resolution(
    session: AsyncSession,
    *,
    tenant_id,
    incident: Incident,
) -> IncidentResolutionRead:
    blockers: list[ResolutionBlocker] = []

    def add(code: str, subject_type: str, subject_id: str, message: str) -> None:
        blockers.append(
            ResolutionBlocker(
                code=code,
                subjectType=subject_type,
                subjectId=subject_id,
                message=message,
            )
        )

    if incident.status not in {IncidentStatus.NEW, IncidentStatus.OPEN}:
        add("INCIDENT_NOT_OPEN", "Incident", str(incident.id), "Incident is already resolved or closed")

    tasks = await TaskRepository(session).list_by_incident(
        tenant_id=tenant_id,
        incident_id=incident.id,
    )
    if not tasks:
        add("TASKS_MISSING", "Incident", str(incident.id), "At least one Task is required before resolution")

    pending_approvals = await session.scalars(
        select(ActionApproval)
        .join(ActionRequest, ActionApproval.action_request_id == ActionRequest.id)
        .where(
            ActionRequest.incident_id == incident.id,
            ActionApproval.status == ApprovalStatus.PENDING,
        )
    )
    seen_actions: set[str] = set()
    for approval in pending_approvals.all():
        seen_actions.add(str(approval.action_request_id))
        add(
            "APPROVAL_PENDING",
            "ActionApproval",
            str(approval.id),
            "A pending approval must be decided before Incident resolution",
        )
    awaiting_actions = await session.scalars(
        select(ActionRequest).where(
            ActionRequest.incident_id == incident.id,
            ActionRequest.status == ActionRequestStatus.AWAITING_APPROVAL.value,
        )
    )
    for action in awaiting_actions.all():
        if str(action.id) not in seen_actions:
            add(
                "APPROVAL_PENDING",
                "ActionRequest",
                str(action.id),
                "An ActionRequest is awaiting approval",
            )

    work_orders = WorkOrderRepository(session)
    qc_repository = QCRepository(session)
    for task in tasks:
        if task.status is not TaskStatus.DONE:
            add(
                "TASK_NOT_DONE",
                "Task",
                str(task.id),
                f"Task status is {task.status.value}; QC PASS is required",
            )
        attempts = await work_orders.list_attempts(
            tenant_id=tenant_id,
            task_id=task.id,
        )
        if not attempts:
            add("WORK_ORDER_MISSING", "Task", str(task.id), "Task has no execution WorkOrder")
            continue
        latest = attempts[-1]
        if latest.status is not WorkOrderStatus.COMPLETED:
            add(
                "WORK_ORDER_NOT_COMPLETED",
                "WorkOrder",
                str(latest.id),
                f"Latest attempt status is {latest.status.value}",
            )
            continue

        try:
            execution_blockers = await _execution_blockers(
                session,
                tenant_id,
                task,
                latest,
            )
        except (InvalidA5Execution, InvalidChecklistContract) as exc:
            # Invalid pinned execution data is a blocker, never a reason to allow resolution.
            add(
                "EXECUTION_DATA_INVALID",
                "WorkOrder",
                str(latest.id),
                f"Execution prerequisites could not be verified: {type(exc).__name__}",
            )
        else:
            for code in execution_blockers:
                add(
                    code,
                    "WorkOrder",
                    str(latest.id),
                    "WorkOrder evidence, checklist, or A5 action prerequisites are incomplete",
                )

        results = await qc_repository.list_results(
            tenant_id=tenant_id,
            work_order_id=latest.id,
        )
        if not results:
            add("QC_REQUIRED", "WorkOrder", str(latest.id), "Latest WorkOrder attempt has no QC result")
        elif results[-1].outcome is not QCOutcome.PASS or results[-1].redo_required:
            add(
                "QC_NOT_PASSED",
                "QCResult",
                str(results[-1].id),
                "Latest WorkOrder attempt must have QC PASS without redo",
            )

    return IncidentResolutionRead(
        incidentId=incident.id,
        status=incident.status,
        resolvedAt=incident.resolved_at,
        canResolve=not blockers,
        blockers=blockers,
    )
