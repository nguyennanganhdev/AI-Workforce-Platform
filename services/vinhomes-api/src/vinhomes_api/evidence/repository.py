"""Tenant-scoped persistence for file metadata and append-only evidence refs."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.evidence import EvidenceRef, FileObject
from ..db.incident import Incident
from ..db.work_order import WorkOrder


class EvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_file_object(self, file_object: FileObject) -> FileObject:
        self.session.add(file_object)
        await self.session.flush()
        return file_object

    async def get_file_object(
        self, *, tenant_id: UUID, file_object_id: UUID
    ) -> FileObject | None:
        return await self.session.scalar(
            select(FileObject).where(
                FileObject.tenant_id == tenant_id,
                FileObject.id == file_object_id,
            )
        )

    async def add_evidence_ref(self, evidence_ref: EvidenceRef) -> EvidenceRef:
        self.session.add(evidence_ref)
        await self.session.flush()
        return evidence_ref

    async def list_work_order_evidence(
        self, *, tenant_id: UUID, work_order: WorkOrder
    ) -> list[tuple[EvidenceRef, FileObject]]:
        rows = await self.session.execute(
            select(EvidenceRef, FileObject)
            .join(FileObject, FileObject.id == EvidenceRef.file_id)
            .join(WorkOrder, WorkOrder.id == EvidenceRef.work_order_id)
            .join(Incident, Incident.id == WorkOrder.incident_id)
            .where(
                Incident.tenant_id == tenant_id,
                WorkOrder.id == work_order.id,
                EvidenceRef.incident_id == work_order.incident_id,
                EvidenceRef.task_id == work_order.task_id,
                FileObject.tenant_id == tenant_id,
            )
            .order_by(EvidenceRef.created_at, EvidenceRef.id)
        )
        return [(row[0], row[1]) for row in rows.all()]

    async def has_later_attempt(self, *, tenant_id: UUID, work_order: WorkOrder) -> bool:
        later = await self.session.scalar(
            select(WorkOrder.id)
            .join(Incident, Incident.id == WorkOrder.incident_id)
            .where(
                Incident.tenant_id == tenant_id,
                WorkOrder.task_id == work_order.task_id,
                WorkOrder.attempt_no > work_order.attempt_no,
            )
            .limit(1)
        )
        return later is not None
