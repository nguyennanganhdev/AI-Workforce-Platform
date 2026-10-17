"""Periodic local-receipt reconciliation. Never retries a model/provider call."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from sqlalchemy import select, update

from . import _tables as t
from ._contracts import PlatformError


async def reconcile_pending(authority, *, limit=100):
    if not 1 <= limit <= 1000:
        raise ValueError("Reconciliation batch must be 1-1000")
    async with authority.engine.connect() as db:
        rows = (await db.execute(select(t.attempts).where(t.attempts.c.state.in_(["reserved", "pending_reconciliation"]))
            .order_by(t.attempts.c.data["reconciliation_checked_at"].as_string().asc().nullsfirst(),
                t.attempts.c.created_at, t.attempts.c.id).limit(limit))).mappings().all()
    counts = {"scanned": len(rows), "settled": 0, "pending": 0}
    for row in rows:
        getter = getattr(authority.storage, "list_model_calls", None)
        receipts = await getter(row["user_id"], since=row["created_at"].isoformat(), limit=20001) if getter else []
        receipt = next((r for r in receipts if r["id"] == row["id"] and r.get("status") != "started"), None)
        async with authority.engine.begin() as db:
            current = (await db.execute(select(t.attempts.c.data).where(t.attempts.c.id == row["id"],
                t.attempts.c.state != "settled").with_for_update())).scalar_one_or_none()
            if current is not None:
                await db.execute(update(t.attempts).where(t.attempts.c.id == row["id"], t.attempts.c.state != "settled")
                    .values(data={**current, "reconciliation_checked_at": datetime.now(UTC).isoformat()}))
        if receipt is None:
            if row["state"] == "pending_reconciliation":
                # Also release slots retained by the earlier pending semantics.
                await authority.quota.settle(row["tenant_id"], row["id"], None)
            counts["pending"] += 1
            continue
        values = [receipt.get("input_tokens"), receipt.get("output_tokens")]
        valid = receipt.get("status") == "completed" and all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in values)
        rejected = 400 <= (receipt.get("provider_http_status") or 0) < 500
        try:
            await authority.quota.settle(row["tenant_id"], row["id"], sum(values) if valid else 0 if rejected else None,
                provider_request_id=receipt.get("provider_request_id"))
        except PlatformError as exc:
            if exc.code != "SETTLEMENT_CONFLICT":
                raise
        counts["settled" if valid or rejected else "pending"] += 1
    return counts


@asynccontextmanager
async def reconciliation_worker(authority, *, interval=30):
    async def run():
        from ..._logging import logger
        while True:
            try:
                await reconcile_pending(authority)
            except Exception:
                logger.exception("Vin quota receipt reconciliation failed")
            await asyncio.sleep(interval)
    task = asyncio.create_task(run(), name="vin-quota-reconciliation")
    try:
        yield
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
