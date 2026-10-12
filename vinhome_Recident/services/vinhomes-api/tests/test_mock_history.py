"""The generated world gives every request the history it would have had (docs/domain/NAP_DU_LIEU.md)."""
import asyncio
import json
from collections import defaultdict
from datetime import date, timedelta

import pytest
from test_integration_auth import person
from test_resident_contract import BASE, key, sql
from test_resident_contract import database as database  # noqa: F401 -- pytest fixture export

from vinhomes_api import database as tool
from vinhomes_api import mock_data
from vinhomes_api.mock_data import build
from vinhomes_api.v3_mutations import ALLOWED_TRANSITIONS, TICKET_TRANSITIONS


@pytest.fixture(scope="module", autouse=True)
def world(database):
    asyncio.run(build(database["admin"], "test", 42))


def tickets(database):
    return sql(database, "select id,status,version,last_event_seq,created_at,resolved_at from tickets where code like 'MOCK-%' order by code")


def events_by_ticket(database):
    grouped = defaultdict(list)
    for e in sql(database, """select ticket_id,seq,event_type,from_status,to_status,occurred_at,payload from ticket_events
                              where ticket_id in (select id from tickets where code like 'MOCK-%') order by ticket_id,seq"""):
        grouped[e["ticket_id"]].append(e)
    return grouped


def test_each_request_has_an_ordered_history_that_ends_where_it_stands_and_follows_the_rules(database):
    grouped = events_by_ticket(database)
    for t in tickets(database):
        events = grouped[t["id"]]
        assert [e["seq"] for e in events] == list(range(1, len(events) + 1)), t["id"]                       # 1: numbered without gaps
        assert events[0]["event_type"] == "ticket.created" and events[0]["to_status"] == "open"
        assert [e["occurred_at"] for e in events] == sorted(e["occurred_at"] for e in events)               # 2: in time order
        assert t["version"] == t["last_event_seq"] == len(events)                                           # 3: the request knows how far it got
        moves = [e for e in events if e["event_type"] == "ticket.status_changed"]
        for e in moves:
            assert e["to_status"] in TICKET_TRANSITIONS.get(e["from_status"], set()), (t["status"], e["from_status"], e["to_status"])   # 4
        assert (moves[-1]["to_status"] if moves else "open") == t["status"]                                  # 5: it ends where it stands
        steps = ["accepted"] + [json.loads(e["payload"])["status"] for e in events if e["event_type"] == "work_order.status_changed"]
        for before, after in zip(steps, steps[1:]):
            assert after in ALLOWED_TRANSITIONS[before], (before, after)                                     # 6: the job moved the way jobs move
    assert sql(database, "select count(*) as n from ticket_events where occurred_at>now()")[0]["n"] == 0       # 7: nothing is dated tomorrow
    assert sql(database, "select count(*) as n from tickets where resolved_at>now() or closed_at>now() or created_at>now()")[0]["n"] == 0


def test_work_matches_the_status_and_nobody_holds_more_than_their_places(database):
    work = defaultdict(list)
    for w in sql(database, """select w.ticket_id,w.status as work,a.status as assignment,a.staff_id,w.category_id,a.accepted_at,a.ended_at,
                              exists(select 1 from staff_specialties s where s.staff_id=a.staff_id and s.category_id=w.category_id) as skilled
                              from work_orders w join work_assignments a on a.work_order_id=w.id
                              where w.ticket_id in (select id from tickets where code like 'MOCK-%')"""):
        work[w["ticket_id"]].append(w)
    expected = {"assigned": ("accepted", "accepted"), "in_progress": ("in_progress", "accepted"),
                "resolved": ("completed", "completed"), "closed": ("completed", "completed")}
    for t in tickets(database):
        jobs = work.get(t["id"], [])
        if t["status"] in expected:
            assert [(j["work"], j["assignment"]) for j in jobs] == [expected[t["status"]]], t["status"]    # 1: the job is where the request says
            assert jobs[0]["skilled"]                                                                     # 2: and the person has the skill
        else:
            assert not jobs, t["status"]                                                                  # 3: no job before there is a plan
    overloaded = sql(database, """select a.staff_id from work_assignments a join work_orders w on w.id=a.work_order_id
        join staff_profiles p on p.id=a.staff_id where a.status='accepted' and w.status not in ('completed','cancelled','rejected')
        group by a.staff_id,p.max_concurrent_jobs having count(*)>p.max_concurrent_jobs""")
    assert overloaded == []                                                                               # 4: nobody has more than their places
    assert sql(database, "select count(*) as n from work_assignments where status='completed' and (ended_at is null or ended_at<accepted_at)")[0]["n"] == 0


def test_at_any_hour_a_technician_is_on_shift_with_room_and_free_hands_for_a_new_repair(database):
    """What the platform's coordinator needs to dispatch a repair, from the generated world alone."""
    free = """select p.user_id from staff_profiles p
        join staff_specialties s on s.staff_id=p.id and s.category_id=$1 and s.active
        join staff_shifts sh on sh.staff_id=p.id and sh.status='available'
          and sh.starts_at<=now()+make_interval(hours => h) and sh.ends_at>now()+make_interval(hours => h)
        where p.user_id like 'mock-%' and p.active and p.availability='available'
          and p.max_concurrent_jobs>(select count(*) from work_assignments a join work_orders w on w.id=a.work_order_id
            where a.staff_id=p.id and a.status in ('offered','accepted') and w.status not in ('completed','cancelled','rejected'))
          and not exists (select 1 from work_assignments a join work_orders w on w.id=a.work_order_id
            where a.staff_id=p.id and a.status='accepted' and w.status in ('en_route','arrived','awaiting_approval','in_progress'))"""
    uncovered = sql(database, f"select h from generate_series(0,71) h where not exists ({free})", mock_data.CAT_TECH)
    assert uncovered == []                                                                                # 1: every hour of the next three days
    shifts = sql(database, """select p.user_id,min(sh.ends_at-sh.starts_at) as shortest,max(sh.ends_at-sh.starts_at) as longest,
        min(extract(hour from sh.starts_at at time zone 'Asia/Ho_Chi_Minh')) as starts from staff_shifts sh join staff_profiles p on p.id=sh.staff_id
        join staff_specialties s on s.staff_id=p.id and s.category_id=$1 where p.user_id like 'mock-%' group by p.user_id order by p.user_id""", mock_data.CAT_TECH)
    assert len(shifts) >= 3 and all(row["shortest"] == row["longest"] == timedelta(hours=8) for row in shifts)   # 2: several people, eight hours each
    assert {int(row["starts"]) for row in shifts} == {6, 14, 22}                                         # 3: morning, afternoon and night


def test_the_chat_and_the_residents_own_timeline_are_there(database):
    for t in tickets(database):
        channel = sql(database, "select channel_id from tickets where id=$1", t["id"])[0]["channel_id"]
        messages = sql(database, "select seq,sender_kind from messages where channel_id=$1 order by seq", channel)
        assert [(m["seq"], m["sender_kind"]) for m in messages] == [(1, "user"), (2, "agent")]            # 1: what was said and the receipt
        case = sql(database, """select c.id,c.status from vh_resident_cases c join vh_resident_case_tickets l on l.case_id=c.id where l.ticket_id=$1""", t["id"])
        if t["status"] == "cancelled":
            assert not case
            continue
        lines = [e["label"] for e in sql(database, "select label from vh_resident_public_events where case_id=$1 order by occurred_at,id", case[0]["id"])]
        assert lines[0] == "Đã tiếp nhận phản ánh"                                                          # 2: the resident's timeline starts at the beginning
        if t["status"] == "resolved":
            assert case[0]["status"] == "confirmation"                                                     # 3: resolved: waiting for the resident's answer
        if t["status"] == "closed":
            assert case[0]["status"] == "completed" and lines[-1] == "Bạn đã xác nhận kết quả"             # 4: closed: the resident confirmed, the timeline ends
    assert sql(database, "select count(*) as n from messages where body::text like '%VH-%'")[0]["n"] == 0    # 5: no internal code in what a resident reads


def test_staff_and_management_see_the_history_through_the_api(database):
    active = sql(database, """select t.id,p.user_id from tickets t join work_orders w on w.ticket_id=t.id join work_assignments a on a.work_order_id=w.id
        join staff_profiles p on p.id=a.staff_id where t.code like 'MOCK-%' and t.status='in_progress' limit 1""")
    assert active, "the generated world has no request in progress"
    with person(database, "local-v3-management") as manager:
        detail = manager.get(f"/tickets/{active[0]['id']}")
        assert detail.status_code == 200, detail.text
        assert [w["status"] for w in detail.json()["workOrders"]] == ["in_progress"]
        conversation = manager.get(f"/tickets/{active[0]['id']}/conversation")
        assert conversation.status_code == 200 and len(conversation.json()["items"]) == 2
    with person(database, active[0]["user_id"]) as worker:
        mine = worker.get("/my-work-orders?limit=100")
        assert mine.status_code == 200
        assert any(j["ticket_id"] == str(active[0]["id"]) and j["assignment_status"] == "accepted" for j in mine.json()["items"])


def test_building_the_world_again_adds_nothing(database):
    tables = ("tickets", "ticket_events", "work_orders", "work_assignments", "vh_ticket_plans", "messages", "ticket_routing_history",
              "vh_resident_cases", "vh_resident_public_events")
    before = {t: sql(database, f"select count(*) as n from {t}")[0]["n"] for t in tables}
    asyncio.run(build(database["admin"], "test", 42))
    assert {t: sql(database, f"select count(*) as n from {t}")[0]["n"] for t in tables} == before


def test_starting_again_leaves_alone_what_people_did_since(database, monkeypatch):
    """The packaged stack runs `seed` and `mock` on every start (deploy/compose.yml), also on a later day."""
    worked = sql(database, """with e as (insert into ticket_events(id,tenant_id,ticket_id,seq,event_type,actor_kind,actor_user_id,idempotency_key,correlation_id,payload,occurred_at)
            select gen_random_uuid(),t.tenant_id,t.id,t.last_event_seq+1,'ticket.note_added','human','local-v3-management','again:'||t.id,gen_random_uuid(),'{}'::jsonb,now()
            from tickets t where t.id=(select id from tickets where code like 'MOCK-%' and status='triaging' order by code limit 1) returning ticket_id)
        update tickets set last_event_seq=last_event_seq+1,version=version+1 where id=(select ticket_id from e) returning id,version,last_event_seq""")
    sql(database, "insert into users(id,email,name,status) values('newcomer','newcomer@example.invalid','Nhân viên mới','active') returning id")
    sql(database, "insert into tenant_memberships(tenant_id,user_id,status,joined_at) select tenant_id,'newcomer','active',now() from tenant_memberships where user_id='mock-minh' returning id")

    def state():
        return (sql(database, "select id,version,last_event_seq from tickets where id=$1", worked[0]["id"]), sql(database, "select count(*) as n from amenity_bookings"),
                sql(database, "select m.user_id,r.role_code from scoped_user_roles r join tenant_memberships m on m.id=r.membership_id where m.user_id in ('newcomer','mock-minh') order by 1,2"))
    before = state()

    class Tomorrow(date):
        @classmethod
        def today(cls):
            return date.today() + timedelta(days=1)
    monkeypatch.setattr(mock_data, "date", Tomorrow)
    asyncio.run(tool.seed(database["admin"]))
    asyncio.run(build(database["admin"], "test", 42))
    assert state() == before                                                                 # 1: the request keeps its place, no new bookings, no new roles
    assert before[0] == worked and all(row["role_code"] != "customer" for row in before[2])  # 2: staff are not made residents of a building


def test_a_resident_can_answer_a_resolved_request_of_the_generated_world(database):
    waiting = sql(database, "select id,requester_user_id from vh_resident_cases where status='confirmation' order by id limit 1")
    assert waiting, "the generated world has no resolved request waiting for its resident"
    with person(database, waiting[0]["requester_user_id"]) as resident:
        detail = resident.get(f"{BASE}/requests/{waiting[0]['id']}").json()
        assert detail["status"] == "confirmation" and detail["permissions"]["canConfirm"] is True
        done = resident.post(f"{BASE}/requests/{waiting[0]['id']}/confirm", headers=key(),
                             json={"expectedVersion": detail["version"], "resolutionRevision": detail["resolutionRevision"]})
        assert done.status_code == 200, done.text
        assert done.json()["status"] == "completed"
