# -*- coding: utf-8 -*-
"""
Atomic normalized fact + inbox outcome + WorkflowPort trigger application.
"""

from typing import Any

from .._utils import ExecutionError, digest, value


class ProviderEventProcessor:
    """Job leases live in Foundation; row locks/CAS protect operation facts."""

    def __init__(self, ingress: Any, workflow: Any, *, metrics: Any = None) -> None:
        self.ingress, self.workflow = ingress, workflow
        self.repo, self.operations = ingress.repo, ingress.operations
        if metrics is None:
            metrics = getattr(ingress, "metrics", None)
        if metrics is None:
            from ...foundation.event_delivery import NullMetricSink

            metrics = NullMetricSink()
        self.metrics = metrics

    def _record(self, status: str) -> str:
        from ...foundation.event_delivery import PROVIDER_EVENTS

        self.metrics.increment(PROVIDER_EVENTS, labels={"outcome": status})
        return status

    async def _outcome(
        self, row: Any, status: Any, error: Any, uow: Any
    ) -> Any:
        row.update(ingestion_status=status, error=error)
        return await self.repo.save("inbox", row, row["revision"], uow)

    async def handle_job(self, job: Any) -> dict[str, Any]:
        """Foundation JobHandler; check namespace against the stored inbox."""
        from ...foundation.event_delivery import DurableJob

        job = DurableJob.model_validate(value(job))
        receipt_id = job.payload.get("receipt_id")
        if (
            job.owner_kind != "provider"
            or job.job_type != "provider_event"
            or not isinstance(receipt_id, str)
            or not receipt_id
        ):
            raise ExecutionError("PROVIDER_JOB_INVALID", 422)
        status = await self.process(
            receipt_id,
            provider_namespace={
                "tenant_id": job.tenant_id,
                "provider_integration_id": job.provider_integration_id,
            },
        )
        return {"receipt_id": receipt_id, "ingestion_status": status}

    async def process(
        self, receipt_id: Any, *, provider_namespace: Any = None
    ) -> Any:
        """Retriable DB failures roll back every module in the shared UOW."""
        async with self.repo.transaction() as uow:
            row = await self.repo.get("inbox", receipt_id, uow, lock=True)
            if row is None:
                raise ExecutionError("RESOURCE_NOT_FOUND", 404)
            if provider_namespace is not None and any(
                row[key] != expected
                for key, expected in provider_namespace.items()
            ):
                raise ExecutionError("RESOURCE_NOT_FOUND", 404)
            principal, envelope = row["provider_ref"], row["envelope"]
            await self.ingress.auth.authorize_integration(
                principal, "process_job_event", uow=uow
            )
            if row["ingestion_status"] in {"applied", "ignored"}:
                return self._record(row["ingestion_status"])
            try:
                op = await self.operations.resolve(principal, envelope, uow)
                if op is None:
                    await self._outcome(
                        row, "quarantined", "OPERATION_NOT_BOUND", uow
                    )
                    return self._record("quarantined")
                if not op["protocol"].get("provider_events"):
                    raise ExecutionError("PROVIDER_EVENTS_NOT_SUPPORTED", 403)
                event = await self.ingress.protocols.normalize_verified_event(
                    principal,
                    op["protocol"],
                    envelope,
                    inbox_event_id=row["id"],
                    received_at=row["received_at"],
                    uow=uow,
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
                        return self._record("ignored")
                    if version == last:
                        if content_hash != op["last_source_hash"]:
                            raise ExecutionError("PROVIDER_VERSION_CONFLICT")
                        await self._outcome(row, "ignored", None, uow)
                        return self._record("ignored")
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
                    return self._record("ignored")
                if transition != "apply":
                    raise ExecutionError("PROVIDER_TRANSITION_CONFLICT")
            except ExecutionError as error:
                await self._outcome(row, "quarantined", error.code, uow)
                return self._record("quarantined")
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
        return self._record("applied")
