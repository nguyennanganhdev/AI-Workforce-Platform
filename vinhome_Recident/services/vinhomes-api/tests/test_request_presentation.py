"""Plan editing is persisted, scoped, versioned and waits for resident consent."""
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from test_resident_contract import sql
from test_resident_contract import database as database  # noqa: F401
from test_v3_agent_database import demo_client
from test_v3_coordination import BASE, SERVICE, app, hand_over


def draft(c, database):
    handoff, _ = hand_over(c, f"Vòi bếp cần sửa {uuid4().hex[:6]}")
    team, ticket = handoff["team"]["id"], handoff["ticket"]["id"]
    message = sql(database, "select message_id from vh_reception_supervisor_messages where team_id=$1", UUID(team))[0]["message_id"]
    assert c.post(BASE + "/reception/verify", headers=SERVICE, json={"team_id": team, "message_id": message}).status_code == 200
    view = c.get(BASE + f"/teams/{team}/view", headers=SERVICE).json()
    response = c.post(BASE + f"/teams/{team}/plans", headers=SERVICE, json={
        "request_id": str(uuid4()), "payload_hash": "a" * 64, "ticket_version": view["ticket_version"], "target_plan_version": 1,
        "plan": {"summary": "Kiểm tra vòi nước", "steps": ["Khóa van", "Kiểm tra gioăng"], "performer_role": "Kỹ thuật viên",
                 "expected_duration": "30 phút", "conditions": "Cư dân có mặt", "cost": None, "result_refs": [], "attachment_ids": []}})
    assert response.status_code == 200, response.text
    return ticket, response.json()["canonical_id"]


def test_management_edits_plan_and_schedule_without_bypassing_resident_consent(database, monkeypatch):
    monkeypatch.setenv("VINHOMES_API_SUPERVISOR_APPROVES_PLANS", "0")
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


def test_appointment_requires_timezone_and_future_time(database, monkeypatch):
    monkeypatch.setenv("VINHOMES_API_SUPERVISOR_APPROVES_PLANS", "0")
    with app(database) as resident:
        _, plan = draft(resident, database)
    with demo_client(database, "management") as manager:
        body = {"version": 0, "summary": "Kiểm tra vòi", "steps": ["Kiểm tra gioăng"], "appointment_at": "2026-01-01T09:00:00"}
        assert manager.patch(f"/plans/{plan}/presentation", json=body).status_code == 422
        assert manager.patch(f"/plans/{plan}/presentation", json={**body, "appointment_at": "2020-01-01T09:00:00+07:00"}).status_code == 422

