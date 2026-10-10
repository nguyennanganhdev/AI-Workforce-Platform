# -*- coding: utf-8 -*-
"""Persistence boundary; the PostgreSQL/UOW adapter is wired in Phase C."""

from typing import Protocol

from ...contracts import AsyncProtocolSnapshotRef, Scope, UnitOfWork
from ._models import AsyncToolProtocol


class AsyncProtocolRepository(Protocol):
    """Scope every read/write; never delete or overwrite pinned content.

    Publish must atomically compare the current reference, append immutable
    (scope, tool_version_id, protocol_id, protocol_version) content, and move
    the current pointer. Same key/hash is idempotent, different hash conflicts.
    Publishing preserves enabled state; only set_enabled may change it.
    Implementations must not commit an injected UOW.
    """

    async def publish(
        self,
        scope: Scope,
        protocol: AsyncToolProtocol,
        expected_snapshot: AsyncProtocolSnapshotRef | None,
        uow: UnitOfWork | None = None,
    ) -> None:
        ...

    async def get_current(
        self,
        scope: Scope,
        tool_version_id: str,
    ) -> tuple[AsyncToolProtocol, bool]:
        ...

    async def get_pinned(
        self,
        scope: Scope,
        snapshot: AsyncProtocolSnapshotRef,
    ) -> AsyncToolProtocol:
        ...

    async def set_enabled(
        self,
        scope: Scope,
        tool_version_id: str,
        enabled: bool,
        expected_snapshot: AsyncProtocolSnapshotRef,
        uow: UnitOfWork | None = None,
    ) -> None:
        ...
