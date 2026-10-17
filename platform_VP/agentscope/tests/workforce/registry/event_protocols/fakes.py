# -*- coding: utf-8 -*-
"""Test-only protocol/storage doubles; no network or real auth/credentials."""

from collections.abc import Sequence
from datetime import datetime

from agentscope.app.workforce.contracts import (
    ActorContext,
    ActorKind,
    AsyncProtocolSnapshotRef,
    CredentialPurpose,
    NormalizedJobEvent,
    ProviderEventEnvelope,
    Scope,
    WorkforceContractError,
    WorkforceErrorCode,
)
from agentscope.app.workforce.registry.event_protocols import AsyncToolProtocol
from agentscope.app.workforce.registry.event_protocols._normalizer import (
    normalize_event,
)


class FakeAsyncProtocolPort:
    """Seed scoped snapshots and one verified inbox context explicitly."""

    def __init__(
        self,
        scope: Scope,
        protocols: Sequence[AsyncToolProtocol],
        provider_context: ActorContext,
        provider_integration_id: str,
        inbox_event_id: str,
        received_at: datetime,
    ) -> None:
        self.scope = scope
        self.provider_context = provider_context
        self.provider_integration_id = provider_integration_id
        self.inbox_event_id = inbox_event_id
        self.received_at = received_at
        # Serialize so caller mutation cannot rewrite a pinned fake snapshot.
        self.protocols = {
            p.snapshot_ref.schema_hash: p.model_dump_json() for p in protocols
        }
        self.current = {p.tool_version_id: p.snapshot_ref for p in protocols}

    def _resolve(self, ref: AsyncProtocolSnapshotRef) -> AsyncToolProtocol:
        protocol = AsyncToolProtocol.model_validate_json(
            self.protocols[ref.schema_hash],
        )
        if protocol.snapshot_ref != ref:
            raise ValueError("protocol snapshot mismatch")
        return protocol

    async def get_snapshot(
        self,
        scope: Scope,
        tool_version_id: str,
    ) -> AsyncProtocolSnapshotRef:
        if scope != self.scope:
            raise PermissionError("scope mismatch")
        return self.current[tool_version_id]

    async def validate_capability_coverage(
        self,
        protocol_snapshot: AsyncProtocolSnapshotRef,
        required_capabilities: Sequence[str],
    ) -> None:
        self._resolve(protocol_snapshot)
        missing = set(required_capabilities) - set(
            protocol_snapshot.capabilities,
        )
        if missing:
            raise WorkforceContractError(
                WorkforceErrorCode.MISSING_REQUIRED_CAPABILITY,
                "Missing capabilities: " + ", ".join(sorted(missing)),
            )

    async def normalize_verified_event(
        self,
        provider_context: ActorContext,
        protocol_snapshot: AsyncProtocolSnapshotRef,
        envelope: ProviderEventEnvelope,
    ) -> NormalizedJobEvent:
        protocol = self._resolve(protocol_snapshot)
        if (
            provider_context != self.provider_context
            or provider_context.kind != ActorKind.PARTNER
            or provider_context.credential_purpose
            != CredentialPurpose.PROVIDER_EVENTS
            or protocol.provider_integration_id != self.provider_integration_id
        ):
            raise PermissionError("provider namespace mismatch")
        return normalize_event(
            protocol,
            envelope,
            inbox_event_id=self.inbox_event_id,
            provider_integration_id=self.provider_integration_id,
            received_at=self.received_at,
        )


class FakeAsyncProtocolRepository:
    """Test-only atomic repository; serialized content cannot be mutated."""

    def __init__(self) -> None:
        self.snapshots = {}
        self.current = {}
        self.uows = []

    @staticmethod
    def _scope(scope):
        return tuple(scope.model_dump().values())

    def _key(self, scope, ref):
        return (
            self._scope(scope),
            ref.tool_version_id,
            ref.protocol_id,
            ref.protocol_version,
        )

    async def publish(self, scope, protocol, expected_snapshot, uow=None):
        ref = protocol.snapshot_ref
        key = self._key(scope, ref)
        previous = self.snapshots.get(key)
        if previous is not None and (
            AsyncToolProtocol.model_validate_json(previous).snapshot_ref != ref
        ):
            raise WorkforceContractError(
                WorkforceErrorCode.IDEMPOTENCY_CONFLICT,
                "protocol version already has different content",
            )
        current_key = (self._scope(scope), protocol.tool_version_id)
        current, enabled = self.current.get(current_key, (None, True))
        if current == ref:
            return
        if current != expected_snapshot:
            raise WorkforceContractError(
                WorkforceErrorCode.REVISION_CONFLICT,
                "current protocol changed",
            )
        self.uows.append(uow)
        self.snapshots[key] = protocol.model_dump_json()
        self.current[current_key] = (ref, enabled)

    async def get_current(self, scope, tool_version_id):
        ref, enabled = self.current[(self._scope(scope), tool_version_id)]
        return await self.get_pinned(scope, ref), enabled

    async def get_pinned(self, scope, ref):
        return AsyncToolProtocol.model_validate_json(
            self.snapshots[self._key(scope, ref)],
        )

    async def set_enabled(
        self,
        scope,
        tool_version_id,
        enabled,
        expected_snapshot,
        uow=None,
    ):
        key = (self._scope(scope), tool_version_id)
        current, _ = self.current[key]
        if current != expected_snapshot:
            raise WorkforceContractError(
                WorkforceErrorCode.REVISION_CONFLICT,
                "current protocol changed",
            )
        self.uows.append(uow)
        self.current[key] = (current, enabled)
