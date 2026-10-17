# -*- coding: utf-8 -*-
"""Request-local Registry context loaded from the durable Execution inbox."""

from typing import Any

from ...contracts import (
    ActorContext,
    Scope,
    VerifiedProviderContext,
)
from .._utils import digest, instant, owner, value
from ..external_operations._protocol import protocol_hash
from ._ingress import canonical_envelope


class PersistedProviderEventContext:
    """Reauthorize stored credentials and resolve the original owner in UOW.

    A loader belongs to one normalization attempt. It never trusts metadata
    from the provider envelope and never caches identity on a shared service.
    """

    def __init__(
        self,
        repository: Any,
        auth: Any,
        operations: Any,
        context: Any,
    ) -> None:
        self.repo, self.auth, self.operations = repository, auth, operations
        self.context = context

    async def __call__(self, actor: Any, envelope: Any) -> Any:
        context = self.context
        uow = context["uow"]
        if uow is None:
            raise PermissionError("persisted event context requires UOW")
        expected = VerifiedProviderContext.model_validate(
            context["provider_context"]
        )
        scope = Scope.model_validate(context["scope"])
        rows = await self.repo.find(
            "inbox",
            {
                "id": context["inbox_event_id"],
                "tenant_id": expected.tenant_id,
                "provider_integration_id": expected.provider_integration_id,
            },
            uow,
        )
        if len(rows) != 1:
            raise PermissionError("persisted provider inbox not found")
        row = rows[0]
        verified = VerifiedProviderContext.model_validate(row["provider_ref"])
        if (
            verified != expected
            or verified.actor != ActorContext.model_validate(actor)
            or verified.actor_id != verified.actor.actor_id
            or row["id"] != context["inbox_event_id"]
            or row["tenant_id"] != verified.tenant_id
            or row["provider_integration_id"]
            != verified.provider_integration_id
            or verified.tenant_id != scope.tenant_id
            or context["provider_integration_id"]
            != verified.provider_integration_id
            or instant(row["received_at"]) != context["received_at"]
        ):
            raise PermissionError("persisted provider context mismatch")
        incoming = canonical_envelope(envelope)
        if digest(incoming) != row[
            "payload_hash"
        ] or incoming != canonical_envelope(row["envelope"]):
            raise PermissionError("persisted provider envelope mismatch")
        await self.auth.authorize_integration(
            verified, "process_job_event", uow=uow
        )
        operation = await self.operations.resolve(
            value(verified), incoming, uow
        )
        ref = context["protocol_snapshot"]
        if (
            operation is None
            or owner(operation["scope"]) != owner(scope)
            or operation["provider_integration_id"]
            != verified.provider_integration_id
            or operation["protocol_hash"] != ref.schema_hash
            or protocol_hash(operation["protocol"]) != ref.schema_hash
            or operation["protocol"]["snapshot_ref"] != value(ref)
        ):
            raise PermissionError("persisted operation scope or pin mismatch")
        return (
            verified.tenant_id,
            verified.provider_integration_id,
            row["id"],
            instant(row["received_at"]),
        )
