"""Personal run and delivery persistence on the existing durable-job queue.

The scheduler/channel runtime remains Person 2's consumer. No second scheduler
or Redis config store is created here. A delivery retry reuses its saved body.
"""

from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ..workforce.foundation._database import SqlAlchemyUnitOfWork
from ..workforce.foundation._job_repository import SqlDurableJobRepository
from ..workforce.foundation._tables import durable_jobs
from ..workforce.foundation.event_delivery import DurableJob, JobOwnerKind
from ._contracts import PersonalJobPage, PlatformError
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
            await self.context_for(job)
            if job.attempt > 1 and job.job_type != "delivery":
                raise PlatformError("OUTCOME_UNKNOWN", 409)
        except PlatformError as exc:
            await self.repository.fail(job.job_id, worker_id, job.fencing_token, {"code": exc.code}, now(), now())
            return None
        return job

    async def context_for(self, job):
        """Recheck a saved job immediately before runtime/delivery starts."""
        if job.owner_kind != JobOwnerKind.PERSONAL or not job.personal_user_id:
            raise PlatformError("CAPABILITY_DENIED", 403)
        purpose = {"schedule-run": "schedule", "channel-event": "channel", "delivery": "delivery", "publish-batch": "builder"}[job.job_type]
        context = await self.authority.context(job.personal_user_id, purpose=purpose,
            environment=job.payload["environment"], workspace_id=job.payload.get("workspace_id"))
        async with self.authority.engine.begin() as db:
            await self.authority.assert_active(db, context)
        if context.tenant_id != job.tenant_id or context.authorization_revision != job.payload["authorization_revision"]:
            raise PlatformError("AUTHORIZATION_REVOKED", 403)
        return context

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

    async def list_page(self, context, kind, *, cursor=None, limit=100):
        """Keyset pagination scoped to the current tenant, owner and kind.

        The cursor is the last returned job ID, not an authorization token.
        Deleting that row invalidates the cursor; consumers must reload.
        """
        if kind not in {"schedule-run", "channel-event", "delivery", "publish-batch"}:
            raise PlatformError("INVALID_JOB_KIND", 422)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise PlatformError("INVALID_PAGINATION", 422)
        if cursor is not None and (not isinstance(cursor, str) or not 1 <= len(cursor) <= 255):
            raise PlatformError("INVALID_JOB_CURSOR", 422)
        owner = and_(durable_jobs.c.owner_kind == "personal", durable_jobs.c.tenant_id == context.tenant_id,
            durable_jobs.c.personal_user_id == context.initiator_user_id, durable_jobs.c.job_type == kind)
        async with self.authority.engine.begin() as db:
            await self.authority.assert_active(db, context, require_eligible=False)
            query = select(durable_jobs).where(owner)
            if cursor is not None:
                marker = (await db.execute(select(durable_jobs.c.created_at, durable_jobs.c.id).where(
                    owner, durable_jobs.c.id == cursor))).mappings().first()
                if marker is None:
                    raise PlatformError("INVALID_JOB_CURSOR", 422)
                query = query.where(or_(durable_jobs.c.created_at > marker["created_at"],
                    and_(durable_jobs.c.created_at == marker["created_at"], durable_jobs.c.id > marker["id"])))
            rows = (await db.execute(query.order_by(durable_jobs.c.created_at, durable_jobs.c.id).limit(limit + 1))).mappings().all()
        has_more = len(rows) > limit
        return PersonalJobPage(items=[self.repository._model(row) for row in rows[:limit]],
            next_cursor=rows[limit - 1]["id"] if has_more else None, has_more=has_more)

    async def list(self, context, kind):
        """Compatibility reader: exhaust pages instead of silently truncating."""
        items, cursor = [], None
        while True:
            page = await self.list_page(context, kind, cursor=cursor)
            items.extend(page.items)
            if not page.has_more:
                return items
            cursor = page.next_cursor
