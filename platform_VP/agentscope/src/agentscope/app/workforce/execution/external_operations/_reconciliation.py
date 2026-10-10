# -*- coding: utf-8 -*-
"""Durable timer handler for status-query; never keep an agent polling."""

from typing import Any

from .._utils import ExecutionError, digest


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
        return await self.jobs.enqueue(
            scope,
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
        async with self.repo.transaction() as uow:
            current = await self.repo.get(
                "operations", operation_id, uow, scope, lock=True
            )
            if current["revision"] != op["revision"]:
                return "stale_query"
            source_hash = digest(
                {"status": event["status"], "facts": event["facts"]}
            )
            if current["last_source_hash"] == source_hash:
                return "unchanged"
            incoming_version = event.get("provider_version")
            current_version = current["last_provider_version"]
            if incoming_version is not None and current_version is not None:
                if incoming_version < current_version:
                    return "stale_query"
                if incoming_version == current_version:
                    return "needs_attention"
            transition = await self.protocols.validate_transition(
                current["protocol"], current, event
            )
            if transition != "apply":
                return "needs_attention"
            current.update(
                creation_status="succeeded",
                external_job_id=result.get("external_job_id")
                or current["external_job_id"],
                job_status=event["status"],
                pending=not event["terminal"],
                last_source_hash=source_hash,
                last_provider_version=event.get("provider_version"),
            )
            current = await self.repo.save(
                "operations", current, current["revision"], uow
            )
            event = {**event, "timer_id": timer_id, "inbox_event_id": timer_id}
            await self.workflow.apply_external_event(
                scope, current, event, uow=uow
            )
        return "applied"

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
