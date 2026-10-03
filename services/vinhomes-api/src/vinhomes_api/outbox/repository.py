"""Outbox record creation and bounded pending-message reads."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.business_event import BusinessEvent
from ..db.outbox_message import OutboxMessage, OutboxStatus


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append_business_event(self, event: BusinessEvent) -> OutboxMessage:
        message = OutboxMessage(
            tenant_id=event.tenant_id,
            business_event_id=event.id,
            event_type=event.event_type,
            payload={
                "eventId": str(event.id),
                "incidentId": str(event.incident_id) if event.incident_id else None,
                "subjectType": event.subject_type,
                "subjectId": event.subject_id,
                "eventType": event.event_type,
                "actorType": event.actor_type,
                "actorId": event.actor_id,
                "actorVersion": event.actor_version,
                "data": event.data,
                "correlationId": event.correlation_id,
                "occurredAt": event.occurred_at.isoformat(),
            },
            status=OutboxStatus.PENDING,
            attempt_count=0,
        )
        self._session.add(message)
        await self._session.flush()
        return message

    async def list_pending(self, *, tenant_id: UUID, limit: int = 100) -> list[OutboxMessage]:
        rows = await self._session.scalars(
            select(OutboxMessage)
            .where(
                OutboxMessage.tenant_id == tenant_id,
                OutboxMessage.status == OutboxStatus.PENDING,
            )
            .order_by(OutboxMessage.created_at, OutboxMessage.id)
            .limit(limit)
        )
        return list(rows.all())
