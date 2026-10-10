"""Authorized durable public projections; no production in-memory storage."""

from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Protocol
from uuid import uuid4

from ...contracts import (
    ConversationEvent,
    ConversationSnapshot,
    EventHistoryPage,
    PartnerAudience,
    PublicEventSignalPort,
    Scope,
    UnitOfWork,
    UnitOfWorkFactory,
    WorkforceModel,
)
from ...foundation.event_delivery import ConversationSseService
from ..workflows._boundary import WorkflowAuthorization
from .phase_a import validate_public_event


class EventCursorExpired(RuntimeError):
    """HTTP 410 requires recovery from an authorized snapshot."""


class ConversationAccess(WorkforceModel):
    scope: Scope
    audience: PartnerAudience
    conversation_id: str
    workflow_id: str
    ticket_id: str | None = None


class EventRepository(Protocol):
    """Reads must enforce scope/audience/cursor even under concurrent writes.

    append assigns a strictly increasing conversation sequence and unique event
    id in the caller's UOW. Snapshot and its cursor come from ONE consistent
    read. Unknown/expired cursors raise EventCursorExpired; foreign cursors
    not be treated as start-of-history. Access must be derived from storage.
    """

    async def access(
        self, conversation_id: str, uow: UnitOfWork | None = None
    ) -> ConversationAccess:
        ...

    async def append(
        self,
        access: ConversationAccess,
        event: ConversationEvent,
        uow: UnitOfWork,
    ) -> ConversationEvent:
        ...

    async def list_after(
        self, access: ConversationAccess, cursor: str | None, limit: int
    ) -> EventHistoryPage:
        ...

    async def snapshot(
        self, access: ConversationAccess
    ) -> ConversationSnapshot:
        ...


def check_event(access: ConversationAccess, event: ConversationEvent) -> None:
    validate_public_event(event)
    audience = access.audience
    if (
        event.conversation_id != access.conversation_id
        or event.workflow_id != access.workflow_id
        or event.ticket_id != access.ticket_id
        or event.external_user_id != audience.external_user_id
        or event.external_conversation_id != audience.external_conversation_id
        or event.external_ticket_id != audience.external_ticket_id
    ):
        raise PermissionError("event audience mismatch")
    if (
        type(event.sequence) is not int
        or event.sequence < 1
        or event.occurred_at.tzinfo is None
        or event.recorded_at.tzinfo is None
    ):
        raise ValueError(
            "public events require strict sequence and aware time"
        )


class ConversationEventService:
    def __init__(
        self,
        repository: EventRepository,
        authorization: WorkflowAuthorization,
        signals: PublicEventSignalPort,
        uows: UnitOfWorkFactory,
        *,
        heartbeat_seconds: float = 15
    ):
        self.repository = repository
        self.authorization = authorization
        self.signals = signals
        self.uows = uows
        self.sse = ConversationSseService(
            self, signals, heartbeat_seconds=heartbeat_seconds
        )

    async def _access(self, actor, conversation_id):
        access = await self.repository.access(conversation_id)
        await self.authorization.authorize(
            access.scope, actor, access.audience, "read_events"
        )
        return access

    async def append(self, scope, audience, event, uow=None):
        # Internal write callers must already hold a verified workflow context.
        stored_access = await self.repository.access(
            event.conversation_id, uow
        )
        if stored_access.scope != scope or stored_access.audience != audience:
            raise PermissionError("conversation write binding mismatch")
        access = stored_access
        check_event(access, event)
        if uow is None:
            async with self.uows() as owned:
                result = await self.append(scope, audience, event, owned)
                await owned.commit()
                return result
        stored = await self.repository.append(access, event, uow)
        check_event(access, stored)
        if stored.model_dump(exclude={"sequence"}) != event.model_dump(
            exclude={"sequence"}
        ):
            raise RuntimeError(
                "event repository rewrote public content/identity"
            )

        async def signal():
            try:
                await self.signals.notify_after_commit(
                    scope, event.conversation_id, stored.sequence
                )
            except Exception:
                # Advisory loss does not invalidate a committed durable result.
                pass

        uow.add_after_commit(signal)
        return stored

    async def list_after(self, actor, conversation_id, cursor, limit):
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("limit must be an integer between 1 and 500")
        access = await self._access(actor, conversation_id)
        page = await self.repository.list_after(access, cursor, limit)
        previous = 0
        for event in page.items:
            check_event(access, event)
            if event.sequence <= previous or event.event_id == cursor:
                raise RuntimeError("event page does not advance")
            previous = event.sequence
        if len(page.items) > limit or (page.has_more and not page.items):
            raise RuntimeError("invalid event page")
        if page.items and page.next_cursor != page.items[-1].event_id:
            raise RuntimeError("cursor must match the last committed event")
        if not page.items and page.next_cursor != cursor:
            raise RuntimeError("empty page must preserve the input cursor")
        return page

    async def snapshot(self, actor, conversation_id):
        access = await self._access(actor, conversation_id)
        snapshot = await self.repository.snapshot(access)
        audience = access.audience
        if (
            snapshot.conversation_id != conversation_id
            or snapshot.external_user_id != audience.external_user_id
            or snapshot.external_conversation_id
            != audience.external_conversation_id
            or any(
                w.external_ticket_id != audience.external_ticket_id
                or w.workflow_id != access.workflow_id
                or w.ticket_id != access.ticket_id
                for w in snapshot.workflows
            )
        ):
            raise PermissionError("snapshot audience mismatch")
        workflow_ids = {w.workflow_id for w in snapshot.workflows}
        if any(m.workflow_id not in workflow_ids for m in snapshot.messages):
            raise PermissionError("snapshot contains foreign messages")
        for approval in snapshot.pending_approvals:
            if approval.get("workflow_id") != access.workflow_id:
                raise PermissionError("snapshot contains foreign approvals")
        return snapshot.model_dump(mode="json")

    async def subscribe(self, actor, conversation_id, cursor=None):
        access = await self._access(actor, conversation_id)
        async for frame in self.sse.frames(
            actor, access.scope, conversation_id, cursor
        ):
            if frame.data is not None:
                yield ConversationEvent.model_validate_json(frame.data)

    async def stream(
        self, actor, conversation_id, cursor=None
    ) -> AsyncIterator[bytes]:
        access = await self._access(actor, conversation_id)
        async for frame in self.sse.stream(
            actor, access.scope, conversation_id, cursor
        ):
            yield frame


class PublicEventWriter:
    """Public projections omit checkpoint and raw provider facts."""

    def __init__(
        self,
        events: ConversationEventService,
        clock: Callable[[], datetime],
        ids: Callable[[], str] = lambda: uuid4().hex,
    ):
        self.events, self.clock, self.ids = events, clock, ids

    async def write(
        self, workflow, event_type, payload, uow, causation_id=None
    ):
        event = ConversationEvent(
            event_id=self.ids(),
            sequence=1,
            event_type=event_type,
            occurred_at=self.clock(),
            recorded_at=self.clock(),
            conversation_id=workflow.conversation_id,
            external_ticket_id=workflow.audience.external_ticket_id,
            external_conversation_id=(
                workflow.audience.external_conversation_id  # Pinned audience.
            ),
            external_user_id=workflow.audience.external_user_id,
            workflow_id=workflow.workflow_id,
            ticket_id=workflow.ticket_id,
            causation_id=causation_id,
            payload=payload,
        )
        return await self.events.append(
            workflow.scope, workflow.audience, event, uow
        )
