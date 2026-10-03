"""Tenant-scoped persistence operations for business Tasks."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.incident import Incident
from ..db.task import Task


class TaskRepository:
    """Task reads are scoped through the owning Incident's tenant."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, *, tenant_id: UUID, task_id: UUID) -> Task | None:
        statement = (
            select(Task)
            .join(Incident, Task.incident_id == Incident.id)
            .where(Incident.tenant_id == tenant_id, Task.id == task_id)
        )
        return await self._session.scalar(statement)

    async def get_by_id_for_update(
        self, *, tenant_id: UUID, task_id: UUID
    ) -> Task | None:
        statement = (
            select(Task)
            .join(Incident, Task.incident_id == Incident.id)
            .where(Incident.tenant_id == tenant_id, Task.id == task_id)
            .with_for_update(of=Task)
            .execution_options(populate_existing=True)
        )
        return await self._session.scalar(statement)

    async def list_by_incident(
        self, *, tenant_id: UUID, incident_id: UUID
    ) -> list[Task]:
        statement = (
            select(Task)
            .join(Incident, Task.incident_id == Incident.id)
            .where(Incident.tenant_id == tenant_id, Incident.id == incident_id)
            .order_by(Task.created_at, Task.id)
        )
        result = await self._session.scalars(statement)
        return list(result.all())

    async def add(self, task: Task, *, tenant_id: UUID) -> Task | None:
        """Add only when the owning Incident is visible to the supplied tenant."""
        incident_id = await self._session.scalar(
            select(Incident.id).where(
                Incident.id == task.incident_id,
                Incident.tenant_id == tenant_id,
            )
        )
        if incident_id is None:
            return None
        self._session.add(task)
        await self._session.flush()
        return task
