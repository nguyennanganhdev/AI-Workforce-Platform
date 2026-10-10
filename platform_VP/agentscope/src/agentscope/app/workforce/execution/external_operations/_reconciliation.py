# -*- coding: utf-8 -*-
"""Durable timer handler for status-query; never keep an agent polling."""

from typing import Any

from ...contracts import Scope
from .._utils import ExecutionError, digest, instant, timestamp, utc_now
from ._protocol import protocol_hash


class OperationReconciler:
    """
    Query adapter enforces scoped credentials and read-only tool bindings.
    """

    def __init__(
        self,
        repository: Any,
        queries: Any,
        protocols: Any,
        workflow: Any,
        jobs: Any,
    ) -> None:
        self.repo, self.queries, self.protocols = (
            repository,
            queries,
            protocols,
        )
        self.workflow, self.jobs = workflow, jobs

    async def schedule(
        self,
        scope: Any,
        operation_id: Any,
        timer_id: Any,
        not_before: Any,
        uow: Any,
    ) -> Any:
        """
        Only schedule a declared query for a pending or unknown operation.
        """
        op = await self.repo.get("operations", operation_id, uow, scope)
        if not op or (
            not op["pending"] and op["creation_status"] != "unknown"
        ):
            return None
        if not op["protocol"].get("status_query"):
            raise ExecutionError("STATUS_QUERY_UNAVAILABLE")
        if isinstance(not_before, str):
            not_before = instant(not_before)
        timestamp(not_before)
        return await self.jobs.enqueue(
            Scope.model_validate(scope),
            "operation_reconcile",
            {
                "operation_id": operation_id,
                "timer_id": timer_id,
            },
            timer_id,
            not_before=not_before,
            uow=uow,
        )

    async def reconcile(
        self, scope: Any, operation_id: Any, timer_id: Any
    ) -> Any:
        """
        No transaction during MCP query; CAS rejects a stale query response.
        """
        op = await self.repo.read("operations", scope, operation_id)
        if not op["pending"] and op["creation_status"] != "unknown":
            return "terminal"
        if not op["protocol"].get("status_query"):
            raise ExecutionError("STATUS_QUERY_UNAVAILABLE")
        result = await self.queries.query(scope, op, timer_id)
        event = await self.protocols.normalize_query_result(
            op["protocol"], result
        )
        observed_at = timestamp(utc_now())
        async with self.repo.transaction() as uow:
            current = await self.repo.get(
                "operations", operation_id, uow, scope, lock=True
            )
            if current["revision"] != op["revision"]:
                return "stale_query"
            incoming_job = result.get("external_job_id")
            if "configuration" in current["protocol"]:
                field = current["protocol"]["configuration"].get(
                    "external_job_id_field"
                )
                incoming_job = result.get(field)
            if incoming_job:
                await self._check_job_binding(
                    scope, current, incoming_job, uow
                )
            source_hash = digest(
                {"status": event["status"], "facts": event["facts"]}
            )
            incoming_version = event.get("provider_version")
            current_version = current["last_provider_version"]
            if incoming_version is not None and current_version is not None:
                if incoming_version < current_version:
                    return "stale_query"
                if (
                    incoming_version == current_version
                    and current["last_source_hash"] != source_hash
                ):
                    return "needs_attention"
            if current["last_source_hash"] == source_hash:
                # Equal business facts can still acknowledge a newer provider
                # version or finish binding a job. Persist that progress so
                # the next delta does not appear to have a missing version.
                advance = incoming_version is not None and (
                    current_version is None
                    or incoming_version > current_version
                )
                bind = incoming_job and current["external_job_id"] is None
                if advance or bind:
                    if advance:
                        current["last_provider_version"] = incoming_version
                    if bind:
                        current["external_job_id"] = incoming_job
                    await self.repo.save(
                        "operations", current, current["revision"], uow
                    )
                return "unchanged"
            transition = await self.protocols.validate_transition(
                current["protocol"], current, event
            )
            if transition != "apply":
                return "needs_attention"
            current.update(
                creation_status="succeeded",
                external_job_id=incoming_job or current["external_job_id"],
                job_status=event["status"],
                pending=not event["terminal"],
                last_source_hash=source_hash,
                last_provider_version=event.get("provider_version"),
            )
            current = await self.repo.save(
                "operations", current, current["revision"], uow
            )
            event = {
                **event,
                "timer_id": timer_id,
                "observed_at": observed_at,
                "source_hash": event.get("source_hash", digest(result)),
                "protocol_schema_hash": protocol_hash(current["protocol"]),
            }
            await self.workflow.apply_external_event(
                scope, current, event, uow=uow
            )
        return "applied"

    async def _check_job_binding(
        self, scope: Any, operation: Any, incoming_job: str, uow: Any
    ) -> None:
        """Check the provider namespace as in create-result binding."""
        if operation["external_job_id"] not in {None, incoming_job}:
            raise ExecutionError("CORRELATION_CONFLICT")
        matches = await self.repo.find(
            "operations",
            {
                "tenant_id": Scope.model_validate(scope).tenant_id,
                "provider_integration_id": operation[
                    "provider_integration_id"
                ],
                "external_job_id": incoming_job,
            },
            uow,
        )
        if matches and matches[0]["id"] != operation["id"]:
            raise ExecutionError("CORRELATION_CONFLICT")

    async def escalate(
        self, scope: Any, operation_id: Any, cause_id: Any, reason: Any
    ) -> Any:
        """
        Persist exhausted-query/long-wait attention without inventing
        completion.
        """
        async with self.repo.transaction() as uow:
            op = await self.repo.get(
                "operations", operation_id, uow, scope, lock=True
            )
            if not op:
                raise ExecutionError("RESOURCE_NOT_FOUND", 404)
            if not op["pending"] and op["creation_status"] != "unknown":
                return "terminal"
            if op.get("attention_cause_id") == cause_id:
                return "needs_attention"
            op.update(attention_cause_id=cause_id, reconciliation_error=reason)
            op = await self.repo.save("operations", op, op["revision"], uow)
            await self.workflow.mark_operation_attention(
                scope, op, cause_id, reason, uow=uow
            )
        return "needs_attention"
