"""What a resident does about their home: what is owed, visitors, cards, requests to the desk, amenities, renovation.

Each home-scoped route names the home in its path. A person with two homes picks one; nothing is merged for them.
An agent acting for the person reaches only the routes registered at the bottom, at the level written there.
"""

import json
import secrets
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .events import emit
from .integration import Tool, register
from .unit_access import ANSWERABLE, delegated, for_agent, my_units, resident_unit
from .zone_rules import unit_rules
from .v3_audit import audit
from .v3_auth import resident_connection

router = APIRouter(tags=["Resident services"])
Resident = Annotated[tuple[AsyncConnection, str], Depends(resident_connection)]
Key = Annotated[str | None, Header(alias="Idempotency-Key", max_length=160)]
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
REQUEST_HOURS = {"goods_move": 24, "card_issue": 48, "card_reissue": 48, "card_cancel": 48}


def mask(value: str | None) -> str | None:
    return None if value is None else "*" * max(len(value) - 4, 0) + value[-4:]


def acting() -> tuple[str, str | None]:
    """How the actor is recorded on a row: a person, or an agent for them."""
    d = delegated()
    return ("agent", d["client_id"]) if d else ("resident", None)


# ---------- what is owed ----------

EFFECTIVE = """case when n.status in ('issued','partially_paid') and n.due_date < current_date then 'overdue' else n.status end"""


@router.get("/resident/units/{unit_id}/debit-notes")
async def debit_notes(unit_id: UUID, scope: Resident, status: Literal["open", "paid", "all"] = "all", limit: int = Query(50, ge=1, le=100)):
    db, user = scope
    unit = await resident_unit(db, user, unit_id, ANSWERABLE)
    rows = await db.execute(text(f"""
        select n.id,n.doc_no,n.period_month,n.kind,n.issue_date,n.due_date,n.subtotal,n.vat_amount,n.total_amount,n.paid_amount,
               n.total_amount-n.paid_amount as outstanding, {EFFECTIVE} as status
        from debit_notes n where n.tenant_id={TENANT} and n.unit_id=:unit and n.status not in ('draft','cancelled')
          and (:which='all' or (:which='paid' and n.status='paid') or (:which='open' and n.status<>'paid'))
        order by n.issue_date desc, n.doc_no limit :limit
    """), {"unit": unit_id, "which": status, "limit": limit})
    return {"unit": {"id": unit["id"], "code": unit["code"]}, "items": [dict(r) for r in rows.mappings()]}


@router.get("/resident/units/{unit_id}/debit-notes/{note_id}")
async def debit_note(unit_id: UUID, note_id: UUID, scope: Resident):
    db, user = scope
    await resident_unit(db, user, unit_id, ANSWERABLE)
    note = (await db.execute(text(f"""
        select n.id,n.doc_no,n.period_month,n.kind,n.issue_date,n.due_date,n.subtotal,n.vat_amount,n.total_amount,n.paid_amount,
               n.total_amount-n.paid_amount as outstanding, {EFFECTIVE} as status, n.note
        from debit_notes n where n.tenant_id={TENANT} and n.unit_id=:unit and n.id=:id and n.status not in ('draft','cancelled')
    """), {"unit": unit_id, "id": note_id})).mappings().first()
    if note is None:
        raise HTTPException(404, "Debit note not found")
    lines = await db.execute(text(f"select line_no,fee_kind,description,quantity,unit_price,vat_rate,amount,service_from,service_to from debit_note_lines where tenant_id={TENANT} and debit_note_id=:id order by line_no"), {"id": note_id})
    return {**dict(note), "lines": [dict(r) for r in lines.mappings()]}


@router.get("/resident/units/{unit_id}/balance")
async def balance(unit_id: UUID, scope: Resident):
    db, user = scope
    unit = await resident_unit(db, user, unit_id, ANSWERABLE)
    row = (await db.execute(text(f"""
        select coalesce(sum(n.total_amount-n.paid_amount) filter (where n.status<>'paid'),0) as outstanding,
               coalesce(sum(n.total_amount-n.paid_amount) filter (where {EFFECTIVE}='overdue'),0) as overdue,
               count(*) filter (where n.status<>'paid') as open_notes,
               count(*) filter (where {EFFECTIVE}='overdue') as overdue_notes,
               min(n.due_date) filter (where n.status<>'paid') as next_due_date
        from debit_notes n where n.tenant_id={TENANT} and n.unit_id=:unit and n.status not in ('draft','cancelled')
    """), {"unit": unit_id})).mappings().one()
    return {"unit": {"id": unit["id"], "code": unit["code"]}, "currency": "VND", **dict(row)}


# ---------- visitors ----------


class VisitorCreate(BaseModel):
    guest_name: str = Field(min_length=1, max_length=200)
    guest_phone: str | None = Field(default=None, max_length=30)
    guest_count: int = Field(default=1, ge=1, le=50)
    purpose: Literal["family_visit", "delivery", "service_provider", "business", "other"]
    vehicle_plate_no: str | None = Field(default=None, max_length=20)
    visit_from: AwareDatetime
    visit_to: AwareDatetime


PASS_FIELDS = "id,code,unit_id,guest_name,guest_phone,guest_count,purpose,vehicle_plate_no,visit_from,visit_to,qr_token,status,created_at"


def pass_view(row: dict) -> dict:
    return for_agent(dict(row), "qr_token")


@router.post("/resident/units/{unit_id}/visitor-passes", status_code=201)
async def create_visitor_pass(unit_id: UUID, body: VisitorCreate, scope: Resident, key: Key = None):
    db, user = scope
    unit = await resident_unit(db, user, unit_id)
    rules = await unit_rules(db, unit_id)
    now = datetime.now(timezone.utc)
    if body.visit_to <= body.visit_from or body.visit_to <= now:
        raise HTTPException(422, "The visit must end in the future and after it starts")
    days_ahead, hours = rules["visit_max_days_ahead"], rules["visit_max_hours"]
    if body.visit_from > now + timedelta(days=days_ahead) or body.visit_to - body.visit_from > timedelta(hours=hours):
        raise HTTPException(422, f"A visit may be announced {days_ahead} days ahead and last {hours} hours at most")
    if key:
        old = (await db.execute(text(f"select {PASS_FIELDS},host_user_id from visitor_passes where tenant_id={TENANT} and idempotency_key=:key"), {"key": f"{user}:{key}"})).mappings().first()
        if old:
            if old["unit_id"] != unit_id or old["guest_name"] != body.guest_name or old["visit_from"] != body.visit_from:
                raise HTTPException(409, "That Idempotency-Key was used for a different visitor")
            return pass_view(old)
    active = (await db.execute(text(f"select count(*) from visitor_passes where tenant_id={TENANT} and unit_id=:unit and status in ('pending_approval','approved','checked_in') and visit_to>now()"), {"unit": unit_id})).scalar_one()
    if active >= rules["visit_max_waiting"]:
        raise HTTPException(409, f"This home already has {rules['visit_max_waiting']} visits waiting; cancel one first")
    d = delegated()
    row = (await db.execute(text(f"""
        insert into visitor_passes(tenant_id,code,unit_id,host_user_id,guest_name,guest_phone,guest_count,purpose,vehicle_plate_no,
                                   visit_from,visit_to,status,created_by_client_id,idempotency_key)
        values({TENANT},:code,:unit,:user,:name,:phone,:count,:purpose,:plate,:from,:to,'pending_approval',:client,:key) returning {PASS_FIELDS}
    """), {"code": "VP-" + now.strftime("%y%m%d") + "-" + secrets.token_hex(3).upper(), "unit": unit_id, "user": user,
           "name": body.guest_name, "phone": body.guest_phone, "count": body.guest_count, "purpose": body.purpose,
           "plate": body.vehicle_plate_no, "from": body.visit_from, "to": body.visit_to,
           "client": d["client_id"] if d else None, "key": f"{user}:{key}" if key else None})).mappings().one()
    # The zone decides which visits need no approval (by purpose and number of people); the rest wait for the desk.
    if body.purpose in rules["visit_auto_approve_purposes"] and body.guest_count <= rules["visit_auto_approve_max_guests"]:
        row = (await db.execute(text(f"update visitor_passes set status='approved',qr_token=:qr where id=:id returning {PASS_FIELDS}"),
                                {"id": row["id"], "qr": secrets.token_urlsafe(24)})).mappings().one()
    await audit(db, user, "visitor_pass.created", "visitor_pass", str(row["id"]), {"code": row["code"], "status": row["status"], "unit": unit["code"]})
    await emit(db, "visitor_pass.created", {"passId": str(row["id"]), "code": row["code"], "unitCode": unit["code"], "status": row["status"]})
    return pass_view(row)


@router.get("/resident/units/{unit_id}/visitor-passes")
async def visitor_passes(unit_id: UUID, scope: Resident, limit: int = Query(50, ge=1, le=100)):
    db, user = scope
    await resident_unit(db, user, unit_id)
    rows = await db.execute(text(f"select {PASS_FIELDS} from visitor_passes where tenant_id={TENANT} and unit_id=:unit order by visit_from desc limit :limit"), {"unit": unit_id, "limit": limit})
    return {"items": [pass_view(r) for r in rows.mappings()]}


@router.post("/resident/visitor-passes/{pass_id}/cancel")
async def cancel_visitor_pass(pass_id: UUID, scope: Resident):
    db, user = scope
    row = (await db.execute(text(f"select id,unit_id,status,code from visitor_passes where tenant_id={TENANT} and id=:id for update"), {"id": pass_id})).mappings().first()
    if row is None:
        raise HTTPException(404, "Visitor pass not found")
    await resident_unit(db, user, row["unit_id"])
    if row["status"] not in ("pending_approval", "approved"):
        raise HTTPException(409, f"A visit that is {row['status']} cannot be cancelled")
    await db.execute(text("update visitor_passes set status='cancelled' where id=:id"), {"id": pass_id})
    await audit(db, user, "visitor_pass.cancelled", "visitor_pass", str(pass_id), {"code": row["code"]})
    return {"id": pass_id, "status": "cancelled"}


# ---------- cards ----------


@router.get("/resident/units/{unit_id}/cards")
async def cards(unit_id: UUID, scope: Resident):
    db, user = scope
    await resident_unit(db, user, unit_id)
    rows = await db.execute(text(f"""
        select c.id,c.card_no,c.kind,c.status,c.holder_name,c.valid_from,c.valid_to,c.monthly_fee,
               v.kind as vehicle_kind,v.plate_no as vehicle_plate_no
        from access_cards c left join vehicles v on v.id=c.vehicle_id and v.tenant_id=c.tenant_id
        where c.tenant_id={TENANT} and c.unit_id=:unit order by c.kind,c.card_no
    """), {"unit": unit_id})
    items = []
    for r in rows.mappings():
        item = dict(r)
        if delegated() is not None:
            item["card_no"] = mask(item["card_no"])
        items.append(item)
    return {"items": items}


@router.post("/resident/cards/{card_id}/report-lost")
async def report_lost(card_id: UUID, scope: Resident):
    db, user = scope
    card = (await db.execute(text(f"select id,unit_id,status,card_no from access_cards where tenant_id={TENANT} and id=:id for update"), {"id": card_id})).mappings().first()
    if card is None or card["unit_id"] is None:
        raise HTTPException(404, "Card not found")
    await resident_unit(db, user, card["unit_id"])
    if card["status"] != "active":
        raise HTTPException(409, f"A card that is {card['status']} cannot be reported lost")
    await db.execute(text("update access_cards set status='lost' where id=:id"), {"id": card_id})
    await audit(db, user, "access_card.reported_lost", "access_card", str(card_id), {"card": mask(card["card_no"])})
    return {"id": card_id, "status": "lost"}


# ---------- requests to the desk ----------


class RequestDraft(BaseModel):
    kind: Literal["card_issue", "card_reissue", "card_cancel", "goods_move", "resident_register", "resident_update", "resident_remove", "other"]
    details: dict[str, Any] = Field(default_factory=dict)
    note: str | None = Field(default=None, max_length=2000)


async def request_event(db, request_id, actor_kind, user, client, from_status, to_status, note=None):
    await db.execute(text(f"""
        insert into service_request_events(tenant_id,service_request_id,actor_kind,actor_user_id,actor_client_id,from_status,to_status,note)
        values({TENANT},:id,:kind,:user,:client,:from,:to,:note)
    """), {"id": request_id, "kind": actor_kind, "user": user, "client": client, "from": from_status, "to": to_status, "note": note})


REQUEST_FIELDS = "id,code,kind,unit_id,status,priority,details,submitted_at,sla_due_at,decision_note,fulfilled_at,cancelled_at,fee_amount,created_at"


@router.post("/resident/units/{unit_id}/service-requests", status_code=201)
async def draft_request(unit_id: UUID, body: RequestDraft, scope: Resident, key: Key = None):
    db, user = scope
    await resident_unit(db, user, unit_id)
    if len(json.dumps(body.details)) > 4000:
        raise HTTPException(422, "details is too large")
    if body.kind in ("card_reissue", "card_cancel"):
        try:
            card_id = UUID(str(body.details.get("card_id")))
        except ValueError:
            raise HTTPException(422, "details.card_id is required") from None
        card = (await db.execute(text(f"select status from access_cards where tenant_id={TENANT} and id=:id and unit_id=:unit"), {"id": card_id, "unit": unit_id})).mappings().first()
        if card is None:
            raise HTTPException(404, "That card is not on this home")
        if card["status"] not in ("lost", "active", "suspended"):
            raise HTTPException(409, f"A card that is {card['status']} cannot be replaced or cancelled")
    if key:
        old = (await db.execute(text(f"select {REQUEST_FIELDS},requester_user_id from service_requests where tenant_id={TENANT} and idempotency_key=:key"), {"key": f"{user}:{key}"})).mappings().first()
        if old:
            if old["unit_id"] != unit_id or old["kind"] != body.kind:
                raise HTTPException(409, "That Idempotency-Key was used for a different request")
            return {k: v for k, v in dict(old).items() if k != "requester_user_id"}
    kind, client = acting()
    d = delegated()
    now = datetime.now(timezone.utc)
    row = (await db.execute(text(f"""
        insert into service_requests(tenant_id,code,kind,unit_id,requester_user_id,channel,status,details,created_by_client_id,idempotency_key)
        values({TENANT},:code,:kind,:unit,:user,:channel,'draft',cast(:details as jsonb),:client,:key) returning {REQUEST_FIELDS}
    """), {"code": "SR-" + now.strftime("%y%m%d") + "-" + secrets.token_hex(3).upper(), "kind": body.kind, "unit": unit_id, "user": user,
           "channel": "agent" if d else "app", "details": json.dumps({**body.details, **({"note": body.note} if body.note else {})}),
           "client": client, "key": f"{user}:{key}" if key else None})).mappings().one()
    await request_event(db, row["id"], kind, user, client, None, "draft")
    await audit(db, user, "service_request.drafted", "service_request", str(row["id"]), {"code": row["code"], "kind": body.kind})
    return dict(row)


@router.get("/resident/units/{unit_id}/service-requests")
async def list_requests(unit_id: UUID, scope: Resident, limit: int = Query(50, ge=1, le=100)):
    db, user = scope
    await resident_unit(db, user, unit_id)
    rows = await db.execute(text(f"select {REQUEST_FIELDS} from service_requests where tenant_id={TENANT} and unit_id=:unit order by created_at desc limit :limit"), {"unit": unit_id, "limit": limit})
    return {"items": [dict(r) for r in rows.mappings()]}


async def own_request(db, user, request_id):
    row = (await db.execute(text(f"select id,unit_id,kind,status,code from service_requests where tenant_id={TENANT} and id=:id for update"), {"id": request_id})).mappings().first()
    if row is None:
        raise HTTPException(404, "Request not found")
    await resident_unit(db, user, row["unit_id"])
    return row


@router.post("/resident/service-requests/{request_id}/submit")
async def submit_request(request_id: UUID, scope: Resident):
    """Sending a draft is the resident's own act: it is not offered to agents."""
    db, user = scope
    row = await own_request(db, user, request_id)
    if row["status"] != "draft":
        raise HTTPException(409, f"A request that is {row['status']} cannot be submitted")
    hours = REQUEST_HOURS.get(row["kind"], 72)
    await db.execute(text("update service_requests set status='submitted',submitted_at=now(),sla_due_at=now()+make_interval(hours=>:h) where id=:id"), {"id": request_id, "h": hours})
    await request_event(db, request_id, "resident", user, None, "draft", "submitted")
    await audit(db, user, "service_request.submitted", "service_request", str(request_id), {"code": row["code"]})
    return {"id": request_id, "status": "submitted"}


@router.post("/resident/service-requests/{request_id}/cancel")
async def cancel_request(request_id: UUID, scope: Resident):
    db, user = scope
    row = await own_request(db, user, request_id)
    if row["status"] not in ("submitted", "in_review", "need_more_info", "approved"):
        raise HTTPException(409, f"A request that is {row['status']} cannot be cancelled")
    await db.execute(text("update service_requests set status='cancelled',cancelled_at=now() where id=:id"), {"id": request_id})
    await request_event(db, request_id, "resident", user, None, row["status"], "cancelled")
    await audit(db, user, "service_request.cancelled", "service_request", str(request_id), {"code": row["code"]})
    return {"id": request_id, "status": "cancelled"}


# ---------- amenities ----------

AMENITY_FIELDS = "a.id,a.code,a.name,a.category,a.booking_mode,a.areas,a.price,a.slot_minutes,a.open_time,a.close_time,a.open_weekdays,a.max_advance_days,a.cancel_before_hours,a.weekly_quota_per_unit,a.max_guests,a.rules_note,a.status"
TZ = "coalesce(s.timezone,'Asia/Ho_Chi_Minh')"


@router.get("/resident/amenities")
async def amenities(scope: Resident):
    db, _ = scope
    rows = await db.execute(text(f"select {AMENITY_FIELDS} from amenities a where a.tenant_id={TENANT} and a.status<>'closed' order by a.name"))
    return {"items": [dict(r) for r in rows.mappings()]}


async def load_amenity(db, amenity_id):
    row = (await db.execute(text(f"""
        select {AMENITY_FIELDS},{TZ} as tz from amenities a
        left join zones z on z.id=a.zone_id and z.tenant_id=a.tenant_id left join sites s on s.id=z.site_id and s.tenant_id=z.tenant_id
        where a.tenant_id={TENANT} and a.id=:id
    """), {"id": amenity_id})).mappings().first()
    if row is None:
        raise HTTPException(404, "Amenity not found")
    return dict(row)


async def expire_unpaid(db):
    """A booking that waits for payment is held for as long as its zone says."""
    return (await db.execute(text(f"""
        update amenity_bookings b set status='expired'
        from amenities a cross join lateral app_zone_rules(a.tenant_id, a.zone_id) r
        where b.tenant_id={TENANT} and b.status='pending_payment' and a.id=b.amenity_id and a.tenant_id=b.tenant_id
          and b.created_at<now()-make_interval(mins=>r.amenity_payment_hold_minutes)
    """))).rowcount


@router.get("/resident/amenities/{amenity_id}/availability")
async def availability(amenity_id: UUID, scope: Resident, date: Annotated[str, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")]):
    db, _ = scope
    amenity = await load_amenity(db, amenity_id)
    await expire_unpaid(db)
    try:
        wanted = date_type.fromisoformat(date)
    except ValueError:
        raise HTTPException(422, "date must be a real calendar day") from None
    day = (await db.execute(text("select cast(:d as date) as day, extract(isodow from cast(:d as date))::int as dow, (now() at time zone :tz)::date as today"), {"d": wanted, "tz": amenity["tz"]})).mappings().one()
    if day["dow"] not in amenity["open_weekdays"] or amenity["status"] != "active" or not 0 <= (day["day"] - day["today"]).days <= amenity["max_advance_days"]:
        return {"amenity_id": amenity_id, "date": date, "timezone": amenity["tz"], "bookable": False, "areas": []}
    slots = (await db.execute(text(f"""
        with slot as (
          select (g at time zone :tz) as start_at, ((g + make_interval(mins=>:m)) at time zone :tz) as end_at
          from generate_series(cast(:d as date) + cast(:open as time), cast(:d as date) + cast(:close as time) - make_interval(mins=>:m), make_interval(mins=>:m)) g
        ), area as (select unnest(cast(:areas as text[])) as area_code)
        select a.area_code, s.start_at, s.end_at,
          not exists(select 1 from amenity_bookings b where b.tenant_id={TENANT} and b.amenity_id=:id and b.area_code=a.area_code
                     and b.status in ('pending_payment','confirmed','checked_in') and tstzrange(b.start_at,b.end_at) && tstzrange(s.start_at,s.end_at)) as free,
          exists(select 1 from amenity_closures c where c.tenant_id={TENANT} and c.amenity_id=:id and tstzrange(c.from_ts,c.to_ts) && tstzrange(s.start_at,s.end_at)) as closed,
          s.start_at > now() as future
        from area a cross join slot s order by a.area_code, s.start_at
    """), {"d": wanted, "tz": amenity["tz"], "m": amenity["slot_minutes"], "open": amenity["open_time"], "close": amenity["close_time"],
           "areas": amenity["areas"], "id": amenity_id})).mappings().all()
    by_area: dict[str, list] = {}
    for s in slots:
        by_area.setdefault(s["area_code"], []).append({"start": s["start_at"], "end": s["end_at"], "free": bool(s["free"] and not s["closed"] and s["future"]),
                                                    "reason": None if s["free"] and not s["closed"] and s["future"] else "closed" if s["closed"] else "past" if not s["future"] else "booked"})
    return {"amenity_id": amenity_id, "date": date, "timezone": amenity["tz"], "bookable": True,
            "areas": [{"area_code": a, "slots": v} for a, v in by_area.items()]}


class BookingCreate(BaseModel):
    unit_id: UUID
    amenity_id: UUID
    area_code: str = Field(default="main", min_length=1, max_length=40)
    start_at: AwareDatetime
    end_at: AwareDatetime
    guests: int = Field(default=1, ge=1, le=100)


BOOKING_FIELDS = "id,code,amenity_id,area_code,unit_id,start_at,end_at,guests,status,total_amount,qr_token,cancelled_at,cancelled_by,cancel_reason,created_at"


@router.post("/resident/amenity-bookings", status_code=201)
async def book(body: BookingCreate, scope: Resident, key: Key = None):
    db, user = scope
    await resident_unit(db, user, body.unit_id)
    amenity = await load_amenity(db, body.amenity_id)
    if amenity["status"] != "active":
        raise HTTPException(409, f"This amenity is {amenity['status']}")
    if body.area_code not in amenity["areas"]:
        raise HTTPException(422, f"Choose one of: {', '.join(amenity['areas'])}")
    # One booking at a time per amenity: two people reaching for the same slot queue here instead of deadlocking
    # on the exclusion constraint, which stays as the final guard.
    await db.execute(text("select pg_advisory_xact_lock(hashtextextended(cast(:k as text), 0))"), {"k": f"amenity:{body.amenity_id}"})
    if key:
        old = (await db.execute(text(f"select {BOOKING_FIELDS} from amenity_bookings where tenant_id={TENANT} and idempotency_key=:key"), {"key": f"{user}:{key}"})).mappings().first()
        if old:
            if old["amenity_id"] != body.amenity_id or old["start_at"] != body.start_at or old["unit_id"] != body.unit_id:
                raise HTTPException(409, "That Idempotency-Key was used for a different booking")
            return for_agent(dict(old), "qr_token")
    await expire_unpaid(db)
    minutes = int((body.end_at - body.start_at).total_seconds() // 60)
    local = (await db.execute(text("""
        select (cast(:s as timestamptz) at time zone :tz)::time as t0, (cast(:e as timestamptz) at time zone :tz)::time as t1,
               (cast(:s as timestamptz) at time zone :tz)::date = (cast(:e as timestamptz) at time zone :tz)::date as same_day,
               extract(isodow from (cast(:s as timestamptz) at time zone :tz))::int as dow,
               date_trunc('week', cast(:s as timestamptz) at time zone :tz) at time zone :tz as week_start,
               (cast(:s as timestamptz) at time zone :tz)::date - (now() at time zone :tz)::date as days_ahead
    """), {"s": body.start_at, "e": body.end_at, "tz": amenity["tz"]})).mappings().one()
    if body.end_at <= body.start_at or minutes % amenity["slot_minutes"] != 0 or body.start_at <= datetime.now(timezone.utc):
        raise HTTPException(422, f"A booking is whole {amenity['slot_minutes']}-minute slots that start in the future")
    if not local["same_day"] or local["t0"] < amenity["open_time"] or local["t1"] > amenity["close_time"] or local["dow"] not in amenity["open_weekdays"]:
        raise HTTPException(422, f"Open {amenity['open_time']} to {amenity['close_time']} on the days listed for this amenity")
    if local["days_ahead"] > amenity["max_advance_days"]:
        raise HTTPException(422, f"Bookings open {amenity['max_advance_days']} days ahead")
    if body.guests > max(amenity["max_guests"], 1):
        raise HTTPException(422, f"At most {max(amenity['max_guests'], 1)} people")
    closed = (await db.execute(text(f"select reason from amenity_closures where tenant_id={TENANT} and amenity_id=:id and tstzrange(from_ts,to_ts) && tstzrange(:s,:e) limit 1"), {"id": body.amenity_id, "s": body.start_at, "e": body.end_at})).first()
    if closed:
        raise HTTPException(409, f"Closed then: {closed[0]}")
    if amenity["weekly_quota_per_unit"] is not None:
        used = (await db.execute(text(f"""
            select count(*) from amenity_bookings where tenant_id={TENANT} and unit_id=:unit and amenity_id=:id
              and status in ('pending_payment','confirmed','checked_in','completed')
              and start_at>=:w and start_at<:w + interval '7 days'
        """), {"unit": body.unit_id, "id": body.amenity_id, "w": local["week_start"]})).scalar_one()
        if used >= amenity["weekly_quota_per_unit"]:
            raise HTTPException(409, f"This home has used its {amenity['weekly_quota_per_unit']} bookings of the week")
    total = amenity["price"] * (minutes // amenity["slot_minutes"])
    status = "pending_payment" if total > 0 else "confirmed"
    kind, client = acting()
    now = datetime.now(timezone.utc)
    try:
        async with db.begin_nested():
            row = (await db.execute(text(f"""
                insert into amenity_bookings(tenant_id,code,amenity_id,area_code,unit_id,booked_by_user_id,start_at,end_at,guests,status,total_amount,qr_token,created_by_client_id,idempotency_key)
                values({TENANT},:code,:amenity,:area,:unit,:user,:s,:e,:guests,:status,:total,:qr,:client,:key) returning {BOOKING_FIELDS}
            """), {"code": "AB-" + now.strftime("%y%m%d") + "-" + secrets.token_hex(3).upper(), "amenity": body.amenity_id, "area": body.area_code,
                   "unit": body.unit_id, "user": user, "s": body.start_at, "e": body.end_at, "guests": body.guests, "status": status,
                   "total": total, "qr": secrets.token_urlsafe(24) if status == "confirmed" else None, "client": client,
                   "key": f"{user}:{key}" if key else None})).mappings().one()
    except Exception as exc:  # noqa: BLE001 - the exclusion constraint is the arbiter of a double booking
        if "amenity_bookings_no_overlap" in str(exc) or "deadlock detected" in str(exc):
            raise HTTPException(409, "That time was just taken") from exc
        raise
    await audit(db, user, "amenity_booking.created", "amenity_booking", str(row["id"]), {"code": row["code"], "status": row["status"]})
    return for_agent(dict(row), "qr_token")


@router.get("/resident/amenity-bookings")
async def my_bookings(scope: Resident, unit_id: UUID, limit: int = Query(50, ge=1, le=100)):
    db, user = scope
    await resident_unit(db, user, unit_id)
    await expire_unpaid(db)
    rows = await db.execute(text(f"select {BOOKING_FIELDS} from amenity_bookings where tenant_id={TENANT} and unit_id=:unit order by start_at desc limit :limit"), {"unit": unit_id, "limit": limit})
    return {"items": [for_agent(dict(r), "qr_token") for r in rows.mappings()]}


@router.post("/resident/amenity-bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: UUID, scope: Resident):
    db, user = scope
    row = (await db.execute(text(f"""
        select b.id,b.unit_id,b.status,b.start_at,a.cancel_before_hours,b.code from amenity_bookings b
        join amenities a on a.id=b.amenity_id and a.tenant_id=b.tenant_id where b.tenant_id={TENANT} and b.id=:id for update of b
    """), {"id": booking_id})).mappings().first()
    if row is None:
        raise HTTPException(404, "Booking not found")
    await resident_unit(db, user, row["unit_id"])
    if row["status"] not in ("pending_payment", "confirmed"):
        raise HTTPException(409, f"A booking that is {row['status']} cannot be cancelled")
    if row["start_at"] - datetime.now(timezone.utc) < timedelta(hours=row["cancel_before_hours"]):
        raise HTTPException(409, f"Cancel at least {row['cancel_before_hours']} hours ahead")
    kind, client = acting()
    await db.execute(text("update amenity_bookings set status='cancelled',cancelled_at=now(),cancelled_by=:by,cancel_reason='Cư dân hủy' where id=:id"),
                     {"id": booking_id, "by": "agent" if client else "resident"})
    await audit(db, user, "amenity_booking.cancelled", "amenity_booking", str(booking_id), {"code": row["code"]})
    return {"id": booking_id, "status": "cancelled"}


# ---------- renovation ----------


@router.get("/resident/units/{unit_id}/construction-policy")
async def construction_policy(unit_id: UUID, scope: Resident):
    db, user = scope
    unit = await resident_unit(db, user, unit_id, ANSWERABLE)
    row = (await db.execute(text(f"""
        select p.zone_id,p.applies_to_unit_kind,p.work_time_from,p.work_time_to,p.noisy_time_from,p.noisy_time_to,p.no_work_weekdays,
               p.deposit_amount,p.overtime_fee_per_hour,p.max_workers,p.max_duration_days,p.effective_from,p.note
        from construction_policies p where p.tenant_id={TENANT} and p.effective_from<=current_date
          and (p.zone_id is null or p.zone_id=:zone) and (p.applies_to_unit_kind is null or p.applies_to_unit_kind=:kind)
        order by (p.zone_id is not null) desc,(p.applies_to_unit_kind is not null) desc,p.effective_from desc limit 1
    """), {"zone": unit["zone_id"], "kind": unit["unit_kind"]})).mappings().first()
    if row is None:
        raise HTTPException(404, "No renovation rules apply to this home")
    return {"unit": {"id": unit["id"], "code": unit["code"], "unit_kind": unit["unit_kind"]}, **dict(row)}


@router.get("/resident/units/{unit_id}/construction-permits")
async def construction_permits(unit_id: UUID, scope: Resident):
    db, user = scope
    await resident_unit(db, user, unit_id, ANSWERABLE)
    rows = await db.execute(text(f"""
        select id,code,category,contractor_name,self_performed,scope_description,planned_start,planned_end,actual_start,actual_end,status,
               submitted_at,appraised_at,approved_at,reject_reason,deposit_amount,deposit_status,created_at
        from construction_permits where tenant_id={TENANT} and unit_id=:unit order by created_at desc limit 50
    """), {"unit": unit_id})
    return {"items": [dict(r) for r in rows.mappings()]}


# ---------- what the building tells its residents ----------


@router.get("/resident/announcements")
async def announcements(scope: Resident, limit: int = Query(30, ge=1, le=100)):
    db, user = scope
    rows = await db.execute(text(f"""
        select a.id,a.code,a.kind,a.title,a.summary,a.body_md,a.is_important,a.published_at,a.effective_from,a.effective_to
        from announcements a
        where a.tenant_id={TENANT} and a.status='published' and a.published_at<=now() and (a.expire_at is null or a.expire_at>now())
          and ((cardinality(a.zone_ids)=0 and cardinality(a.building_ids)=0) or exists (
            select 1 from unit_residents ur join units u on u.id=ur.unit_id and u.tenant_id=ur.tenant_id
            where ur.tenant_id=a.tenant_id and ur.user_id=:user and ur.verification_status='verified'
              and ur.valid_from<=now() and (ur.valid_to is null or ur.valid_to>now())
              and (u.building_id=any(a.building_ids) or u.zone_id=any(a.zone_ids))))
        order by a.published_at desc limit :limit
    """), {"user": user, "limit": limit})
    return {"items": [dict(r) for r in rows.mappings()]}


class Emergency(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
    source_message_id: str = Field(min_length=1, max_length=200)


@router.post("/resident/tickets/{ticket_id}/emergency", status_code=201)
async def raise_emergency(ticket_id: UUID, body: Emergency, scope: Resident, key: Key = None):
    """Tell management now: the request becomes critical and the management of its building is notified once."""
    from uuid import uuid4

    from .v3_reception_operations import OperationCall, _escalate_emergency
    call = OperationCall(operation="escalate_emergency", idempotency_key=key or str(uuid4()),
                         input={"ticket_id": str(ticket_id), "reason": body.reason, "source_message_id": body.source_message_id})
    return await _escalate_emergency(scope, call)


@router.get("/resident/homes")
async def homes(scope: Resident):
    """The homes this person is verified for, to choose one (nothing is merged across homes)."""
    db, user = scope
    return {"items": await my_units(db, user)}


@router.get("/resident/units/{unit_id}/rules")
async def home_rules(unit_id: UUID, scope: Resident):
    """The limits that apply to this home, from its zone: what to answer when asked how many cards or visits are allowed."""
    db, user = scope
    await resident_unit(db, user, unit_id)
    r = await unit_rules(db, unit_id)
    return {"visits": {"maxWaiting": r["visit_max_waiting"], "maxDaysAhead": r["visit_max_days_ahead"], "maxHours": r["visit_max_hours"],
                       "noApprovalPurposes": r["visit_auto_approve_purposes"], "noApprovalMaxGuests": r["visit_auto_approve_max_guests"],
                       "earlyEntryMinutes": r["visit_early_minutes"]},
            "cards": {"resident": r["card_limit_resident"], "vehicle": r["card_limit_vehicle"]},
            "amenities": {"paymentHoldMinutes": r["amenity_payment_hold_minutes"]}}


register(
    Tool("resident.homes", "resident", "read", "GET", "/resident/homes", "The homes the resident is verified for"),
    Tool("resident.home_rules", "resident", "read", "GET", "/resident/units/{unit_id}/rules", "Limits that apply to a home: cards, visits, booking payment hold"),
    Tool("resident.emergency.raise", "resident", "act_small", "POST", "/resident/tickets/{ticket_id}/emergency", "Make a request critical and tell management now"),
    Tool("resident.debit_notes.list", "resident", "read", "GET", "/resident/units/{unit_id}/debit-notes", "What a home owes, by statement"),
    Tool("resident.debit_notes.get", "resident", "read", "GET", "/resident/units/{unit_id}/debit-notes/{note_id}", "One statement with its lines"),
    Tool("resident.debit_notes.balance", "resident", "read", "GET", "/resident/units/{unit_id}/balance", "How much a home owes and what is overdue"),
    Tool("resident.visitors.list", "resident", "read", "GET", "/resident/units/{unit_id}/visitor-passes", "Visits announced for a home"),
    Tool("resident.visitors.create", "resident", "act_small", "POST", "/resident/units/{unit_id}/visitor-passes", "Announce a visitor"),
    Tool("resident.visitors.cancel", "resident", "act_small", "POST", "/resident/visitor-passes/{pass_id}/cancel", "Cancel a visit that has not started"),
    Tool("resident.cards.list", "resident", "read", "GET", "/resident/units/{unit_id}/cards", "Cards of a home"),
    Tool("resident.cards.report_lost", "resident", "act_small", "POST", "/resident/cards/{card_id}/report-lost", "Lock a lost card at once"),
    Tool("resident.service_requests.list", "resident", "read", "GET", "/resident/units/{unit_id}/service-requests", "Requests to the front desk"),
    Tool("resident.service_requests.draft", "resident", "draft", "POST", "/resident/units/{unit_id}/service-requests", "Prepare a request; the resident sends it"),
    Tool("resident.amenities.list", "resident", "read", "GET", "/resident/amenities", "Amenities that can be booked"),
    Tool("resident.amenities.availability", "resident", "read", "GET", "/resident/amenities/{amenity_id}/availability", "Free slots of an amenity on a day"),
    Tool("resident.amenity_bookings.list", "resident", "read", "GET", "/resident/amenity-bookings", "Bookings of a home"),
    Tool("resident.amenity_bookings.create", "resident", "act_small", "POST", "/resident/amenity-bookings", "Book an amenity"),
    Tool("resident.amenity_bookings.cancel", "resident", "act_small", "POST", "/resident/amenity-bookings/{booking_id}/cancel", "Cancel a booking in time"),
    Tool("resident.construction.policy", "resident", "read", "GET", "/resident/units/{unit_id}/construction-policy", "Renovation rules that apply to a home"),
    Tool("resident.construction.permits", "resident", "read", "GET", "/resident/units/{unit_id}/construction-permits", "Renovation permits of a home"),
    Tool("resident.announcements.list", "resident", "read", "GET", "/resident/announcements", "Notices for the resident's buildings"),
)
