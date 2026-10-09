"""Plan editing is persisted, scoped, versioned and waits for resident consent."""


import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from test_domain_database import app, demo_client, operation
from test_integration_auth import CLIENT, bearer, outsider
from test_resident_contract import CATEGORY, sql
from test_resident_contract import database as database  # noqa: F401

from vinhomes_api.integration import digest, new_secret


def draft(c, database):
    """The resident reports through Reception; the client that takes the case proposes a plan. Returns (ticket, plan)."""
    context, _ = operation(c, "get_verified_resident_context")
    place = context["residences"][0]
    channel = c.post("/resident/chats", json={"title": "Rò nước"}).json()["id"]
    message = c.post(f"/resident/chats/{channel}/messages", json={"text": "Vòi bếp rò nước", "client_message_id": str(uuid4())}).json()
    created, _ = operation(c, "create_ticket_draft", {"channel_id": channel, "domain_id": place["domain_id"], "building_id": place["building_id"],
                                                       "unit_id": place["unit_id"], "category_id": CATEGORY})
    target = {"channel_id": channel, "draft_id": created["draftId"]}
    operation(c, "update_ticket_incident", {**target, "fields": {"source_message_id": message["id"], "facts": [
        {"key": "symptom", "value": "rò nước", "source": "customer_report", "source_message_id": message["id"]},
        {"key": "item", "value": "vòi bếp", "source": "customer_report", "source_message_id": message["id"]}]}})
    operation(c, "submit_ticket_assessment", {**target, "assessment": {"priority": "normal", "severity": "minor", "reason": "Cư dân báo"}})
    operation(c, "resolve_management_destination", target)
    handoff, _ = operation(c, "handoff_ticket", {**target, "plan_required": True})
    ticket = handoff["ticket"]["id"]
    secret = new_secret()
    sql(database, "update integration_clients set secret_hash=$1 where id=$2 returning id", digest(secret), CLIENT)
    headers = {"X-Client-Id": CLIENT, **bearer(secret)}
    with outsider(database) as o:
        version = o.get(f"/integration/v1/cases/{ticket}", headers=headers).json()["ticket"]["version"]
        proposed = o.post(f"/integration/v1/cases/{ticket}/plans", headers={**headers, "Idempotency-Key": uuid4().hex},
                          json={"ticket_version": version, "summary": "Thay gioăng vòi", "steps": ["Khóa van", "Thay gioăng"]})
        assert proposed.status_code == 201, proposed.text
    sql(database, "update integration_clients set secret_hash=null where id=$1 returning id", CLIENT)
    return ticket, proposed.json()["id"]


def test_management_edits_plan_and_schedule_without_bypassing_resident_consent(database):
    with app(database) as resident:
        ticket, plan = draft(resident, database)
        staff = sql(database, """select sp.id from staff_profiles sp join staff_specialties ss on ss.staff_id=sp.id
            join tickets t on t.management_unit_id=sp.management_unit_id and t.category_id=ss.category_id
            where t.id=$1 and sp.active and ss.active limit 1""", UUID(ticket))[0]["id"]
        sql(database, "update staff_profiles set availability='available' where id=$1", staff)
        sql(database, "update staff_shifts set status='available',starts_at=now()-interval '1 hour',ends_at=now()+interval '2 days' where staff_id=$1", staff)
        appointment = (datetime.now(UTC) + timedelta(hours=2)).replace(microsecond=0).isoformat()
        body = {"version": 0, "summary": "Thay gioăng vòi nước", "steps": ["Khóa van", "Thay gioăng", "Kiểm tra rò rỉ"],
                "performer_staff_id": str(staff), "appointment_at": appointment}
        with demo_client(database, "technical") as technical:
            assert technical.patch(f"/plans/{plan}/presentation", json=body).status_code in (403, 404)
        with demo_client(database, "management") as manager:
            updated = manager.patch(f"/plans/{plan}/presentation", json=body)
            assert updated.status_code == 200, updated.text
            assert updated.json()["version"] == 1
            assert manager.patch(f"/plans/{plan}/presentation", json=body).status_code == 409
            assert manager.patch(f"/plans/{plan}/presentation", json={**body, "version": 1, "performer_staff_id": str(uuid4())}).status_code == 422
            shown = manager.get(f"/tickets/{ticket}/presentation")
            assert shown.status_code == 200, shown.text
            assert shown.json()["schedule"]["performer_staff_id"] == str(staff)
            assert shown.json()["schedule"]["performer_name"]
            assert shown.json()["resident"]["name"]
            stored = sql(database, "select title,steps::text,proposal::text from vh_ticket_plans where id=$1", UUID(plan))[0]
            assert stored["title"] == body["summary"]
            assert json.loads(stored["proposal"])["steps"] == body["steps"]
            assert json.loads(stored["steps"])[0]["description"] == "1. Khóa van\n2. Thay gioăng\n3. Kiểm tra rò rỉ"
            approved = manager.post(f"/plans/{plan}/management-decision", json={"version": 1, "decision": "approve", "note": "Đồng ý phương án."})
            assert approved.status_code == 200, approved.text
            assert not sql(database, "select id from work_orders where ticket_id=$1", UUID(ticket))
            assert manager.patch(f"/plans/{plan}/presentation", json={**body, "version": 2}).status_code == 409
        agreed = resident.post(f"/resident/plans/{plan}/decision", json={"version": 2, "decision": "approve", "note": "Đồng ý"})
        assert agreed.status_code == 200, agreed.text
        order = sql(database, "select w.scheduled_at,a.staff_id,w.status from work_orders w left join work_assignments a on a.work_order_id=w.id where w.ticket_id=$1", UUID(ticket))[0]
        assert order["scheduled_at"] == datetime.fromisoformat(appointment)
        assert order["staff_id"] == staff and order["status"] == "offered"
        audit = sql(database, "select count(*) as n from audit_events where event_type='plan.presentation_updated' and target_id=$1", plan)
        assert audit[0]["n"] == 1


def test_appointment_requires_timezone_and_future_time(database):
    with app(database) as resident:
        _, plan = draft(resident, database)
    with demo_client(database, "management") as manager:
        body = {"version": 0, "summary": "Kiểm tra vòi", "steps": ["Kiểm tra gioăng"], "appointment_at": "2026-01-01T09:00:00"}
        assert manager.patch(f"/plans/{plan}/presentation", json=body).status_code == 422
        assert manager.patch(f"/plans/{plan}/presentation", json={**body, "appointment_at": "2020-01-01T09:00:00+07:00"}).status_code == 422

