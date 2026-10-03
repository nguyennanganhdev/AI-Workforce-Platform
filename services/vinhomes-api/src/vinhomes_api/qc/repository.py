"""Tenant and Incident-scoped QC persistence operations."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.evidence import EvidenceCapturePhase, EvidenceRef, FileObject
from ..db.incident import Incident
from ..db.qc_result import QCResult, QCResultEvidence
from ..db.task import Task
from ..db.work_order import WorkOrder, WorkOrderStatus


class QCRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_waiting_work_orders(
        self,
        *,
        tenant_id: UUID,
        scoped_incident_ids: list[UUID],
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[WorkOrder, Task, Incident]], int]:
        has_result = select(QCResult.id).where(QCResult.work_order_id == WorkOrder.id).exists()
        conditions = [
            Incident.tenant_id == tenant_id,
            Incident.id.in_(scoped_incident_ids),
            WorkOrder.incident_id == Incident.id,
            Task.incident_id == Incident.id,
            WorkOrder.task_id == Task.id,
            WorkOrder.status == WorkOrderStatus.COMPLETED,
            ~has_result,
        ]
        base = (
            select(WorkOrder.id)
            .join(Incident, Incident.id == WorkOrder.incident_id)
            .join(Task, Task.id == WorkOrder.task_id)
            .where(*conditions)
        )
        total = int(
            await self.session.scalar(select(func.count()).select_from(base.subquery())) or 0
        )
        statement = (
            select(WorkOrder, Task, Incident)
            .join(Incident, Incident.id == WorkOrder.incident_id)
            .join(Task, Task.id == WorkOrder.task_id)
            .where(*conditions)
            .order_by(
                WorkOrder.execution_completed_at.asc().nulls_last(),
                WorkOrder.task_id.asc(),
                WorkOrder.attempt_no.asc(),
                WorkOrder.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        rows = await self.session.execute(statement)
        return list(rows.all()), total

    async def has_result(self, *, work_order_id: UUID) -> bool:
        result_id = await self.session.scalar(
            select(QCResult.id).where(QCResult.work_order_id == work_order_id).limit(1)
        )
        return result_id is not None

    async def list_results(
        self, *, tenant_id: UUID, work_order_id: UUID
    ) -> list[QCResult]:
        rows = await self.session.scalars(
            select(QCResult)
            .join(WorkOrder, WorkOrder.id == QCResult.work_order_id)
            .join(Incident, Incident.id == WorkOrder.incident_id)
            .where(
                Incident.tenant_id == tenant_id,
                WorkOrder.id == work_order_id,
            )
            .order_by(QCResult.checked_at, QCResult.id)
        )
        return list(rows.all())

    async def list_result_evidence(
        self, *, tenant_id: UUID, qc_result_id: UUID
    ) -> list[tuple[EvidenceRef, FileObject]]:
        rows = await self.session.execute(
            select(EvidenceRef, FileObject)
            .join(QCResultEvidence, QCResultEvidence.evidence_ref_id == EvidenceRef.id)
            .join(QCResult, QCResult.id == QCResultEvidence.qc_result_id)
            .join(WorkOrder, WorkOrder.id == QCResult.work_order_id)
            .join(Incident, Incident.id == WorkOrder.incident_id)
            .join(FileObject, FileObject.id == EvidenceRef.file_id)
            .where(
                QCResult.id == qc_result_id,
                Incident.tenant_id == tenant_id,
                EvidenceRef.work_order_id == WorkOrder.id,
                EvidenceRef.incident_id == WorkOrder.incident_id,
                EvidenceRef.task_id == WorkOrder.task_id,
                EvidenceRef.capture_phase == EvidenceCapturePhase.QC,
                FileObject.tenant_id == tenant_id,
            )
            .order_by(EvidenceRef.created_at, EvidenceRef.id)
        )
        return [(row[0], row[1]) for row in rows.all()]

    async def add_result(self, result: QCResult) -> QCResult:
        self.session.add(result)
        await self.session.flush()
        return result

    async def add_evidence_link(self, qc_result_id: UUID, evidence_ref_id: UUID) -> None:
        self.session.add(
            QCResultEvidence(qc_result_id=qc_result_id, evidence_ref_id=evidence_ref_id)
        )
        await self.session.flush()
