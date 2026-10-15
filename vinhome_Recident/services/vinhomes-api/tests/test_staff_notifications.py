"""A staff member is told, durably, when work is offered to them (migration 0010)."""
from uuid import UUID

from test_resident_contract import client, sql
from test_resident_contract import database as database  # noqa: F401 -- pytest fixture export
from test_staff_dispatch import approved_order, offer


def inbox(database, actor):
    with client(database, actor) as person:
        listed = person.get("/my/notifications")
        assert listed.status_code == 200, listed.text
        return listed.json()["items"]


def test_an_offer_leaves_a_notification_for_the_person_offered_the_work_and_no_one_else(database):
    sql(database, "update staff_profiles set max_concurrent_jobs=3 where user_id='local-v3-technical' returning id")
    staff = sql(database, "select id from staff_profiles where user_id='local-v3-technical'")[0]["id"]
    before = {item["id"] for item in inbox(database, "technical")}
    elsewhere = len(inbox(database, "security"))
    order, _ = approved_order(database)
    offered = offer(database, order, staff)
    assert offered.status_code == 201, offered.text

    new = [item for item in inbox(database, "technical") if item["id"] not in before]
    assert len(new) == 1, new                                                                       # 1: once
    note = new[0]
    assert note["payload"]["type"] == "work.offered" and note["read_at"] is None                    # 2: unread, of the right kind
    assert note["payload"]["workOrderId"] == order["id"] and note["payload"]["assignmentId"] == offered.json()["id"]
    ticket = sql(database, "select id,code,title from tickets where id=$1", UUID(note["payload"]["ticketId"]))[0]
    assert note["payload"]["ticketCode"] == ticket["code"] and note["payload"]["title"] == ticket["title"]
    assert len(inbox(database, "security")) == elsewhere                                            # 3: nobody else is told

    with client(database, "technical") as person:                                                   # 4: reading it marks it read
        assert person.post(f"/my/notifications/{note['id']}/read").status_code == 200
    assert next(i for i in inbox(database, "technical") if i["id"] == note["id"])["read_at"] is not None


def test_an_offer_that_is_refused_and_made_again_is_told_again(database):
    sql(database, "update staff_profiles set max_concurrent_jobs=3 where user_id='local-v3-technical' returning id")
    staff = sql(database, "select id from staff_profiles where user_id='local-v3-technical'")[0]["id"]
    before = {item["id"] for item in inbox(database, "technical")}
    order, _ = approved_order(database)
    first = offer(database, order, staff)
    assert first.status_code == 201, first.text
    with client(database, "technical") as person:
        refused = person.post(f"/assignments/{first.json()['id']}/response", json={"status": "rejected", "rejection_reason": "Đang bận"})
        assert refused.status_code == 200, refused.text
    with client(database, "management") as manager:
        order = manager.get(f"/work-orders/{order['id']}").json()["workOrder"]
    second = offer(database, order, staff)
    assert second.status_code == 201, second.text
    told = [i["payload"]["assignmentId"] for i in inbox(database, "technical") if i["id"] not in before]
    assert sorted(told) == sorted([first.json()["id"], second.json()["id"]])
