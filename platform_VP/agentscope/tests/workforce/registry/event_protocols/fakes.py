# -*- coding: utf-8 -*-
"""Phase-A fake only: no network, persistence, credential lookup or auth."""

from collections.abc import Sequence
from datetime import datetime
import hashlib
import json

from jsonschema import Draft202012Validator
from referencing import Registry

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
        if envelope.schema_version != protocol.event_schema_version:
            raise ValueError("event schema version mismatch")
        if protocol.ordering == "provider_version" and (
            envelope.provider_version is None
        ):
            raise ValueError("provider_version is required")
        mapping = protocol.event_mappings[envelope.event_type]
        Draft202012Validator(
            mapping.data_schema,
            registry=Registry(),
        ).validate(envelope.data)
        source = json.dumps(
            envelope.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return NormalizedJobEvent(
            inbox_event_id=self.inbox_event_id,
            provider_integration_id=self.provider_integration_id,
            external_event_id=envelope.external_event_id,
            external_job_id=envelope.external_job_id,
            client_reference=envelope.client_reference,
            normalized_status=mapping.status,
            facts={
                k: envelope.data[k]
                for k in mapping.fact_fields
                if k in envelope.data
            },
            provider_version=envelope.provider_version,
            protocol_schema_hash=protocol_snapshot.schema_hash,
            source_hash=hashlib.sha256(source.encode()).hexdigest(),
            occurred_at=envelope.occurred_at,
            received_at=self.received_at,
        )
