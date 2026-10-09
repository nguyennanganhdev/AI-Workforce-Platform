"""What staff do about homes: gates, the front desk, amenity closures and notices.

Staff routes use the operations sign-in (a management or staff role). Deciding is for people; the routes an
agent may reach are the ones registered at the bottom, and none of them decides.
"""

import json
import secrets
from datetime import datetime, timezone
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .events import emit
from .integration import Tool, register
from .resident_services import request_event
from .zone_rules import unit_rules
from .unit_access import UNIT_VISIBILITY, delegated, require_management, staff_unit
from .v3_audit import audit
from .v3_auth import scoped_connection

router = APIRouter(tags=["Operations services"])
Staff = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection)]
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"


# ---------- gates ----------


class Scan(BaseModel):
    qr_token: str = Field(min_length=8, max_length=200)
    gate_code: str = Field(min_length=1, max_length=40)
    direction: Literal["in", "out"] = "in"


async def log_access(db, user, gate, direction, kind, result, reason=None, card_id=None, pass_id=None, plate=None):
    await db.execute(text(f"""
        insert into access_events(tenant_id,gate_code,direction,credential_kind,access_card_id,visitor_pass_id,vehicle_plate_no,result,deny_reason,guard_user_id)
        values({TENANT},:gate,:direction,:kind,:card,:pass,:plate,:result,:reason,:guard)
    """), {"gate": gate, "direction": direction, "kind": kind, "card": card_id, "pass": pass_id, "plate": plate,
           "result": result, "reason": reason, "guard": user})


@router.post("/operations/gate/scan")
async def gate_scan(body: Scan, scope: Staff):
    """A guard scans a visitor's QR. The answer is always written to the gate log, granted or not."""
    db, user, _ = scope
    row = (await db.execute(text(f"""
        select p.id,p.code,p.status,p.guest_name,p.guest_count,p.vehicle_plate_no,p.visit_from,p.visit_to,u.code as unit_code,
               p.unit_id,now() as now from visitor_passes p join units u on u.id=p.unit_id and u.tenant_id=p.tenant_id
        where p.tenant_id={TENANT} and p.qr_token=:qr for update of p
    """), {"qr": body.qr_token})).mappings().first()
    if row is None:
        await log_access(db, user, body.gate_code, body.direction, "qr_pass", "denied", "unknown_qr")
        return {"result": "denied", "reason": "unknown_qr"}
    reason, granted = None, False
    if body.direction == "in":
        if row["status"] == "approved":
            if row["now"] > row["visit_to"]:
                await db.execute(text("update visitor_passes set status='expired' where id=:id"), {"id": row["id"]})
                reason = "expired"
            elif (row["visit_from"] - row["now"]).total_seconds() > (await unit_rules(db, row["unit_id"]))["visit_early_minutes"] * 60:
                reason = "too_early"
            else:
                await db.execute(text("update visitor_passes set status='checked_in' where id=:id"), {"id": row["id"]})
                granted = True
        else:
            reason = {"checked_in": "already_inside", "pending_approval": "not_approved"}.get(row["status"], f"pass_{row['status']}")
    else:
        if row["status"] == "checked_in":
            await db.execute(text("update visitor_passes set status='checked_out' where id=:id"), {"id": row["id"]})
            granted = True
        else:
            reason = "not_inside"
    await log_access(db, user, body.gate_code, body.direction, "qr_pass", "granted" if granted else "denied", reason, pass_id=row["id"], plate=row["vehicle_plate_no"])
    return {"result": "granted" if granted else "denied", "reason": reason,
            "pass": {"code": row["code"], "guest_name": row["guest_name"], "guest_count": row["guest_count"], "unit_code": row["unit_code"],
                     "vehicle_plate_no": row["vehicle_plate_no"]}}


class Swipe(BaseModel):
    card_no: str = Field(min_length=1, max_length=60)
    gate_code: str = Field(min_length=1, max_length=40)
    direction: Literal["in", "out"] = "in"


@router.post("/operations/gate/swipe")
async def gate_swipe(body: Swipe, scope: Staff):
    db, user, _ = scope
    card = (await db.execute(text(f"""
        select c.id,c.status,c.kind,c.valid_from,c.valid_to,v.plate_no from access_cards c
        left join vehicles v on v.id=c.vehicle_id and v.tenant_id=c.tenant_id where c.tenant_id={TENANT} and c.card_no=:no
    """), {"no": body.card_no})).mappings().first()
    if card is None:
        await log_access(db, user, body.gate_code, body.direction, "card", "denied", "unknown_card")
        return {"result": "denied", "reason": "unknown_card"}
    today = (await db.execute(text("select current_date"))).scalar_one()
    reason = None
    if card["status"] != "active":
        reason = f"card_{card['status']}"
    elif card["valid_from"] and today < card["valid_from"]:
        reason = "not_yet_valid"
    elif card["valid_to"] and today > card["valid_to"]:
        reason = "card_expired"
    await log_access(db, user, body.gate_code, body.direction, "card", "denied" if reason else "granted", reason, card_id=card["id"], plate=card["plate_no"])
    return {"result": "denied" if reason else "granted", "reason": reason}


class Decision(BaseModel):
    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=2000)


@router.post("/operations/visitor-passes/{pass_id}/decision")
async def visitor_decision(pass_id: UUID, body: Decision, scope: Staff):
    db, user, _ = scope
    row = (await db.execute(text(f"select id,unit_id,status,code from visitor_passes where tenant_id={TENANT} and id=:id for update"), {"id": pass_id})).mappings().first()
    if row is None:
        raise HTTPException(404, "Visitor pass not found")
    await staff_unit(scope, row["unit_id"])
    if row["status"] != "pending_approval":
        raise HTTPException(409, f"A visit that is {row['status']} cannot be decided")
    staff_id = (await db.execute(text(f"select id from staff_profiles where tenant_id={TENANT} and user_id=:u"), {"u": user})).scalar_one_or_none()
    if body.decision == "approve":
        await db.execute(text("update visitor_passes set status='approved',qr_token=:qr,approved_by_staff_id=:s where id=:id"),
                         {"id": pass_id, "qr": secrets.token_urlsafe(24), "s": staff_id})
    else:
        await db.execute(text("update visitor_passes set status='rejected',approved_by_staff_id=:s where id=:id"), {"id": pass_id, "s": staff_id})
    await audit(db, user, f"visitor_pass.{body.decision}d", "visitor_pass", str(pass_id), {"code": row["code"], "note": body.note})
    return {"id": pass_id, "status": "approved" if body.decision == "approve" else "rejected"}


# ---------- the front desk ----------

DESK_FIELDS = "r.id,r.code,r.kind,r.unit_id,u.code as unit_code,r.requester_user_id,r.status,r.priority,r.details,r.submitted_at,r.sla_due_at,r.decision_note,r.fulfilled_at,r.created_at"


@router.get("/operations/service-requests")
async def desk_requests(scope: Staff, status: str | None = Query(default=None, max_length=30), limit: int = Query(50, ge=1, le=100)):
    db, user, is_admin = scope
    rows = await db.execute(text(f"""
        select {DESK_FIELDS} from service_requests r join units u on u.id=r.unit_id and u.tenant_id=r.tenant_id
        where r.tenant_id={TENANT} and r.status<>'draft' and (cast(:status as text) is null or r.status=:status) and {UNIT_VISIBILITY}
        order by r.sla_due_at nulls last, r.created_at limit :limit
    """), {"status": status, "user_id": user, "is_admin": is_admin, "limit": limit})
    return {"items": [dict(r) for r in rows.mappings()]}


class Transition(BaseModel):
    to_status: Literal["in_review", "need_more_info", "approved", "rejected", "fulfilled"]
    note: str | None = Field(default=None, max_length=2000)


async def fulfil_card_request(db, request, staff_id, user):
    """Hand over what an approved card request asked for, inside the same transaction as the status change."""
    details = request["details"] if isinstance(request["details"], dict) else json.loads(request["details"])
    old = None
    if request["kind"] in ("card_reissue", "card_cancel"):
        old = (await db.execute(text(f"select id,kind,vehicle_id,holder_user_id,holder_name,status,monthly_fee from access_cards where tenant_id={TENANT} and id=cast(:id as uuid) and unit_id=:unit for update"),
                                {"id": details.get("card_id"), "unit": request["unit_id"]})).mappings().first()
        if old is None:
            raise HTTPException(409, "The card named in this request is no longer on the home")
    if request["kind"] == "card_cancel":
        await db.execute(text("update access_cards set status='revoked' where id=:id"), {"id": old["id"]})
        return {"revoked_card_id": str(old["id"])}
    kind = old["kind"] if old else details.get("card_kind", "resident")
    if kind not in ("resident", "vehicle"):
        raise HTTPException(409, "Only resident and vehicle cards are issued from a request")
    limit = (await unit_rules(db, request["unit_id"]))[f"card_limit_{kind}"]
    live = (await db.execute(text(f"select count(*) from access_cards where tenant_id={TENANT} and unit_id=:unit and kind=:kind and status in ('pending_issue','active','suspended') and (cast(:old as uuid) is null or id<>cast(:old as uuid))"),
                             {"unit": request["unit_id"], "kind": kind, "old": str(old["id"]) if old else None})).scalar_one()
    if live >= limit:
        raise HTTPException(409, f"This home already holds {limit} {kind} cards")
    number = "C-" + datetime.now(timezone.utc).strftime("%y%m%d") + "-" + secrets.token_hex(3).upper()
    created = (await db.execute(text(f"""
        insert into access_cards(tenant_id,card_no,kind,holder_user_id,holder_name,unit_id,vehicle_id,status,monthly_fee)
        values({TENANT},:no,:kind,:holder,:name,:unit,:vehicle,'pending_issue',:fee) returning id
    """), {"no": number, "kind": kind, "holder": old["holder_user_id"] if old else request["requester_user_id"], "name": old["holder_name"] if old else None,
           "unit": request["unit_id"], "vehicle": old["vehicle_id"] if old else None, "fee": old["monthly_fee"] if old else None})).scalar_one()
    await db.execute(text("update access_cards set status='active',issued_at=now(),issued_by_staff_id=:s,valid_from=current_date where id=:id"), {"id": created, "s": staff_id})
    if old and old["status"] != "revoked":
        await db.execute(text("update access_cards set status='revoked' where id=:id"), {"id": old["id"]})
    return {"issued_card_id": str(created), **({"revoked_card_id": str(old["id"])} if old else {})}


@router.post("/operations/service-requests/{request_id}/transition")
async def desk_transition(request_id: UUID, body: Transition, scope: Staff):
    db, user, is_admin = scope
    row = (await db.execute(text(f"select * from service_requests where tenant_id={TENANT} and id=:id for update"), {"id": request_id})).mappings().first()
    if row is None:
        raise HTTPException(404, "Request not found")
    await staff_unit(scope, row["unit_id"])
    allowed = (await db.execute(text("select actors from state_transitions where entity='service_requests' and from_status=:f and to_status=:t"),
                                {"f": row["status"], "t": body.to_status})).scalar_one_or_none()
    if allowed is None or not set(allowed) & {"staff", "manager"}:
        raise HTTPException(409, f"A request that is {row['status']} cannot go to {body.to_status} by staff")
    if body.to_status == "rejected" and not body.note:
        raise HTTPException(422, "A rejection needs a reason")
    staff_id = (await db.execute(text(f"select id from staff_profiles where tenant_id={TENANT} and user_id=:u"), {"u": user})).scalar_one_or_none()
    result: dict[str, Any] = {}
    if body.to_status == "fulfilled":
        if row["kind"] in ("card_issue", "card_reissue", "card_cancel"):
            result = await fulfil_card_request(db, dict(row), staff_id, user)
        await db.execute(text("update service_requests set status='fulfilled',fulfilled_at=now(),details=details||cast(:r as jsonb) where id=:id"),
                         {"id": request_id, "r": json.dumps(result)})
    elif body.to_status in ("approved", "rejected"):
        await db.execute(text("update service_requests set status=:s,decided_by_staff_id=:staff,decided_at=now(),decision_note=:note where id=:id"),
                         {"id": request_id, "s": body.to_status, "staff": staff_id, "note": body.note})
    else:
        await db.execute(text("update service_requests set status=:s,assigned_staff_id=coalesce(assigned_staff_id,:staff),decision_note=coalesce(:note,decision_note) where id=:id"),
                         {"id": request_id, "s": body.to_status, "staff": staff_id, "note": body.note})
    await request_event(db, request_id, "staff", user, None, row["status"], body.to_status, body.note)
    await audit(db, user, "service_request.transitioned", "service_request", str(request_id), {"code": row["code"], "from": row["status"], "to": body.to_status})
    return {"id": request_id, "status": body.to_status, **result}


# ---------- amenities ----------


class Closure(BaseModel):
    from_ts: AwareDatetime
    to_ts: AwareDatetime
    reason: str = Field(min_length=1, max_length=500)


@router.post("/operations/amenities/{amenity_id}/closures", status_code=201)
async def close_amenity(amenity_id: UUID, body: Closure, scope: Staff):
    """Closing an amenity cancels the live bookings it cuts across and tells the people who made them."""
    db, user, _ = scope
    await require_management(scope)
    if body.to_ts <= body.from_ts:
        raise HTTPException(422, "The closure must end after it starts")
    if (await db.execute(text(f"select 1 from amenities where tenant_id={TENANT} and id=:id"), {"id": amenity_id})).first() is None:
        raise HTTPException(404, "Amenity not found")
    closure = (await db.execute(text(f"""
        insert into amenity_closures(tenant_id,amenity_id,from_ts,to_ts,reason,created_by_user_id) values({TENANT},:a,:f,:t,:r,:u) returning id
    """), {"a": amenity_id, "f": body.from_ts, "t": body.to_ts, "r": body.reason, "u": user})).scalar_one()
    hit = (await db.execute(text(f"""
        update amenity_bookings set status='cancelled',cancelled_at=now(),cancelled_by='system',cancel_reason=:reason
        where tenant_id={TENANT} and amenity_id=:a and status in ('pending_payment','confirmed') and tstzrange(start_at,end_at) && tstzrange(:f,:t)
        returning id,code,booked_by_user_id
    """), {"a": amenity_id, "f": body.from_ts, "t": body.to_ts, "reason": "Tiện ích đóng cửa: " + body.reason})).mappings().all()
    for booking in hit:
        await db.execute(text(f"""
            insert into notification_deliveries(tenant_id,user_id,channel,dedupe_key,payload,status,available_at)
            values({TENANT},:u,'in_app',:key,cast(:payload as jsonb),'pending',now()) on conflict do nothing
        """), {"u": booking["booked_by_user_id"], "key": f"closure:{closure}:{booking['id']}",
               "payload": json.dumps({"type": "amenity_booking.cancelled_by_closure", "bookingCode": booking["code"], "reason": body.reason})})
        await emit(db, "amenity_booking.cancelled_by_closure", {"bookingId": str(booking["id"]), "closureId": str(closure)}, dedupe_key=f"closure:{closure}:{booking['id']}")
    await audit(db, user, "amenity_closure.created", "amenity_closure", str(closure), {"amenity": str(amenity_id), "cancelled": len(hit)})
    return {"id": closure, "cancelled_bookings": len(hit)}


# ---------- notices ----------


class AnnouncementDraft(BaseModel):
    kind: Literal["news", "bulletin", "urgent_notice", "outage_notice", "event_notice", "fee_notice"]
    title: str = Field(min_length=1, max_length=300)
    summary: str | None = Field(default=None, max_length=1000)
    body_md: str = Field(min_length=1, max_length=20000)
    is_important: bool = False
    effective_from: AwareDatetime | None = None
    effective_to: AwareDatetime | None = None
    zone_ids: list[UUID] = Field(default_factory=list, max_length=50)
    building_ids: list[UUID] = Field(default_factory=list, max_length=200)


@router.post("/operations/announcements", status_code=201)
async def draft_announcement(body: AnnouncementDraft, scope: Staff):
    db, user, _ = scope
    if body.effective_from and body.effective_to and body.effective_to <= body.effective_from:
        raise HTTPException(422, "effective_to must be after effective_from")
    d = delegated()
    row = (await db.execute(text(f"""
        insert into announcements(tenant_id,code,kind,title,summary,body_md,is_important,status,effective_from,effective_to,zone_ids,building_ids,
                                  author_user_id,drafted_by,drafted_by_client_id)
        values({TENANT},:code,:kind,:title,:summary,:body,:imp,'draft',:f,:t,:zones,:buildings,:user,:by,:client)
        returning id,code,kind,title,status,drafted_by,zone_ids,building_ids,effective_from,effective_to
    """), {"code": "AN-" + datetime.now(timezone.utc).strftime("%y%m%d") + "-" + secrets.token_hex(3).upper(), "kind": body.kind, "title": body.title,
           "summary": body.summary, "body": body.body_md, "imp": body.is_important, "f": body.effective_from, "t": body.effective_to,
           "zones": body.zone_ids, "buildings": body.building_ids, "user": user, "by": "agent" if d else "staff",
           "client": d["client_id"] if d else None})).mappings().one()
    await audit(db, user, "announcement.drafted", "announcement", str(row["id"]), {"code": row["code"], "kind": body.kind})
    return dict(row)


@router.get("/operations/announcements")
async def list_announcements(scope: Staff, status: str | None = Query(default=None, max_length=20), limit: int = Query(50, ge=1, le=100)):
    db, _, _ = scope
    rows = await db.execute(text(f"""
        select id,code,kind,title,status,drafted_by,zone_ids,building_ids,effective_from,effective_to,published_at,created_at
        from announcements where tenant_id={TENANT} and (cast(:status as text) is null or status=:status) order by created_at desc limit :limit
    """), {"status": status, "limit": limit})
    return {"items": [dict(r) for r in rows.mappings()]}


@router.post("/operations/announcements/{announcement_id}/publish")
async def publish_announcement(announcement_id: UUID, scope: Staff):
    """Publishing is management's: it tells the residents of the buildings it names, once each."""
    db, user, _ = scope
    await require_management(scope)
    row = (await db.execute(text(f"select id,code,title,kind,status,zone_ids,building_ids from announcements where tenant_id={TENANT} and id=:id for update"), {"id": announcement_id})).mappings().first()
    if row is None:
        raise HTTPException(404, "Announcement not found")
    if row["status"] == "published":
        return {"id": announcement_id, "status": "published", "notified": 0, "already_published": True}
    if row["status"] not in ("draft", "scheduled"):
        raise HTTPException(409, f"An announcement that is {row['status']} cannot be published")
    await db.execute(text("update announcements set status='published',published_at=now(),author_user_id=coalesce(author_user_id,:u) where id=:id"), {"id": announcement_id, "u": user})
    sent = await db.execute(text(f"""
        insert into notification_deliveries(tenant_id,user_id,channel,dedupe_key,payload,status,available_at)
        select distinct {TENANT}, ur.user_id, 'in_app', cast(:key as text) || ur.user_id, cast(:payload as jsonb), 'pending', now()
        from unit_residents ur join units u on u.id=ur.unit_id and u.tenant_id=ur.tenant_id
        join users usr on usr.id=ur.user_id and usr.status='active'
        join tenant_memberships m on m.user_id=ur.user_id and m.tenant_id=ur.tenant_id and m.status='active'
        where ur.tenant_id={TENANT} and ur.verification_status='verified' and ur.valid_from<=now() and (ur.valid_to is null or ur.valid_to>now())
          and ((cardinality(cast(:zones as uuid[]))=0 and cardinality(cast(:buildings as uuid[]))=0)
               or u.building_id=any(cast(:buildings as uuid[])) or u.zone_id=any(cast(:zones as uuid[])))
        on conflict do nothing returning id
    """), {"key": f"announcement:{announcement_id}:", "zones": row["zone_ids"], "buildings": row["building_ids"],
           "payload": json.dumps({"type": "announcement.published", "announcementId": str(announcement_id), "kind": row["kind"], "title": row["title"]})})
    notified = len(sent.all())
    await emit(db, "announcement.published", {"announcementId": str(announcement_id), "code": row["code"], "kind": row["kind"]}, dedupe_key=f"announcement:{announcement_id}:published")
    await audit(db, user, "announcement.published", "announcement", str(announcement_id), {"code": row["code"], "notified": notified})
    return {"id": announcement_id, "status": "published", "notified": notified}


register(
    Tool("staff.announcements.list", "staff", "read", "GET", "/operations/announcements", "Notices, drafts included"),
    Tool("staff.announcements.draft", "staff", "draft", "POST", "/operations/announcements", "Prepare a notice; management publishes it"),
    Tool("staff.service_requests.list", "staff", "read", "GET", "/operations/service-requests", "Requests waiting at the front desk"),
)
