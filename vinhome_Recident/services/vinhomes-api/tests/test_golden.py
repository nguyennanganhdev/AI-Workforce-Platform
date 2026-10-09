"""The golden scenarios of docs/domain/KICH_BAN_VANG.md, one test each, on the generated test world.

Each test checks the lines under "Chấp nhận" of its scenario. Preconditions that a scenario assumes (a request in a
certain status, a shift that covers the appointment) are set with SQL; everything the scenario *does* goes through the API.
"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import asyncpg
import pytest
from test_domain_database import operation
from test_integration_auth import CLIENT, bearer, mint, outsider, person, secret  # noqa: F401 -- `secret` is a pytest fixture
from test_resident_contract import CATEGORY, TENANT, client, sql
from test_resident_contract import database as database  # noqa: F401 -- pytest fixture export

from vinhomes_api.jobs import sweep_tenant
from vinhomes_api.mock_data import build

AN, CHAU, BINH, DUNG, EM = "mock-an", "mock-chau", "mock-binh", "mock-dung", "mock-em"
MINH, GIANG, HOA, KHOA = "mock-minh", "mock-giang", "mock-hoa", "mock-khoa"
KEY = {"Idempotency-Key": "k"}


@pytest.fixture(scope="module", autouse=True)
def world(database):
    asyncio.run(build(database["admin"], "test", 42))


def unit(database, code):
    return sql(database, "select id from units where tenant_id=$1 and code=$2", TENANT, code)[0]["id"]


def idem():
    return {"Idempotency-Key": uuid4().hex}


def tomorrow_at(hour, minute=0, days=1):
    day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days)
    return (day + timedelta(hours=hour, minutes=minute)).isoformat()


def in_minutes(minutes):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


# ---------------------------------------------------------------- G01


def test_G01_a_resident_asks_what_the_home_owes(database):
    home = unit(database, "S1.01-1201")
    owed = sql(database, """select coalesce(sum(total_amount-paid_amount),0) as owed from debit_notes
        where unit_id=$1 and status in ('issued','partially_paid','overdue')""", home)[0]["owed"]
    with person(database, AN) as c:
        balance = c.get(f"/resident/units/{home}/balance")
        assert balance.status_code == 200, balance.text
        assert balance.json()["outstanding"] == owed > 0                                     # 1
        notes = c.get(f"/resident/units/{home}/debit-notes").json()["items"]
        by_month = {n["period_month"][:7]: n["status"] for n in notes}
        months = sorted(by_month)
        assert by_month[months[-1]] == "issued" and by_month[months[-2]] == "overdue"         # 2
        one = c.get(f"/resident/units/{home}/debit-notes/{notes[0]['id']}")
        assert one.status_code == 200 and sum(l["amount"] for l in one.json()["lines"]) == one.json()["subtotal"]
        assert balance.json()["overdue_notes"] >= 1
    with person(database, CHAU) as c:
        assert c.get(f"/resident/units/{home}/balance").status_code == 403                     # 3: household
    with person(database, EM) as c:
        assert c.get(f"/resident/units/{unit(database, 'S1.01-0402')}/balance").status_code == 403   # 4: pending
    with person(database, DUNG) as c:
        homes = c.get("/resident/homes").json()["items"]
        assert {h["code"] for h in homes} == {"S1.01-1502", "HA2.05"}                          # 5: pick one, nothing merged
        for h in homes:
            assert c.get(f"/resident/units/{h['id']}/balance").status_code == 200
        assert c.get(f"/resident/units/{home}/balance").status_code == 403
    token = mint(database, AN)["token"]                                                        # 6: an agent only reads
    with outsider(database) as c:
        assert c.get(f"/resident/units/{home}/balance", headers=bearer(token)).status_code == 200
        for path in ("/invoices/%s/issue" % uuid4(), "/invoices/%s/demo-payments" % uuid4()):
            assert c.post(path, headers={**bearer(token), **KEY}, json={}).status_code == 404
    with person(database, BINH) as c:  # a tenant answers for the home too
        assert c.get(f"/resident/units/{unit(database, 'S1.02-0803')}/balance").status_code == 200


# ---------------------------------------------------------------- G02


def test_G02_a_leak_from_report_to_an_approved_plan_the_agent_proposes_and_people_decide(database, secret):
    resident = "local-v3-resident"
    with client(database) as c:       # the resident reports through Reception; the handoff creates the case for the platform client
        context, _ = operation(c, "get_verified_resident_context")
        place = context["residences"][0]
        channel = c.post("/resident/chats", json={"title": "Rò nước"}).json()["id"]
        message = c.post(f"/resident/chats/{channel}/messages", json={"text": "Vòi bếp nhà tôi rò nước", "client_message_id": str(uuid4())}).json()
        draft, _ = operation(c, "create_ticket_draft", {"channel_id": channel, "domain_id": place["domain_id"], "building_id": place["building_id"],
                                                         "unit_id": place["unit_id"], "category_id": CATEGORY})
        target = {"channel_id": channel, "draft_id": draft["draftId"]}
        operation(c, "update_ticket_incident", {**target, "fields": {"source_message_id": message["id"], "facts": [
            {"key": "symptom", "value": "rò nước", "source": "customer_report", "source_message_id": message["id"]},
            {"key": "item", "value": "vòi bếp", "source": "customer_report", "source_message_id": message["id"]}]}})
        operation(c, "submit_ticket_assessment", {**target, "assessment": {"priority": "normal", "severity": "minor", "reason": "Cư dân báo"}})
        operation(c, "resolve_management_destination", target)
        handoff, _ = operation(c, "handoff_ticket", {**target, "plan_required": True})
        ticket = UUID(handoff["ticket"]["id"])
    assert sql(database, "select status from tickets where id=$1", ticket)[0]["status"] in ("open", "triaging")   # 1: drafts became a request only on handoff

    headers = {"X-Client-Id": CLIENT, **bearer(secret)}
    with outsider(database) as c:
        inbox = c.get("/integration/v1/cases/inbox", headers=headers)
        assert inbox.status_code == 200, inbox.text
        mine = [m for m in inbox.json()["items"] if m["ticket_id"] == str(ticket)]
        assert mine and mine[0]["message_type"] == "ticket_submitted"                                       # the case reached the client
        case = c.get(f"/integration/v1/cases/{ticket}", headers=headers).json()
        version = case["ticket"]["version"]

        staff = sql(database, "select id from staff_profiles where user_id='local-v3-technical'")[0]["id"]
        sql(database, "update staff_shifts set starts_at=now()-interval '1 day',ends_at=now()+interval '30 days' where staff_id=$1 returning id", staff)
        appointment = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
        body = {"ticket_version": version, "summary": "Thay gioăng vòi bếp", "steps": ["Khóa van", "Thay gioăng", "Kiểm tra rò rỉ"],
                "performer_staff_id": str(staff), "appointment_at": appointment, "estimated_amount": 150000, "cost_bearer": "resident"}
        key = idem()
        proposed = c.post(f"/integration/v1/cases/{ticket}/plans", headers={**headers, **key}, json=body)
        assert proposed.status_code == 201, proposed.text                                                   # 2
        plan = proposed.json()
        assert plan["status"] == "management_pending" and plan["proposed_by_client_id"] == CLIENT
        again = c.post(f"/integration/v1/cases/{ticket}/plans", headers={**headers, **key}, json=body)
        assert again.status_code == 201 and again.json()["id"] == plan["id"]                                 # 3: same key, same plan
        assert c.post(f"/integration/v1/cases/{ticket}/plans", headers={**headers, **key}, json={**body, "summary": "Khác"}).status_code == 409
        assert c.post(f"/integration/v1/cases/{ticket}/plans", headers={**headers, **idem()}, json=body).status_code == 409   # one at a time
        khoa = sql(database, "select id from staff_profiles where user_id=$1", KHOA)[0]["id"]
        assert c.post(f"/integration/v1/cases/{ticket}/plans", headers={**headers, **idem()}, json={**body, "performer_staff_id": str(khoa)}).status_code in (409, 422)   # 6

        # 4: a client, with or without a person's delegation, cannot decide
        manager_token = mint(database, "local-v3-management", "staff_assistant")["token"]
        resident_token = mint(database, resident)["token"]
        assert c.post(f"/plans/{plan['id']}/management-decision", headers={**bearer(manager_token), **KEY}, json={"decision": "approve", "version": 0, "note": "ok"}).status_code == 404
        assert c.post(f"/resident/plans/{plan['id']}/decision", headers={**bearer(resident_token), **KEY}, json={"decision": "approve", "version": 0, "note": "ok"}).status_code == 404

    with person(database, "local-v3-management") as m:                                                      # 5: people decide, in order
        decided = m.post(f"/plans/{plan['id']}/management-decision", json={"decision": "approve", "version": 0, "note": "Đồng ý phương án."})
        assert decided.status_code == 200, decided.text
        assert not sql(database, "select id from work_orders where ticket_id=$1", ticket)
    with person(database, resident) as r:
        agreed = r.post(f"/resident/plans/{plan['id']}/decision", json={"decision": "approve", "version": 1, "note": "Đồng ý"})
        assert agreed.status_code == 200, agreed.text
    offer = sql(database, """select a.status,a.staff_id from work_assignments a join work_orders w on w.id=a.work_order_id where w.ticket_id=$1""", ticket)
    assert len(offer) == 1 and offer[0]["status"] == "offered" and offer[0]["staff_id"] == staff            # exactly one job, offered to the performer
    audit = sql(database, "select initiator_kind,initiator_id from audit_events where event_type='plan.proposed' and target_id=$1", plan["id"])
    assert audit == [{"initiator_kind": "agent", "initiator_id": CLIENT}]                                    # 8
    events = sql(database, "select actor_kind,actor_client_id from ticket_events where ticket_id=$1 and event_type='plan.proposed'", ticket)
    assert events == [{"actor_kind": "agent", "actor_client_id": CLIENT}]
    assert sql(database, "select count(*) as n from event_outbox where topic='plan.proposed' and (payload->>'ticketId')=$1", str(ticket))[0]["n"] == 1


# ---------------------------------------------------------------- G03


def test_G03_an_emergency_reaches_management_once_and_an_agent_cannot_send_guards(database):
    home = unit(database, "S1.01-1201")
    with person(database, AN) as c:
        chat = c.post("/resident/chats", json={"title": "Khẩn cấp"}).json()["id"]
        said = c.post(f"/resident/chats/{chat}/messages", json={"text": "Có mùi gas ở bếp", "client_message_id": str(uuid4())}).json()["id"]
        other = c.post("/resident/chats", json={"title": "Khác"}).json()["id"]
        stray = c.post(f"/resident/chats/{other}/messages", json={"text": "Tin khác", "client_message_id": str(uuid4())}).json()["id"]
    ticket = sql(database, """insert into tickets(tenant_id,code,requester_user_id,channel_id,unit_id,site_id,zone_id,building_id,management_unit_id,domain_id,category_id,
        title,description,priority,status,contact_name,contact_phone,address_snapshot,request_kind)
        select $1,'G03-'||substr(md5(random()::text),1,6),$2,$3,u.id,u.site_id,u.zone_id,u.building_id,'88888888-8888-5888-a888-888888888888','22222222-2222-5222-a222-222222222222',
               '33333333-3333-5333-a333-333333333333','Mùi gas','Có mùi gas','normal','open','Nguyễn Văn An','0901000001','{}','incident' from units u where u.id=$4 returning id""",
                 TENANT, AN, chat, home)[0]["id"]
    managers = sql(database, """select count(distinct m.user_id) as n from scoped_user_roles r join tenant_memberships m on m.id=r.membership_id
        where r.role_code='management' and m.status='active'""")[0]["n"]
    with person(database, AN) as c:
        assert c.post(f"/resident/tickets/{ticket}/emergency", json={"reason": "Mùi gas", "source_message_id": stray}).status_code == 422   # not this conversation
        raised = c.post(f"/resident/tickets/{ticket}/emergency", json={"reason": "Mùi gas ở bếp", "source_message_id": said})
        assert raised.status_code == 201, raised.text
        result = raised.json()["result"] if "result" in raised.json() else raised.json()
    row = sql(database, "select is_emergency,priority,severity from tickets where id=$1", ticket)[0]
    assert row == {"is_emergency": True, "priority": "critical", "severity": "critical"}                    # 1
    sent = sql(database, "select count(*) as n from notification_deliveries where dedupe_key like $1", f"ticket:{ticket}:emergency:%")[0]["n"]
    assert 1 <= sent <= managers
    with person(database, AN) as c:
        again = c.post(f"/resident/tickets/{ticket}/emergency", json={"reason": "Vẫn mùi gas", "source_message_id": said})
        assert again.status_code == 201
    assert sql(database, "select count(*) as n from notification_deliveries where dedupe_key like $1", f"ticket:{ticket}:emergency:%")[0]["n"] == sent   # not twice
    # the agent may raise it (a small act) but cannot send or recall guards
    token = mint(database, AN)["token"]
    staff_token = mint(database, MINH, "staff_assistant")["token"]
    with outsider(database) as c:
        assert c.post(f"/resident/tickets/{ticket}/emergency", headers={**bearer(token), **idem()}, json={"reason": "Mùi gas", "source_message_id": said}).status_code == 201
        for who in (token, staff_token):
            assert c.post(f"/work-orders/{uuid4()}/security/dispatch-request", headers={**bearer(who), **KEY}, json={}).status_code == 404   # 3
    sql(database, "update tickets set status='cancelled' where id=$1 returning id", ticket)
    with person(database, AN) as c:
        assert c.post(f"/resident/tickets/{ticket}/emergency", json={"reason": "x", "source_message_id": said}).status_code == 409   # final


# ---------------------------------------------------------------- G04


def test_G04_a_visitor_is_announced_checked_at_the_gate_and_never_walks_in_twice(database):
    home = unit(database, "S1.01-1201")
    soon = {"guest_name": "Bạn của An", "guest_count": 2, "purpose": "family_visit", "visit_from": in_minutes(5), "visit_to": in_minutes(180)}
    with person(database, AN) as c:
        made = c.post(f"/resident/units/{home}/visitor-passes", json=soon)
        assert made.status_code == 201, made.text
        one = made.json()
        assert one["status"] == "approved" and one["qr_token"]                                             # 1
        assert c.post(f"/resident/units/{home}/visitor-passes", json={**soon, "visit_from": in_minutes(-300), "visit_to": in_minutes(-100)}).status_code == 422   # 2
        assert c.post(f"/resident/units/{home}/visitor-passes", json={**soon, "visit_from": in_minutes(60), "visit_to": in_minutes(30)}).status_code == 422
        # business visit needs the desk
        desk = c.post(f"/resident/units/{home}/visitor-passes", json={**soon, "purpose": "business"}).json()
        assert desk["status"] == "pending_approval" and not desk["qr_token"]
    with person(database, GIANG) as g:
        scan = lambda token, direction="in": g.post("/operations/gate/scan", json={"qr_token": token, "gate_code": "G1", "direction": direction}).json()
        assert scan(one["qr_token"])["result"] == "granted"                                                  # 4
        assert scan(one["qr_token"]) == {**scan(one["qr_token"]), "result": "denied", "reason": "already_inside"}
        assert scan("khong-co-ma-nay-het")["reason"] == "unknown_qr"
        assert scan(one["qr_token"], "out")["result"] == "granted"
        assert scan(one["qr_token"])["reason"] == "pass_checked_out"
    with person(database, AN) as c:
        later = c.post(f"/resident/units/{home}/visitor-passes", json={**soon, "visit_from": tomorrow_at(10), "visit_to": tomorrow_at(12)}).json()
        with person(database, GIANG) as g:
            assert g.post("/operations/gate/scan", json={"qr_token": later["qr_token"], "gate_code": "G1"}).json()["reason"] == "too_early"
        assert c.post(f"/resident/visitor-passes/{later['id']}/cancel").json()["status"] == "cancelled"      # 5
        assert c.post(f"/resident/visitor-passes/{one['id']}/cancel").status_code == 409
        # a visit nobody came to ends by itself
        past = c.post(f"/resident/units/{home}/visitor-passes", json=soon).json()
        sql(database, "update visitor_passes set visit_from=now()-interval '5 hours',visit_to=now()-interval '1 hour' where id=$1 returning id", UUID(past["id"]))
        with person(database, GIANG) as g:
            assert g.post("/operations/gate/scan", json={"qr_token": past["qr_token"], "gate_code": "G1"}).json()["reason"] == "expired"
        assert sql(database, "select status from visitor_passes where id=$1", UUID(past["id"]))[0]["status"] == "expired"
        # the limit on waiting visits
        for _ in range(9):
            c.post(f"/resident/units/{home}/visitor-passes", json={**soon, "visit_from": tomorrow_at(8), "visit_to": tomorrow_at(9)})
        assert c.post(f"/resident/units/{home}/visitor-passes", json=soon).status_code == 409                 # 3
    with person(database, CHAU) as c:
        assert c.post(f"/resident/units/{home}/visitor-passes", json=soon).status_code in (201, 409)       # a household member may announce
    with person(database, EM) as c:
        assert c.post(f"/resident/units/{unit(database, 'S1.01-0402')}/visitor-passes", json=soon).status_code == 403
    # an agent can announce and cancel, and never sees the QR
    token = mint(database, DUNG)["token"]
    villa = unit(database, "HA2.05")
    with outsider(database) as c:
        mine = c.post(f"/resident/units/{villa}/visitor-passes", headers={**bearer(token), **idem()}, json=soon)
        assert mine.status_code == 201 and "qr_token" not in mine.json()
        assert c.post(f"/resident/visitor-passes/{mine.json()['id']}/cancel", headers={**bearer(token), **idem()}).status_code == 200
    assert sql(database, "select initiator_kind from audit_events where event_type='visitor_pass.created' and target_id=$1", mine.json()["id"])[0]["initiator_kind"] == "agent"


# ---------------------------------------------------------------- G05


def test_G05_a_lost_card_is_locked_at_once_and_a_new_one_needs_the_desk(database):
    home = unit(database, "S1.01-1201")
    with person(database, AN) as c:
        listed = c.get(f"/resident/units/{home}/cards").json()["items"]
        bike = next(card for card in listed if card["card_no"] == "C-MOCK-AN-V1")
        assert bike["status"] == "active" and bike["vehicle_plate_no"]
        stranger = sql(database, "select id from access_cards where unit_id=$1 limit 1", unit(database, "S1.02-0803"))[0]["id"]
        assert c.post(f"/resident/cards/{stranger}/report-lost").status_code == 403                              # 2
        assert c.post(f"/resident/cards/{bike['id']}/report-lost").json()["status"] == "lost"                    # 1
        assert c.post(f"/resident/cards/{bike['id']}/report-lost").status_code == 409
    with person(database, GIANG) as g:
        swipe = g.post("/operations/gate/swipe", json={"card_no": "C-MOCK-AN-V1", "gate_code": "G2"}).json()
        assert swipe == {"result": "denied", "reason": "card_lost"}                                              # 3
    assert sql(database, "select result,deny_reason from access_events where access_card_id=$1", bike["id"]) == [{"result": "denied", "deny_reason": "card_lost"}]

    token = mint(database, AN)["token"]
    with outsider(database) as c:
        draft = c.post(f"/resident/units/{home}/service-requests", headers={**bearer(token), **idem()},
                       json={"kind": "card_reissue", "details": {"card_id": str(bike["id"])}})
        assert draft.status_code == 201 and draft.json()["status"] == "draft"
        request = draft.json()["id"]
        assert c.post(f"/resident/service-requests/{request}/submit", headers={**bearer(token), **KEY}).status_code == 404   # 5: only the resident sends
        shown = c.get(f"/resident/units/{home}/cards", headers=bearer(token)).json()["items"]
        assert all(card["card_no"].endswith(card["card_no"][-4:]) and "*" in card["card_no"] for card in shown)   # masked for an agent
    with person(database, AN) as c:
        assert c.post(f"/resident/service-requests/{request}/submit").json()["status"] == "submitted"
    with person(database, MINH) as m:
        step = lambda to, note=None: m.post(f"/operations/service-requests/{request}/transition", json={"to_status": to, "note": note})
        assert step("approved").status_code == 409                                                               # must be reviewed first
        assert step("in_review").status_code == 200 and step("approved").status_code == 200
        done = step("fulfilled")
        assert done.status_code == 200, done.text
    assert sql(database, "select status from access_cards where id=$1", bike["id"])[0]["status"] == "revoked"   # 4
    fresh = sql(database, "select status,vehicle_id from access_cards where id=$1", UUID(done.json()["issued_card_id"]))[0]
    assert fresh["status"] == "active" and fresh["vehicle_id"] is not None
    # a home cannot hold more cards than its limit
    for n in range(3):
        sql(database, """insert into access_cards(tenant_id,card_no,kind,unit_id,vehicle_id,status) select $1,$2,'vehicle',$3,vehicle_id,'pending_issue' from access_cards where id=$4 returning id""",
            TENANT, f"C-FULL-{n}-{uuid4().hex[:5]}", home, UUID(done.json()["issued_card_id"]))
    sql(database, "update access_cards set status='active' where unit_id=$1 and status='pending_issue' returning id", home)
    with person(database, AN) as c:
        extra = c.post(f"/resident/units/{home}/service-requests", json={"kind": "card_issue", "details": {"card_kind": "vehicle"}}).json()["id"]
        c.post(f"/resident/service-requests/{extra}/submit")
    with person(database, MINH) as m:
        for to in ("in_review", "approved"):
            m.post(f"/operations/service-requests/{extra}/transition", json={"to_status": to})
        assert m.post(f"/operations/service-requests/{extra}/transition", json={"to_status": "fulfilled"}).status_code == 409   # 6
        assert m.post(f"/operations/service-requests/{request}/transition", json={"to_status": "rejected"}).status_code == 409


# ---------------------------------------------------------------- G06


def free_slot(c, amenity, day, area=None):
    response = c.get(f"/resident/amenities/{amenity}/availability", params={"date": day})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["bookable"], data
    for a in data["areas"]:
        if area and a["area_code"] != area:
            continue
        for s in a["slots"]:
            if s["free"]:
                return a["area_code"], s
    raise AssertionError("no free slot")


def test_G06_booking_an_amenity_never_double_books_and_cancelling_has_a_deadline(database):
    sql(database, "update amenities set weekly_quota_per_unit=null where code='BBQ-S1' returning id")
    bbq = sql(database, "select id from amenities where code='BBQ-S1'")[0]["id"]
    tennis = sql(database, "select id from amenities where code='TENNIS-S1'")[0]["id"]
    home, other_home = unit(database, "S1.01-1201"), unit(database, "S1.02-0803")
    day = sql(database, "select ((now() at time zone 'Asia/Ho_Chi_Minh')::date + 2)::text as d")[0]["d"]
    with person(database, AN) as c:
        area, slot = free_slot(c, bbq, day)
        body = {"unit_id": str(home), "amenity_id": str(bbq), "area_code": area, "start_at": slot["start"], "end_at": slot["end"], "guests": 6}
        first = c.post("/resident/amenity-bookings", json=body)
        assert first.status_code == 201 and first.json()["status"] == "confirmed", first.text                     # 1: free
        assert c.post("/resident/amenity-bookings", json=body).status_code == 409                                  # 2: same place and time
        other_area = next(a for a in sql(database, "select unnest(areas) as a from amenities where id=$1", bbq) if a["a"] != area)["a"]
        assert c.post("/resident/amenity-bookings", json={**body, "area_code": other_area}).status_code == 201     # another pit is fine
        assert c.post("/resident/amenity-bookings", json={**body, "guests": 50}).status_code == 422
        odd = (datetime.fromisoformat(slot["end"]) + timedelta(minutes=30)).isoformat()
        assert c.post("/resident/amenity-bookings", json={**body, "area_code": other_area, "end_at": odd}).status_code == 422   # whole slots only
        # paid amenity waits for payment, then lapses
        t_area, t_slot = free_slot(c, tennis, day)
        paid = c.post("/resident/amenity-bookings", json={"unit_id": str(home), "amenity_id": str(tennis), "area_code": t_area, "start_at": t_slot["start"], "end_at": t_slot["end"]})
        assert paid.status_code == 201 and paid.json()["status"] == "pending_payment" and paid.json()["total_amount"] > 0
        sql(database, "update amenity_bookings set created_at=now()-interval '20 minutes' where id=$1 returning id", UUID(paid.json()["id"]))
        assert next(b for b in c.get("/resident/amenity-bookings", params={"unit_id": str(home)}).json()["items"] if b["id"] == paid.json()["id"])["status"] == "expired"   # 5
        # the weekly quota: this home has two bookings this week now
        sql(database, "update amenities set weekly_quota_per_unit=2 where id=$1 returning id", bbq)
        a3, s3 = free_slot(c, bbq, day)
        assert c.post("/resident/amenity-bookings", json={**body, "area_code": a3, "start_at": s3["start"], "end_at": s3["end"]}).status_code == 409   # 3
        sql(database, "update amenities set weekly_quota_per_unit=null where id=$1 returning id", bbq)
        # cancelling has a deadline
        sql(database, "update amenities set cancel_before_hours=1000 where id=$1 returning id", bbq)
        assert c.post(f"/resident/amenity-bookings/{first.json()['id']}/cancel").status_code == 409              # 4: too close
        sql(database, "update amenities set cancel_before_hours=2 where id=$1 returning id", bbq)
        assert c.post(f"/resident/amenity-bookings/{first.json()['id']}/cancel").json()["status"] == "cancelled"
    # another home cannot cancel it, agent or not
    with person(database, BINH) as c:
        again = c.post("/resident/amenity-bookings", json={**body, "unit_id": str(other_home)})
        assert again.status_code == 201       # the slot was freed by the cancel
        token = mint(database, AN)["token"]
        with outsider(database) as o:
            assert o.post(f"/resident/amenity-bookings/{again.json()['id']}/cancel", headers={**bearer(token), **idem()}).status_code == 403   # 6
    # two people reach for the same slot at the same moment
    with person(database, AN) as looking:
        area3, slot3 = free_slot(looking, bbq, sql(database, "select ((now() at time zone 'Asia/Ho_Chi_Minh')::date + 4)::text as d")[0]["d"])
    race = {"amenity_id": str(bbq), "area_code": area3, "start_at": slot3["start"], "end_at": slot3["end"], "guests": 2}

    def reach(user, code):
        with person(database, user) as p:
            return p.post("/resident/amenity-bookings", json={**race, "unit_id": str(unit(database, code))}).status_code

    with ThreadPoolExecutor(2) as pool:
        codes = sorted(pool.map(lambda args: reach(*args), [(AN, "S1.01-1201"), (BINH, "S1.02-0803")]))
    assert codes == [201, 409]                                                                                 # 3 (concurrent)


# ---------------------------------------------------------------- G07


def test_G07_renovation_rules_and_permits(database):
    flat, villa = unit(database, "S1.01-1201"), unit(database, "HA2.05")
    with person(database, AN) as c:
        rules = c.get(f"/resident/units/{flat}/construction-policy").json()
        assert rules["deposit_amount"] == 10_000_000 and rules["unit"]["unit_kind"] == "apartment"            # 1
        permits = c.get(f"/resident/units/{flat}/construction-permits").json()["items"]
        assert permits and permits[0]["status"] == "in_progress" and permits[0]["deposit_status"] == "held"   # 2
        assert c.get(f"/resident/units/{villa}/construction-permits").status_code == 403
    with person(database, DUNG) as c:
        assert c.get(f"/resident/units/{villa}/construction-policy").json()["deposit_amount"] == 30_000_000    # the villa has its own
        assert 7 in c.get(f"/resident/units/{villa}/construction-policy").json()["no_work_weekdays"]
    with person(database, CHAU) as c:
        assert c.get(f"/resident/units/{flat}/construction-policy").status_code == 403
    token = mint(database, AN)["token"]
    with outsider(database) as c:
        assert c.get(f"/resident/units/{flat}/construction-permits", headers=bearer(token)).status_code == 200
    assert sql(database, "select count(*) as n from state_transitions where entity='construction_permits'")[0]["n"] > 10   # 3 (the database holds the rule)


# ---------------------------------------------------------------- G08


def test_G08_a_planned_outage_is_drafted_by_an_agent_published_by_management_and_told_once(database):
    s101 = sql(database, "select id from buildings where code='S1.01'")[0]["id"]
    staff_token = mint(database, MINH, "staff_assistant")["token"]
    with outsider(database) as c:
        drafted = c.post("/operations/announcements", headers={**bearer(staff_token), **idem()}, json={
            "kind": "outage_notice", "title": "Cắt nước S1.01", "body_md": "Cắt nước 09:00 đến 12:00.", "building_ids": [str(s101)],
            "effective_from": tomorrow_at(2), "effective_to": tomorrow_at(5)})
        assert drafted.status_code == 201, drafted.text
        notice = drafted.json()
        assert notice["status"] == "draft" and notice["drafted_by"] == "agent"                                   # 1
        assert c.post(f"/operations/announcements/{notice['id']}/publish", headers={**bearer(staff_token), **KEY}).status_code == 404   # agents do not publish
    assert sql(database, "select count(*) as n from notification_deliveries where dedupe_key like $1", f"announcement:{notice['id']}:%")[0]["n"] == 0
    expected = sql(database, """select count(distinct ur.user_id) as n from unit_residents ur join units u on u.id=ur.unit_id
        join tenant_memberships m on m.user_id=ur.user_id and m.status='active' where u.building_id=$1 and ur.verification_status='verified'""", s101)[0]["n"]
    with person(database, MINH) as m:
        done = m.post(f"/operations/announcements/{notice['id']}/publish")
        assert done.status_code == 200, done.text
        assert done.json()["notified"] == expected > 2                                                           # 2
        assert m.post(f"/operations/announcements/{notice['id']}/publish").json()["already_published"] is True   # 3
    told = {r["user_id"] for r in sql(database, "select user_id from notification_deliveries where dedupe_key like $1", f"announcement:{notice['id']}:%")}
    assert {AN, CHAU} <= told and BINH not in told and EM not in told
    with person(database, AN) as c:
        assert notice["id"] in [a["id"] for a in c.get("/resident/announcements").json()["items"]]               # 4
    with person(database, BINH) as c:
        assert notice["id"] not in [a["id"] for a in c.get("/resident/announcements").json()["items"]]
    with person(database, AN) as c:
        assert c.post("/operations/announcements", json={"kind": "news", "title": "x", "body_md": "x"}).status_code == 403   # residents do not write notices
    resident_token = mint(database, AN)["token"]
    with outsider(database) as c:
        assert c.post("/operations/announcements", headers={**bearer(resident_token), **idem()}, json={"kind": "news", "title": "x", "body_md": "x"}).status_code == 403


# ---------------------------------------------------------------- G09


def test_G09_what_each_kind_of_resident_may_do(database):
    flat, tenant_home, pending_home = unit(database, "S1.01-1201"), unit(database, "S1.02-0803"), unit(database, "S1.01-0402")
    guest = {"guest_name": "Khách", "purpose": "family_visit", "visit_from": in_minutes(30), "visit_to": in_minutes(90)}
    matrix = {
        "debit": lambda c, u: c.get(f"/resident/units/{u}/balance").status_code,
        "visitor": lambda c, u: c.post(f"/resident/units/{u}/visitor-passes", json=guest).status_code,
        "card": lambda c, u: c.get(f"/resident/units/{u}/cards").status_code,
        "renovation": lambda c, u: c.get(f"/resident/units/{u}/construction-permits").status_code,
    }
    expect = {                       # (person, home) -> {action: allowed}
        (AN, flat): dict(debit=True, visitor=True, card=True, renovation=True),
        (CHAU, flat): dict(debit=False, visitor=True, card=True, renovation=False),
        (BINH, tenant_home): dict(debit=True, visitor=True, card=True, renovation=True),
        (EM, pending_home): dict(debit=False, visitor=False, card=False, renovation=False),
    }
    # earlier scenarios leave visits waiting on these homes; the limit on waiting visits is G04's business
    sql(database, "update visitor_passes set status='cancelled' where unit_id in ($1,$2,$3) and status in ('pending_approval','approved') returning id", flat, tenant_home, pending_home)
    for (user, home), actions in expect.items():
        with person(database, user) as c:
            for name, call in matrix.items():
                code = call(c, home)
                assert (code < 300) is actions[name], f"{user} {name}: {code}"                                      # 1
    # ending a link ends the rights, even for a token already issued
    token = mint(database, CHAU)["token"]
    with outsider(database) as c:
        assert c.get(f"/resident/units/{flat}/cards", headers=bearer(token)).status_code == 200
        sql(database, "update unit_residents set valid_to=now()-interval '1 second' where user_id=$1 and unit_id=$2 returning id", CHAU, flat)
        try:
            assert c.get(f"/resident/units/{flat}/cards", headers=bearer(token)).status_code == 403              # 2
        finally:
            sql(database, "update unit_residents set valid_to=null where user_id=$1 and unit_id=$2 returning id", CHAU, flat)
    with person(database, DUNG) as c:
        for code in ("S1.01-1502", "HA2.05"):
            assert c.get(f"/resident/units/{unit(database, code)}/balance").status_code == 200                    # 3


# ---------------------------------------------------------------- G10


def test_G10_field_staff_see_only_their_jobs_and_a_resident_cannot_use_staff_routes(database):
    with person(database, "mock-hoa") as c:
        mine = c.get("/my-work-orders")
        assert mine.status_code == 200
        assert all(w.get("staff_user_id", HOA) == HOA for w in mine.json()["items"])
    with person(database, AN) as c:
        assert c.get("/my-work-orders").status_code == 403
        assert c.get("/tickets").status_code == 403
    on_leave = sql(database, "select availability from staff_profiles where user_id=$1", KHOA)[0]["availability"]
    assert on_leave == "on_leave"
    assert sql(database, "select count(*) as n from staff_shifts s join staff_profiles p on p.id=s.staff_id where p.user_id=$1", KHOA)[0]["n"] == 0   # 4 (nothing to be assigned to)


# ---------------------------------------------------------------- G11


def test_G11_a_manager_asks_what_is_overdue_and_how_many_incidents(database):
    with person(database, MINH) as m:
        late = m.get("/tickets", params={"overdue": "true", "limit": 100})
        assert late.status_code == 200, late.text
        got = [t["id"] for t in late.json()["items"]]
        due = [t["resolution_due_at"] for t in late.json()["items"]]
        assert due == sorted(due)                                                                                # oldest deadline first
        want = {str(r["id"]) for r in sql(database, "select id from tickets where status not in ('resolved','closed','cancelled') and resolution_due_at<now() order by resolution_due_at limit 100")}
        assert set(got) == want and got                                                                          # 2
        s101 = sql(database, "select id from buildings where code='S1.01'")[0]["id"]
        freq = m.get("/reports/incident-frequency", params={"buildingId": str(s101), "fromDate": "2020-01-01", "toDate": "2100-01-01"})
        assert freq.status_code == 200, freq.text
        direct = sql(database, "select count(*) as n from tickets where building_id=$1 and request_kind='incident'", s101)[0]["n"]
        assert sum(r["incident_count"] for r in freq.json()["items"]) == direct                                  # 1
    with person(database, AN) as c:
        assert c.get("/reports/incident-frequency", params={"buildingId": str(uuid4()), "fromDate": "2020-01-01", "toDate": "2100-01-01"}).status_code == 403   # 3


# ---------------------------------------------------------------- G12


def test_G12_a_late_request_warns_once_and_the_platform_follows_the_events(database, secret, monkeypatch):
    monkeypatch.setenv("VINHOMES_API_EVENT_SETTLE_SECONDS", "0")
    assert sql(database, "select count(*) as n from tickets where sla_policy_id is not null and response_due_at is not null and resolution_due_at is not null")[0]["n"] > 30   # 1
    shown = sql(database, "select count(*) as n from tickets where status not in ('resolved','closed','cancelled') and resolution_due_at<now()")[0]["n"]
    assert shown > 0

    async def sweep():
        conn = await asyncpg.connect(database["admin"])
        try:
            async with conn.transaction():
                await conn.execute("select set_config('app.tenant_id',$1,true)", str(TENANT))
                from sqlalchemy.ext.asyncio import create_async_engine
        finally:
            await conn.close()
        engine = create_async_engine(database["admin"].replace("postgresql://", "postgresql+asyncpg://", 1))
        async with engine.begin() as db:
            from sqlalchemy import text
            await db.execute(text("select set_config('app.tenant_id',:t,true)"), {"t": str(TENANT)})
            counts = await sweep_tenant(db)
        await engine.dispose()
        return counts

    first = asyncio.run(sweep())
    assert first["sla_breaches"] >= shown                                                                         # 2
    second = asyncio.run(sweep())
    assert second["sla_breaches"] == 0 and second["sla_warnings"] == 0
    headers = {"X-Client-Id": CLIENT, **bearer(secret)}
    with outsider(database) as c:
        page = c.get("/integration/v1/events", params={"topics": "ticket.sla_*", "limit": 100}, headers=headers).json()
        seqs = [e["seq"] for e in page["items"]]
        assert seqs == sorted(seqs) and len({e["event_id"] for e in page["items"]}) == len(seqs)
        collected, cursor = list(page["items"]), page["next_cursor"]
        while True:                                                                                               # 3: follow by cursor, nothing lost or repeated
            more = c.get("/integration/v1/events", params={"topics": "ticket.sla_*", "after": cursor, "limit": 100}, headers=headers).json()
            if not more["items"]:
                break
            collected += more["items"]
            cursor = more["next_cursor"]
        assert len({e["seq"] for e in collected}) == len(collected)
        assert sum(e["topic"] == "ticket.sla_breached" for e in collected) == first["sla_breaches"]
        assert c.get("/integration/v1/events", params={"after": cursor}, headers=headers).json()["next_cursor"] == str(max(cursor, "0"))
        assert c.get("/integration/v1/events").status_code == 401
    # nothing a client proposes changes data before a person decides (the plan stays management_pending, proven in G02)
    assert sql(database, "select count(*) as n from event_outbox where payload::text ilike '%0901%'")[0]["n"] == 0   # events carry no phone numbers


# ---------------------------------------------------------------- G13


def test_G13_a_request_reported_to_reception_shows_in_the_residents_list(database):
    from test_resident_contract import BASE
    with client(database) as c:
        context, _ = operation(c, "get_verified_resident_context")
        place = context["residences"][0]
        channel = c.post("/resident/chats", json={"title": "Đèn hành lang"}).json()["id"]
        message = c.post(f"/resident/chats/{channel}/messages", json={"text": "Đèn hành lang tầng 12 hỏng", "client_message_id": str(uuid4())}).json()
        draft, _ = operation(c, "create_ticket_draft", {"channel_id": channel, "domain_id": place["domain_id"], "building_id": place["building_id"],
                                                         "unit_id": place["unit_id"], "category_id": CATEGORY})
        target = {"channel_id": channel, "draft_id": draft["draftId"]}
        operation(c, "update_ticket_incident", {**target, "fields": {"source_message_id": message["id"], "facts": [
            {"key": "symptom", "value": "hỏng", "source": "customer_report", "source_message_id": message["id"]},
            {"key": "item", "value": "đèn hành lang", "source": "customer_report", "source_message_id": message["id"]}]}})
        operation(c, "submit_ticket_assessment", {**target, "assessment": {"priority": "normal", "severity": "minor", "reason": "Cư dân báo"}})
        operation(c, "resolve_management_destination", target)
        handoff, _ = operation(c, "handoff_ticket", {**target, "plan_required": True})
        ticket = UUID(handoff["ticket"]["id"])

        linked = sql(database, "select c.id,c.status,c.code from vh_resident_cases c join vh_resident_case_tickets l on l.case_id=c.id where l.ticket_id=$1", ticket)
        assert len(linked) == 1 and linked[0]["status"] == "processing"                                    # 1: the request has a case
        listed = c.get(BASE + "/requests?filter=open")
        assert listed.status_code == 200, listed.text
        mine = [r for r in listed.json()["items"] if r["id"] == str(linked[0]["id"])]
        assert len(mine) == 1 and mine[0]["status"] == "processing"                                         # 2: and it is in the list
        detail = c.get(BASE + f"/requests/{linked[0]['id']}")
        assert detail.status_code == 200, detail.text
        labels = [e["label"] for e in detail.json()["events"]]
        assert labels[:2] == ["Đã tiếp nhận phản ánh", "Đã chuyển phản ánh đến bộ phận xử lý"]             # 3: with its public timeline
        assert "VH-" not in detail.text and "VH-" not in listed.text                                       # 4: no internal code reaches the resident
    sql(database, "select app_ensure_case($1)", ticket)
    assert sql(database, "select count(*) as n from vh_resident_cases c join vh_resident_case_tickets l on l.case_id=c.id where l.ticket_id=$1", ticket)[0]["n"] == 1   # 5: asking again adds nothing


# ---------------------------------------------------------------- the pack the platform learns from


def test_the_knowledge_pack_keeps_management_documents_out_of_the_residents_pack(database, secret):
    headers = {"X-Client-Id": CLIENT, **bearer(secret)}
    with outsider(database) as c:
        resident = c.get("/integration/v1/knowledge/pack", params={"audience": "resident"}, headers=headers)
        assert resident.status_code == 200, resident.text
        titles = [d["title"] for d in resident.json()["documents"]]
        assert titles and not any("nội bộ" in t for t in titles)
        management = c.get("/integration/v1/knowledge/pack", params={"audience": "management"}, headers=headers).json()
        assert any("nội bộ" in d["title"] for d in management["documents"])
        again = c.get("/integration/v1/knowledge/pack", params={"audience": "resident", "since": resident.json()["version"]}, headers=headers).json()
        assert again["unchanged"] is True and again["documents"] == []
        assert all(d["checksum"].startswith("sha256:") for d in resident.json()["documents"])
        assert c.get("/integration/v1/knowledge/pack", headers=bearer("ics_wrong")).status_code == 401
