# -*- coding: utf-8 -*-
"""Best-effort Workforce wake-up signals over the existing message bus."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from hashlib import sha256

from agentscope.app.message_bus import MessageBus

from ...contracts import OpaqueId, Scope


HealthProbe = Callable[[], Awaitable[bool]]


def _scoped_channel(kind: str, scope: Scope, resource_id: str) -> str:
    values = (
        scope.tenant_id,
        scope.domain_id,
        scope.area_id,
        scope.manager_account_id,
        resource_id,
    )
    canonical = "".join(f"{len(value)}:{value}" for value in values)
    digest = sha256(canonical.encode("utf-8")).hexdigest()
    return f"agentscope:workforce:{kind}:{digest}"


class _MessageBusSignal:
    def __init__(
        self,
        bus: MessageBus,
        *,
        health_probe: HealthProbe | None = None,
    ) -> None:
        self._bus = bus
        self._health_probe = health_probe

    async def health(self) -> bool:
        if self._health_probe is not None:
            try:
                return bool(await self._health_probe())
            except Exception:  # pragma: no cover - defensive adapter boundary
                return False
        return True

    async def _wait(
        self,
        channel: str,
        timeout: float,
    ) -> dict[str, object] | None:
        if timeout < 0:
            raise ValueError("timeout must not be negative")
        subscription = self._bus.subscribe(channel)
        try:
            async with asyncio.timeout(timeout):
                return await anext(subscription)
        except TimeoutError:
            return None
        finally:
            await subscription.aclose()


class MessageBusPublicEventSignal(_MessageBusSignal):
    """PublicEventSignalPort adapter; never used as event persistence."""

    async def notify_after_commit(
        self,
        scope: Scope,
        conversation_id: OpaqueId,
        committed_sequence: int,
    ) -> None:
        if committed_sequence < 1:
            raise ValueError("committed_sequence must be positive")
        await self._bus.publish(
            _scoped_channel("conversation", scope, conversation_id),
            {"committed_sequence": committed_sequence},
        )

    async def wait_for_signal(
        self,
        scope: Scope,
        conversation_id: OpaqueId,
        timeout: float,
    ) -> int | None:
        payload = await self._wait(
            _scoped_channel("conversation", scope, conversation_id),
            timeout,
        )
        if payload is None:
            return None
        sequence = payload.get("committed_sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool):
            return None
        return sequence if sequence >= 1 else None


class MessageBusRequestCompletionSignal(_MessageBusSignal):
    """RequestCompletionSignalPort adapter for bounded POST waits."""

    async def notify_after_commit(
        self,
        scope: Scope,
        request_id: OpaqueId,
    ) -> None:
        await self._bus.publish(
            _scoped_channel("request", scope, request_id),
            {"completed": True},
        )

    async def wait_for_completion(
        self,
        scope: Scope,
        request_id: OpaqueId,
        timeout: float,
    ) -> bool:
        payload = await self._wait(
            _scoped_channel("request", scope, request_id),
            timeout,
        )
        return payload is not None and payload.get("completed") is True
