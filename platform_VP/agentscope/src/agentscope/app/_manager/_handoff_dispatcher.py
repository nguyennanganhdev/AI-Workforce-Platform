"""Restart-safe delivery of durable agent-to-agent handoffs."""

import asyncio
from typing import Self

from ..._logging import logger
from .._bus_ops import deliver_to_inbox
from .._shared_context import ContextDirective, SharedContextService
from .._team_turn import team_is_awaiting_user
from ..message_bus import MessageBus, MessageBusKeys
from ..storage import StorageBase, TeamHandoffRecord


class HandoffDispatcher:
    """Recover pending handoffs and retry failed deliveries at least once."""

    def __init__(
        self,
        message_bus: MessageBus,
        storage: StorageBase,
        *,
        interval_seconds: float = 2.0,
    ) -> None:
        self._bus = message_bus
        self._storage = storage
        self._context = SharedContextService(storage, message_bus)
        self._interval = interval_seconds
        self._task: asyncio.Task | None = None

    async def __aenter__(self) -> Self:
        # Includes rows marked delivered whose Redis inbox/marker disappeared
        # during a Redis restart. Recipient-side handoff-id dedupe makes this
        # recovery safe.
        await self._recover(include_delivered=True)
        self._task = asyncio.create_task(
            self._loop(),
            name="team-handoff-dispatcher",
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self._recover(include_delivered=False)
            except Exception:  # noqa: BLE001 - dispatcher isolation boundary
                logger.exception("HandoffDispatcher recovery pass failed")

    async def _recover(self, *, include_delivered: bool) -> None:
        rows = await self._storage.list_outstanding_team_handoffs(limit=500)
        for record in rows:
            if record.delivery_status == "delivered" and not include_delivered:
                continue
            await self._deliver(record)

    async def _deliver(self, record: TeamHandoffRecord) -> None:
        marker_key = MessageBusKeys.team_handoff_delivery(record.handoff_id)
        async with self._bus.acquire_lock(
            MessageBusKeys.team_handoff_delivery_lock(
                record.handoff_id,
                record.recipient_session_id,
            ),
            ttl_secs=MessageBusKeys.TEAM_HANDOFF_DELIVERY_LOCK_TTL_SECS,
        ):
            if (
                await self._bus.registry_get(
                    marker_key,
                    record.recipient_session_id,
                )
                is not None
            ):
                return
            await self._context.register_directive(
                record.recipient_session_id,
                ContextDirective(
                    handoff_id=record.handoff_id,
                    mode=record.context_mode,
                    task_id=record.task_id,
                    reference_event_ids=record.reference_event_ids,
                    context_ref=record.context_ref,
                    context_revision=record.context_revision,
                    thread_id=record.thread_id,
                    in_reply_to=record.in_reply_to,
                    hop_count=record.hop_count,
                ),
            )
            wake = not await team_is_awaiting_user(
                self._bus,
                record.team_id,
                storage=self._storage,
                user_id=record.user_id,
            )
            try:
                await deliver_to_inbox(
                    self._bus,
                    user_id=record.user_id,
                    session_id=record.recipient_session_id,
                    agent_id=record.recipient_agent_id,
                    payload=record.payload,
                    wake=wake,
                )
            except Exception as exc:  # noqa: BLE001 - durable retry boundary
                await self._context.mark_handoff(
                    record,
                    "failed",
                    error=str(exc),
                )
                return
            await self._context.mark_handoff(record, "delivered")
            await self._bus.registry_set(
                marker_key,
                record.recipient_session_id,
                "1",
                ttl_secs=MessageBusKeys.TEAM_HANDOFF_DELIVERY_TTL_SECS,
            )


__all__ = ["HandoffDispatcher"]
