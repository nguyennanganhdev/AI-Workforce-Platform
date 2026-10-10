# -*- coding: utf-8 -*-
"""Provider inbox ACK only after durable inbox and job commit."""

from typing import Any

from .._utils import (
    ExecutionError,
    digest,
    freeze,
    new_id,
    timestamp,
    utc_now,
    value,
)

ENVELOPE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "external_event_id",
        "event_type",
        "occurred_at",
        "data",
    ],
    "properties": {
        "schema_version": {"const": "1"},
        "external_event_id": {
            "type": "string",
            "minLength": 1,
            "maxLength": 255,
        },
        "external_job_id": {
            "type": "string",
            "minLength": 1,
            "maxLength": 255,
        },
        "client_reference": {
            "type": "string",
            "minLength": 1,
            "maxLength": 255,
        },
        "event_type": {"type": "string", "minLength": 1, "maxLength": 255},
        "provider_version": {"type": "integer", "minimum": 0},
        "occurred_at": {"type": "string", "format": "date-time"},
        "data": {"type": "object"},
    },
    "anyOf": [
        {"required": ["external_job_id"]},
        {"required": ["client_reference"]},
    ],
}


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
    ) -> None:
        self.repo, self.auth, self.protocols = repository, auth, protocols
        self.jobs, self.operations, self.clock = jobs, operations, clock

    async def accept(
        self, verified_principal: Any, envelope: Any, payload_hash: Any = None
    ) -> Any:
        """
        Verified principal must be obtained from ProviderAuthPort, never the
        body.
        """
        from jsonschema import Draft202012Validator, FormatChecker

        principal, envelope = value(verified_principal), freeze(envelope)
        if principal.get("purpose") != "provider_events":
            raise ExecutionError("PROVIDER_AUTH_REQUIRED", 403)
        if list(
            Draft202012Validator(
                ENVELOPE_SCHEMA, format_checker=FormatChecker()
            ).iter_errors(envelope)
        ):
            raise ExecutionError("PROVIDER_EVENT_INVALID", 422)
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
            # Retain identity only, never authentication material.
            "provider_ref": {
                k: principal[k]
                for k in (
                    "tenant_id",
                    "provider_integration_id",
                    "actor_id",
                    "kind",
                    "purpose",
                )
            },
            "received_at": timestamp(self.clock()),
            "ingestion_status": "accepted",
            "error": None,
        }
        async with self.repo.transaction() as uow:
            await self.auth.authorize_integration(
                principal, "publish_job_event", uow=uow
            )
            stored = await self.repo.insert_once(
                "inbox", record, namespace, uow
            )
            if stored["payload_hash"] != source_hash:
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
        return {
            "receipt_id": stored["id"],
            "ingestion_status": stored["ingestion_status"],
            "duplicate": duplicate,
        }

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
                    "provider_integration_id": principal[
                        "provider_integration_id"
                    ],
                },
                uow,
            )
            if not rows:
                raise ExecutionError("RESOURCE_NOT_FOUND", 404)
            row = rows[0]
            return {
                "receipt_id": row["id"],
                "ingestion_status": row["ingestion_status"],
                "error": row["error"],
            }
