# -*- coding: utf-8 -*-
"""Production Registry provider consumed by Execution composition."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ...contracts import AsyncProtocolSnapshotRef, Scope
from ._models import AsyncToolProtocol
from ._service import AsyncProtocolService, EventContextLoader
from ._sql_repository import SqlAsyncProtocolRepository


class SqlAsyncProtocolProvider:
    """Bind scoped services and resolve exact pins without importing Execution.

    C2 supplies Registry persistence and the exact-detail resolver. C3 injects
    its persisted provider-inbox loader when binding a service. The final root
    composition may pass ``resolve_detail`` directly to
    ``ExecutionProtocolAdapter``.
    """

    def __init__(self, uows: Callable[[], Any]) -> None:
        self.repository = SqlAsyncProtocolRepository(uows)

    def bind(
        self,
        scope: Scope,
        load_event_context: EventContextLoader,
    ) -> AsyncProtocolService:
        return AsyncProtocolService(
            self.repository,
            Scope.model_validate(scope),
            load_event_context,
        )

    async def resolve_detail(
        self,
        scope: Scope,
        snapshot: AsyncProtocolSnapshotRef,
    ) -> AsyncToolProtocol:
        scope = Scope.model_validate(scope)
        snapshot = AsyncProtocolSnapshotRef.model_validate(snapshot)
        protocol = await self.repository.get_pinned(scope, snapshot)
        if protocol.snapshot_ref != snapshot:
            raise ValueError("async protocol snapshot mismatch")
        return protocol


__all__ = ["SqlAsyncProtocolProvider"]
