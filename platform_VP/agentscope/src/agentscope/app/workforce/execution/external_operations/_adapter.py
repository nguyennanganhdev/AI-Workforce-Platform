# -*- coding: utf-8 -*-
"""Canonical ExternalOperationPort projection over Execution records."""

from typing import Any

from ...contracts import ExternalOperation, PartnerAudience, Scope
from .._utils import ExecutionError, value
from ._protocol import protocol_hash


class ExternalOperationAdapter:
    """Expose shared DTOs and honor a supplied transaction without commit."""

    def __init__(self, service: Any, protocols: Any) -> None:
        self.service, self.protocols = service, protocols
        self.repo = service.repo

    def _project(self, record: Any) -> ExternalOperation:
        try:
            if protocol_hash(record["protocol"]) != record["protocol_hash"]:
                raise ValueError
            return ExternalOperation(
                operation_id=record["id"],
                scope=record["scope"],
                audience=record["audience_ref"],
                workflow_id=record["workflow_id"],
                ticket_id=record.get("ticket_id"),
                conversation_id=record["conversation_id"],
                call_id=record["call_id"],
                provider_integration_id=record["provider_integration_id"],
                protocol_snapshot=record["protocol"]["snapshot_ref"],
                correlation_id=record["correlation_id"],
                external_job_id=record["external_job_id"],
                creation_status=record["creation_status"],
                job_status=record["job_status"],
                last_provider_version=record["last_provider_version"],
                revision=record["revision"],
            )
        except (KeyError, ValueError):
            raise ExecutionError(
                "OPERATION_PROJECTION_UNAVAILABLE", 409
            ) from None

    async def prepare(
        self,
        scope: Any,
        run_context: Any,
        call: Any,
        protocol: Any,
        uow: Any = None,
    ) -> ExternalOperation:
        scope = Scope.model_validate(scope)
        context = value(run_context)
        # The shared DTO requires partner audience. Manager-only operations
        # stay internal pending an explicit shared-contract decision.
        try:
            PartnerAudience.model_validate(context.get("partner_audience"))
        except ValueError:
            raise ExecutionError("PARTNER_AUDIENCE_INVALID", 422) from None
        detailed = await self.protocols.resolve_snapshot(scope, protocol)
        if uow is None:
            async with self.repo.transaction() as transaction:
                record = await self.service.prepare(
                    scope, context, value(call), detailed, transaction
                )
                return self._project(record)
        record = await self.service.prepare(
            scope, context, value(call), detailed, uow
        )
        return self._project(record)

    async def bind_result(
        self,
        scope: Any,
        operation_id: str,
        result: Any,
        uow: Any = None,
    ) -> ExternalOperation:
        if uow is None:
            async with self.repo.transaction() as transaction:
                record = await self.service.bind_result(
                    scope, operation_id, value(result), transaction
                )
                return self._project(record)
        record = await self.service.bind_result(
            scope, operation_id, value(result), uow
        )
        return self._project(record)

    async def get_for_workflow(
        self, scope: Any, workflow_id: str
    ) -> tuple[ExternalOperation, ...]:
        return tuple(
            self._project(record)
            for record in await self.service.get_for_workflow(
                scope, workflow_id
            )
        )
