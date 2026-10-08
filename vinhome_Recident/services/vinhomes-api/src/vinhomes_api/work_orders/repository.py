"""Tenant-scoped WorkOrder persistence."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.incident import Incident
from ..db.task import Task, TaskStatus
from ..db.work_order import WorkOrder, WorkOrderStatus
from ..db.work_order_assignment import WorkOrderAssignment


class WorkOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _scoped(self, tenant_id: UUID):
        return (
            select(WorkOrder)
            .join(Incident, WorkOrder.incident_id == Incident.id)
            .join(Task, WorkOrder.task_id == Task.id)
            .where(
                Incident.tenant_id == tenant_id,
                Task.incident_id == Incident.id,
            )
        )

    async def get_by_id(self, *, tenant_id: UUID, work_order_id: UUID) -> WorkOrder | None:
        return await self.session.scalar(
            self._scoped(tenant_id).where(WorkOrder.id == work_order_id)
        )

    async def get_by_id_for_update(self, *, tenant_id: UUID, work_order_id: UUID) -> WorkOrder | None:
        return await self.session.scalar(
            self._scoped(tenant_id)
            .where(WorkOrder.id == work_order_id)
            .with_for_update(of=WorkOrder)
        )

    async def list_by_incident(self, *, tenant_id: UUID, incident_id: UUID) -> list[WorkOrder]:
        rows = await self.session.scalars(
            self._scoped(tenant_id)
            .where(WorkOrder.incident_id == incident_id)
            .order_by(WorkOrder.task_id, WorkOrder.attempt_no, WorkOrder.id)
        )
        return list(rows.all())

    async def list_for_supervisor(
        self,
        *,
        tenant_id: UUID,
        scoped_incident_ids: list[UUID],
        limit: int,
        offset: int,
        now: datetime,
        unassigned_only: bool = False,
        blocked_only: bool = False,
        overdue_only: bool = False,
        team_executor_id: UUID | None = None,
        area_location_id: str | None = None,
    ) -> tuple[list[tuple[WorkOrder, Task, Incident]], int]:
        """List operational rows inside trusted Incident scope.

        Team, area, and contractor agreement memberships are not persisted here;
        the upstream scope resolver must provide the effective Incident subjects.
        """
        conditions = [
            Incident.tenant_id == tenant_id,
            Incident.id.in_(scoped_incident_ids),
            Task.incident_id == Incident.id,
            WorkOrder.incident_id == Incident.id,
            WorkOrder.task_id == Task.id,
        ]
        if unassigned_only:
            conditions.extend(
                [
                    WorkOrder.status == WorkOrderStatus.OPEN,
                    WorkOrder.executor_id.is_(None),
                ]
            )
        if blocked_only:
            conditions.extend(
                [
                    Task.status == TaskStatus.BLOCKED,
                    WorkOrder.status.in_(
                        {
                            WorkOrderStatus.OPEN,
                            WorkOrderStatus.ASSIGNED,
                            WorkOrderStatus.IN_PROGRESS,
                        }
                    ),
                ]
            )
        if overdue_only:
            conditions.append(
                or_(
                    Incident.sla_due_at <= now,
                    and_(
                        Task.due_at <= now,
                        Task.status.not_in({TaskStatus.DONE, TaskStatus.CANCELLED}),
                    ),
                )
            )
        if team_executor_id is not None:
            conditions.extend(
                [
                    WorkOrder.executor_type == "TEAM",
                    WorkOrder.executor_id == team_executor_id,
                ]
            )
        if area_location_id is not None:
            conditions.append(
                Incident.location_json["locationId"].as_string() == area_location_id
            )

        base = (
            select(WorkOrder.id)
            .join(Incident, WorkOrder.incident_id == Incident.id)
            .join(Task, WorkOrder.task_id == Task.id)
            .where(*conditions)
        )
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        statement = (
            select(WorkOrder, Task, Incident)
            .join(Incident, WorkOrder.incident_id == Incident.id)
            .join(Task, WorkOrder.task_id == Task.id)
            .where(*conditions)
            .order_by(
                Task.due_at.asc().nulls_last(),
                Incident.sla_due_at.asc().nulls_last(),
                WorkOrder.task_id.asc(),
                WorkOrder.attempt_no.asc(),
                WorkOrder.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(statement)
        return list(result.all()), total

    async def list_for_executor(
        self,
        *,
        tenant_id: UUID,
        executor_id: UUID,
        executor_types: list[str],
        scoped_incident_ids: list[UUID],
        status: WorkOrderStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[WorkOrder], int]:
        """List only this executor's attempts inside trusted Incident scope."""
        conditions = [
            Incident.tenant_id == tenant_id,
            Incident.id.in_(scoped_incident_ids),
            Task.incident_id == Incident.id,
            WorkOrder.incident_id == Incident.id,
            WorkOrder.task_id == Task.id,
            WorkOrder.executor_id == executor_id,
            WorkOrder.executor_type.in_(executor_types),
        ]
        if status is not None:
            conditions.append(WorkOrder.status == status)

        base = (
            select(WorkOrder.id)
            .join(Incident, WorkOrder.incident_id == Incident.id)
            .join(Task, WorkOrder.task_id == Task.id)
            .where(*conditions)
        )
        total = int(
            await self.session.scalar(select(func.count()).select_from(base.subquery()))
            or 0
        )
        statement = (
            select(WorkOrder)
            .join(Incident, WorkOrder.incident_id == Incident.id)
            .join(Task, WorkOrder.task_id == Task.id)
            .where(*conditions)
            .order_by(
                WorkOrder.execution_started_at.desc().nulls_last(),
                WorkOrder.id,
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.scalars(statement)
        return list(result.all()), total

    async def list_attempts(self, *, tenant_id: UUID, task_id: UUID) -> list[WorkOrder]:
        rows = await self.session.scalars(
            self._scoped(tenant_id)
            .where(WorkOrder.task_id == task_id)
            .order_by(WorkOrder.attempt_no, WorkOrder.id)
        )
        return list(rows.all())

    async def has_later_attempt(self, *, tenant_id: UUID, work_order: WorkOrder) -> bool:
        later_id = await self.session.scalar(
            select(WorkOrder.id)
            .join(Incident, WorkOrder.incident_id == Incident.id)
            .where(
                Incident.tenant_id == tenant_id,
                WorkOrder.task_id == work_order.task_id,
                WorkOrder.attempt_no > work_order.attempt_no,
            )
            .limit(1)
        )
        return later_id is not None

    async def list_assignments(
        self, *, tenant_id: UUID, work_order_id: UUID
    ) -> list[WorkOrderAssignment]:
        statement = (
            select(WorkOrderAssignment)
            .join(WorkOrder, WorkOrderAssignment.work_order_id == WorkOrder.id)
            .join(Incident, WorkOrder.incident_id == Incident.id)
            .where(Incident.tenant_id == tenant_id, WorkOrder.id == work_order_id)
            .order_by(WorkOrderAssignment.work_order_version, WorkOrderAssignment.id)
        )
        result = await self.session.scalars(statement)
        return list(result.all())
