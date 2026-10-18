# -*- coding: utf-8 -*-
"""Authorized durable public event projection, history, snapshot, and SSE."""

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import datetime
import math
from time import monotonic
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
from ..workflows import WorkflowAuthorization, next_action
from ..workflows._models import raw_value
from .phase_a import ApprovalRequiredPayload, validate_public_event


class EventCursorExpired(RuntimeError):
    """Transport adapters map this to HTTP 410 and snapshot recovery."""


class ConversationAccess(WorkforceModel):
    scope: Scope
    audience: PartnerAudience
    conversation_id: str
    workflow_id: str
    ticket_id: str | None = None


class EventRepository(Protocol):
    """Repository must derive access from storage and isolate every cursor."""

    async def access(
        self, conversation_id: str, uow: UnitOfWork | None = None
    ) -> ConversationAccess: ...

    async def append(
        self,
        access: ConversationAccess,
        event: ConversationEvent,
        uow: UnitOfWork,
    ) -> ConversationEvent: ...

    async def list_after(
        self,
        access: ConversationAccess,
        cursor: str | None,
        limit: int,
    ) -> EventHistoryPage: ...

    async def snapshot(
        self, access: ConversationAccess
    ) -> ConversationSnapshot: ...


class _ReliableReplaySignal:
    """A broken advisory signal delays but can never replace durable replay."""

    def __init__(self, signal: PublicEventSignalPort) -> None:
        self._signal = signal

    async def wait_for_signal(self, scope, conversation_id, timeout):
        started = monotonic()
        try:
            return await asyncio.wait_for(
                self._signal.wait_for_signal(scope, conversation_id, timeout),
                timeout,
            )
        except Exception:
            remaining = max(0.0, timeout - (monotonic() - started))
            if remaining:
                await asyncio.sleep(remaining)
            return None

    async def notify_after_commit(self, *args):
        return await self._signal.notify_after_commit(*args)

    async def health(self):
        return await self._signal.health()


def _check_event(access: ConversationAccess, event: ConversationEvent) -> None:
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
        raise PermissionError(
            "public event does not match conversation binding"
        )
    if (
        type(event.sequence) is not int
        or event.sequence < 1
        or event.occurred_at.tzinfo is None
        or event.recorded_at.tzinfo is None
    ):
        raise ValueError(
            "public event requires strict sequence and aware timestamps"
        )


class ConversationEventService:
    def __init__(
        self,
        repository: EventRepository,
        authorization: WorkflowAuthorization,
        signals: PublicEventSignalPort,
        uows: UnitOfWorkFactory,
        *,
        heartbeat_seconds: float = 15.0,
    ) -> None:
        if (
            isinstance(heartbeat_seconds, bool)
            or not isinstance(heartbeat_seconds, (int, float))
            or not math.isfinite(heartbeat_seconds)
            or not 0 < heartbeat_seconds <= 60
        ):
            raise ValueError("heartbeat must be finite and at most 60 seconds")
        self.repository = repository
        self.authorization = authorization
        self.signals = signals
        self.uows = uows
        self._sse = ConversationSseService(
            self,
            _ReliableReplaySignal(signals),
            heartbeat_seconds=heartbeat_seconds,
        )

    async def _authorized_access(
        self, actor, conversation_id
    ) -> ConversationAccess:
        access = ConversationAccess.model_validate(
            raw_value(await self.repository.access(conversation_id))
        )
        await self.authorization.authorize(
            access.scope,
            actor,
            access.audience,
            "read_events",
        )
        return access

    async def append(self, scope, audience, event, uow=None):
        parsed = ConversationEvent.model_validate(raw_value(event))
        if uow is None:
            async with self.uows() as owned:
                stored = await self.append(scope, audience, parsed, owned)
                await owned.commit()
                return stored
        access = ConversationAccess.model_validate(
            raw_value(
                await self.repository.access(parsed.conversation_id, uow)
            )
        )
        if access.scope != scope or access.audience != audience:
            raise PermissionError("conversation write binding mismatch")
        _check_event(access, parsed)
        stored = ConversationEvent.model_validate(
            raw_value(await self.repository.append(access, parsed, uow))
        )
        _check_event(access, stored)
        if stored.model_dump(exclude={"sequence"}) != parsed.model_dump(
            exclude={"sequence"}
        ):
            raise RuntimeError("event repository changed public content")

        async def notify() -> None:
            try:
                await self.signals.notify_after_commit(
                    scope, parsed.conversation_id, stored.sequence
                )
            except Exception:
                return

        uow.add_after_commit(notify)
        return stored

    async def list_after(self, actor, conversation_id, cursor, limit):
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError(
                "history limit must be a strict integer from 1 to 500"
            )
        access = await self._authorized_access(actor, conversation_id)
        raw_page = raw_value(
            await self.repository.list_after(access, cursor, limit)
        )
        if (
            not isinstance(raw_page, dict)
            or type(raw_page.get("has_more")) is not bool
        ):
            raise ValueError("history repository returned an invalid page")
        page = EventHistoryPage.model_validate(raw_page)
        previous = 0
        seen: set[str] = set()
        for event in page.items:
            _check_event(access, event)
            if (
                event.sequence <= previous
                or event.event_id in seen
                or event.event_id == cursor
            ):
                raise RuntimeError(
                    "history page does not advance monotonically"
                )
            previous = event.sequence
            seen.add(event.event_id)
        if len(page.items) > limit or (page.has_more and not page.items):
            raise RuntimeError(
                "history repository returned an impossible page"
            )
        expected_cursor = page.items[-1].event_id if page.items else cursor
        if page.next_cursor != expected_cursor:
            raise RuntimeError(
                "history next_cursor does not match delivered events"
            )
        return page

    async def snapshot(self, actor, conversation_id):
        access = await self._authorized_access(actor, conversation_id)
        snapshot = ConversationSnapshot.model_validate(
            raw_value(await self.repository.snapshot(access))
        )
        audience = access.audience
        if (
            snapshot.conversation_id != access.conversation_id
            or snapshot.external_user_id != audience.external_user_id
            or snapshot.external_conversation_id
            != audience.external_conversation_id
            or len(snapshot.workflows) != 1
        ):
            raise PermissionError(
                "snapshot does not match conversation audience"
            )
        workflow = snapshot.workflows[0]
        if (
            workflow.workflow_id != access.workflow_id
            or workflow.ticket_id != access.ticket_id
            or workflow.external_ticket_id != audience.external_ticket_id
            or workflow.next_action != next_action(workflow.state)
        ):
            raise PermissionError("snapshot workflow binding is invalid")
        if any(
            message.workflow_id != access.workflow_id
            or message.created_at.tzinfo is None
            for message in snapshot.messages
        ):
            raise PermissionError(
                "snapshot contains a message from another workflow"
            )
        # A pending approval is its id and status, plus what its
        # approval.required event said (same shape, same checks).
        allowed_approval_fields = {
            "workflow_id",
            "status",
            *ApprovalRequiredPayload.model_fields,
        }
        approval_ids: set[str] = set()
        for approval in snapshot.pending_approvals:
            approval_id = approval.get("approval_id")
            status = approval.get("status")
            required = {
                key: value
                for key, value in approval.items()
                if key not in ("workflow_id", "status")
            }
            try:
                if set(required) - {"approval_id"}:
                    ApprovalRequiredPayload.model_validate(required)
                valid = True
            except ValueError:
                valid = False
            if (
                not valid
                or approval.get("workflow_id") != access.workflow_id
                or set(approval) - allowed_approval_fields
                or not isinstance(approval_id, str)
                or not approval_id
                or (
                    status is not None
                    and (
                        not isinstance(status, str)
                        or not status
                        or len(status) > 128
                    )
                )
                or approval_id in approval_ids
            ):
                raise PermissionError("snapshot contains an invalid approval")
            approval_ids.add(approval_id)
        return snapshot.model_dump(mode="json")

    async def _frames(self, actor, conversation_id, cursor):
        original = await self._authorized_access(actor, conversation_id)
        frames = self._sse.frames(
            actor, original.scope, conversation_id, cursor
        )
        try:
            async for frame in frames:
                current = await self._authorized_access(actor, conversation_id)
                if current != original:
                    raise PermissionError(
                        "conversation binding changed during stream"
                    )
                yield frame
        finally:
            await frames.aclose()

    async def subscribe(self, actor, conversation_id, cursor=None):
        frames = self._frames(actor, conversation_id, cursor)
        try:
            async for frame in frames:
                if frame.data is not None:
                    yield ConversationEvent.model_validate_json(frame.data)
        finally:
            await frames.aclose()

    async def stream(
        self, actor, conversation_id, cursor=None
    ) -> AsyncIterator[bytes]:
        frames = self._frames(actor, conversation_id, cursor)
        try:
            async for frame in frames:
                yield frame.encode()
        finally:
            await frames.aclose()


class PublicEventWriter:
    """Build allowlisted public events from persisted workflow bindings."""

    def __init__(
        self,
        service: ConversationEventService,
        clock: Callable[[], datetime],
        ids: Callable[[], str] = lambda: uuid4().hex,
    ) -> None:
        self.service = service
        self.clock = clock
        self.ids = ids

    async def write(
        self, workflow, event_type, payload, uow, causation_id=None
    ):
        now = self.clock()
        event = ConversationEvent(
            event_id=self.ids(),
            sequence=1,
            event_type=event_type,
            occurred_at=now,
            recorded_at=now,
            conversation_id=workflow.conversation_id,
            external_ticket_id=workflow.audience.external_ticket_id,
            external_conversation_id=(
                workflow.audience.external_conversation_id
            ),
            external_user_id=workflow.audience.external_user_id,
            workflow_id=workflow.workflow_id,
            ticket_id=workflow.ticket_id,
            causation_id=causation_id,
            payload=payload,
        )
        return await self.service.append(
            workflow.scope, workflow.audience, event, uow
        )

