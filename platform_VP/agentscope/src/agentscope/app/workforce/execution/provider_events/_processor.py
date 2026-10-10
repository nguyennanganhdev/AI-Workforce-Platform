# -*- coding: utf-8 -*-
"""
Atomic normalized fact + inbox outcome + WorkflowPort trigger application.
"""

from typing import Any

from .._utils import ExecutionError, digest


class ProviderEventProcessor:
    """Job leases live in Foundation; row locks/CAS protect operation facts."""

    def __init__(self, ingress: Any, workflow: Any) -> None:
        self.ingress, self.workflow = ingress, workflow
        self.repo, self.operations = ingress.repo, ingress.operations

    async def _outcome(
        self, row: Any, status: Any, error: Any, uow: Any
    ) -> Any:
        row.update(ingestion_status=status, error=error)
        return await self.repo.save("inbox", row, row["revision"], uow)

    async def process(self, receipt_id: Any) -> Any:
        """Retriable DB failures roll back every module in the shared UOW."""
        async with self.repo.transaction() as uow:
            row = await self.repo.get("inbox", receipt_id, uow, lock=True)
            if row is None:
                raise ExecutionError("RESOURCE_NOT_FOUND", 404)
            if row["ingestion_status"] in {"applied", "ignored"}:
                return row["ingestion_status"]
            principal, envelope = row["provider_ref"], row["envelope"]
            await self.ingress.auth.authorize_integration(
                principal, "process_job_event", uow=uow
            )
            try:
                op = await self.operations.resolve(principal, envelope, uow)
                if op is None:
                    await self._outcome(
                        row, "quarantined", "OPERATION_NOT_BOUND", uow
                    )
                    return "quarantined"
                if not op["protocol"].get("provider_events"):
                    raise ExecutionError("PROVIDER_EVENTS_NOT_SUPPORTED", 403)
                event = await self.ingress.protocols.normalize_verified_event(
                    principal,
                    op["protocol"],
                    envelope,
                )
                event = dict(event)
                event.update(
                    inbox_event_id=row["id"], received_at=row["received_at"]
                )
                content_hash = digest(
                    {"status": event["status"], "facts": event["facts"]}
                )
                version, last = (
                    event.get("provider_version"),
                    op["last_provider_version"],
                )
                mode = event["order_mode"]
                if mode not in {"snapshot", "delta", "transition"}:
                    raise ExecutionError("ORDERING_POLICY_INVALID")
                if mode in {"snapshot", "delta"} and version is None:
                    raise ExecutionError("PROVIDER_VERSION_REQUIRED")
                if version is not None and last is not None:
                    if version < last:
                        await self._outcome(row, "ignored", None, uow)
                        return "ignored"
                    if version == last:
                        if content_hash != op["last_source_hash"]:
                            raise ExecutionError("PROVIDER_VERSION_CONFLICT")
                        await self._outcome(row, "ignored", None, uow)
                        return "ignored"
                expected = (
                    (last + 1)
                    if last is not None
                    else op["protocol"].get("initial_version", 1)
                )
                if mode == "delta" and version != expected:
                    raise ExecutionError("PROVIDER_VERSION_GAP")
                transition = await self.ingress.protocols.validate_transition(
                    op["protocol"], op, event
                )
                if transition == "stale":
                    await self._outcome(row, "ignored", None, uow)
                    return "ignored"
                if transition != "apply":
                    raise ExecutionError("PROVIDER_TRANSITION_CONFLICT")
            except ExecutionError as error:
                await self._outcome(row, "quarantined", error.code, uow)
                return "quarantined"
            op.update(
                external_job_id=envelope.get("external_job_id")
                or op["external_job_id"],
                creation_status="succeeded",
                job_status=event["status"],
                pending=not event["terminal"],
                last_provider_version=version,
                last_source_hash=content_hash,
            )
            op = await self.repo.save("operations", op, op["revision"], uow)
            # WorkflowPort checks immutable binding and current grant/closed
            # state, preserving pending approval and suppressing forbidden
            # sends.
            await self.workflow.apply_external_event(
                op["scope"], op, event, uow=uow
            )
            await self._outcome(row, "applied", None, uow)
        return "applied"
