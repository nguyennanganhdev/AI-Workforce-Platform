"""Retention is tied to closed aggregates; open work and ambiguous intents survive."""
import time

from sqlalchemy import delete, select, text, update

from . import schema as s
from .service import row


async def prune(service, now=None):
    now = time.time() if now is None else now
    async with service.tx() as conn:
        if conn.dialect.name == "postgresql" and not (await conn.execute(
                text("SELECT pg_try_advisory_xact_lock(724103819)"))).scalar():
            return 0
        expired = (await conn.execute(select(s.approvals).where(s.approvals.c.status == "pending",
            s.approvals.c.expires < now))).mappings().all()
        for approval in expired:
            wf = await row(conn, s.workflows, s.workflows.c.id == approval["workflow_id"], lock=True)
            await conn.execute(update(s.approvals).where(s.approvals.c.id == approval["id"]).values(
                status="expired", revision=s.approvals.c.revision + 1))
            await conn.execute(update(s.operations).where(s.operations.c.id == approval["operation_id"],
                s.operations.c.status == "awaiting_approval").values(status="rejected"))
            if wf["state"] != "closed":
                await service.transition(conn, wf, "needs_attention")
                await service.event(conn, wf, "approval.expired", {"approval_id": approval["id"]})
        flows = (await conn.execute(select(s.workflows).where(s.workflows.c.state == "closed",
            s.workflows.c.closed_at < now - 90 * 86400))).mappings().all()
        for wf in flows:
            conv = await row(conn, s.conversations, s.conversations.c.id == wf["conversation_id"], lock=True)
            await conn.execute(delete(s.events).where(s.events.c.workflow_id == wf["id"]))
            await conn.execute(update(s.conversations).where(s.conversations.c.id == conv["id"]).values(
                purged_through=conv["sequence"]))
        # Never discard an early event still awaiting correlation.
        await conn.execute(delete(s.receipts).where(s.receipts.c.received < now - 180 * 86400,
            s.receipts.c.status.in_(["applied", "duplicate", "rejected"])))
        await conn.execute(delete(s.rate_limits).where(s.rate_limits.c.window < int(now) // 60 - 1440))
    return len(flows)
