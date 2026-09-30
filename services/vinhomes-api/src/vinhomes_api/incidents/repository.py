"""Tenant and effective-scope persistence operations for Incidents."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.incident import Incident, IncidentStatus
from .schemas import IncidentSlaStatus, IncidentSortField, IncidentSortOrder


class IncidentRepository:
    """Tenant-scoped Incident persistence; transaction ownership stays with caller."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, *, tenant_id: UUID, incident_id: UUID) -> Incident | None:
        statement = select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.id == incident_id,
        )
        return await self._session.scalar(statement)

    async def get_by_id_for_update(
        self, *, tenant_id: UUID, incident_id: UUID
    ) -> Incident | None:
        statement = (
            select(Incident)
            .where(Incident.tenant_id == tenant_id, Incident.id == incident_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return await self._session.scalar(statement)

    async def list_for_queue(
        self,
        *,
        tenant_id: UUID,
        scoped_incident_ids: list[UUID],
        limit: int,
        offset: int,
        now: datetime,
        status: IncidentStatus | None = None,
        severity: str | None = None,
        category: str | None = None,
        tower_id: UUID | None = None,
        sla_status: IncidentSlaStatus | None = None,
        sort_by: IncidentSortField = IncidentSortField.SLA,
        sort_order: IncidentSortOrder | None = None,
    ) -> tuple[list[Incident], int]:
        """Return a stable, filtered page restricted to tenant and incident scope."""
        conditions = [
            Incident.tenant_id == tenant_id,
            Incident.id.in_(scoped_incident_ids),
        ]
        if status is not None:
            conditions.append(Incident.status == status)
        if severity is not None:
            conditions.append(func.lower(Incident.severity) == severity.strip().lower())
        if category is not None:
            conditions.append(func.lower(Incident.category) == category.strip().lower())
        if tower_id is not None:
            conditions.append(Incident.tower_id == tower_id)
        if sla_status is IncidentSlaStatus.OVERDUE:
            conditions.append(Incident.sla_due_at.is_not(None))
            conditions.append(Incident.sla_due_at <= now)
        elif sla_status is IncidentSlaStatus.ON_TRACK:
            conditions.append(Incident.sla_due_at > now)
        elif sla_status is IncidentSlaStatus.NO_DEADLINE:
            conditions.append(Incident.sla_due_at.is_(None))

        count_statement = select(func.count(Incident.id)).where(*conditions)
        total = int(await self._session.scalar(count_statement) or 0)

        order = sort_order
        if order is None:
            order = (
                IncidentSortOrder.DESC
                if sort_by is IncidentSortField.CREATED_AT
                else IncidentSortOrder.ASC
            )

        if sort_by is IncidentSortField.SLA:
            null_deadline_last = case((Incident.sla_due_at.is_(None), 1), else_=0).asc()
            primary_order = (
                Incident.sla_due_at.desc()
                if order is IncidentSortOrder.DESC
                else Incident.sla_due_at.asc()
            )
            ordering = [null_deadline_last, primary_order]
        elif sort_by is IncidentSortField.SEVERITY:
            # The UX reference orders its defined L1/L2/L3 labels by urgency.
            # Other open severity codes remain supported and sort lexically after those.
            severity_rank = case(
                (func.upper(Incident.severity) == "L1", 0),
                (func.upper(Incident.severity) == "L2", 1),
                (func.upper(Incident.severity) == "L3", 2),
                else_=3,
            )
            rank_order = severity_rank.desc() if order is IncidentSortOrder.DESC else severity_rank.asc()
            code_order = func.upper(Incident.severity).desc() if order is IncidentSortOrder.DESC else func.upper(Incident.severity).asc()
            ordering = [rank_order, code_order, Incident.created_at.desc()]
        else:
            ordering = [
                Incident.created_at.desc()
                if order is IncidentSortOrder.DESC
                else Incident.created_at.asc()
            ]
        ordering.append(Incident.id.asc())

        statement = (
            select(Incident)
            .where(*conditions)
            .order_by(*ordering)
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.scalars(statement)
        return list(result.all()), total

    async def add(self, incident: Incident) -> Incident:
        self._session.add(incident)
        await self._session.flush()
        return incident
