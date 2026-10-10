# -*- coding: utf-8 -*-
"""Scoped AsyncProtocolPort implementation with injected persistence/auth."""

from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime

from pydantic import AwareDatetime, TypeAdapter

from ...contracts import (
    ActorContext,
    ActorKind,
    AsyncProtocolSnapshotRef,
    CredentialPurpose,
    NormalizedJobEvent,
    OpaqueId,
    ProviderEventEnvelope,
    Scope,
    UnitOfWork,
    WorkforceContractError,
    WorkforceErrorCode,
)
from ._models import AsyncToolProtocol
from ._normalizer import normalize_event
from ._repository import AsyncProtocolRepository


# shortcut: use an injected inbox reader until the shared context DTO lands.
EventContextLoader = Callable[
    [ActorContext, ProviderEventEnvelope],
    Awaitable[tuple[str, str, str, datetime]],
]
_metadata = TypeAdapter(tuple[OpaqueId, OpaqueId, OpaqueId, AwareDatetime])


class AsyncProtocolService:
    """Bind one server-resolved operation/manager scope, never a body scope.

    load_event_context must authorize the actor for this scope/integration,
    verify the exact envelope against persisted inbox content, then return
    (tenant_id, provider_integration_id, inbox_event_id, received_at).
    It is called per event/retry; no metadata is cached or fabricated here.
    """

    def __init__(
        self,
        repository: AsyncProtocolRepository,
        scope: Scope,
        load_event_context: EventContextLoader,
    ) -> None:
        self._repository = repository
        self._scope = scope
        self._load_event_context = load_event_context

    async def publish(
        self,
        protocol: AsyncToolProtocol,
        expected_snapshot: AsyncProtocolSnapshotRef | None = None,
        uow: UnitOfWork | None = None,
    ) -> AsyncProtocolSnapshotRef:
        protocol = AsyncToolProtocol.model_validate_json(
            protocol.model_dump_json(),
        )
        await self._repository.publish(
            self._scope,
            protocol,
            expected_snapshot,
            uow,
        )
        return protocol.snapshot_ref

    async def set_enabled(
        self,
        tool_version_id: str,
        enabled: bool,
        expected_snapshot: AsyncProtocolSnapshotRef,
        uow: UnitOfWork | None = None,
    ) -> None:
        await self._repository.set_enabled(
            self._scope,
            tool_version_id,
            enabled,
            expected_snapshot,
            uow,
        )

    async def get_snapshot(
        self,
        scope: Scope,
        tool_version_id: str,
    ) -> AsyncProtocolSnapshotRef:
        if scope != self._scope:
            raise PermissionError("scope mismatch")
        protocol, enabled = await self._repository.get_current(
            scope,
            tool_version_id,
        )
        if not enabled:
            raise PermissionError("protocol disabled for new calls")
        return protocol.snapshot_ref

    async def get_detailed_snapshot(
        self,
        protocol_snapshot: AsyncProtocolSnapshotRef,
    ) -> AsyncToolProtocol:
        """Resolve the exact scoped pin even after disable or catalog drift."""
        protocol = await self._repository.get_pinned(
            self._scope,
            protocol_snapshot,
        )
        protocol = AsyncToolProtocol.model_validate_json(
            protocol.model_dump_json(),
        )
        if protocol.snapshot_ref != protocol_snapshot:
            raise ValueError("protocol snapshot mismatch")
        return protocol

    async def validate_capability_coverage(
        self,
        protocol_snapshot: AsyncProtocolSnapshotRef,
        required_capabilities: Sequence[str],
    ) -> None:
        protocol = await self.get_detailed_snapshot(protocol_snapshot)
        missing = set(required_capabilities) - set(
            protocol.snapshot_ref.capabilities,
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
        if (
            provider_context.kind != ActorKind.PARTNER
            or provider_context.credential_purpose
            != CredentialPurpose.PROVIDER_EVENTS
        ):
            raise PermissionError("provider_events credential required")
        (
            tenant_id,
            integration_id,
            inbox_id,
            received_at,
        ) = _metadata.validate_python(
            await self._load_event_context(provider_context, envelope),
            strict=True,
        )
        if tenant_id != self._scope.tenant_id:
            raise PermissionError("provider tenant mismatch")
        protocol = await self.get_detailed_snapshot(protocol_snapshot)
        return normalize_event(
            protocol,
            envelope,
            provider_integration_id=integration_id,
            inbox_event_id=inbox_id,
            received_at=received_at,
        )
