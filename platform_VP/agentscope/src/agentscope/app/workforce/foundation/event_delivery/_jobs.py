# -*- coding: utf-8 -*-
"""Durable job orchestration with repository-owned atomic operations.

The service contains lease, fencing and retry policy. Persistence is kept
behind :class:`DurableJobRepository` so Phase C can bind PostgreSQL without
changing workers or consumers.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Callable, Protocol
from uuid import uuid4

from pydantic import Field, model_validator

from ...contracts import JsonObject, OpaqueId, Scope, UnitOfWork, WorkforceModel


class JobStatus(StrEnum):
    PENDING = "pending"
    LEASED = "leased"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobOwnerKind(StrEnum):
    SCOPE = "scope"
    PROVIDER = "provider"


class DurableJob(WorkforceModel):
    job_id: OpaqueId
    owner_kind: JobOwnerKind
    scope: Scope | None = None
    tenant_id: OpaqueId
    provider_integration_id: OpaqueId | None = None
    job_type: str = Field(min_length=1, max_length=200)
    payload: JsonObject
    idempotency_key: str = Field(min_length=1, max_length=500)
    status: JobStatus = JobStatus.PENDING
    attempt: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=5, ge=1)
    not_before: datetime
    lease_owner: str | None = Field(default=None, max_length=200)
    lease_expires_at: datetime | None = None
    fencing_token: int = Field(default=0, ge=0)
    result: JsonObject | None = None
    error: JsonObject | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_owner(self) -> "DurableJob":
        if self.owner_kind == JobOwnerKind.SCOPE:
            if self.scope is None or self.provider_integration_id is not None:
                raise ValueError("scoped job requires scope only")
            if self.tenant_id != self.scope.tenant_id:
                raise ValueError("job tenant_id must match scope")
        elif self.scope is not None or self.provider_integration_id is None:
            raise ValueError(
                "provider job requires provider integration namespace only",
            )
        return self


class JobClaim(WorkforceModel):
    job: DurableJob
    worker_id: str = Field(min_length=1, max_length=200)
    fencing_token: int = Field(ge=1)
    lease_expires_at: datetime


class DurableJobRepository(Protocol):
    """Atomic persistence operations required by the job service."""

    async def enqueue_once(
        self,
        job: DurableJob,
        uow: UnitOfWork | None = None,
    ) -> DurableJob: ...

    async def claim_next(
        self,
        worker_id: str,
        now: datetime,
        lease_expires_at: datetime,
    ) -> DurableJob | None: ...

    async def renew_lease(
        self,
        job_id: OpaqueId,
        worker_id: str,
        fencing_token: int,
        now: datetime,
        lease_expires_at: datetime,
    ) -> DurableJob: ...

    async def complete(
        self,
        job_id: OpaqueId,
        worker_id: str,
        fencing_token: int,
        result: JsonObject,
        now: datetime,
    ) -> DurableJob: ...

    async def fail(
        self,
        job_id: OpaqueId,
        worker_id: str,
        fencing_token: int,
        error: JsonObject,
        now: datetime,
        retry_at: datetime,
    ) -> DurableJob: ...


class JobNamespaceError(ValueError):
    """Raised when unverified provider namespace data reaches the queue."""


class JobLeaseLostError(RuntimeError):
    """Raised when this service no longer owns a valid job fence."""


class DurableJobService:
    """JobPort implementation independent from the Phase-C SQL adapter."""

    def __init__(
        self,
        repository: DurableJobRepository,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        id_factory: Callable[[], str] = lambda: str(uuid4()),
        max_attempts: int = 5,
        retry_base: timedelta = timedelta(seconds=5),
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if retry_base.total_seconds() < 0:
            raise ValueError("retry_base must not be negative")
        self._repository = repository
        self._clock = clock
        self._id_factory = id_factory
        self._max_attempts = max_attempts
        self._retry_base = retry_base
        self._claims: dict[str, tuple[str, int]] = {}

    async def enqueue(
        self,
        scope: Scope,
        job_type: str,
        payload: JsonObject,
        idempotency_key: str,
        uow: UnitOfWork | None = None,
        not_before: datetime | None = None,
    ) -> OpaqueId:
        job = self._new_job(
            owner_kind=JobOwnerKind.SCOPE,
            tenant_id=scope.tenant_id,
            scope=scope,
            provider_integration_id=None,
            job_type=job_type,
            payload=payload,
            idempotency_key=idempotency_key,
            not_before=not_before,
        )
        stored = await self._repository.enqueue_once(job, uow)
        return stored.job_id

    async def enqueue_provider(
        self,
        provider_context: Mapping[str, object],
        job_type: str,
        payload: JsonObject,
        idempotency_key: str,
        uow: UnitOfWork | None = None,
        not_before: datetime | None = None,
    ) -> OpaqueId:
        tenant_id = provider_context.get("tenant_id")
        integration_id = provider_context.get("provider_integration_id")
        if not isinstance(tenant_id, str) or not tenant_id:
            raise JobNamespaceError(
                "verified provider context requires tenant_id",
            )
        if not isinstance(integration_id, str) or not integration_id:
            raise JobNamespaceError(
                "verified provider context requires provider_integration_id",
            )
        job = self._new_job(
            owner_kind=JobOwnerKind.PROVIDER,
            tenant_id=tenant_id,
            scope=None,
            provider_integration_id=integration_id,
            job_type=job_type,
            payload=payload,
            idempotency_key=idempotency_key,
            not_before=not_before,
        )
        stored = await self._repository.enqueue_once(job, uow)
        return stored.job_id

    async def claim(
        self,
        worker_id: str,
        lease: timedelta,
    ) -> JobClaim | None:
        if not worker_id:
            raise ValueError("worker_id must not be empty")
        if lease.total_seconds() <= 0:
            raise ValueError("lease must be positive")
        now = self._now()
        job = await self._repository.claim_next(
            worker_id,
            now,
            now + lease,
        )
        if job is None:
            return None
        self._claims[job.job_id] = (worker_id, job.fencing_token)
        return JobClaim(
            job=job,
            worker_id=worker_id,
            fencing_token=job.fencing_token,
            lease_expires_at=job.lease_expires_at,
        )

    async def heartbeat(
        self,
        job_id: OpaqueId,
        lease: timedelta = timedelta(seconds=30),
    ) -> None:
        worker_id, token = self._claim_for(job_id)
        await self._heartbeat_with_fence(job_id, worker_id, token, lease)

    async def heartbeat_claim(
        self,
        claim: JobClaim,
        lease: timedelta = timedelta(seconds=30),
    ) -> None:
        """Renew exactly the fence returned to this worker claim."""
        await self._heartbeat_with_fence(
            claim.job.job_id,
            claim.worker_id,
            claim.fencing_token,
            lease,
        )

    async def _heartbeat_with_fence(
        self,
        job_id: OpaqueId,
        worker_id: str,
        token: int,
        lease: timedelta,
    ) -> None:
        if lease.total_seconds() <= 0:
            raise ValueError("lease must be positive")
        now = self._now()
        await self._repository.renew_lease(
            job_id,
            worker_id,
            token,
            now,
            now + lease,
        )

    async def complete(
        self,
        job_id: OpaqueId,
        result: JsonObject,
    ) -> None:
        worker_id, token = self._claim_for(job_id)
        await self._complete_with_fence(job_id, worker_id, token, result)

    async def complete_claim(
        self,
        claim: JobClaim,
        result: JsonObject,
    ) -> None:
        """Complete exactly the claimed fence, never a newer replacement."""
        await self._complete_with_fence(
            claim.job.job_id,
            claim.worker_id,
            claim.fencing_token,
            result,
        )

    async def _complete_with_fence(
        self,
        job_id: OpaqueId,
        worker_id: str,
        token: int,
        result: JsonObject,
    ) -> None:
        await self._repository.complete(
            job_id,
            worker_id,
            token,
            result,
            self._now(),
        )
        self._forget_claim(job_id, worker_id, token)

    async def fail(self, job_id: OpaqueId, error: JsonObject) -> None:
        worker_id, token = self._claim_for(job_id)
        await self._fail_with_fence(job_id, worker_id, token, error)

    async def fail_claim(
        self,
        claim: JobClaim,
        error: JsonObject,
    ) -> JobStatus:
        """Fail exactly the claimed fence and report retry/terminal status."""
        failed = await self._fail_with_fence(
            claim.job.job_id,
            claim.worker_id,
            claim.fencing_token,
            error,
        )
        return failed.status

    async def _fail_with_fence(
        self,
        job_id: OpaqueId,
        worker_id: str,
        token: int,
        error: JsonObject,
    ) -> DurableJob:
        now = self._now()
        failed = await self._repository.fail(
            job_id,
            worker_id,
            token,
            error,
            now,
            now + self._retry_base,
        )
        self._forget_claim(job_id, worker_id, token)
        if failed.status == JobStatus.LEASED:
            raise RuntimeError("repository returned leased job after fail")
        return failed

    def _new_job(
        self,
        *,
        owner_kind: JobOwnerKind,
        tenant_id: str,
        scope: Scope | None,
        provider_integration_id: str | None,
        job_type: str,
        payload: JsonObject,
        idempotency_key: str,
        not_before: datetime | None,
    ) -> DurableJob:
        now = self._now()
        available_at = not_before or now
        if available_at.tzinfo is None:
            raise ValueError("not_before must be timezone-aware")
        return DurableJob(
            job_id=self._id_factory(),
            owner_kind=owner_kind,
            tenant_id=tenant_id,
            scope=scope,
            provider_integration_id=provider_integration_id,
            job_type=job_type,
            payload=payload,
            idempotency_key=idempotency_key,
            max_attempts=self._max_attempts,
            not_before=available_at,
            created_at=now,
            updated_at=now,
        )

    def _claim_for(self, job_id: str) -> tuple[str, int]:
        claim = self._claims.get(job_id)
        if claim is None:
            raise JobLeaseLostError(f"no active claim for job {job_id}")
        return claim

    def _forget_claim(self, job_id: str, worker_id: str, token: int) -> None:
        if self._claims.get(job_id) == (worker_id, token):
            self._claims.pop(job_id, None)

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("clock must return timezone-aware datetime")
        return now
