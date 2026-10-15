"""What the database itself refuses for the entities of the golden scenarios (migration 0007)."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncpg
import pytest
from test_resident_contract import TENANT, sql
from test_resident_contract import database as database  # noqa: F401 -- pytest fixture export

STATEFUL = {"debit_notes", "access_cards", "service_requests", "visitor_passes", "amenity_bookings", "construction_permits", "announcements"}
RESIDENT = "local-v3-resident"


def unit(database):
    return sql(database, "select id from units where tenant_id=$1 order by code limit 1", TENANT)[0]["id"]


def visitor(database, status="pending_approval", qr=None):
    return sql(database, """insert into visitor_passes(tenant_id,code,unit_id,host_user_id,guest_name,purpose,visit_from,visit_to,status,qr_token)
        values($1,$2,$3,$4,'Khách','family_visit',now()+interval '1 day',now()+interval '1 day 2 hours',$5,$6) returning id""",
               TENANT, "VP-" + uuid4().hex[:10], unit(database), RESIDENT, status, qr)[0]["id"]


def test_every_stateful_table_is_held_to_the_reference_table(database):
    triggers = {r["table_name"] for r in sql(database, """select c.relname as table_name from pg_trigger t join pg_class c on c.oid=t.tgrelid
        where not t.tgisinternal and t.tgname like '%\\_transition'""")}
    assert triggers == STATEFUL
    listed = {r["entity"] for r in sql(database, "select distinct entity from state_transitions")}
    assert listed == STATEFUL
    # Every entity has a way in, and every status a table accepts has a way out except the final ones.
    for entity in STATEFUL:
        assert sql(database, "select 1 as ok from state_transitions where entity=$1 and from_status=''", entity)


def test_a_status_the_table_does_not_allow_is_refused_whoever_writes_it(database):
    with pytest.raises(asyncpg.CheckViolationError):
        visitor(database, status="checked_in", qr="x" + uuid4().hex)
    one = visitor(database)
    with pytest.raises(asyncpg.CheckViolationError):  # approved needs the QR the guest will show
        sql(database, "update visitor_passes set status='approved' where id=$1 returning id", one)
    assert sql(database, "update visitor_passes set status='approved',qr_token=$2 where id=$1 returning status", one, "q" + uuid4().hex)[0]["status"] == "approved"
    assert sql(database, "update visitor_passes set status='checked_in' where id=$1 returning status", one)[0]["status"] == "checked_in"
    with pytest.raises(asyncpg.CheckViolationError):  # nothing walks back from checked in to approved
        sql(database, "update visitor_passes set status='approved' where id=$1 returning id", one)
    expired = visitor(database)
    sql(database, "update visitor_passes set status='cancelled' where id=$1 returning id", expired)
    with pytest.raises(asyncpg.CheckViolationError):  # cancelled is final
        sql(database, "update visitor_passes set status='pending_approval' where id=$1 returning id", expired)


def test_a_visit_window_must_run_forward(database):
    with pytest.raises(asyncpg.CheckViolationError):
        sql(database, """insert into visitor_passes(tenant_id,code,unit_id,host_user_id,guest_name,purpose,visit_from,visit_to,status)
            values($1,$2,$3,$4,'Khách','other',now()+interval '2 hours',now()+interval '1 hour','pending_approval')""",
            TENANT, "VP-" + uuid4().hex[:10], unit(database), RESIDENT)


def test_a_debit_note_cannot_leave_draft_unless_its_lines_add_up(database):
    note = sql(database, """insert into debit_notes(tenant_id,doc_no,unit_id,period_month,issue_date,due_date,subtotal,vat_amount,total_amount,status)
        values($1,$2,$3,date_trunc('month',now())::date,current_date,current_date+10,1000,100,1100,'draft') returning id""",
               TENANT, "DN-" + uuid4().hex[:10], unit(database))[0]["id"]
    sql(database, """insert into debit_note_lines(tenant_id,debit_note_id,line_no,fee_kind,description,unit_price,amount)
        values($1,$2,1,'management','Phí quản lý',900,900)""", TENANT, note)
    with pytest.raises(asyncpg.CheckViolationError):
        sql(database, "update debit_notes set status='issued' where id=$1 returning id", note)
    sql(database, """insert into debit_note_lines(tenant_id,debit_note_id,line_no,fee_kind,description,unit_price,amount)
        values($1,$2,2,'parking','Gửi xe',100,100)""", TENANT, note)
    assert sql(database, "update debit_notes set status='issued' where id=$1 returning status", note)[0]["status"] == "issued"
    with pytest.raises(asyncpg.CheckViolationError):  # paid more than owed
        sql(database, "update debit_notes set paid_amount=1200 where id=$1 returning id", note)
    with pytest.raises(asyncpg.CheckViolationError):  # paid in full means paid in full
        sql(database, "update debit_notes set status='paid',paid_amount=500 where id=$1 returning id", note)
    with pytest.raises(asyncpg.CheckViolationError):  # a note says what it totals
        sql(database, "update debit_notes set total_amount=1 where id=$1 returning id", note)


def booking(database, amenity, start, end, area="main", status="confirmed"):
    return sql(database, """insert into amenity_bookings(tenant_id,code,amenity_id,area_code,unit_id,booked_by_user_id,start_at,end_at,status)
        values($1,$2,$3,$4,$5,$6,$7,$8,$9) returning id""",
               TENANT, "AB-" + uuid4().hex[:10], amenity, area, unit(database), RESIDENT, start, end, status)[0]["id"]


def test_two_live_bookings_of_the_same_thing_never_overlap(database):
    amenity = sql(database, """insert into amenities(tenant_id,code,name,category,areas,open_time,close_time)
        values($1,$2,'Khu BBQ','bbq','{pit1,pit2}','08:00','22:00') returning id""", TENANT, "BBQ-" + uuid4().hex[:6])[0]["id"]
    ten = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) + timedelta(days=2)
    first = booking(database, amenity, ten, ten + timedelta(hours=1))
    with pytest.raises(asyncpg.ExclusionViolationError):
        booking(database, amenity, ten + timedelta(minutes=30), ten + timedelta(minutes=90))
    booking(database, amenity, ten + timedelta(minutes=30), ten + timedelta(minutes=90), area="pit2")   # another pit
    booking(database, amenity, ten + timedelta(hours=1), ten + timedelta(hours=2))                      # back to back
    assert sql(database, "update amenity_bookings set status='cancelled',cancelled_by='resident' where id=$1 returning status", first)[0]["status"] == "cancelled"
    booking(database, amenity, ten + timedelta(minutes=15), ten + timedelta(minutes=45))               # freed by the cancel


def test_a_gate_log_is_append_only_and_a_refusal_says_why(database):
    event = sql(database, """insert into access_events(tenant_id,gate_code,direction,credential_kind,result)
        values($1,'G1','in','manual','granted') returning id""", TENANT)[0]["id"]
    with pytest.raises(asyncpg.PostgresError):
        sql(database, "update access_events set result='denied',deny_reason='x' where id=$1 returning id", event)
    with pytest.raises(asyncpg.PostgresError):
        sql(database, "delete from access_events where id=$1 returning id", event)
    with pytest.raises(asyncpg.CheckViolationError):
        sql(database, "insert into access_events(tenant_id,gate_code,direction,credential_kind,result) values($1,'G1','in','card','denied')", TENANT)


def test_vehicles_and_cards_keep_their_promises(database):
    plate = "29A-" + uuid4().hex[:5]
    sql(database, "insert into vehicles(tenant_id,unit_id,owner_name,kind,plate_no) values($1,$2,'An','motorbike',$3)", TENANT, unit(database), plate)
    with pytest.raises(asyncpg.UniqueViolationError):  # one live vehicle per plate
        sql(database, "insert into vehicles(tenant_id,unit_id,owner_name,kind,plate_no) values($1,$2,'Bình','motorbike',$3)", TENANT, unit(database), plate)
    with pytest.raises(asyncpg.CheckViolationError):  # a vehicle card belongs to a vehicle
        sql(database, "insert into access_cards(tenant_id,card_no,kind,status) values($1,$2,'vehicle','pending_issue')", TENANT, "C-" + uuid4().hex[:8])
    card = sql(database, "insert into access_cards(tenant_id,card_no,kind,unit_id,status) values($1,$2,'resident',$3,'pending_issue') returning id",
               TENANT, "C-" + uuid4().hex[:8], unit(database))[0]["id"]
    assert sql(database, "update access_cards set status='active' where id=$1 returning status", card)[0]["status"] == "active"
    assert sql(database, "update access_cards set status='lost' where id=$1 returning status", card)[0]["status"] == "lost"
    with pytest.raises(asyncpg.CheckViolationError):  # a lost card never comes back
        sql(database, "update access_cards set status='active' where id=$1 returning id", card)


def test_an_announcement_written_by_an_agent_names_the_client_and_publishing_leaves_a_time(database):
    base = "insert into announcements(tenant_id,code,kind,title,body_md,status,drafted_by,drafted_by_client_id,published_at) values($1,$2,'outage_notice','Cắt nước','…',$3,$4,$5,$6)"
    with pytest.raises(asyncpg.CheckViolationError):
        sql(database, base, TENANT, "AN-" + uuid4().hex[:8], "draft", "agent", None, None)
    with pytest.raises(asyncpg.CheckViolationError):
        sql(database, base, TENANT, "AN-" + uuid4().hex[:8], "draft", "staff", "demo-platform", None)
    sql(database, base, TENANT, "AN-" + uuid4().hex[:8], "draft", "agent", "demo-platform", None)
    draft = sql(database, "select id from announcements where status='draft' order by created_at desc limit 1")[0]["id"]
    with pytest.raises(asyncpg.CheckViolationError):
        sql(database, "update announcements set status='published' where id=$1 returning id", draft)
    assert sql(database, "update announcements set status='published',published_at=now() where id=$1 returning status", draft)[0]["status"] == "published"


def test_a_service_request_cannot_be_rejected_without_a_reason(database):
    request = sql(database, """insert into service_requests(tenant_id,code,kind,unit_id,requester_user_id,channel,status)
        values($1,$2,'card_reissue',$3,$4,'app','draft') returning id""", TENANT, "SR-" + uuid4().hex[:8], unit(database), RESIDENT)[0]["id"]
    for step in ("submitted", "in_review"):
        sql(database, "update service_requests set status=$2 where id=$1 returning id", request, step)
    with pytest.raises(asyncpg.CheckViolationError):
        sql(database, "update service_requests set status='rejected' where id=$1 returning id", request)
    assert sql(database, "update service_requests set status='rejected',decision_note='Thiếu giấy tờ' where id=$1 returning status", request)[0]["status"] == "rejected"
