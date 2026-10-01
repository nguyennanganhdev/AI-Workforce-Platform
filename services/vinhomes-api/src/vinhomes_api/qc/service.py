"""QC prerequisite and immutable decision construction."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.checklist import Checklist, ChecklistVersion
from ..db.evidence import EvidenceRef, FileObject
from ..db.qc_result import QCOutcome
from ..db.task import Task, TaskDomainType
from ..db.work_order import WorkOrder
from ..evidence.repository import EvidenceRepository
from ..evidence.schemas import EvidenceRefRead
from ..evidence.service import work_order_evidence_read
from ..work_orders.a5_execution import InvalidA5Execution, a5_execution_read, task_for_execution
from ..work_orders.checklist_execution import checklist_execution_read
from ..work_orders.checklist_repository import ChecklistRepository
from ..work_orders.execution_details import InvalidExecutionDetails, execution_details_read
from .repository import QCRepository
from .schemas import QCWorkOrderDetail, qc_result_read


async def build_qc_work_order_detail(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    work_order: WorkOrder,
    task: Task,
    actor_id: str,
) -> QCWorkOrderDetail:
    evidence_rows = await EvidenceRepository(session).list_work_order_evidence(
        tenant_id=tenant_id,
        work_order=work_order,
    )
    checklist: Checklist | None = None
    checklist_version: ChecklistVersion | None = None
    if work_order.checklist_version_id is not None:
        pair = await ChecklistRepository(session).get_version_for_tenant(
            tenant_id=tenant_id,
            checklist_version_id=work_order.checklist_version_id,
        )
        if pair is None:
            raise HTTPException(status_code=409, detail="Pinned checklist version is unavailable")
        checklist, checklist_version = pair

    a5_read = None
    try:
        execution_task = task_for_execution(work_order, task)
        checklist_read = checklist_execution_read(
            work_order,
            task=execution_task,
            checklist=checklist,
            checklist_version=checklist_version,
        )
        evidence_read = work_order_evidence_read(
            work_order,
            task=execution_task,
            rows=evidence_rows,
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
        execution_details = execution_details_read(work_order)
    except InvalidA5Execution as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidExecutionDetails as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    repository = QCRepository(session)
    results = await repository.list_results(tenant_id=tenant_id, work_order_id=work_order.id)
    result_reads = []
    for result in results:
        linked_rows = await repository.list_result_evidence(
            tenant_id=tenant_id,
            qc_result_id=result.id,
        )
        result_reads.append(
            qc_result_read(result, evidence=qc_evidence_projection(linked_rows))
        )

    blockers = list(a5_read.blockers if a5_read is not None else evidence_read.blockers)
    qc_criteria = a5_read.qc_criteria if a5_read is not None else None
    if task.domain_type in {TaskDomainType.TECHNICAL, TaskDomainType.SECURITY}:
        raw_criteria = task.domain_data.get("qcCriteria")
        if isinstance(raw_criteria, list) and all(isinstance(item, str) and item.strip() for item in raw_criteria):
            qc_criteria = list(dict.fromkeys(item.strip() for item in raw_criteria))
    if qc_criteria is None:
        blockers.append("QC_CRITERIA_CONTRACT_UNDEFINED")
    if results:
        blockers.append("QC_RESULT_ALREADY_RECORDED")
    if work_order.executor_id is not None and actor_matches_executor(
        actor_id, work_order.executor_id
    ):
        blockers.append("EXECUTOR_CANNOT_QC_OWN_WORK")

    return QCWorkOrderDetail(
        workOrder=work_order,
        a5Execution=a5_read,
        qcCriteria=qc_criteria,
        executionDetails=execution_details,
        evidence=evidence_read,
        qcResults=result_reads,
        canSubmitQC=not blockers,
        blockers=blockers,
    )


def validate_qc_result(
    *,
    criteria: list[str],
    outcome: QCOutcome,
    failed_criteria: list[str],
    redo_required: bool,
) -> list[str]:
    if len(criteria) != len(set(criteria)):
        raise HTTPException(status_code=409, detail="Pinned QC criteria contain duplicate codes")
    unknown = sorted(set(failed_criteria) - set(criteria))
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"failedCriteria contains codes outside the pinned plan: {', '.join(unknown)}",
        )
    if outcome is QCOutcome.FAIL and not failed_criteria:
        raise HTTPException(status_code=422, detail="FAIL requires at least one failed criterion")
    if outcome is QCOutcome.PASS and failed_criteria:
        raise HTTPException(status_code=422, detail="PASS cannot include failed criteria")
    if redo_required and outcome is not QCOutcome.FAIL:
        raise HTTPException(status_code=422, detail="redoRequired is only valid for FAIL")
    failed = set(failed_criteria)
    return [criterion for criterion in criteria if criterion in failed]


def qc_evidence_projection(
    rows: list[tuple[EvidenceRef, FileObject]],
) -> list[EvidenceRefRead]:
    return [
        EvidenceRefRead(
            id=reference.id,
            fileObjectId=file_object.id,
            kind=reference.kind,
            capturePhase=reference.capture_phase,
            metadata=reference.evidence_metadata,
            mimeType=file_object.mime_type,
            sizeBytes=file_object.size_bytes,
            checksum=file_object.checksum,
            uploadedBy=reference.uploaded_by,
            createdAt=reference.created_at,
        )
        for reference, file_object in rows
    ]


def actor_matches_executor(actor_id: str, executor_id: UUID) -> bool:
    try:
        return UUID(actor_id) == executor_id
    except ValueError:
        return False
