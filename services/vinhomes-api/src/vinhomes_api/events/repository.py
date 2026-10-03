"""Tenant-aware append operations for the business event stream."""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.business_event import BusinessEvent
from ..db.incident import Incident
from ..outbox import OutboxRepository


class BusinessEventRepository:
    """Append events using the caller's session and transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        *,
        tenant_id: UUID,
        incident_id: UUID | None,
        subject_type: str,
        subject_id: str,
        event_type: str,
        actor_type: str,
        actor_id: str,
        actor_version: int | None,
        data: dict[str, Any],
        correlation_id: str,
    ) -> BusinessEvent | None:
        """Append when the optional Incident belongs to the supplied tenant.

        A ``None`` result means the Incident is missing or outside this tenant;
        callers should return their normal not-found response.
        """

        if incident_id is not None:
            visible_incident = await self._session.scalar(
                select(Incident.id).where(
                    Incident.id == incident_id,
                    Incident.tenant_id == tenant_id,
                )
            )
            if visible_incident is None:
                return None

        business_event = BusinessEvent(
            tenant_id=tenant_id,
            incident_id=incident_id,
            subject_type=subject_type,
            subject_id=subject_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_version=actor_version,
            data=data,
            correlation_id=correlation_id,
        )
        self._session.add(business_event)
        await self._session.flush()
        await OutboxRepository(self._session).append_business_event(business_event)
        return business_event

    async def list_for_incident(
        self,
        *,
        tenant_id: UUID,
        incident_id: UUID,
        event_types: list[str] | None,
        limit: int,
        offset: int,
    ) -> tuple[list[BusinessEvent], int]:
        conditions = [
            BusinessEvent.tenant_id == tenant_id,
            BusinessEvent.incident_id == incident_id,
        ]
        if event_types:
            conditions.append(BusinessEvent.event_type.in_(event_types))
        total = int(
            await self._session.scalar(
                select(func.count(BusinessEvent.id)).where(*conditions)
            )
            or 0
        )
        rows = await self._session.scalars(
            select(BusinessEvent)
            .where(*conditions)
            .order_by(BusinessEvent.occurred_at.desc(), BusinessEvent.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(rows.all()), total
