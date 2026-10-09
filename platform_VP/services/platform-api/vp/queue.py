import asyncio
import socket

from sqlalchemy import and_, or_, select, update

from .config import settings
from .db import Artifact, Job, Reservation, Session, emit, now, transaction, uid
from .limits import reconcile


class StaleLease(Exception):
    pass


async def fence(db, job_id: str, generation: int):
    # Lock order is session, then job. Queue claiming doesn't lock sessions.
    job = await db.get(Job, job_id)
    session = await db.scalar(
        select(Session)
        .where(
            Session.id == job.session_id,
        )
        .with_for_update()
    )
    job = await db.scalar(
        select(Job)
        .where(Job.id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if job.status != "running" or job.generation != generation or job.lease_until <= now():
        raise StaleLease(job_id)
    if job.body.get("turn") != session.turn or session.status not in {"running", "indexing"}:
        raise StaleLease("Session no longer accepts this execution")
    return session, job


async def claim(worker_id: str, kind="agent") -> Job | None:
    async with transaction() as db:
        ready = or_(
            and_(Job.status == "queued", Job.available <= now()),
            and_(Job.status == "running", Job.lease_until < now()),
        )
        # Least recently served session first; one durable job per session at a time.
        query = select(Job).where(ready, Job.kind == kind).order_by(Job.available, Job.created)
        if db.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        job = await db.scalar(query.limit(1))
        if not job:
            return None
        old_generation = job.generation
        result = await db.execute(
            update(Job)
            .where(
                Job.id == job.id,
                Job.generation == old_generation,
                ready,
            )
            .values(
                status="running",
                generation=old_generation + 1,
                attempts=Job.attempts + 1,
                lease_owner=worker_id,
                lease_until=now() + settings.lease_seconds,
            )
            .returning(Job)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()


async def fence_for_execution(db, job_id, generation):
    from .domain import authorize_execution

    session, job = await fence(db, job_id, generation)
    await authorize_execution(db, session)
    return session, job


async def renew(job_id: str, generation: int):
    async with transaction() as db:
        result = await db.execute(
            update(Job)
            .where(
                Job.id == job_id,
                Job.generation == generation,
                Job.status == "running",
                Job.lease_until > now(),
            )
            .values(lease_until=now() + settings.lease_seconds)
        )
        if result.rowcount != 1:
            raise StaleLease(job_id)


async def heartbeat(job: Job):
    while True:
        await asyncio.sleep(settings.lease_seconds / 3)
        await renew(job.id, job.generation)


async def settle_orphaned_reservations(db, session, job):
    rows = (
        await db.scalars(
            select(Reservation).where(
                Reservation.job_id == job.id,
                Reservation.status == "reserved",
                Reservation.generation < job.generation,
            )
        )
    ).all()
    for row in rows:
        await reconcile(db, row.id, {}, None)
        await emit(
            db, session, "usage.uncertain", {"reservation_id": row.id, "charged_micros": row.amount}
        )


async def worker_loop(index: int, stop: asyncio.Event, runtime, kind="agent"):
    worker_id = f"{socket.gethostname()}:{uid()}:{index}"
    while not stop.is_set():
        job = await claim(worker_id, kind)
        if not job:
            from .signals import wait_for_work

            await wait_for_work(stop)
            continue
        pulse = asyncio.create_task(heartbeat(job))
        try:
            async with transaction() as db:
                session, current = await fence(db, job.id, job.generation)
                await settle_orphaned_reservations(db, session, current)
                task = await db.get(Artifact, job.id)
                if task:
                    task.body = {**task.body, "status": "running", "generation": job.generation}
                await emit(
                    db, session, "task.started", {"task_id": job.id, "generation": job.generation}
                )
            if job.attempts > 3:
                from .runtime import SafeRuntimeError

                raise SafeRuntimeError("recovery_limit")
            await runtime(job)
        except StaleLease:
            pass
        except asyncio.CancelledError:
            # Leave running lease and reservations intact: recovery is explicit.
            raise
        except Exception as exc:
            from .limits import BudgetExceeded, RateExceeded
            from .runtime import SafeRuntimeError

            try:
                async with transaction() as db:
                    session, current = await fence(db, job.id, job.generation)
                    if isinstance(exc, RateExceeded):
                        current.status = "queued"
                        # A controlled rate delay is not a failed recovery attempt.
                        current.attempts = max(0, current.attempts - 1)
                        current.available = now() + 60
                        current.error = "provider_rate_limit"
                        await emit(db, session, "task.delayed", {"task_id": job.id, "seconds": 60})
                    else:
                        # Never expose provider exceptions (can contain URLs, headers and secrets).
                        code = (
                            "budget_exhausted"
                            if isinstance(exc, BudgetExceeded)
                            else "runtime_error"
                        )
                        if isinstance(exc, SafeRuntimeError):
                            code = exc.code
                        current.status = "failed"
                        current.error = code
                        session.status = code if code == "budget_exhausted" else "needs_review"
                        task = await db.get(Artifact, job.id)
                        if task:
                            task.body = {**task.body, "status": "failed", "error": code}
                        await emit(db, session, "task.failed", {"task_id": job.id, "code": code})
            except StaleLease:
                pass
        finally:
            pulse.cancel()
            await asyncio.gather(pulse, return_exceptions=True)
