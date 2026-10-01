"""Publish a resident result only after all work has passed QC."""
import json
from sqlalchemy import text
from .v3_mutations import record_event


async def publish_completion(scope, ticket_id):
    db = scope[0]
    result = await db.execute(text("select id,status,last_event_seq from tickets where id=:id for update"), {"id": ticket_id})
    ticket = dict(result.mappings().one())
    if ticket["status"] in {"resolved", "closed", "cancelled"}:
        return
    result = await db.execute(text("""
        select w.id,w.status,q.outcome from work_orders w
        left join lateral (select outcome from vh_qc_results
          where work_order_id=w.id order by checked_at desc,id desc limit 1) q on true
        where w.ticket_id=:id and w.status not in ('cancelled','rejected')
          and not exists (select 1 from vh_qc_redo_orders r where r.source_work_order_id=w.id)
    """), {"id": ticket_id})
    orders = result.mappings().all()
    if not orders or any(w["status"] != "completed" or w["outcome"] != "pass" for w in orders):
        return
    await db.execute(text("""
        insert into work_approvals(tenant_id,work_order_id,kind,requested_to_user_id,request_detail,status,request_hash)
        select tenant_id,:order_id,'customer_completion',requester_user_id,
          jsonb_build_object('note','Kết quả đã được nghiệm thu. Vui lòng kiểm tra và xác nhận.'),
          'pending',:revision from tickets where id=:id
    """), {"id": ticket_id, "order_id": orders[0]["id"], "revision": f"completion:{ticket_id}:{ticket['last_event_seq']}"})
    await db.execute(text("update tickets set status='resolved',resolved_at=now() where id=:id"), {"id": ticket_id})
    event_id = await record_event(scope, ticket, "ticket.resolution_published", json.dumps({"message": "Kết quả đã được nghiệm thu"}), to_status="resolved")
    await db.execute(text("""
        insert into notification_deliveries(tenant_id,user_id,ticket_event_id,channel,dedupe_key,payload,status,available_at)
        select tenant_id,requester_user_id,:event_id,'in_app',:key,
          jsonb_build_object('type','ticket.resolution_published','ticketId',id),'pending',now()
        from tickets where id=:id on conflict (tenant_id,user_id,channel,dedupe_key) do nothing
    """), {"event_id": event_id, "key": str(event_id), "id": ticket_id})
