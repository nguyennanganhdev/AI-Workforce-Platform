# -*- coding: utf-8 -*-
"""External operation intent and immutable provider/workflow correlation."""

from typing import Any

from .._utils import (
    ExecutionError,
    digest,
    freeze,
    new_id,
    owner,
    timestamp,
    utc_now,
)


class ExternalOperationService:
    """Creation success is independent of eventual job completion."""

    def __init__(self, repository: Any, clock: Any = utc_now) -> None:
        self.repo, self.clock = repository, clock

    async def prepare(
        self, scope: Any, run_context: Any, call: Any, protocol: Any, uow: Any
    ) -> Any:
        """
        Persist protocol pin and server correlation before any provider call.
        """
        protocol = freeze(protocol)
        if (
            protocol.get("capability") != "external_tracking"
            or not (
                protocol.get("provider_events") or protocol.get("status_query")
            )
            or not run_context.get("workflow_id")
        ):
            raise ExecutionError("TRACKING_PROTOCOL_REQUIRED", 422)
        record = {
            "id": new_id(),
            "scope": owner(scope),
            "revision": 1,
            "operation_id": None,
            "call_id": call["call_id"],
            "workflow_id": run_context["workflow_id"],
            "conversation_id": run_context["conversation_id"],
            "group_id": run_context.get("group_id"),
            "ticket_id": run_context.get("ticket_id"),
            "audience_ref": freeze(run_context.get("partner_audience")),
            "provider_integration_id": protocol["provider_integration_id"],
            "protocol": protocol,
            "protocol_hash": digest(protocol),
            "correlation_id": new_id(),
            "external_job_id": None,
            "creation_status": "intent",
            "job_status": None,
            "pending": True,
            "last_provider_version": None,
            "last_source_hash": None,
            "created_at": timestamp(self.clock()),
        }
        record["operation_id"] = record["id"]
        stored = await self.repo.insert_once(
            "operations", record, {"call_id": call["call_id"]}, uow, scope
        )
        if (
            stored["protocol_hash"] != record["protocol_hash"]
            or stored["workflow_id"] != record["workflow_id"]
        ):
            raise ExecutionError("OPERATION_PIN_CONFLICT")
        return stored

    def create_arguments(self, operation: Any, arguments: Any) -> Any:
        """
        Only declared protocol fields receive correlation/idempotency values.
        """
        arguments = freeze(arguments)
        for kind, field in (
            operation["protocol"].get("create_fields", {}).items()
        ):
            if kind not in {"client_reference", "idempotency_key"}:
                raise ExecutionError("PROTOCOL_FIELD_INVALID", 422)
            if field in arguments:
                raise ExecutionError("CORRELATION_FIELD_SERVER_OWNED", 422)
            arguments[field] = operation["correlation_id"]
        return arguments

    async def bind_result(
        self, scope: Any, operation_id: Any, result: Any, uow: Any
    ) -> Any:
        """
        Bind normalized creation output without overwriting an early event.
        """
        operation = await self.repo.get(
            "operations", operation_id, uow, scope, lock=True
        )
        if not operation:
            raise ExecutionError("RESOURCE_NOT_FOUND", 404)
        incoming_id = result.get("external_job_id")
        existing_id = operation["external_job_id"]
        if existing_id and incoming_id and incoming_id != existing_id:
            raise ExecutionError("CORRELATION_CONFLICT")
        if incoming_id:
            conflicts = await self.repo.find(
                "operations",
                {
                    "tenant_id": owner(scope)["tenant_id"],
                    "provider_integration_id": operation[
                        "provider_integration_id"
                    ],
                    "external_job_id": incoming_id,
                },
                uow,
            )
            if conflicts and conflicts[0]["id"] != operation_id:
                raise ExecutionError("CORRELATION_CONFLICT")
            operation["external_job_id"] = incoming_id
        if (
            operation["last_source_hash"] is not None
            and result["creation_status"] == "failed"
        ):
            raise ExecutionError("CREATION_FACT_CONFLICT")
        operation["creation_status"] = result["creation_status"]
        if operation["last_source_hash"] is None:
            operation["job_status"] = result.get("job_status")
            operation["pending"] = result.get("pending", True)
        elif operation["creation_status"] == "unknown":
            operation["creation_status"] = "succeeded"
        return await self.repo.save(
            "operations", operation, operation["revision"], uow
        )

    async def get_for_workflow(self, scope: Any, workflow_id: Any) -> Any:
        """
        Owner-filtered reads; audience authorization remains with the caller.
        """
        async with self.repo.transaction() as uow:
            return await self.repo.find(
                "operations", {"workflow_id": workflow_id}, uow, scope
            )

    async def resolve(self, principal: Any, envelope: Any, uow: Any) -> Any:
        """
        The only unscoped lookup is restricted to the verified integration.
        """
        namespace = {
            "tenant_id": principal["tenant_id"],
            "provider_integration_id": principal["provider_integration_id"],
        }
        found = []
        for key, field in (
            ("external_job_id", "external_job_id"),
            ("client_reference", "correlation_id"),
        ):
            if envelope.get(key):
                rows = await self.repo.find(
                    "operations", {**namespace, field: envelope[key]}, uow
                )
                found.append(rows[0] if rows else None)
        resolved = [r for r in found if r]
        if not resolved:
            return None
        if len({r["id"] for r in resolved}) != 1:
            raise ExecutionError("CORRELATION_CONFLICT")
        operation = await self.repo.get(
            "operations",
            resolved[0]["id"],
            uow,
            resolved[0]["scope"],
            lock=True,
        )
        # A previously unbound job may arrive early with the known correlation.
        if (
            envelope.get("client_reference")
            and envelope["client_reference"] != operation["correlation_id"]
        ):
            raise ExecutionError("CORRELATION_CONFLICT")
        incoming = envelope.get("external_job_id")
        if incoming and operation["external_job_id"] not in {None, incoming}:
            raise ExecutionError("CORRELATION_CONFLICT")
        return operation
