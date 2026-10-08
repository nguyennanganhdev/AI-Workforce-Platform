from fastapi.testclient import TestClient
from vinhomes_api.demo_api import create_demo_app


def call(client, method, path, actor="resident", body=None, expected=200):
    response = client.request(method, path, headers={"X-Demo-Actor": actor}, json=body)
    assert response.status_code == expected, response.text
    return response.json()


def work(client, category="technical", severity="P2"):
    chat = call(client, "POST", "/resident/chats", body={"title": "Demo"}, expected=201)
    ticket = call(client, "POST", f'/resident/chats/{chat["id"]}/tickets', body={"title": "Incident", "description": "Mock incident", "category_id": category, "business_severity": severity}, expected=201)
    call(client, "POST", f'/tickets/{ticket["id"]}/routing/ack', "management")
    order = call(client, "POST", f'/tickets/{ticket["id"]}/work-orders', "management", expected=201)
    return ticket, order


def accept(client, order, actor):
    call(client, "POST", f'/work-orders/{order["id"]}/assignments', "management", {"staff_id": actor})
    call(client, "POST", f'/assignments/{order["id"]}/response', actor, {"approved": True, "note": "Accepted"})
    call(client, "PATCH", f'/work-orders/{order["id"]}/status', actor, {"status": "in_progress"})


def test_full_water_flow_and_issued_revenue():
    with TestClient(create_demo_app()) as client:
        ticket, order = work(client)
        accept(client, order, "technical")
        water = call(client, "POST", f'/work-orders/{order["id"]}/water-shutdown-request', "technical", expected=201)
        call(client, "POST", f'/water-interruptions/{water["id"]}/start', "technical", expected=409)
        call(client, "POST", f'/approvals/{water["approval_id"]}/decision', "management", {"approved": True, "note": "Approved"})
        call(client, "POST", f'/water-interruptions/{water["id"]}/notify', "management")
        call(client, "POST", f'/water-interruptions/{water["id"]}/start', "technical")
        call(client, "PATCH", f'/work-orders/{order["id"]}/status', "technical", {"status": "completed", "evidence": "photo-demo"}, expected=409)
        call(client, "POST", f'/water-interruptions/{water["id"]}/restore', "technical")
        call(client, "PATCH", f'/work-orders/{order["id"]}/status', "technical", {"status": "completed", "evidence": "photo-demo"})
        assert call(client, "GET", "/reports/issued-revenue", "management")["billedAmount"] == 150000
        approval = call(client, "GET", "/resident/approvals")["items"][0]
        call(client, "POST", f'/resident/approvals/{approval["id"]}/decision', body={"approved": True, "note": "Done"})
        assert call(client, "GET", f'/resident/tickets/{ticket["id"]}')["ticket"]["status"] == "closed"
        response = client.get("/reports/issued-revenue.docx", headers={"X-Demo-Actor": "management"})
        assert response.status_code == 200 and response.content.startswith(b"PK")


def test_security_dispatch_and_emergency_ack():
    with TestClient(create_demo_app()) as client:
        ticket, order = work(client, "security", "P0")
        assert ticket["severity"] == "p1"
        call(client, "POST", f'/work-orders/{order["id"]}/assignments', "management", {"staff_id": "security"}, expected=409)
        approval = call(client, "POST", f'/work-orders/{order["id"]}/security/dispatch-request', "security", expected=201)
        call(client, "POST", f'/approvals/{approval["id"]}/decision', "management", {"approved": True, "note": "Dispatch"})
        accept(client, order, "security")
        call(client, "PATCH", f'/work-orders/{order["id"]}/status', "security", {"status": "completed", "evidence": "camera-demo"}, expected=409)
        alert = call(client, "POST", f'/tickets/{ticket["id"]}/emergency-alerts', "security", expected=201)
        call(client, "POST", f'/security/alerts/{alert["id"]}/escalate', "security")
        call(client, "POST", f'/security/alerts/{alert["id"]}/ack', "management")
        call(client, "PATCH", f'/work-orders/{order["id"]}/status', "security", {"status": "completed", "evidence": "camera-demo"})


def test_roles_busy_queue_idempotency_and_account_access():
    with TestClient(create_demo_app()) as client:
        _, first = work(client)
        accept(client, first, "technical")
        _, second = work(client)
        call(client, "POST", f'/work-orders/{second["id"]}/assignments', "management", {"staff_id": "technical"}, expected=409)
        call(client, "GET", "/admin/accounts", expected=403)
        body = {"text": "Report", "client_message_id": "one", "mention_agent_id": "report"}
        a = call(client, "POST", "/rooms/management-room/messages", "management", body, 201)
        b = call(client, "POST", "/rooms/management-room/messages", "management", body, 201)
        assert a["id"] == b["id"]
        assert len(call(client, "GET", "/rooms/management-room/messages", "management")["items"]) == 2
        call(client, "PATCH", "/admin/accounts/technical/access", "admin", {"status": "suspended"})
        call(client, "GET", "/my-work-orders", "technical", expected=403)
