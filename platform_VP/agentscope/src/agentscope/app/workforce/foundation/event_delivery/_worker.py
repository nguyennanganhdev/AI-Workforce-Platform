# -*- coding: utf-8 -*-
"""One-job worker runner with lease heartbeats and fenced completion."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from datetime import timedelta
from enum import StrEnum

from ...contracts import JsonObject, WorkforceModel
from ._jobs import (
    DurableJob,
    DurableJobService,
    JobClaim,
    JobLeaseLostError,
    JobStatus,
)


JobHandler = Callable[[DurableJob], Awaitable[JsonObject]]


class WorkerOutcomeStatus(StrEnum):
    IDLE = "idle"
    SUCCEEDED = "succeeded"
    RETRY_SCHEDULED = "retry_scheduled"
    FAILED = "failed"
    LEASE_LOST = "lease_lost"


class WorkerOutcome(WorkforceModel):
    status: WorkerOutcomeStatus
    job_id: str | None = None


class DurableJobWorker:
    """Claims and dispatches one job without holding a DB transaction."""

    def __init__(
        self,
        jobs: DurableJobService,
        handlers: Mapping[str, JobHandler],
        *,
        worker_id: str,
        lease: timedelta = timedelta(seconds=30),
        heartbeat_interval: float = 10.0,
    ) -> None:
        if not worker_id:
            raise ValueError("worker_id must not be empty")
        if lease.total_seconds() <= 0:
            raise ValueError("lease must be positive")
        if not 0 < heartbeat_interval < lease.total_seconds():
            raise ValueError("heartbeat_interval must be inside lease window")
        self._jobs = jobs
        self._handlers = dict(handlers)
        self._worker_id = worker_id
        self._lease = lease
        self._heartbeat_interval = heartbeat_interval

    async def run_once(self) -> WorkerOutcome:
        claim = await self._jobs.claim(self._worker_id, self._lease)
        if claim is None:
            return WorkerOutcome(status=WorkerOutcomeStatus.IDLE)

        heartbeat = asyncio.create_task(
            self._heartbeat(claim),
        )
        handler = self._handlers.get(claim.job.job_type)
        try:
            if handler is None:
                status = await self._jobs.fail_claim(
                    claim,
                    {"code": "JOB_HANDLER_NOT_FOUND"},
                )
                return WorkerOutcome(
                    status=self._failure_outcome(status),
                    job_id=claim.job.job_id,
                )
            try:
                result = await handler(claim.job)
            except Exception as error:  # handler is an isolation boundary
                status = await self._jobs.fail_claim(
                    claim,
                    {
                        "code": "JOB_HANDLER_FAILED",
                        "error_type": type(error).__name__,
                    },
                )
                return WorkerOutcome(
                    status=self._failure_outcome(status),
                    job_id=claim.job.job_id,
                )

            if heartbeat.done():
                heartbeat.result()
            await self._jobs.complete_claim(claim, result)
            return WorkerOutcome(
                status=WorkerOutcomeStatus.SUCCEEDED,
                job_id=claim.job.job_id,
            )
        except JobLeaseLostError:
            return WorkerOutcome(
                status=WorkerOutcomeStatus.LEASE_LOST,
                job_id=claim.job.job_id,
            )
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat

    @staticmethod
    def _failure_outcome(status: JobStatus) -> WorkerOutcomeStatus:
        if status == JobStatus.FAILED:
            return WorkerOutcomeStatus.FAILED
        return WorkerOutcomeStatus.RETRY_SCHEDULED

    async def _heartbeat(self, claim: JobClaim) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            await self._jobs.heartbeat_claim(claim, self._lease)
