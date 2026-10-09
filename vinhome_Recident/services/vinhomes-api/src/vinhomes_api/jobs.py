"""Work the domain does on a timer: deadlines, expiries.

    python -m vinhomes_api.jobs sweep        (reads DATABASE_URL; run every minute)

Every step is safe to run twice: a deadline warns once, an expiry happens once.
"""

import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from .events import emit
from .resident_services import expire_unpaid

TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
WARN_AT = 0.8  # share of the resolution window after which a warning is due
OPEN = "('resolved','closed','cancelled')"


async def sweep_tenant(db) -> dict[str, int]:
    """One pass for the tenant the connection is scoped to."""
    counts = {"sla_warnings": 0, "sla_breaches": 0, "visits_expired": 0, "bookings_expired": 0, "requests_cancelled": 0}
    rows = await db.execute(text(f"""
        select id,code,status,priority,resolution_due_at,created_at,
               now()>=resolution_due_at as breached
        from tickets
        where tenant_id={TENANT} and status not in {OPEN} and resolution_due_at is not null
          and now() >= created_at + (resolution_due_at-created_at)*{WARN_AT}
    """))
    for t in rows.mappings().all():
        kind = "breached" if t["breached"] else "warning"
        queued = await emit(db, f"ticket.sla_{kind}", {"ticketId": str(t["id"]), "ticketCode": t["code"], "priority": t["priority"],
                                                    "dueAt": t["resolution_due_at"].isoformat()}, dedupe_key=f"sla:{kind}:{t['id']}")
        counts["sla_breaches" if kind == "breached" else "sla_warnings"] += int(queued)
    counts["visits_expired"] = (await db.execute(text(f"update visitor_passes set status='expired' where tenant_id={TENANT} and status='approved' and visit_to<now()"))).rowcount
    counts["bookings_expired"] = await expire_unpaid(db)
    counts["requests_cancelled"] = (await db.execute(text(f"""
        update service_requests set status='cancelled',cancelled_at=now(),cancel_reason='Quá 7 ngày không bổ sung hồ sơ'
        where tenant_id={TENANT} and status='need_more_info' and updated_at<now()-interval '7 days'
    """))).rowcount
    return counts


async def sweep(url: str) -> dict[str, dict[str, int]]:
    engine = create_async_engine(url, pool_pre_ping=True)
    done: dict[str, dict[str, int]] = {}
    try:
        async with engine.connect() as probe:
            tenants = [str(r[0]) for r in await probe.execute(text("select id from tenants where status='active'"))]
        for tenant in tenants:
            async with engine.begin() as db:
                await db.execute(text("select set_config('app.tenant_id',:t,true)"), {"t": tenant})
                done[tenant] = await sweep_tenant(db)
    finally:
        await engine.dispose()
    return done


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if args != ["sweep"]:
        raise SystemExit("usage: python -m vinhomes_api.jobs sweep")
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    for tenant, counts in asyncio.run(sweep(url.replace("postgresql://", "postgresql+asyncpg://", 1))).items():
        print(tenant, counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
