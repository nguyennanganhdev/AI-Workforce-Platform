# -*- coding: utf-8 -*-
"""Consume the real scoped Registry provider without owning its storage."""

from typing import Any

from ...contracts import Scope
from .._utils import ExecutionError
from ._protocol import ExecutionProtocolAdapter, protocol_hash


class RegistryExecutionProtocols:
    """Multiplex request-local protocol services by persisted operation scope.

    Supply Registry's SqlAsyncProtocolProvider and the same Execution
    repository/auth/operations used by ingress and processor. No engine,
    mutable normalizer context or permissive event loader is created here.
    """

    def __init__(
        self, provider: Any, repository: Any, auth: Any, operations: Any
    ) -> None:
        self.provider, self.repo = provider, repository
        self.auth, self.operations = auth, operations

    def bind(self, scope: Any) -> ExecutionProtocolAdapter:
        """Bind new-call reads to an already authorized manager scope."""
        scope = Scope.model_validate(scope)

        async def no_inbox(actor: Any, envelope: Any) -> Any:
            raise PermissionError("provider normalization requires inbox")

        def event_port(context: Any) -> Any:
            from ..provider_events._context import (
                PersistedProviderEventContext,
            )

            if Scope.model_validate(context["scope"]) != scope:
                raise PermissionError("protocol scope mismatch")
            loader = PersistedProviderEventContext(
                self.repo, self.auth, self.operations, context
            )
            return self.provider.bind(scope, loader)

        return ExecutionProtocolAdapter(
            self.provider.bind(scope, no_inbox),
            self.provider.resolve_detail,
            event_port,
        )

    async def get_snapshot(self, scope: Any, tool_version_id: str) -> Any:
        return await self.bind(scope).get_snapshot(scope, tool_version_id)

    async def resolve_snapshot(self, scope: Any, ref: Any) -> Any:
        return await self.bind(scope).resolve_snapshot(scope, ref)

    async def _pinned_adapter(self, protocol: Any) -> ExecutionProtocolAdapter:
        adapter = self.bind(protocol["scope"])
        resolved = await adapter.resolve_snapshot(
            protocol["scope"], protocol["snapshot_ref"]
        )
        if protocol_hash(protocol) != protocol_hash(resolved):
            raise ExecutionError("ASYNC_PROTOCOL_PIN_MISMATCH", 403)
        return adapter

    async def validate_envelope(self, principal: Any, envelope: Any) -> None:
        # The owner is unknown before inbox/correlation lookup. Structural
        # validation does not select a manager or a current protocol.
        await ExecutionProtocolAdapter.validate_envelope(principal, envelope)

    async def normalize_verified_event(
        self, principal: Any, protocol: Any, envelope: Any, **metadata: Any
    ) -> Any:
        adapter = await self._pinned_adapter(protocol)
        return await adapter.normalize_verified_event(
            principal, protocol, envelope, **metadata
        )

    async def normalize_creation_result(
        self, protocol: Any, output: Any
    ) -> Any:
        adapter = await self._pinned_adapter(protocol)
        return await adapter.normalize_creation_result(protocol, output)

    async def normalize_query_result(self, protocol: Any, output: Any) -> Any:
        adapter = await self._pinned_adapter(protocol)
        return await adapter.normalize_query_result(protocol, output)

    async def validate_transition(
        self, protocol: Any, operation: Any, event: Any
    ) -> str:
        adapter = await self._pinned_adapter(protocol)
        return await adapter.validate_transition(protocol, operation, event)
