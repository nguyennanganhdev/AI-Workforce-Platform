# -*- coding: utf-8 -*-
"""Provider inbox ACK only after durable inbox and job commit."""

from typing import Any

from ...contracts import (
    ProviderEventEnvelope,
    ProviderEventReceipt,
    VerifiedProviderContext,
)
from .._utils import (
    ExecutionError,
    digest,
    freeze,
    new_id,
    timestamp,
    utc_now,
    value,
)


def canonical_envelope(
    envelope: ProviderEventEnvelope | dict[str, Any],
) -> dict[str, Any]:
    """Canonical shared DTO wire form for persistence and business hashes."""
    from .._utils import instant

    try:
        wire = value(envelope)
        if not isinstance(wire, dict):
            raise ValueError
        if not isinstance(wire.get("occurred_at"), str):
            raise ValueError
        version = wire.get("provider_version")
        if version is not None and type(version) is not int:
            raise ValueError
        dto = ProviderEventEnvelope.model_validate(envelope)
        # Shared datetime currently permits naive values; execution cannot
        # order such provider facts safely.
        instant(dto.occurred_at.isoformat())
        return dto.model_dump(mode="json", exclude_none=True)
    except (ValueError, ExecutionError):
        raise ExecutionError("PROVIDER_EVENT_INVALID", 422) from None


def receipt_projection(
    record: dict[str, Any], duplicate: bool = False
) -> dict[str, Any]:
    """Expose the shared receipt, with no internal quarantine/auth details."""
    status = record["ingestion_status"]
    # A stale fact that was deliberately ignored was not applied. The shared
    # public enum calls that outcome rejected; keep the internal reason/state.
    if status == "ignored":
        status = "rejected"
    return ProviderEventReceipt(
        receipt_id=record["id"],
        ingestion_status=status,
        duplicate=duplicate,
        received_at=record["received_at"],
    ).model_dump(mode="json")


class ProviderEventIngress:
    """
    Auth and protocol validation are injected; no LLM participates in routing.
    """

    def __init__(
        self,
        repository: Any,
        auth: Any,
        protocols: Any,
        jobs: Any,
        operations: Any,
        clock: Any = utc_now,
        *,
        metrics: Any = None,
        assets: Any = None,
    ) -> None:
        self.repo, self.auth, self.protocols = repository, auth, protocols
        self.jobs, self.operations, self.clock = jobs, operations, clock
        if metrics is None:
            from ...foundation.event_delivery import NullMetricSink

            metrics = NullMetricSink()
        self.metrics = metrics
        self.assets = assets

    async def accept(
        self,
        verified_principal: Any,
        envelope: ProviderEventEnvelope | dict[str, Any],
        payload_hash: str | None = None,
    ) -> Any:
        """
        Verified principal must be obtained from ProviderAuthPort, never the
        body.
        """
        principal = value(verified_principal)
        if principal.get("purpose") != "provider_events":
            raise ExecutionError("PROVIDER_AUTH_REQUIRED", 403)
        envelope = canonical_envelope(envelope)
        await self.auth.authorize_integration(principal, "publish_job_event")
        await self.protocols.validate_envelope(principal, envelope)
        source_hash = digest(envelope)
        if payload_hash is not None and source_hash != payload_hash:
            raise ExecutionError("PAYLOAD_HASH_MISMATCH", 422)
        namespace = {
            "tenant_id": principal["tenant_id"],
            "provider_integration_id": principal["provider_integration_id"],
            "external_event_id": envelope["external_event_id"],
        }
        record = {
            "id": new_id(),
            **namespace,
            "revision": 1,
            "payload_hash": source_hash,
            "envelope": envelope,
            # Preserve the full server-only VerifiedProviderContext for
            # credential revalidation after restart. It contains identifiers
            # and authentication time, never API keys or signing secrets.
            "provider_ref": freeze(
                {
                    k: v
                    for k, v in principal.items()
                    if k in VerifiedProviderContext.model_fields
                }
            ),
            "received_at": timestamp(self.clock()),
            "ingestion_status": "accepted",
            "error": None,
        }
        async with self.repo.transaction() as uow:
            await self.auth.authorize_integration(
                principal, "publish_job_event", uow=uow
            )
            if self.assets is not None:
                await self.assets.validate_provider_event_assets(
                    verified_principal, envelope, uow
                )
            stored = await self.repo.insert_once("inbox", record, namespace, uow)
            # Accept pre-Phase-A rows only when their normalized business
            # envelope is identical. Never overwrite the original audit hash.
            if (
                stored["payload_hash"] != source_hash
                and digest(canonical_envelope(stored["envelope"])) != source_hash
            ):
                raise ExecutionError("EVENT_ID_CONFLICT")
            duplicate = stored["id"] != record["id"]
            if not duplicate:
                # Jobs resolve the provider namespace internally before scope
                # is
                # available. This narrow JobPort extension requires Foundation.
                await self.jobs.enqueue_provider(
                    principal,
                    "provider_event",
                    {"receipt_id": stored["id"]},
                    stored["id"],
                    uow=uow,
                )
        from ...foundation.event_delivery import PROVIDER_EVENTS

        self.metrics.increment(
            PROVIDER_EVENTS,
            labels={"outcome": "duplicate" if duplicate else "accepted"},
        )
        return receipt_projection(stored, duplicate)

    async def read_receipt(self, principal: Any, receipt_id: Any) -> Any:
        """
        Receipt projection contains no workflow, owner, actor or raw payload.
        """
        principal = value(principal)
        await self.auth.authorize_integration(principal, "read_event_receipt")
        async with self.repo.transaction() as uow:
            rows = await self.repo.find(
                "inbox",
                {
                    "id": receipt_id,
                    "tenant_id": principal["tenant_id"],
                    "provider_integration_id": principal["provider_integration_id"],
                },
                uow,
            )
            if not rows:
                raise ExecutionError("RESOURCE_NOT_FOUND", 404)
            row = rows[0]
            return receipt_projection(row)
