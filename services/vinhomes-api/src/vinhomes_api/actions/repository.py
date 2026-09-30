"""Tenant-scoped persistence operations for ActionRequest."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.action_request import ActionRequest
from ..db.incident import Incident
from ..db.task import Task


class ActionRequestRepository:
    """ActionRequest reads and writes are scoped to the owning Incident."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self, *, tenant_id: UUID, action_request_id: UUID
    ) -> ActionRequest | None:
        statement = (
            select(ActionRequest)
            .join(Incident, ActionRequest.incident_id == Incident.id)
            .where(
                Incident.tenant_id == tenant_id,
                ActionRequest.id == action_request_id,
            )
        )
        return await self._session.scalar(statement)

    async def get_by_id_for_update(
        self, *, tenant_id: UUID, action_request_id: UUID
    ) -> ActionRequest | None:
        statement = (
            select(ActionRequest)
            .join(Incident, ActionRequest.incident_id == Incident.id)
            .where(
                Incident.tenant_id == tenant_id,
                ActionRequest.id == action_request_id,
            )
            .with_for_update(of=ActionRequest)
        )
        return await self._session.scalar(statement)

    async def add(
        self, action_request: ActionRequest, *, tenant_id: UUID
    ) -> ActionRequest | None:
        statement = (
            select(Task.id)
            .join(Incident, Task.incident_id == Incident.id)
            .where(
                Task.id == action_request.task_id,
                Task.incident_id == action_request.incident_id,
                Incident.tenant_id == tenant_id,
            )
        )
        task_id = await self._session.scalar(statement)
        if task_id is None:
            return None
        self._session.add(action_request)
        await self._session.flush()
        return action_request
