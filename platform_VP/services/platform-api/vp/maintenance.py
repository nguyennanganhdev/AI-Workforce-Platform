import asyncio
import socket

from sqlalchemy import select

from .db import Job, Record, Reservation, now, transaction, uid
from .limits import reconcile


async def settle_abandoned():
    async with transaction() as db:
        reservation_ids = (
            await db.scalars(
                select(Reservation.id)
                .where(
                    Reservation.status == "reserved",
                )
                .order_by(Reservation.created)
                .limit(100)
            )
        ).all()
    # One session per transaction: do not hold the shared wallet while acquiring
    # a different session lock (runtime locks session before wallet).
    for reservation_id in reservation_ids:
        async with transaction() as db:
            row = await db.get(Reservation, reservation_id)
            job = await db.get(Job, row.job_id)
            if job and job.lease_until <= now() and job.status in {"cancelled", "failed", "done"}:
                await reconcile(db, row.id, {}, None)


async def maintenance_loop(stop, workers):
    identity = uid()
    while not stop.is_set():
        await settle_abandoned()
        async with transaction() as db:
            record = await db.get(Record, identity)
            if not record:
                record = Record(
                    id=identity,
                    workspace="system",
                    owner="system",
                    kind="worker",
                    body={"hostname": socket.gethostname(), "capacity": workers},
                )
                db.add(record)
            record.updated = now()
        try:
            await asyncio.wait_for(stop.wait(), 10)
        except TimeoutError:
            pass
