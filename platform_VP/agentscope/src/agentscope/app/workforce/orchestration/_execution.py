"""Read-only bridge from Execution's persisted operation to Orchestration."""

from __future__ import annotations

from typing import Any

from ..contracts import ExternalOperation, Scope
from ..execution._utils import ExecutionError
from ..execution.external_operations._protocol import protocol_hash


class ExecutionOperationReader:
    """OperationReader using the caller's canonical SQL UOW when supplied."""

    def __init__(self, repository: Any) -> None:
        self._repository = repository

    @staticmethod
    def _project(record: dict[str, Any]) -> ExternalOperation:
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
                external_job_id=record.get("external_job_id"),
                creation_status=record["creation_status"],
                job_status=record.get("job_status"),
                last_provider_version=record.get("last_provider_version"),
                revision=record["revision"],
            )
        except (KeyError, TypeError, ValueError):
            raise ExecutionError(
                "OPERATION_PROJECTION_UNAVAILABLE", 409
            ) from None

    async def get(self, scope, operation_id, uow=None):
        scope = Scope.model_validate(scope)
        if uow is None:
            async with self._repository.transaction() as owned:
                record = await self._repository.get(
                    "operations", operation_id, owned, scope
                )
        else:
            record = await self._repository.get(
                "operations", operation_id, uow, scope
            )
        if record is None:
            raise KeyError("external operation not found in owner scope")
        return self._project(record)

    async def is_pending(self, operation, uow=None):
        operation = ExternalOperation.model_validate(operation)
        if uow is None:
            async with self._repository.transaction() as owned:
                record = await self._repository.get(
                    "operations",
                    operation.operation_id,
                    owned,
                    operation.scope,
                )
        else:
            record = await self._repository.get(
                "operations",
                operation.operation_id,
                uow,
                operation.scope,
            )
        if record is None or self._project(record) != operation:
            raise PermissionError("operation fact changed during workflow turn")
        return bool(record.get("pending"))


__all__ = ["ExecutionOperationReader"]
