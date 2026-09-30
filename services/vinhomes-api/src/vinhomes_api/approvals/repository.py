"""Tenant and Incident scoped persistence for action approvals."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.action_request import ActionRequest
from ..db.approval import ActionApproval, ApprovalStatus
from ..db.incident import Incident


class ActionApprovalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _scoped(self, tenant_id: UUID, incident_ids: list[UUID]):
        return (
            select(ActionApproval, ActionRequest)
            .join(ActionRequest, ActionApproval.action_request_id == ActionRequest.id)
            .join(Incident, ActionRequest.incident_id == Incident.id)
            .where(
                Incident.tenant_id == tenant_id,
                Incident.id.in_(incident_ids),
            )
        )

    async def list_by_scope(
        self,
        *,
        tenant_id: UUID,
        incident_ids: list[UUID],
        status: ApprovalStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[ActionApproval, ActionRequest]], int]:
        statement = self._scoped(tenant_id, incident_ids)
        if status is not None:
            statement = statement.where(ActionApproval.status == status)
        count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
        total = int(await self._session.scalar(count_statement) or 0)
        rows = await self._session.execute(
            statement.order_by(ActionApproval.expires_at, ActionApproval.id)
            .limit(limit)
            .offset(offset)
        )
        return list(rows.all()), total

    async def get_by_id(
        self,
        *,
        tenant_id: UUID,
        incident_ids: list[UUID],
        approval_id: UUID,
        for_update: bool = False,
    ) -> tuple[ActionApproval, ActionRequest] | None:
        statement = self._scoped(tenant_id, incident_ids).where(
            ActionApproval.id == approval_id
        )
        if for_update:
            statement = statement.with_for_update(of=(ActionApproval, ActionRequest))
        result = await self._session.execute(statement)
        return result.one_or_none()
