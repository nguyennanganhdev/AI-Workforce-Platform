# -*- coding: utf-8 -*-
"""Translate Execution facts to the shared WorkflowPort without data loss."""

from typing import Any

from ...contracts import (
    NormalizedJobEvent,
    ProviderEventEnvelope,
    Scope,
    WorkflowRecord,
)
from ..external_operations._protocol import protocol_hash
from .._utils import (
    ExecutionError,
    audience_ref,
    digest,
    instant,
    owner,
    value,
)


class WorkflowEventAdapter:
    """Join the caller's UOW; never commit or implement Workflow routing.

    Attention/result hooks are explicit injected extensions pending shared
    promotion, not silently assumed methods of WorkflowPort.
    """

    def __init__(
        self,
        repository: Any,
        workflow_port: Any,
        attention_sink: Any = None,
        execution_result_sink: Any = None,
        query_sink: Any = None,
    ) -> None:
        self.repo, self.port = repository, workflow_port
        self.attention_sink = attention_sink
        self.execution_result_sink = execution_result_sink
        self.query_sink = query_sink

    async def apply_external_event(
        self, scope: Any, operation: Any, event: Any, uow: Any
    ) -> Any:
        scope = Scope.model_validate(scope)
        stored = await self.repo.get(
            "operations", operation["id"], uow, scope, lock=True
        )
        if stored is None or any(
            stored[key] != operation[key]
            for key in (
                "scope",
                "workflow_id",
                "conversation_id",
                "group_id",
                "audience_ref",
                "correlation_id",
                "external_job_id",
                "protocol_hash",
                "call_id",
            )
        ):
            raise ExecutionError("WORKFLOW_BINDING_MISMATCH", 403)
        if "normalized_event" in event:
            normalized = NormalizedJobEvent.model_validate(
                event["normalized_event"]
            )
            row = await self.repo.get(
                "inbox", normalized.inbox_event_id, uow, lock=True
            )
            if row is None:
                raise ExecutionError("PROVIDER_NORMALIZATION_INVALID", 422)
            envelope = ProviderEventEnvelope.model_validate(row["envelope"])
            if (
                row["tenant_id"] != scope.tenant_id
                or row["provider_integration_id"]
                != stored["provider_integration_id"]
                or normalized.external_event_id != envelope.external_event_id
                or normalized.external_job_id != envelope.external_job_id
                or normalized.client_reference != envelope.client_reference
                or normalized.received_at != instant(row["received_at"])
                or normalized.occurred_at != envelope.occurred_at
                or normalized.provider_version != envelope.provider_version
                or normalized.source_hash != digest(value(envelope))
            ):
                raise ExecutionError("PROVIDER_NORMALIZATION_INVALID", 422)
        elif "timer_id" in event:
            # Query results have a timer cause, not a provider inbox identity.
            # Keep this explicit extension until the shared contract has a
            # canonical query-result type; never fabricate provider IDs.
            if self.query_sink is None:
                raise ExecutionError("WORKFLOW_QUERY_UNAVAILABLE", 503)
            instant(event["observed_at"])
            if (
                event["protocol_schema_hash"]
                != protocol_hash(stored["protocol"])
                or not event["source_hash"]
            ):
                raise ExecutionError("WORKFLOW_BINDING_MISMATCH", 403)
            result = await self.query_sink(scope, stored["id"], event, uow=uow)
            return self._checked_result(result, scope, stored)
        else:
            raise ExecutionError("PROVIDER_NORMALIZATION_INVALID", 422)
        if (
            normalized.provider_integration_id
            != stored["provider_integration_id"]
            or normalized.protocol_schema_hash != stored["protocol_hash"]
            or normalized.normalized_status != event["status"]
            or normalized.facts != event["facts"]
            or normalized.provider_version != event.get("provider_version")
            or (
                normalized.external_job_id is not None
                and normalized.external_job_id != stored["external_job_id"]
            )
            or (
                normalized.client_reference is not None
                and normalized.client_reference != stored["correlation_id"]
            )
        ):
            raise ExecutionError("WORKFLOW_BINDING_MISMATCH", 403)
        result = await self.port.apply_external_event(
            scope, stored["id"], normalized, uow=uow
        )
        return self._checked_result(result, scope, stored)

    def _checked_result(
        self, result: Any, scope: Scope, stored: Any
    ) -> WorkflowRecord:
        result = WorkflowRecord.model_validate(value(result))
        if (
            result.scope != scope
            or result.workflow_id != stored["workflow_id"]
            or result.conversation_id != stored["conversation_id"]
            or result.group_id != stored["group_id"]
            or result.ticket_id != stored.get("ticket_id")
            or audience_ref(result.audience) != stored["audience_ref"]
        ):
            raise ExecutionError("WORKFLOW_BINDING_MISMATCH", 403)
        return result

    async def mark_operation_attention(
        self,
        scope: Any,
        operation: Any,
        cause_id: str,
        reason: str,
        uow: Any,
    ) -> Any:
        if self.attention_sink is None:
            raise ExecutionError("WORKFLOW_ATTENTION_UNAVAILABLE", 503)
        if owner(scope) != operation["scope"]:
            raise ExecutionError("WORKFLOW_BINDING_MISMATCH", 403)
        return await self.attention_sink(
            Scope.model_validate(scope), operation, cause_id, reason, uow=uow
        )

    async def apply_execution_result(
        self, scope: Any, call: Any, cause_id: str, uow: Any
    ) -> Any:
        if self.execution_result_sink is None:
            raise ExecutionError("WORKFLOW_RESULT_UNAVAILABLE", 503)
        if owner(scope) != call["scope"]:
            raise ExecutionError("WORKFLOW_BINDING_MISMATCH", 403)
        return await self.execution_result_sink(
            Scope.model_validate(scope), call, cause_id, uow=uow
        )
