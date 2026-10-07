"""What the Supervisor does in management's place on a request it coordinates.

Management no longer approves each plan or picks the technician by hand: the Supervisor approves
the plan it proposed, the resident still decides on it, and the work goes to an available
technician of the unit. Management reads the session and closes it at the end. Each step is a
ticket event with the Supervisor as its actor, so the trail says who decided.

`VINHOMES_API_SUPERVISOR_APPROVES_PLANS=0` gives management both steps back.
"""

import json
import os
from uuid import UUID, uuid4

from sqlalchemy import text

TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
APPROVAL_NOTE = "Supervisor duyệt phương án thay Ban quản lý."
# How long an offered job waits for the technician before management has to step in.
OFFER_HOURS = 24


def supervisor_approves() -> bool:
    return os.getenv("VINHOMES_API_SUPERVISOR_APPROVES_PLANS", "1").strip() != "0"


async def agent_event(db, ticket_id: UUID, agent_id: str, event_type: str, payload: dict, to_status: str | None = None) -> UUID:
    """A ticket event whose actor is an agent. The caller holds the ticket's row lock."""
    ticket = (await db.execute(text("select status,last_event_seq from tickets where id=:id for update"),
                               {"id": ticket_id})).mappings().one()
    seq, event_id = ticket["last_event_seq"] + 1, uuid4()
    await db.execute(text(f"""
        insert into ticket_events(id,tenant_id,ticket_id,seq,event_type,actor_kind,actor_agent_id,idempotency_key,
          correlation_id,payload,occurred_at,from_status,to_status)
        values(:event,{TENANT},:ticket,:seq,:type,'agent',:agent,:key,:event,cast(:payload as jsonb),now(),:status,:to_status)
    """), {"event": event_id, "ticket": ticket_id, "seq": seq, "type": event_type, "agent": agent_id, "key": str(event_id),
           "payload": json.dumps(payload), "status": ticket["status"], "to_status": to_status})
    await db.execute(text("update tickets set last_event_seq=:seq,version=version+1,updated_at=now() where id=:id"),
                     {"seq": seq, "id": ticket_id})
    from .resident_cases import append_domain_event
    await append_domain_event(db, ticket_id, event_type, to_status)
    return event_id


async def approve_for_management(db, plan_id: UUID, ticket_id: UUID, agent_id: str) -> bool:
    """The Supervisor's own plan goes on to the resident. False when it was no longer waiting."""
    changed = await db.execute(text(f"""
        update vh_ticket_plans set status='resident_pending',version=version+1,management_note=:note,
          management_at=now(),updated_at=now()
        where id=:plan and tenant_id={TENANT} and status='management_pending' and proposed_by_agent_id=:agent
    """), {"plan": plan_id, "agent": agent_id, "note": APPROVAL_NOTE})
    if changed.rowcount != 1:
        return False
    await agent_event(db, ticket_id, agent_id, "plan.management_decided",
                      {"planId": str(plan_id), "status": "resident_pending", "decidedBy": "supervisor"})
    return True


async def coordinated(db, ticket_id: object) -> bool:
    """The ticket's work comes from a plan the Supervisor proposed and the resident approved."""
    found = await db.execute(text(f"""
        select 1 from vh_ticket_plans where ticket_id=:id and tenant_id={TENANT} and status='approved'
          and proposed_by_agent_id is not null and management_by is null limit 1
    """), {"id": ticket_id})
    return found.first() is not None


async def offer_work(db, ticket_id: UUID, work_order_id: UUID, agent_id: str) -> bool:
    """Offer the work to the least busy available technician of the ticket's unit with this specialty.

    False when nobody can take it now: the work stays queued until a slot is released or management dispatches it.
    """
    staff = (await db.execute(text(f"""
        select sp.id from staff_profiles sp
        join users u on u.id=sp.user_id and u.status='active'
        join work_orders w on w.id=:work and w.tenant_id=sp.tenant_id
        join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id and t.id=:ticket
        cross join lateral (
          select count(*) as load from work_assignments a
          join work_orders o on o.id=a.work_order_id and o.tenant_id=a.tenant_id
          where a.staff_id=sp.id and o.status not in ('completed','cancelled','rejected')
            and (a.status='accepted' or (a.status='offered' and a.offer_expires_at>now()))) busy
        where sp.tenant_id={TENANT} and sp.active and sp.availability='available'
          and sp.management_unit_id=t.management_unit_id and busy.load<sp.max_concurrent_jobs
          and exists (select 1 from staff_specialties ss where ss.staff_id=sp.id and ss.tenant_id=sp.tenant_id
            and ss.category_id=w.category_id and ss.active)
          and exists (select 1 from staff_shifts sh where sh.staff_id=sp.id and sh.tenant_id=sp.tenant_id
            and sh.status='available' and sh.starts_at<=now() and sh.ends_at>now())
        order by busy.load,sp.id limit 1 for update of sp skip locked
    """), {"work": work_order_id, "ticket": ticket_id})).scalar_one_or_none()
    if staff is None:
        return False
    assignment = (await db.execute(text(f"""
        insert into work_assignments(tenant_id,work_order_id,staff_id,assigned_by_agent_id,status,offered_at,offer_expires_at)
        values({TENANT},:work,:staff,:agent,'offered',now(),now()+make_interval(hours => :hours)) returning id
    """), {"work": work_order_id, "staff": staff, "agent": agent_id, "hours": OFFER_HOURS})).scalar_one()
    await db.execute(text("update work_orders set status='offered',version=version+1,updated_at=now() where id=:id"),
                     {"id": work_order_id})
    await agent_event(db, ticket_id, agent_id, "work_order.offered", {"assignmentId": str(assignment), "offeredBy": "supervisor"})
    return True


async def offer_queued_work(db, released_work_order_id: UUID) -> None:
    """Use a released queue slot for approved Supervisor work of the same unit and specialty."""
    staff = (await db.execute(text(f"""
        select sp.id,sp.management_unit_id from work_assignments a
        join staff_profiles sp on sp.id=a.staff_id and sp.tenant_id=a.tenant_id
        where a.work_order_id=:work and a.tenant_id={TENANT} and sp.active
        order by a.created_at desc limit 1
    """), {"work": released_work_order_id})).mappings().first()
    if staff is None:
        return
    # Skip tickets another transaction already holds; it will release its own slot.
    # A rejected offer is not immediately sent back to the worker who refused it.
    for _ in range(25):
        queued = (await db.execute(text(f"""
            select w.id,w.ticket_id,plan.proposed_by_agent_id,plan.proposal,plan.management_by from work_orders w
            join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id
            join lateral (
                select p.proposed_by_agent_id,p.proposal,p.management_by from vh_ticket_plans p
                where p.ticket_id=t.id and p.tenant_id=t.tenant_id and p.status='approved'
                  and p.proposed_by_agent_id is not null and p.management_by is null
                  and exists (select 1 from jsonb_array_elements(p.steps) step
                    where step->>'work_order_id'=w.id::text)
                order by p.created_at desc limit 1
            ) plan on true
            where w.tenant_id={TENANT} and w.status='queued' and w.id<>:released
              and t.management_unit_id=:unit and t.status not in ('resolved','closed','cancelled')
              and exists (select 1 from staff_specialties ss where ss.staff_id=:staff
                and ss.tenant_id=w.tenant_id and ss.category_id=w.category_id and ss.active)
              and (plan.proposal->>'performer_staff_id' is null
                or plan.proposal->>'performer_staff_id'=cast(:staff as text))
              and not exists (select 1 from work_assignments a
                where a.work_order_id=w.id and a.tenant_id=w.tenant_id
                  and (a.status='accepted' or (a.status='offered' and a.offer_expires_at>now())))
            order by w.created_at,w.id limit 1 for update of t,w skip locked
        """), {"released": released_work_order_id, "unit": staff["management_unit_id"],
               "staff": staff["id"]})).mappings().first()
        if queued is None:
            return
        if (queued["proposal"] or {}).get("performer_staff_id"):
            from .v3_request_presentation import offer_planned_work
            offered = await offer_planned_work(db, queued["ticket_id"], queued["id"], queued)
        else:
            offered = await offer_work(db, queued["ticket_id"], queued["id"], queued["proposed_by_agent_id"])
        if not offered:
            return
