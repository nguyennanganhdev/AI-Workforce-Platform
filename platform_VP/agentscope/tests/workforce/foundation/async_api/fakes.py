# -*- coding: utf-8 -*-
"""Phase-B test doubles for Foundation-owned durable boundaries."""

from __future__ import annotations

import asyncio
from datetime import datetime
import json

from agentscope.app.workforce.contracts import (
    ActorContext,
    ConversationEvent,
    EventHistoryPage,
    Scope,
)
from agentscope.app.workforce.foundation.event_delivery import (
    DurableJob,
    JobLeaseLostError,
    JobStatus,
)


class FakeDurableJobRepository:
    """Atomic in-memory fake; production persistence belongs to Phase C."""

    def __init__(self) -> None:
        self.jobs: dict[str, DurableJob] = {}
        self._idempotency: dict[tuple[str, str], tuple[str, str]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _owner(job: DurableJob) -> str:
        if job.scope is not None:
            scope = job.scope
            return ":".join(
                (
                    "scope",
                    scope.tenant_id,
                    scope.domain_id,
                    scope.area_id,
                    scope.manager_account_id,
                ),
            )
        return ":".join(
            (
                "provider",
                job.tenant_id,
                job.provider_integration_id or "",
            ),
        )

    @staticmethod
    def _fingerprint(job: DurableJob) -> str:
        return json.dumps(
            {"job_type": job.job_type, "payload": job.payload},
            sort_keys=True,
            separators=(",", ":"),
        )

    async def enqueue_once(self, job: DurableJob, uow=None) -> DurableJob:
        del uow
        key = (self._owner(job), job.idempotency_key)
        fingerprint = self._fingerprint(job)
        async with self._lock:
            existing = self._idempotency.get(key)
            if existing is not None:
                job_id, original_fingerprint = existing
                if original_fingerprint != fingerprint:
                    raise ValueError("idempotency key reused with new payload")
                return self.jobs[job_id]
            self.jobs[job.job_id] = job.model_copy(deep=True)
            self._idempotency[key] = (job.job_id, fingerprint)
            return self.jobs[job.job_id]

    async def claim_next(
        self,
        worker_id: str,
        now: datetime,
        lease_expires_at: datetime,
    ) -> DurableJob | None:
        async with self._lock:
            eligible = [
                job
                for job in self.jobs.values()
                if job.not_before <= now
                and (
                    job.status == JobStatus.PENDING
                    or (
                        job.status == JobStatus.LEASED
                        and job.lease_expires_at is not None
                        and job.lease_expires_at <= now
                    )
                )
            ]
            if not eligible:
                return None
            job = min(eligible, key=lambda item: (item.not_before, item.created_at))
            claimed = job.model_copy(
                update={
                    "status": JobStatus.LEASED,
                    "attempt": job.attempt + 1,
                    "lease_owner": worker_id,
                    "lease_expires_at": lease_expires_at,
                    "fencing_token": job.fencing_token + 1,
                    "updated_at": now,
                },
                deep=True,
            )
            self.jobs[job.job_id] = claimed
            return claimed

    def _leased(self, job_id: str, worker_id: str, token: int) -> DurableJob:
        job = self.jobs[job_id]
        if (
            job.status != JobStatus.LEASED
            or job.lease_owner != worker_id
            or job.fencing_token != token
        ):
            raise JobLeaseLostError(f"stale fence for job {job_id}")
        return job

    async def renew_lease(
        self,
        job_id: str,
        worker_id: str,
        fencing_token: int,
        now: datetime,
        lease_expires_at: datetime,
    ) -> DurableJob:
        async with self._lock:
            job = self._leased(job_id, worker_id, fencing_token)
            if job.lease_expires_at is None or job.lease_expires_at <= now:
                raise JobLeaseLostError(f"expired lease for job {job_id}")
            updated = job.model_copy(
                update={
                    "lease_expires_at": lease_expires_at,
                    "updated_at": now,
                },
            )
            self.jobs[job_id] = updated
            return updated

    async def complete(
        self,
        job_id: str,
        worker_id: str,
        fencing_token: int,
        result: dict,
        now: datetime,
    ) -> DurableJob:
        async with self._lock:
            job = self._leased(job_id, worker_id, fencing_token)
            if job.lease_expires_at is None or job.lease_expires_at <= now:
                raise JobLeaseLostError(f"expired lease for job {job_id}")
            updated = job.model_copy(
                update={
                    "status": JobStatus.SUCCEEDED,
                    "result": result,
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "updated_at": now,
                },
                deep=True,
            )
            self.jobs[job_id] = updated
            return updated

    async def fail(
        self,
        job_id: str,
        worker_id: str,
        fencing_token: int,
        error: dict,
        now: datetime,
        retry_at: datetime,
    ) -> DurableJob:
        async with self._lock:
            job = self._leased(job_id, worker_id, fencing_token)
            terminal = job.attempt >= job.max_attempts
            updated = job.model_copy(
                update={
                    "status": JobStatus.FAILED if terminal else JobStatus.PENDING,
                    "error": error,
                    "not_before": retry_at,
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "updated_at": now,
                },
                deep=True,
            )
            self.jobs[job_id] = updated
            return updated


class FakeConversationEventPort:
    def __init__(self, events: list[ConversationEvent]) -> None:
        self.events = events

    async def list_after(
        self,
        actor: ActorContext,
        conversation_id: str,
        cursor: str | None,
        limit: int,
    ) -> EventHistoryPage:
        del actor
        matching = [
            event
            for event in self.events
            if event.conversation_id == conversation_id
        ]
        start = 0
        if cursor is not None:
            ids = [event.event_id for event in matching]
            if cursor not in ids:
                raise ValueError("EVENT_CURSOR_EXPIRED")
            start = ids.index(cursor) + 1
        page = matching[start : start + limit]
        has_more = start + len(page) < len(matching)
        return EventHistoryPage(
            items=tuple(page),
            next_cursor=page[-1].event_id if page else cursor,
            has_more=has_more,
        )

    async def append(self, scope, audience, event, uow=None):
        del scope, audience, uow
        self.events.append(event)
        return event

    async def snapshot(self, actor, conversation_id):
        del actor
        return {"conversation_id": conversation_id}

    async def subscribe(self, actor, conversation_id, cursor=None):
        del actor, conversation_id, cursor
        if False:
            yield None


class ImmediateTimeoutSignal:
    async def notify_after_commit(
        self,
        scope: Scope,
        conversation_id: str,
        committed_sequence: int,
    ) -> None:
        del scope, conversation_id, committed_sequence

    async def wait_for_signal(
        self,
        scope: Scope,
        conversation_id: str,
        timeout: float,
    ) -> int | None:
        del scope, conversation_id, timeout
        return None

    async def health(self) -> bool:
        return True
