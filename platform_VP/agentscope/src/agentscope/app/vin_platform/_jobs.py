"""Personal run and delivery persistence on the existing durable-job queue.

The scheduler/channel runtime remains Person 2's consumer. No second scheduler
or Redis config store is created here. A delivery retry reuses its saved body.
"""

from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ..workforce.foundation._database import SqlAlchemyUnitOfWork
from ..workforce.foundation._job_repository import SqlDurableJobRepository
from ..workforce.foundation._tables import durable_jobs
from ..workforce.foundation.event_delivery import DurableJob, JobOwnerKind
from ._contracts import PlatformError
from ._service import now


class PersonalJobs:
    def __init__(self, authority):
        self.authority = authority
        sessions = async_sessionmaker(authority.engine, expire_on_commit=False)
        self.repository = SqlDurableJobRepository(lambda: SqlAlchemyUnitOfWork(sessions), personal_only=True)

    async def enqueue(self, context, *, kind, key, payload, not_before=None):
        if kind not in {"schedule-run", "channel-event", "delivery", "publish-batch"}:
            raise PlatformError("INVALID_JOB_KIND", 422)
        async with self.authority.engine.begin() as db:
            await self.authority.assert_active(db, context)
        at = now()
        ident = str(uuid5(NAMESPACE_URL, ":".join(("vin-job", context.tenant_id, context.initiator_user_id, kind, key))))
        job = DurableJob(job_id=ident, owner_kind=JobOwnerKind.PERSONAL, personal_user_id=context.initiator_user_id,
            tenant_id=context.tenant_id, job_type=kind, payload={"authorization_revision": context.authorization_revision,
                "environment": context.environment, "workspace_id": context.workspace_id, "body": payload}, idempotency_key=kind + ":" + key,
            not_before=not_before or at, created_at=at, updated_at=at,
            # Model/business runs are never automatically repeated after a crash.
            # Delivery has separate immutable payload/idempotency and may retry.
            max_attempts=5 if kind == "delivery" else 1)
        try:
            return await self.repository.enqueue_once(job)
        except ValueError as exc:
            raise PlatformError("IDEMPOTENCY_CONFLICT", 409) from exc

    async def claim(self, worker_id, *, seconds=60):
        if not 1 <= seconds <= 300:
            raise PlatformError("INVALID_LEASE", 422)
        at = now()
        job = await self.repository.claim_next(worker_id, at, at + timedelta(seconds=seconds))
        if job is None:
            return None
        try:
            context = await self.authority.context(job.personal_user_id, environment=job.payload["environment"],
                workspace_id=job.payload.get("workspace_id"))
            async with self.authority.engine.begin() as db:
                await self.authority.assert_active(db, context)
            if context.authorization_revision != job.payload["authorization_revision"]:
                raise PlatformError("AUTHORIZATION_REVOKED", 403)
            if job.attempt > 1 and job.job_type != "delivery":
                raise PlatformError("OUTCOME_UNKNOWN", 409)
        except PlatformError as exc:
            await self.repository.fail(job.job_id, worker_id, job.fencing_token, {"code": exc.code}, now(), now())
            return None
        return job

    async def complete(self, job, worker_id, result):
        return await self.repository.complete(job.job_id, worker_id, job.fencing_token, result, now())

    async def checkpoint(self, job, worker_id, result):
        """Persist a partial publish manifest/repair cursor while keeping lease."""
        return await self.repository._fenced_update(job.job_id, worker_id, job.fencing_token, now(),
            {"result": result, "updated_at": now()})

    async def heartbeat(self, job, worker_id, *, seconds=60):
        if not 1 <= seconds <= 300:
            raise PlatformError("INVALID_LEASE", 422)
        return await self.repository.renew_lease(job.job_id, worker_id, job.fencing_token,
            now(), now() + timedelta(seconds=seconds))

    async def fail(self, job, worker_id, code, *, retry_after=30):
        return await self.repository.fail(job.job_id, worker_id, job.fencing_token, {"code": code}, now(), now() + timedelta(seconds=retry_after))

    async def list(self, context, kind):
        async with self.authority.engine.begin() as db:
            await self.authority.assert_active(db, context, require_eligible=False)
            rows = (await db.execute(select(durable_jobs).where(durable_jobs.c.owner_kind == "personal",
                durable_jobs.c.tenant_id == context.tenant_id, durable_jobs.c.personal_user_id == context.initiator_user_id,
                durable_jobs.c.job_type == kind).order_by(durable_jobs.c.created_at).limit(100))).mappings().all()
        return [self.repository._model(row) for row in rows]
