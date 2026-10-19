"""Resident decision controls for linked tickets follow Platform acknowledgement."""
from fastapi import HTTPException
from sqlalchemy import text

from .platform import TENANT

# Used only with the verified files alias `f` and authenticated resident `:actor`.
# A staff upload alone never grants visibility: it must be active job evidence,
# on this resident's ticket, with its result acknowledged by Platform.
RESULT_PHOTO_VISIBLE = """exists(
    select 1 from ticket_files tfv join tickets tv on tv.id=tfv.ticket_id and tv.tenant_id=tfv.tenant_id
    join evidence_items ev on ev.file_id=tfv.file_id and ev.ticket_id=tv.id and ev.tenant_id=tv.tenant_id
    where tfv.file_id=f.id and tfv.tenant_id=f.tenant_id and tv.requester_user_id=:actor
      and ev.status='active' and ev.purpose in ('before','after','verification')
      and ((not exists(select 1 from platform_links lv where lv.ticket_id=tv.id and lv.tenant_id=tv.tenant_id)
        and tv.status in ('resolved','closed'))
        or exists(select 1 from platform_outbox ov where ov.ticket_id=tv.id and ov.tenant_id=tv.tenant_id
          and ov.external_job_id=cast(ev.work_order_id as text) and ov.event_type='job.result_published'
          and ov.receipt->>'ingestion_status'='applied')))
"""


async def approval_ready(db, approval_id) -> bool:
    customer = (await db.execute(text(f"""SELECT pc.case_id FROM work_approvals a
        JOIN work_orders w ON w.id=a.work_order_id AND w.tenant_id=a.tenant_id
        JOIN vh_resident_case_tickets ct ON ct.ticket_id=w.ticket_id AND ct.tenant_id=w.tenant_id
        JOIN platform_customer_cases pc ON pc.case_id=ct.case_id AND pc.tenant_id=ct.tenant_id
        WHERE a.id=:id AND a.tenant_id={TENANT}"""), {"id": approval_id})).first()
    if customer:
        from .resident_cases import PROJECTION
        return bool((await db.execute(text(f"""WITH projection AS ({PROJECTION} AND c.id=:case)
            SELECT 1 FROM projection p JOIN platform_customer_projection_acks ack
              ON ack.case_id=p.id AND ack.tenant_id=p.tenant_id AND ack.canonical_version=p.public_version
            JOIN platform_customer_links cl ON cl.id=ack.link_id AND cl.tenant_id=ack.tenant_id
            WHERE cl.active AND cl.expires_at>now() AND cl.revision=ack.link_revision"""), {"case": customer.case_id})).first())
    return bool((await db.execute(text(f"""
        select not exists(select 1 from platform_links l
            where l.ticket_id=w.ticket_id and l.tenant_id=a.tenant_id and l.status in ('pending','open'))
          or exists(select 1 from platform_links l where l.ticket_id=w.ticket_id and l.tenant_id=a.tenant_id
            and l.status='open' and (
              (a.kind='customer_repair' and exists(select 1 from platform_outbox o
                where o.ticket_id=w.ticket_id and o.tenant_id=a.tenant_id and o.event_type='job.quote_ready'
                  and o.data->>'approval_id'=cast(a.id as text) and o.receipt->>'ingestion_status'='applied'))
              or (a.kind='customer_completion' and w.status='completed' and exists(
                select 1 from platform_outbox o where o.ticket_id=w.ticket_id and o.tenant_id=a.tenant_id
                  and o.external_job_id=cast(w.id as text) and o.event_type='job.result_published'
                  and o.receipt->>'ingestion_status'='applied'))))
        from work_approvals a join work_orders w on w.id=a.work_order_id and w.tenant_id=a.tenant_id
        where a.id=:id and a.tenant_id={TENANT}
    """), {"id": approval_id})).scalar_one_or_none())


async def require_approval_ready(db, approval_id) -> None:
    if not await approval_ready(db, approval_id):
        raise HTTPException(409, "Platform has not published this decision step yet")
