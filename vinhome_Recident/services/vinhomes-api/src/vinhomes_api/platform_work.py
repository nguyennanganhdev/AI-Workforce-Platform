"""What the platform's coordinator may look up and do in the domain (docs/domain/NOI_WORKFORCE_V1.md section 6).

The platform tells a tool nothing about who is asking. Every function takes the ticket id the agent copied from the
hand-over message and works only on a ticket handed to the platform whose workflow still runs; the resident, the
home and the zone are read from that ticket, never taken from the agent. `db` is a connection scoped to the tenant.
Nothing here returns the VH code, a phone number, a contact name or what staff wrote for themselves.

A look-up returns a dict or raises Refused (words for the coordinator). An action takes the platform's
client_reference, does its work and stores its answer in one transaction, and answers a repeated reference with the
stored answer; a refusal is {"status": "failed", "reason": ...} and changes nothing.
"""

import json
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text

from .knowledge import search
from .platform import ACTIVE, CLIENT_ID, TENANT, VN, _quote, command, platform_client, vn_time
from .platform import booking_card, post_chat
from .resident_services import (BookingCreate, VisitorCreate, amenities, announcements, availability, balance, cancel_booking,
                                cancel_visitor_pass, cards, construction_permits, construction_policy, create_visitor_pass,
                                debit_notes, home_rules, list_requests, load_amenity, mask, my_bookings, report_lost, visitor_passes)
from .v3_resident import list_my_tickets
from .v3_mutations import requires_plan
from .work_offers import agent_event, offer_queued_work, offer_work

UNKNOWN = "Không có yêu cầu nào đang giao cho trợ lý với ticket_id này. Hãy chép đúng ticket_id ở tin nhắn đầu tiên."
RELATION = {"owner": "chủ hộ", "tenant": "người thuê", "household": "thành viên trong hộ"}
# Work that is over, one way or another.
ENDED = "('completed','cancelled','rejected')"
MILESTONES = {
    "ticket.created": "Tiếp nhận yêu cầu", "work_order.created": "Tạo việc cho nhân viên", "work_order.offered": "Mời nhân viên nhận việc",
    "work_assignment.responded:accepted": "Nhân viên nhận việc", "work_assignment.responded:rejected": "Nhân viên từ chối",
    "work_assignment.expired": "Lời mời hết hạn", "work_order.unassigned": "Chưa có nhân viên nhận",
    "work_order.rescheduled": "Đổi lịch hẹn", "work_order.status_changed:en_route": "Nhân viên đang đến",
    "work_order.status_changed:arrived": "Nhân viên đã đến", "work_order.status_changed:in_progress": "Bắt đầu làm",
    "work_order.status_changed:completed": "Nhân viên báo làm xong", "work_order.status_changed:cancelled": "Hủy việc",
    "work_order.repair_proposed": "Nhân viên gửi báo giá", "work_approval.decided:approved": "Cư dân đồng ý",
    "work_approval.decided:rejected": "Cư dân không đồng ý", "work_order.qc_recorded:acceptance_report": "Nhân viên gửi kết quả nghiệm thu",
    "work_order.qc_recorded": "Ban quản lý nghiệm thu",
    "ticket.resolution_published": "Gửi kết quả để cư dân xác nhận", "ticket.status_changed": "Đổi trạng thái yêu cầu",
}


class Refused(Exception):
    """Said back to the coordinator in plain words; nothing was changed."""


def _at(value: datetime | None) -> str | None:
    return vn_time(value) if value else None


def _appointment(value: str | None) -> datetime | None:
    """A time the agent wrote, in the future. Without an offset it is Vietnam time, as the resident said it."""
    if not (value or "").strip():
        return None
    try:
        at = datetime.fromisoformat(value.strip())
    except ValueError:
        raise Refused("Giờ hẹn không đọc được. Hãy ghi dạng 2026-10-12T09:00:00+07:00.") from None
    at = at if at.tzinfo else at.replace(tzinfo=VN)
    if at <= datetime.now(VN):
        raise Refused("Giờ hẹn phải ở tương lai.")
    return at


async def _ticket(db, ticket_id, lock: bool = False) -> dict:
    """The ticket, if the platform is working on it. The id comes from the agent: it proves nothing by itself."""
    try:
        key = UUID(str(ticket_id).strip())
    except ValueError:
        raise Refused(UNKNOWN) from None
    row = (await db.execute(text(f"""
        select t.id,t.status,t.version,t.requester_user_id,t.unit_id,t.building_id,t.zone_id,t.management_unit_id,
          t.category_id,c.code as category_code,c.name as category
        from tickets t join platform_links l on l.ticket_id=t.id and l.tenant_id=t.tenant_id
        left join service_categories c on c.id=t.category_id and c.tenant_id=t.tenant_id
        where t.id=:id and t.tenant_id={TENANT} and l.status in {ACTIVE} {"for update of t" if lock else ""}
    """), {"id": key})).mappings().first()
    if row is None:
        raise Refused(UNKNOWN)
    return dict(row)


# ---- look-ups --------------------------------------------------------------------------------------------------------

async def ticket_get(db, ticket_id) -> dict:
    ticket = await _ticket(db, ticket_id)
    told = (await db.execute(text(f"""
        select t.title,t.description,t.request_kind,t.priority,t.severity,t.is_emergency,t.created_at,t.response_due_at,
          t.resolution_due_at,u.code as unit,b.name as building,z.name as zone,
          (select count(*) from ticket_files f where f.ticket_id=t.id and f.tenant_id=t.tenant_id
             and f.uploaded_by=t.requester_user_id) as resident_photos
        from tickets t left join units u on u.id=t.unit_id and u.tenant_id=t.tenant_id
        left join buildings b on b.id=t.building_id and b.tenant_id=t.tenant_id
        left join zones z on z.id=t.zone_id and z.tenant_id=t.tenant_id where t.id=:id
    """), {"id": ticket["id"]})).mappings().one()
    orders = (await db.execute(text(f"""
        select w.description,w.status,w.scheduled_at,w.arrived_at,w.started_at,w.completed_at,
          case when a.status='offered' and a.offer_expires_at<=now() then 'expired' else a.status end as offer,
          a.eta_at,a.offer_expires_at,su.name as staff_name,q.outcome,q.checked_at,q.reported_by,q.note,
          p.photos_before,p.photos_after,p.photos_verification
        from work_orders w
        left join lateral (select x.status,x.eta_at,x.offer_expires_at,x.staff_id from work_assignments x
          where x.work_order_id=w.id and x.tenant_id=w.tenant_id order by x.created_at desc,x.id desc limit 1) a on true
        left join staff_profiles sp on sp.id=a.staff_id and sp.tenant_id=w.tenant_id left join users su on su.id=sp.user_id
        left join lateral (select x.outcome,x.checked_at,case when x.criteria->0->>'name'='acceptance_report' then x.note end as note,
            (select u.name from users u where u.id=x.checked_by and x.criteria->0->>'name'='acceptance_report') as reported_by
          from vh_qc_results x where x.work_order_id=w.id and x.tenant_id=w.tenant_id order by x.checked_at desc,x.id desc limit 1) q on true
        cross join lateral (select count(*) filter (where e.purpose='before') as photos_before,
            count(*) filter (where e.purpose='after') as photos_after,
            count(*) filter (where e.purpose='verification') as photos_verification
          from evidence_items e where e.work_order_id=w.id and e.tenant_id=w.tenant_id and e.status='active') p
        where w.ticket_id=:id and w.tenant_id={TENANT} order by w.created_at,w.id
    """), {"id": ticket["id"]})).mappings().all()
    approvals = (await db.execute(text(f"""
        select a.id,a.kind,a.request_detail as detail,a.created_at from work_approvals a
        join work_orders w on w.id=a.work_order_id and w.tenant_id=a.tenant_id
        where w.ticket_id=:id and a.tenant_id={TENANT} and a.status='pending' and (a.expires_at is null or a.expires_at>now())
          and a.kind in ('customer_repair','customer_completion') order by a.created_at
    """), {"id": ticket["id"]})).mappings().all()
    quote = next((a for a in reversed(approvals) if a["kind"] == "customer_repair"), None)
    asked = next((a for a in reversed(approvals) if a["kind"] == "customer_completion"), None)
    events = (await db.execute(text(f"""
        select event_type,coalesce(payload->>'status',payload->>'channel') as status,occurred_at from ticket_events
        where ticket_id=:id and tenant_id={TENANT} order by seq
    """), {"id": ticket["id"]})).mappings().all()
    return {
        "ticket_status": ticket["status"],
        # The platform reads a top-level "status" as proof that the work is done: only once it was accepted.
        **({"status": "completed"} if ticket["status"] in ("resolved", "closed") else {}),
        "title": told["title"], "description": told["description"], "category": ticket["category"],
        "request_kind": told["request_kind"], "priority": told["priority"], "severity": told["severity"],
        "is_emergency": told["is_emergency"], "unit": told["unit"], "building": told["building"], "zone": told["zone"],
        "created_at": _at(told["created_at"]), "response_due_at": _at(told["response_due_at"]),
        "resolution_due_at": _at(told["resolution_due_at"]), "resident_photos": told["resident_photos"],
        "work_orders": [{
            "description": w["description"], "work_status": w["status"], "appointment": _at(w["scheduled_at"]),
            "staff_name": w["staff_name"], "offer": w["offer"], "eta": _at(w["eta_at"]),
            "offer_expires_at": _at(w["offer_expires_at"]) if w["offer"] == "offered" else None,
            "arrived_at": _at(w["arrived_at"]), "started_at": _at(w["started_at"]), "completed_at": _at(w["completed_at"]),
            # The technician's report of the result (their note is for the resident), or management's inspection.
            # Neither says the resident accepted: that is the resident's own answer (completion_request).
            "acceptance_report": w["outcome"] and {"result": w["outcome"], "reported_by": w["reported_by"] or "Ban quản lý",
                                                   "reported_at": _at(w["checked_at"]), "note": w["note"]},
            "photos": {"before": w["photos_before"], "after": w["photos_after"], "verification": w["photos_verification"]},
        } for w in orders],
        "quote": quote and _quote({"quote": quote}),
        "completion_request": asked and {"waiting_for_resident": True, "asked_at": _at(asked["created_at"])},
        "milestones": [{"at": _at(e["occurred_at"]), "what": what} for e in events
                       if (what := MILESTONES.get(f"{e['event_type']}:{e['status']}") or MILESTONES.get(e["event_type"]))],
    }


async def resident_context(db, ticket_id) -> dict:
    ticket = await _ticket(db, ticket_id)
    row = (await db.execute(text("""
        select p.name,u.code as unit,u.unit_kind,b.name as building,z.name as zone,s.name as site,
          (select ur.relation from unit_residents ur where ur.unit_id=t.unit_id and ur.user_id=t.requester_user_id
             and ur.tenant_id=t.tenant_id and ur.verification_status='verified' and ur.valid_from<=now()
             and (ur.valid_to is null or ur.valid_to>now()) order by (ur.relation='owner') desc limit 1) as relation
        from tickets t join users p on p.id=t.requester_user_id
        left join units u on u.id=t.unit_id and u.tenant_id=t.tenant_id
        left join buildings b on b.id=t.building_id and b.tenant_id=t.tenant_id
        left join zones z on z.id=t.zone_id and z.tenant_id=t.tenant_id
        left join sites s on s.id=t.site_id and s.tenant_id=t.tenant_id where t.id=:id
    """), {"id": ticket["id"]})).mappings().one()
    # How to address them is given, not left to a guess from the name: nothing here says "anh" or "chị".
    return {"resident": {"name": row["name"], "address_as": "anh/chị " + row["name"].split()[-1],
                         "relation_to_home": RELATION.get(row["relation"])},
            "home": {"unit": row["unit"], "kind": row["unit_kind"], "building": row["building"], "zone": row["zone"], "site": row["site"]}}


async def knowledge_search(db, ticket_id, query: str) -> dict:
    ticket = await _ticket(db, ticket_id)
    if not (query or "").strip():
        raise Refused("Cần nội dung để tìm trong tài liệu.")
    tenant = (await db.execute(text(f"select {TENANT}"))).scalar_one()
    found = await search(db, tenant, "resident", ticket["zone_id"], ticket["building_id"], query.strip()[:1000], 5)
    return {"found": bool(found["hits"]), "passages": [
        {"document": hit["title"], "section": hit["section"], "text": hit["text"], **({"unverified": True} if hit["unverified"] else {})}
        for hit in found["hits"]]}


async def _home(db, ticket_id, call, *more):
    """A read the resident may make about the home of the ticket, made as that resident."""
    ticket = await _ticket(db, ticket_id)
    if ticket["unit_id"] is None:
        raise Refused("Yêu cầu này không gắn với căn hộ nào.")
    try:
        return await call(ticket["unit_id"], (db, ticket["requester_user_id"]), *more)
    except HTTPException:
        raise Refused("Người gửi yêu cầu không có quyền xem thông tin này của căn (công nợ chỉ dành cho chủ hộ và người thuê).") from None


def _ref(value, what: str) -> UUID:
    """An item the agent names by the *_ref a look-up gave it."""
    try:
        return UUID(str(value).strip())
    except ValueError:
        raise Refused(f"{what} không đúng. Hãy tra lại danh sách và chép đúng giá trị *_ref.") from None


def _day(value: datetime) -> str:
    return value.astimezone(VN).strftime("%H:%M")


async def visitors(db, ticket_id) -> dict:
    found = await _home(db, ticket_id, visitor_passes, 20)
    return {"visits": [{"visit_ref": str(v["id"]), "guest_name": v["guest_name"], "guest_count": v["guest_count"],
                        "purpose": VISIT_PURPOSES.get(v["purpose"], v["purpose"]), "visit_from": _at(v["visit_from"]),
                        "visit_to": _at(v["visit_to"]), "visit_status": v["status"]} for v in found["items"]]}


async def access_cards(db, ticket_id) -> dict:
    found = await _home(db, ticket_id, cards)
    # The number is shown as its last four digits: enough for the resident to tell their cards apart.
    return {"cards": [{"card_ref": str(c["id"]), "card_no": mask(c["card_no"]), "kind": c["kind"], "card_status": c["status"],
                       "holder_name": c["holder_name"], "vehicle_plate_no": c["vehicle_plate_no"],
                       "valid_to": _at(c["valid_to"]) if isinstance(c["valid_to"], datetime) else c["valid_to"]} for c in found["items"]]}


async def amenity_list(db, ticket_id) -> dict:
    """What can be booked, and what this home has booked from now on."""
    ticket = await _ticket(db, ticket_id)
    scope = (db, ticket["requester_user_id"])
    places = (await amenities(scope))["items"]
    names = {p["id"]: p["name"] for p in places}
    booked = (await _home(db, ticket_id, lambda unit, who: my_bookings(who, unit, 50)))["items"]
    return {"amenities": [{"amenity_ref": str(p["id"]), "name": p["name"], "category": p["category"], "areas": p["areas"],
                           "price_per_slot": int(p["price"]), "slot_minutes": p["slot_minutes"], "open": str(p["open_time"])[:5],
                           "close": str(p["close_time"])[:5], "open_weekdays": p["open_weekdays"], "book_days_ahead": p["max_advance_days"],
                           "cancel_hours_ahead": p["cancel_before_hours"], "max_people": p["max_guests"], "rules": p["rules_note"],
                           "open_now_for_booking": p["status"] == "active"} for p in places],
            "bookings": [{"booking_ref": str(b["id"]), "amenity": names.get(b["amenity_id"]), "area": b["area_code"], "start": _at(b["start_at"]),
                          "end": _at(b["end_at"]), "people": b["guests"], "booking_status": b["status"], "total": int(b["total_amount"])}
                         for b in booked if b["status"] in ("pending_payment", "confirmed") and b["end_at"] > datetime.now(VN)]}


async def amenity_free(db, ticket_id, amenity_ref, date: str) -> dict:
    ticket = await _ticket(db, ticket_id)
    try:
        found = await availability(_ref(amenity_ref, "amenity_ref"), (db, ticket["requester_user_id"]), (date or "").strip())
    except (HTTPException, ValueError):
        raise Refused("Không có tiện ích đó, hoặc ngày không đúng dạng 2026-10-12.") from None
    if not found["bookable"]:
        return {"date": found["date"], "bookable": False, "areas": [], "note": "Ngày này tiện ích không mở, đang đóng, hoặc ngoài thời hạn được đặt trước."}
    return {"date": found["date"], "bookable": True, "areas": [
        {"area": area["area_code"], "free_slots": [f"{_day(slot['start'])}-{_day(slot['end'])}" for slot in area["slots"] if slot["free"]]}
        for area in found["areas"]]}


async def desk_requests(db, ticket_id) -> dict:
    found = await _home(db, ticket_id, list_requests, 20)
    return {"requests": [{"kind": r["kind"], "request_status": r["status"], "details": r["details"], "created_at": _at(r["created_at"]),
                          "submitted_at": _at(r["submitted_at"]), "due_at": _at(r["sla_due_at"]), "fulfilled_at": _at(r["fulfilled_at"]),
                          "decision_note": r["decision_note"], "fee": int(r["fee_amount"]) if r["fee_amount"] is not None else None}
                         for r in found["items"]]}


async def renovation(db, ticket_id) -> dict:
    """The renovation rules of the home and its permits (owner and tenant only, as in the resident's app)."""
    ticket = await _ticket(db, ticket_id)
    if ticket["unit_id"] is None:
        raise Refused("Yêu cầu này không gắn với căn hộ nào.")
    scope = (db, ticket["requester_user_id"])
    try:
        permits = (await construction_permits(ticket["unit_id"], scope))["items"]
    except HTTPException:
        raise Refused("Chỉ chủ hộ và người thuê xem được quy định và giấy phép thi công của căn.") from None
    try:
        rules = await construction_policy(ticket["unit_id"], scope)
    except HTTPException:
        rules = None
    return {"rules": None if rules is None else {
                "work_time": f"{str(rules['work_time_from'])[:5]}-{str(rules['work_time_to'])[:5]}",
                "noisy_time": f"{str(rules['noisy_time_from'])[:5]}-{str(rules['noisy_time_to'])[:5]}" if rules["noisy_time_from"] else None,
                "no_work_weekdays": rules["no_work_weekdays"], "deposit": int(rules["deposit_amount"] or 0),
                "overtime_fee_per_hour": int(rules["overtime_fee_per_hour"] or 0), "max_workers": rules["max_workers"],
                "max_duration_days": rules["max_duration_days"], "note": rules["note"]},
            "permits": [{"category": x["category"], "work": x["scope_description"], "contractor": x["contractor_name"],
                         "planned_start": str(x["planned_start"]), "planned_end": str(x["planned_end"]), "permit_status": x["status"],
                         "reject_reason": x["reject_reason"], "deposit": int(x["deposit_amount"] or 0), "deposit_status": x["deposit_status"]}
                        for x in permits]}


async def other_requests(db, ticket_id) -> dict:
    """The resident's other requests, newest first; only this one can be worked on with the tools."""
    ticket = await _ticket(db, ticket_id)
    mine = (await list_my_tickets((db, ticket["requester_user_id"]), 20, 0))["items"]
    return {"requests": [{"title": t["title"], "request_status": t["status"], "priority": t["priority"], "created_at": _at(t["created_at"]),
                          "updated_at": _at(t["updated_at"])} for t in mine if str(t["id"]) != str(ticket["id"])]}


async def rules(db, ticket_id) -> dict:
    return await _home(db, ticket_id, home_rules)


async def debts(db, ticket_id, view: str) -> dict:
    if view not in ("balance", "open", "paid", "all"):
        raise Refused("view phải là balance, open, paid hoặc all.")
    if view == "balance":
        owed = await _home(db, ticket_id, balance)
        return {**owed, "unit": owed["unit"]["code"]}
    notes = await _home(db, ticket_id, debit_notes, view, 20)
    return {"unit": notes["unit"]["code"], "currency": "VND",
            "notes": [{key: value for key, value in note.items() if key != "id"} for note in notes["items"]]}


async def staff_available(db, ticket_id) -> dict:
    ticket = await _ticket(db, ticket_id)
    if ticket["category_id"] is None:
        raise Refused("Yêu cầu chưa được phân loại nên chưa biết cần chuyên môn nào.")
    # Who offer_work would consider: of the ticket's unit, with the specialty, on shift now and with room for a job.
    rows = (await db.execute(text(f"""
        select sp.id,u.name,ss.proficiency,sp.max_concurrent_jobs,busy.load,sh.ends_at from staff_profiles sp
        join users u on u.id=sp.user_id and u.status='active'
        join staff_specialties ss on ss.staff_id=sp.id and ss.tenant_id=sp.tenant_id and ss.category_id=:category and ss.active
        cross join lateral (select max(x.ends_at) as ends_at from staff_shifts x where x.staff_id=sp.id and x.tenant_id=sp.tenant_id
          and x.status='available' and x.starts_at<=now() and x.ends_at>now()) sh
        cross join lateral (select count(*) as load from work_assignments a
          join work_orders o on o.id=a.work_order_id and o.tenant_id=a.tenant_id
          where a.staff_id=sp.id and o.status not in {ENDED}
            and (a.status='accepted' or (a.status='offered' and a.offer_expires_at>now()))) busy
        where sp.tenant_id={TENANT} and sp.active and sp.availability='available' and sp.management_unit_id=:unit
          and sh.ends_at is not null and busy.load<sp.max_concurrent_jobs order by busy.load,sp.id
    """), {"category": ticket["category_id"], "unit": ticket["management_unit_id"]})).mappings().all()
    return {"specialty": ticket["category"], "staff": [
        {"staff_id": str(r["id"]), "name": r["name"], "proficiency": r["proficiency"], "active_jobs": r["load"],
         "max_concurrent_jobs": r["max_concurrent_jobs"], "shift_ends_at": _at(r["ends_at"])} for r in rows]}


async def notices(db, ticket_id) -> dict:
    """What management has announced to the resident's tower and zone, newest first."""
    ticket = await _ticket(db, ticket_id)
    found = await announcements((db, ticket["requester_user_id"]), 10)
    return {"announcements": [
        {"title": a["title"], "kind": a["kind"], "important": a["is_important"], "published_at": _at(a["published_at"]),
         "summary": a["summary"], "text": (a["body_md"] or "")[:1200]} for a in found["items"]]}


# ---- actions ---------------------------------------------------------------------------------------------------------

async def _stored(db, reference: str, tool: str, ticket_id):
    """The answer already given for this reference, to the same tool about the same ticket only."""
    row = (await db.execute(text(f"select ticket_id,tool,answer from platform_operations where client_reference=:ref and tenant_id={TENANT}"),
                            {"ref": reference})).first()
    if row is None:
        return None
    if row.tool != tool or str(row.ticket_id) != str(ticket_id).strip().lower():
        raise Refused("client_reference này đã dùng cho một lời gọi khác.")
    return row.answer


async def _act(db, tool: str, ticket_id, reference, effect) -> dict:
    """Run `effect(ticket)` once for this reference. It returns the answer and, for a dispatch, the work order."""
    if not isinstance(reference, str) or not 8 <= len(reference) <= 120:
        return {"status": "failed", "reason": "Thiếu client_reference của platform."}
    try:
        # Before the ticket is judged: a repeat gets its first answer even after the workflow ended.
        answer = await _stored(db, reference, tool, ticket_id)
        if answer is None:
            ticket = await _ticket(db, ticket_id, lock=True)
            # The same call twice at once: the second waited for the ticket and finds the first one's answer.
            answer = await _stored(db, reference, tool, ticket_id)
        if answer is None:
            # A refusal half way undoes what the effect already wrote.
            async with db.begin_nested():
                await platform_client(db)
                answer, work = await effect(ticket)
                await db.execute(text(f"""
                    insert into platform_operations(client_reference,tenant_id,ticket_id,tool,work_order_id,answer)
                    values (:ref,{TENANT},:ticket,:tool,:work,cast(:answer as jsonb))
                """), {"ref": reference, "ticket": ticket["id"], "tool": tool, "work": work,
                       "answer": json.dumps(answer, ensure_ascii=False)})
        return answer
    except Refused as no:
        return {"status": "failed", "reason": str(no)}


async def dispatch(db, ticket_id, description: str, staff_id: str | None, appointment_at: str | None, client_reference) -> dict:
    """Create the work and offer it. Its id is the platform's job id: staff progress is reported under this call."""
    async def effect(ticket):
        text_ = (description or "").strip()
        if not 1 <= len(text_) <= 2000:
            raise Refused("description cần từ 1 đến 2000 ký tự, nói rõ việc cần làm.")
        at = _appointment(appointment_at)
        if ticket["status"] not in ("open", "triaging", "assigned", "in_progress"):
            raise Refused("Yêu cầu đã có kết quả hoặc đã kết thúc nên không giao việc mới được.")
        if await requires_plan((db, None, False), ticket["id"]):
            raise Refused("Yêu cầu này đi theo phương án do Ban quản lý duyệt; trợ lý không tự giao việc.")
        if ticket["category_id"] is None:
            raise Refused("Yêu cầu chưa được phân loại nên chưa giao việc được.")
        if ticket["category_code"] == "security":
            raise Refused("Việc an ninh do Ban quản lý điều động; trợ lý không tự giao.")
        # One job at a time: work that waits for staff, is being done, or is done but not yet accepted.
        open_ = (await db.execute(text(f"""
            select w.status from work_orders w where w.ticket_id=:ticket and w.tenant_id={TENANT} and w.status not in ('cancelled','rejected')
              and (w.status<>'completed' or coalesce((select q.outcome from vh_qc_results q where q.work_order_id=w.id
                and q.tenant_id=w.tenant_id order by q.checked_at desc,q.id desc limit 1),'')<>'pass') limit 1
        """), {"ticket": ticket["id"]})).scalar_one_or_none()
        if open_ == "queued":
            raise Refused("Việc đã giao vẫn đang xếp hàng chờ nhân viên; hệ thống tự mời ngay khi có người rảnh.")
        if open_ is not None:
            raise Refused("Yêu cầu đang có việc chưa kết thúc nên chưa giao thêm việc mới.")
        work = (await db.execute(text(f"""
            insert into work_orders(tenant_id,ticket_id,category_id,required_specialty_id,description,status,scheduled_at)
            values ({TENANT},:ticket,:category,:category,:description,'queued',:at) returning id
        """), {"ticket": ticket["id"], "category": ticket["category_id"], "description": text_, "at": at})).scalar_one()
        fresh = ticket["status"] in ("open", "triaging")
        await agent_event(db, ticket["id"], CLIENT_ID, "work_order.created", {"workOrderId": str(work)}, "assigned" if fresh else None)
        if fresh:
            await db.execute(text("update tickets set status='assigned' where id=:id"), {"id": ticket["id"]})
        try:
            named = UUID(staff_id.strip()) if (staff_id or "").strip() else None
        except ValueError:
            named = None
        # The person the coordinator named when they can take it, else whoever is least busy.
        if not ((named and await offer_work(db, ticket["id"], work, CLIENT_ID, named, at))
                or await offer_work(db, ticket["id"], work, CLIENT_ID, eta_at=at)):
            return {"status": "queued", "external_job_id": str(work), "appointment": _at(at),
                    "note": "Chưa có nhân viên rảnh; hệ thống tự mời ngay khi có người."}, work
        offered = (await db.execute(text(f"""
            select u.name,a.offer_expires_at from work_assignments a
            join staff_profiles sp on sp.id=a.staff_id and sp.tenant_id=a.tenant_id join users u on u.id=sp.user_id
            where a.work_order_id=:work and a.tenant_id={TENANT} and a.status='offered'
        """), {"work": work})).mappings().one()
        return {"status": "pending", "external_job_id": str(work), "offered_to": offered["name"],
                "offer_expires_at": _at(offered["offer_expires_at"]), "appointment": _at(at),
                "note": "Đã mời nhân viên, đang chờ người nhận."}, work
    return await _act(db, "vh_work_order_dispatch", ticket_id, client_reference, effect)


async def reschedule(db, ticket_id, appointment_at: str, reason: str | None, client_reference) -> dict:
    async def effect(ticket):
        at = _appointment(appointment_at)
        if at is None:
            raise Refused("Cần giờ hẹn mới.")
        work = (await db.execute(text(f"""
            select id,status from work_orders where ticket_id=:ticket and tenant_id={TENANT} and status not in {ENDED}
            order by created_at desc,id desc limit 1 for update
        """), {"ticket": ticket["id"]})).mappings().first()
        if work is None:
            raise Refused("Yêu cầu chưa có việc nào đang chờ làm để đổi lịch.")
        if work["status"] not in ("queued", "offered", "accepted"):
            raise Refused("Nhân viên đã lên đường hoặc đang làm nên không đổi lịch được.")
        await db.execute(text("update work_orders set scheduled_at=:at,version=version+1,updated_at=now() where id=:id"),
                         {"at": at, "id": work["id"]})
        # The appointment is also what the person who holds the job is expected at.
        holder = (await db.execute(text(f"""
            update work_assignments a set eta_at=:at,updated_at=now() from staff_profiles sp
            where a.work_order_id=:work and a.tenant_id={TENANT} and sp.id=a.staff_id and sp.tenant_id=a.tenant_id
              and (a.status='accepted' or (a.status='offered' and a.offer_expires_at>now())) returning sp.user_id
        """), {"at": at, "work": work["id"]})).scalar_one_or_none()
        event = await agent_event(db, ticket["id"], CLIENT_ID, "work_order.rescheduled", {
            "workOrderId": str(work["id"]), "appointmentAt": at.isoformat(), "reason": (reason or "").strip()[:2000]})
        if holder:
            await db.execute(text(f"""
                insert into notification_deliveries(tenant_id,user_id,ticket_event_id,channel,dedupe_key,payload,status,available_at)
                values ({TENANT},:user,:event,'in_app',:key,cast(:payload as jsonb),'pending',now())
            """), {"user": holder, "event": event, "key": str(event), "payload": json.dumps({
                "type": "work.rescheduled", "workOrderId": str(work["id"]), "ticketId": str(ticket["id"]), "appointmentAt": at.isoformat()})})
        return {"status": "confirmed", "appointment": _at(at)}, None
    return await _act(db, "vh_work_order_reschedule", ticket_id, client_reference, effect)


async def cancel(db, ticket_id, reason: str | None, client_reference) -> dict:
    """The resident no longer wants the request: the ticket, its unfinished work and the offers end together."""
    async def effect(ticket):
        why = (reason or "").strip()[:2000] or "Cư dân đề nghị hủy yêu cầu."
        # TICKET_TRANSITIONS: only these may become cancelled.
        if ticket["status"] not in ("open", "triaging", "assigned", "in_progress"):
            raise Refused("Yêu cầu đã có kết quả hoặc đã kết thúc nên không hủy được.")
        orders = (await db.execute(text(f"""
            select w.id,w.status,c.code as category from work_orders w
            join service_categories c on c.id=w.category_id and c.tenant_id=w.tenant_id
            where w.ticket_id=:ticket and w.tenant_id={TENANT} and w.status not in ('cancelled','rejected')
            order by w.created_at,w.id for update of w
        """), {"ticket": ticket["id"]})).mappings().all()
        # ALLOWED_TRANSITIONS: work that reached the home or is under way has no way to cancelled. Work that was
        # done there is not thrown away by a word in the chat either: what happens to it is for people to settle.
        if any(w["status"] in ("arrived", "in_progress", "completed") for w in orders):
            raise Refused("Nhân viên đã đến nơi, đã bắt đầu làm hoặc đã làm xong nên không hủy được yêu cầu. Việc này cần Ban quản lý xử lý.")
        if any(w["category"] == "security" for w in orders):
            raise Refused("Việc an ninh chỉ Ban quản lý hủy được.")
        for work in orders:
            await db.execute(text("update work_orders set status='cancelled',version=version+1,updated_at=now() where id=:id"), {"id": work["id"]})
            await db.execute(text("""
                update work_assignments set status='cancelled',ended_at=now(),updated_at=now()
                where work_order_id=:id and status in ('accepted','offered')
            """), {"id": work["id"]})
            await db.execute(text("""
                update work_approvals set status='cancelled',updated_at=now()
                where work_order_id=:id and status='pending' and kind in ('customer_repair','customer_completion')
            """), {"id": work["id"]})
            await agent_event(db, ticket["id"], CLIENT_ID, "work_order.status_changed", {
                "workOrderId": str(work["id"]), "status": "cancelled", "note": why, "cancelledBy": "resident"})
        await db.execute(text("update tickets set status='cancelled' where id=:id"), {"id": ticket["id"]})
        await agent_event(db, ticket["id"], CLIENT_ID, "ticket.status_changed", {"reason": why, "cancelledBy": "resident"}, "cancelled")
        for work in orders:
            await offer_queued_work(db, work["id"])  # the slots this freed go to the work that waits
        # Nothing is left to coordinate: the workflow ends after this turn and the chat goes back to Reception.
        await command(db, ticket["id"], "close", {"reason": "resident_cancelled"})
        return {"status": "confirmed", "ticket_status": "cancelled", "cancelled_work_orders": len(orders)}, None
    return await _act(db, "vh_ticket_cancel", ticket_id, client_reference, effect)


async def add_note(db, ticket_id, note: str, client_reference) -> dict:
    """Something the resident added for the staff. It is kept in the ticket's history, which staff read."""
    async def effect(ticket):
        said = (note or "").strip()
        if not 1 <= len(said) <= 2000:
            raise Refused("note cần từ 1 đến 2000 ký tự.")
        await agent_event(db, ticket["id"], CLIENT_ID, "ticket.note_added", {"note": said})
        return {"status": "confirmed"}, None
    return await _act(db, "vh_ticket_add_note", ticket_id, client_reference, effect)


# ---- offers that were turned down or ran out -------------------------------------------------------------------------

VISIT_PURPOSES = {"family_visit": "thăm gia đình", "delivery": "giao hàng", "service_provider": "thợ, dịch vụ", "business": "công việc", "other": "khác"}


def _time(value: str, what: str) -> datetime:
    try:
        at = datetime.fromisoformat((value or "").strip())
    except ValueError:
        raise Refused(f"{what} không đọc được. Hãy ghi dạng 2026-10-12T09:00:00+07:00.") from None
    return at if at.tzinfo else at.replace(tzinfo=VN)


async def visitor_register(db, ticket_id, guest_name: str, visit_from: str, visit_to: str, purpose: str, guest_count: int,
                           vehicle_plate_no: str | None, client_reference) -> dict:
    """Announce a visitor for the home of the ticket, as its resident would in the app: same rules of the zone."""
    async def effect(ticket):
        if ticket["unit_id"] is None:
            raise Refused("Yêu cầu này không gắn với căn hộ nào.")
        if purpose not in VISIT_PURPOSES or not (guest_name or "").strip():
            raise Refused("Cần tên khách và mục đích: " + ", ".join(VISIT_PURPOSES) + ".")
        try:
            visit = VisitorCreate(guest_name=guest_name.strip(), guest_count=guest_count, purpose=purpose,
                                  vehicle_plate_no=(vehicle_plate_no or "").strip() or None,
                                  visit_from=_time(visit_from, "Giờ khách đến"), visit_to=_time(visit_to, "Giờ khách về"))
            made = await create_visitor_pass(ticket["unit_id"], visit, (db, ticket["requester_user_id"]), client_reference)
        except ValueError:
            raise Refused("Thông tin khách không hợp lệ (tên tối đa 200 ký tự, số khách từ 1 đến 50).") from None
        except HTTPException as no:
            # The rule of the zone that was not met, as the resident's own app would say it.
            raise Refused(f"Chưa đăng ký được khách: {no.detail}") from None
        waits = made["status"] == "pending_approval"
        return {"status": "confirmed", "visit_status": made["status"], "needs_desk_approval": waits, "guest_name": made["guest_name"],
                "guest_count": made["guest_count"], "visit_from": _at(made["visit_from"]), "visit_to": _at(made["visit_to"]),
                "note": "Lượt khách này chờ quầy lễ tân duyệt." if waits else "Đã được duyệt; mã vào cổng nằm ở mục Khách đến thăm trong ứng dụng của cư dân."}, None
    return await _act(db, "vh_visitor_register", ticket_id, client_reference, effect)


async def _as_resident(db, tool: str, ticket_id, reference, what: str, call, item, done: dict) -> dict:
    """One thing the resident may do to an item of their own (cancel a visit, a booking, report a card lost), done
    for them through the resident's own rule: it refuses what the app would refuse."""
    async def effect(ticket):
        try:
            await call(_ref(item, what), (db, ticket["requester_user_id"]))
        except HTTPException as no:
            raise Refused(f"Chưa thực hiện được: {no.detail}") from None
        return {"status": "confirmed", **done}, None
    return await _act(db, tool, ticket_id, reference, effect)


async def visitor_cancel(db, ticket_id, visit_ref, client_reference) -> dict:
    return await _as_resident(db, "vh_visitor_cancel", ticket_id, client_reference, "visit_ref", cancel_visitor_pass, visit_ref, {"visit_status": "cancelled"})


async def card_lost(db, ticket_id, card_ref, client_reference) -> dict:
    return await _as_resident(db, "vh_card_report_lost", ticket_id, client_reference, "card_ref", report_lost, card_ref,
                              {"card_status": "lost", "note": "Thẻ đã bị khóa. Cấp thẻ mới là một yêu cầu riêng tại quầy lễ tân."})


async def amenity_cancel(db, ticket_id, booking_ref, client_reference) -> dict:
    return await _as_resident(db, "vh_amenity_cancel", ticket_id, client_reference, "booking_ref", cancel_booking, booking_ref, {"booking_status": "cancelled"})


async def amenity_book(db, ticket_id, amenity_ref, start_at: str, end_at: str, area: str | None, people: int, client_reference) -> dict:
    """Shows the resident a booking card in the chat. Nothing is booked here: the place is taken when the resident
    taps the card (a booking may cost money), under the rules of the amenity, checked again at that moment."""
    async def effect(ticket):
        if ticket["unit_id"] is None:
            raise Refused("Yêu cầu này không gắn với căn hộ nào.")
        try:
            place = await load_amenity(db, _ref(amenity_ref, "amenity_ref"))
            wanted = BookingCreate(unit_id=ticket["unit_id"], amenity_id=place["id"], area_code=(area or "").strip() or place["areas"][0],
                                   start_at=_time(start_at, "Giờ bắt đầu"), end_at=_time(end_at, "Giờ kết thúc"), guests=people)
        except HTTPException:
            raise Refused("Không có tiện ích đó.") from None
        except ValueError:
            raise Refused("Thông tin đặt chỗ không hợp lệ (số người từ 1 đến 100).") from None
        minutes = int((wanted.end_at - wanted.start_at).total_seconds() // 60)
        if place["status"] != "active" or wanted.area_code not in place["areas"] or minutes <= 0 or minutes % place["slot_minutes"]:
            raise Refused(f"Tiện ích phải đang mở, khu vực là một trong: {', '.join(place['areas'])}, và thời gian là các lượt {place['slot_minutes']} phút.")
        total = int(place["price"]) * (minutes // place["slot_minutes"])
        link = (await db.execute(text(f"select ticket_id,channel_id from platform_links where ticket_id=:id and tenant_id={TENANT}"),
                                 {"id": ticket["id"]})).mappings().one()
        await post_chat(db, link, "booking:" + client_reference, booking_card(client_reference, place, wanted, total))
        return {"status": "confirmed", "card_shown": True, "booked": False, "amenity": place["name"], "area": wanted.area_code,
                "start": _at(wanted.start_at), "end": _at(wanted.end_at), "people": wanted.guests, "total": total,
                "note": "CHƯA đặt chỗ. Cư dân đã nhận một thẻ trong hộp chat và phải tự bấm xác nhận; khi họ bấm bạn sẽ nhận được tin."}, None
    return await _act(db, "vh_amenity_book", ticket_id, client_reference, effect)


async def offer_waiting(db, turned_down=()) -> int:
    """Offer every queued job the platform dispatched to whoever can take it now; returns how many found someone.

    `turned_down`: jobs whose offer was just refused or ran out. One of those that nobody else can take is reported,
    once, as 'work_order.unassigned'; it stays queued and is offered when someone who has not refused it is free.
    """
    waiting = (await db.execute(text(f"""
        select w.id,w.ticket_id,w.scheduled_at from work_orders w
        join platform_operations po on po.work_order_id=w.id and po.tenant_id=w.tenant_id
        join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id
        where w.tenant_id={TENANT} and w.status='queued' and t.status not in ('resolved','closed','cancelled')
        order by w.created_at,w.id for update of t,w skip locked
    """))).mappings().all()
    said, offered = {str(work) for work in turned_down}, 0
    for work in waiting:
        if await offer_work(db, work["ticket_id"], work["id"], CLIENT_ID, eta_at=work["scheduled_at"]):
            offered += 1
        elif str(work["id"]) in said:
            await agent_event(db, work["ticket_id"], CLIENT_ID, "work_order.unassigned", {"workOrderId": str(work["id"])})
    return offered


async def expire_offers(db) -> int:
    """Sweep step: an offer of platform-dispatched work that ran out is ended and said once, then the work that waits
    (this and any other) goes to whoever can take it. Returns how many offers ran out."""
    expired = (await db.execute(text(f"""
        select a.id,a.work_order_id,w.ticket_id from work_assignments a
        join work_orders w on w.id=a.work_order_id and w.tenant_id=a.tenant_id
        join platform_operations po on po.work_order_id=w.id and po.tenant_id=w.tenant_id
        join tickets t on t.id=w.ticket_id and t.tenant_id=w.tenant_id
        where a.tenant_id={TENANT} and a.status='offered' and a.offer_expires_at<=now() and w.status='offered'
        order by a.offer_expires_at,a.id for update of t,w,a skip locked
    """))).mappings().all()
    for offer in expired:
        await db.execute(text("update work_assignments set status='released',ended_at=now(),updated_at=now() where id=:id"), {"id": offer["id"]})
        await db.execute(text("update work_orders set status='queued',version=version+1,updated_at=now() where id=:id"), {"id": offer["work_order_id"]})
        await agent_event(db, offer["ticket_id"], CLIENT_ID, "work_assignment.expired", {
            "assignmentId": str(offer["id"]), "workOrderId": str(offer["work_order_id"])})
    await offer_waiting(db, {offer["work_order_id"] for offer in expired})
    return len(expired)
