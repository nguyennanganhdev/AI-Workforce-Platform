# -*- coding: utf-8 -*-
"""Truthful partial outcomes without implicit compensation or retry writes."""

from typing import Any

from ._utils import ExecutionError


class BookingReconciler:
    """
    Reconcile an unknown synchronous result without creating a provider job.
    """

    def __init__(self, repository: Any, queries: Any, workflow: Any) -> None:
        self.repo, self.queries, self.workflow = repository, queries, workflow

    async def reconcile(self, scope: Any, call_id: Any, cause_id: Any) -> Any:
        """
        Query stored provider reference; never invoke create or reuse consent.
        """
        booking = await self.repo.read("bookings", scope, call_id)
        call = await self.repo.read("calls", scope, call_id)
        if booking["status"] != "unknown":
            return booking["status"]
        if self.queries is None:
            return "needs_attention"
        result = await self.queries.query_booking(
            scope, booking, call, cause_id
        )
        if result.get("status") not in {"succeeded", "failed", "unknown"}:
            raise ExecutionError("RECONCILIATION_RESULT_INVALID", 422)
        if result.get("provider_reference") != booking["provider_reference"]:
            raise ExecutionError("CORRELATION_CONFLICT")
        if result["status"] == "unknown":
            return "needs_attention"
        async with self.repo.transaction() as uow:
            current = await self.repo.get(
                "calls", call_id, uow, scope, lock=True
            )
            stored = await self.repo.get(
                "bookings", call_id, uow, scope, lock=True
            )
            if (
                current["revision"] != call["revision"]
                or stored["revision"] != booking["revision"]
            ):
                return "stale_query"
            current.update(
                status=result["status"],
                output=result.get("output"),
                external_transaction_id=result.get("external_transaction_id"),
                error=None,
            )
            stored.update(
                status=result["status"],
                external_transaction_id=result.get("external_transaction_id"),
            )
            current = await self.repo.save(
                "calls", current, current["revision"], uow
            )
            await self.repo.save("bookings", stored, stored["revision"], uow)
            await self.workflow.apply_execution_result(
                scope, current, cause_id, uow=uow
            )
        return result["status"]


def summarize(results: Any) -> Any:
    """
    Summarize independent operations; do not pretend to roll back providers.
    """
    states = [r["status"] for r in results]
    if not states:
        raise ExecutionError("EXECUTION_RESULTS_REQUIRED", 422)
    if all(s == "succeeded" for s in states):
        status = "confirmed"
    elif "succeeded" in states:
        status = "partial"
    elif any(s in {"unknown", "executing"} for s in states):
        status = "unknown"
    else:
        status = "failed"
    return {
        "status": status,
        "calls": results,
        "requires_attention": any(s == "unknown" for s in states),
        "automatic_compensation": False,
    }
