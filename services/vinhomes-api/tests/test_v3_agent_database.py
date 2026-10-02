"""Agent business APIs exercised against migrated, seeded PostgreSQL."""

from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from test_resident_contract import CATEGORY, TENANT, client, sql
from test_resident_contract import (
    database as database,  # noqa: PLC0414 -- pytest fixture export
)
from vinhomes_api.main import create_app
from vinhomes_api.v3_config import V3Settings

EXECUTE = "/internal/reception/operations/execute"
RECONCILE = "/internal/reception/operations/reconcile"


@contextmanager
def demo_client(database, actor):
    settings = V3Settings(
        "127.0.0.1", 8000, database["runtime"], TENANT, None, None, demo_mode=True
    )
    with TestClient(
        create_app(settings),
        client=("127.0.0.1", 50000),
        headers={"X-Demo-Actor": actor},
    ) as c:
        yield c


def operation(c, name, payload=None, expected=200):
    body = {
        "operation": name,
        "input": payload or {},
        "context": {},
        "idempotency_key": str(uuid4()),
    }
    response = c.post(EXECUTE, json=body)
    assert response.status_code == expected, response.text
    return response.json(), body


def test_reception_draft_handoff_and_durable_retry(database):
    with client(database) as c:
        context, _ = operation(c, "get_verified_resident_context")
        place = context["residences"][0]
        chat = c.post("/resident/chats", json={"title": "PostgreSQL agent flow"})
        assert chat.status_code == 201, chat.text
        channel = chat.json()["id"]
        message = c.post(
            f"/resident/chats/{channel}/messages",
            json={
                "text": "Bathroom is overflowing",
                "client_message_id": str(uuid4()),
            },
        )
        assert message.status_code == 201, message.text
        before = sql(database, "select count(*) as n from tickets")[0]["n"]
        draft, request = operation(
            c,
            "create_ticket_draft",
            {
                "channel_id": channel,
                "title": "Bathroom overflow",
                "description": "Resident reports water overflowing in bathroom",
                "domain_id": place["domain_id"],
                "building_id": place["building_id"],
                "unit_id": place["unit_id"],
                "category_id": CATEGORY,
                "source_message_id": message.json()["id"],
            },
        )
        assert sql(database, "select count(*) as n from tickets")[0]["n"] == before
        assert c.post(EXECUTE, json=request).json()["replayed"] is True
        assert c.post(RECONCILE, json=request).json()["status"] == "completed"
        bad = {**request, "input": {**request["input"], "title": "Changed"}}
        assert c.post(EXECUTE, json=bad).status_code == 409
        target = {"channel_id": channel, "draft_id": draft["draftId"]}
        operation(
            c,
            "update_ticket_incident",
            {**target, "fields": {"request_kind": "incident"}},
        )
        operation(
            c,
            "submit_ticket_assessment",
            {
                **target,
                "assessment": {
                    "priority": "high",
                    "severity": "major",
                    "reason": "Resident-reported overflow",
                },
            },
        )
        destination, _ = operation(c, "resolve_management_destination", target)
        assert destination["available"], destination
        handoff, request = operation(c, "handoff_ticket", target)
        assert handoff["accepted"], handoff
        ticket_id = handoff["ticket"]["id"]
        assert c.post(EXECUTE, json=request).json()["ticket"]["id"] == ticket_id
        assert (
            c.post(RECONCILE, json=request).json()["result"]["ticket"]["id"]
            == ticket_id
        )
        persisted = sql(
            database,
            "select priority,severity from tickets where id=$1",
            UUID(ticket_id),
        )[0]
        assert persisted == {"priority": "high", "severity": "major"}
        assert (
            sql(
                database,
                "select count(*) as n from vh_reception_supervisor_messages where ticket_id=$1",
                UUID(ticket_id),
            )[0]["n"]
            == 1
        )
        waiting, _ = operation(c, "register_supervisor_wait", {"ticket_id": ticket_id})
        assert waiting["registered"] and waiting["waitMode"] == "poll"
        operation(c, "get_supervisor_event", {"ticket_id": ticket_id})
        status, _ = operation(c, "get_ticket_status", {"ticket_id": ticket_id})
        assert status["ticket"]["id"] == ticket_id
        assert status["agentContext"]["source"] == "business_api"


def test_handoff_without_supervisor_creates_a_direct_flow_ticket(database):
    """A management unit with no versioned Supervisor still receives the ticket."""
    sql(database, "update agents set status='archived' where id='demo-supervisor'")
    try:
        with client(database) as c:
            context, _ = operation(c, "get_verified_resident_context")
            place = context["residences"][0]
            assert place["building_code"] and place["domain_name"]
            channel = c.post("/resident/chats", json={"title": "No supervisor"}).json()["id"]
            message = c.post(f"/resident/chats/{channel}/messages",
                             json={"text": "Light is broken", "client_message_id": str(uuid4())}).json()
            draft, _ = operation(c, "create_ticket_draft", {
                "channel_id": channel, "title": "Broken light", "description": "Hallway light does not turn on",
                "domain_id": place["domain_id"], "building_id": place["building_id"], "unit_id": place["unit_id"],
                "category_id": CATEGORY, "source_message_id": message["id"]})
            target = {"channel_id": channel, "draft_id": draft["draftId"]}
            operation(c, "submit_ticket_assessment", {**target, "assessment": {
                "priority": "normal", "severity": "minor", "reason": "Resident report"}})
            operation(c, "handoff_ticket", {**target, "plan_required": "no"}, expected=422)
            handoff, _ = operation(c, "handoff_ticket", {**target, "plan_required": False})
            assert handoff["accepted"] and handoff["team"] is None and handoff["handoff"] is None
            ticket_id = handoff["ticket"]["id"]
        created = sql(database, "select payload from ticket_events where ticket_id=$1 and event_type='ticket.created'", UUID(ticket_id))[0]
        payload = created["payload"] if isinstance(created["payload"], dict) else __import__("json").loads(created["payload"])
        assert "requiresPlan" not in payload
        with demo_client(database, "management") as c:
            session = c.get(f"/tickets/{ticket_id}/session").json()
            assert session == {"session": None, "missing": "supervisor"}
    finally:
        sql(database, "update agents set status='active' where id='demo-supervisor'")


def delegate(c, channel, message_id, actor="local-v3-resident"):
    """Open a run the way the backend does once a resident message is committed."""
    from vinhomes_api.reception_delegation import start_run
    from vinhomes_api.v3_reception_runtime import POLICY_VERSION, _resident_transaction

    async def run():
        async with _resident_transaction(c.app, actor) as db:
            return await start_run(db, actor, channel, message_id, POLICY_VERSION)

    return c.portal.call(run)


def resident_message(c, title, text="Xin chào"):
    channel = c.post("/resident/chats", json={"title": title}).json()["id"]
    message = c.post(f"/resident/chats/{channel}/messages", json={"text": text, "client_message_id": str(uuid4())}).json()
    return channel, message["id"]


def test_reception_policy_and_reply_are_backend_decisions(database, monkeypatch):
    monkeypatch.setenv("RECEPTION_DELEGATION_KEY", "ab" * 32)
    with client(database) as c:
        channel, message_id = resident_message(c, "Reply")
        policy = "/internal/reception/policy/evaluate"
        # A resident session is not a Reception delegation.
        assert c.post(policy, json={"message_text": "Xin chào", "assessment": None}).status_code == 401
        c.headers["Authorization"] = "Bearer " + delegate(c, channel, message_id)["token"]
        fire = c.post(policy, json={"message_text": "Bếp nhà tôi đang cháy", "assessment": None}).json()
        assert fire["emergency"] and fire["handoff_reason"] == "emergency"
        # "chảy" (leaking) shares its letters with "cháy" (fire) once diacritics are dropped.
        leak = c.post(policy, json={
            "message_text": "Vòi nước bị chảy nhỏ giọt", "assessment": {"intent": "incident"}}).json()
        assert not leak["emergency"] and leak["staff_required"] and leak["handoff_reason"] == "needs_staff"
        bulb = c.post(policy, json={"message_text": "Bóng đèn hành lang bị cháy bóng, tối om", "assessment": {"intent": "incident"}}).json()
        assert not bulb["emergency"] and bulb["staff_required"]
        smoke = c.post(policy, json={"message_text": "Bóng đèn bị cháy và đang bốc khói", "assessment": None}).json()
        assert smoke["emergency"]
        raised = c.post(policy, json={"message_text": "Ổ điện phát tia sáng lạ", "assessment": {"proposed_action": "emergency_handoff"}}).json()
        assert raised["emergency"] and raised["handoff_reason"] == "emergency"
        # A model proposal cannot lower what the keywords found.
        kept = c.post(policy, json={"message_text": "Có mùi khét trong bếp", "assessment": {"proposed_action": "start_ticket"}}).json()
        assert kept["emergency"]
        question = c.post(policy, json={
            "message_text": "Phí quản lý tháng này bao nhiêu?", "assessment": {"intent": "information"}}).json()
        assert not question["staff_required"] and question["self_help_allowed"] is False
        body = {"text": "Chào bạn.", "reply_to_id": message_id}
        first = c.post(f"/internal/reception/chats/{channel}/replies", json=body)
        assert first.status_code == 201, first.text
        assert c.post(f"/internal/reception/chats/{channel}/replies", json=body).json() == first.json()
        assert c.post(f"/internal/reception/chats/{channel}/replies",
                      json={**body, "reply_to_id": str(uuid4())}).status_code == 422


def test_reception_delegation_is_bound_to_one_running_turn(database, monkeypatch):
    from vinhomes_api.reception_delegation import finish_run
    from vinhomes_api.v3_reception_runtime import _resident_transaction

    monkeypatch.setenv("RECEPTION_DELEGATION_KEY", "cd" * 32)
    v1 = "/internal/reception/v1/execute"
    with client(database) as c:
        channel, message_id = resident_message(c, "Delegation")
        other, other_message = resident_message(c, "Another conversation")
        delegation = delegate(c, channel, message_id)
        bearer = {"Authorization": "Bearer " + delegation["token"]}
        call = {"operation": "get_verified_resident_context", "input": {}, "context": {}, "idempotency_key": str(uuid4())}

        done = c.post(v1, headers=bearer, json=call)
        assert done.status_code == 200, done.text
        # The resident comes from the run; the response carries the canonical context.
        assert done.json()["result"]["resident"]["id"] == "local-v3-resident"
        assert done.json()["context"] == delegation["context"]
        run = sql(database, "select status,actor_user_id,channel_id from agent_runs where id=$1", UUID(delegation["context"]["runId"]))[0]
        assert run == {"status": "running", "actor_user_id": "local-v3-resident", "channel_id": channel}

        # Neither the caller's context nor its input can widen the binding.
        assert c.post(v1, headers=bearer, json={**call, "context": {"runId": str(uuid4())}}).status_code == 403
        assert c.post(v1, headers=bearer, json={**call, "operation": "create_ticket_draft", "input": {"channel_id": other},
                                                 "idempotency_key": str(uuid4())}).status_code == 403
        assert c.post(f"/internal/reception/chats/{other}/replies", headers=bearer,
                      json={"text": "x", "reply_to_id": other_message}).status_code == 403
        forged = delegation["token"][:-1] + ("0" if delegation["token"][-1] != "0" else "1")
        assert c.post(v1, headers={"Authorization": "Bearer " + forged}, json=call).status_code == 401
        # A second message of the same conversation reuses the binding under a new run.
        second = c.post(f"/resident/chats/{channel}/messages", json={"text": "Còn nữa", "client_message_id": str(uuid4())}).json()
        again = delegate(c, channel, second["id"])
        assert again["context"]["bindingId"] == delegation["context"]["bindingId"]
        assert again["context"]["runId"] != delegation["context"]["runId"]

        async def finish():
            async with _resident_transaction(c.app, "local-v3-resident") as db:
                await finish_run(db, delegation["context"]["runId"], True)

        c.portal.call(finish)
        # The token dies with its run, well before it expires.
        assert c.post(v1, headers=bearer, json={**call, "idempotency_key": str(uuid4())}).status_code == 403
        assert c.get("/internal/reception/catalog", headers=bearer).status_code == 403
        assert c.get("/internal/reception/catalog", headers={"Authorization": "Bearer " + again["token"]}).status_code == 200


def test_operation_identity_rollback_and_missing_receipt(database):
    with client(database) as c:
        body = {
            "operation": "get_verified_resident_context",
            "input": {},
            "context": {"principalId": "local-v3-admin"},
            "idempotency_key": str(uuid4()),
        }
        assert c.post(EXECUTE, json=body).status_code == 403
        body["context"] = {"tenantId": str(uuid4())}
        assert c.post(EXECUTE, json=body).status_code == 403
        body["context"] = {}
        assert c.post(RECONCILE, json=body).json()["found"] is False
        _, unsupported = operation(c, "process_self_help", expected=501)
        assert c.post(RECONCILE, json=unsupported).json()["found"] is False


@pytest.mark.parametrize(
    "path",
    [
        "/catalogs",
        "/dashboard",
        "/operations-profile",
        "/tickets",
        "/work-orders",
        "/dispatch-queue",
        "/tasks",
        "/approvals",
        "/triage-reviews",
        "/plans",
        "/rooms",
        "/assets",
        "/technical/active-outages",
        "/security/alerts",
        "/reports/filter-options",
        "/reports/employee-performance",
        "/reports/employee-feedback",
        "/reports/repair-revenue",
        "/reports/incident-frequency-summary",
        "/memory/namespaces",
        "/admin/accounts",
        "/admin/agent-reviews",
        "/admin/memory-candidates",
        "/my/notifications",
    ],
)
def test_seeded_database_read_apis(database, path):
    actor = "management" if path.startswith("/reports/") else "admin"
    with client(database, actor) as c:
        params = {
            "buildingId": "77777777-7777-5777-a777-777777777777",
            "categoryId": CATEGORY,
            "fromDate": "2020-01-01",
            "toDate": "2029-01-01",
        }
        if path == "/reports/employee-feedback":
            params["staffId"] = str(
                sql(
                    database,
                    "select id from staff_profiles where user_id='local-v3-technical'",
                )[0]["id"]
            )
        if path == "/memory/namespaces":
            params["ticketId"] = str(
                sql(database, "select id from tickets limit 1")[0]["id"]
            )
        response = c.get(path, params=params)
        assert response.status_code == 200, response.text


def test_billing_invoice_payment_retry_and_database_totals(database):
    ticket = sql(
        database, "select id from tickets where category_id=$1 limit 1", UUID(CATEGORY)
    )[0]["id"]
    issuer = sql(
        database, "select id from staff_profiles where user_id='local-v3-technical'"
    )[0]["id"]
    with demo_client(database, "management") as c:
        body = {
            "issued_by_staff_id": str(issuer),
            "bill_to_user_id": "local-v3-resident",
            "idempotency_key": str(uuid4()),
            "lines": [
                {
                    "category_id": CATEGORY,
                    "description": "Demo labor",
                    "quantity": 1,
                    "unit_price": 150000,
                }
            ],
        }
        response = c.post(f"/tickets/{ticket}/invoices", json=body)
        assert response.status_code == 201, response.text
        iid = response.json()["invoice"]["id"]
        assert (
            c.post(f"/tickets/{ticket}/invoices", json=body).json()["invoice"]["id"]
            == iid
        )
        payment = {"amount": 50000, "idempotency_key": str(uuid4())}
        assert c.post(f"/invoices/{iid}/demo-payments", json=payment).status_code == 409
        assert c.post(f"/invoices/{iid}/issue").status_code == 200
        paid = c.post(f"/invoices/{iid}/demo-payments", json=payment)
        assert paid.status_code == 201, paid.text
        assert (
            c.post(f"/invoices/{iid}/demo-payments", json=payment).json()["paymentId"]
            == paid.json()["paymentId"]
        )
        detail = c.get(f"/invoices/{iid}").json()
        assert float(detail["collectedAmount"]) == 50000
        assert float(detail["outstandingAmount"]) == 100000
        assert (
            c.post(
                f"/invoices/{iid}/demo-payments",
                json={"amount": 100001, "idempotency_key": str(uuid4())},
            ).status_code
            == 409
        )
    assert (
        sql(
            database,
            "select count(*) as n from payments where invoice_id=$1",
            UUID(iid),
        )[0]["n"]
        == 1
    )


def test_security_emergency_notification_ack_and_retry(database):
    ticket = sql(
        database, "select id,version from tickets where code='DEMO-SEC-EMERGENCY'"
    )[0]
    with client(database, "management") as c:
        body = {
            "message": "Synthetic emergency",
            "ticket_version": ticket["version"],
            "idempotency_key": str(uuid4()),
        }
        response = c.post(f"/tickets/{ticket['id']}/emergency-alerts", json=body)
        assert response.status_code == 201, response.text
        alert = response.json()
        assert (
            c.post(f"/tickets/{ticket['id']}/emergency-alerts", json=body).json()["id"]
            == alert["id"]
        )
        action = {"version": alert["version"], "note": "Acknowledged test"}
        assert (
            c.post(f"/security/alerts/{alert['id']}/ack", json=action).status_code
            == 403
        )
        assert (
            c.post(f"/security/alerts/{alert['id']}/escalate", json=action).status_code
            == 409
        )
    with client(database, "security") as c:
        ack = c.post(f"/security/alerts/{alert['id']}/ack", json=action)
        assert ack.status_code == 200, ack.text
        assert ack.json()["status"] == "acknowledged"
        assert (
            c.post(f"/security/alerts/{alert['id']}/ack", json=action).status_code
            == 200
        )
    assert (
        sql(
            database,
            "select status from security_alerts where id=$1",
            UUID(alert["id"]),
        )[0]["status"]
        == "acknowledged"
    )


def test_sensor_history_and_scoped_report_export(database):
    building = "77777777-7777-5777-a777-777777777777"
    with client(database, "management") as c:
        assets = c.get("/assets", params={"buildingId": building}).json()["items"]
        aid = assets[0]["id"]
        reading = c.post(
            f"/assets/{aid}/sensor-readings",
            json={
                "parameter": "pressure",
                "value": 2.5,
                "unit": "bar",
                "measured_at": datetime.now(UTC).isoformat(),
                "source": "synthetic-test",
            },
        )
        assert reading.status_code == 201, reading.text
        readings = c.get(f"/assets/{aid}/sensor-readings")
        assert readings.status_code == 200 and readings.json()["items"]
        assert c.get(f"/assets/{aid}/maintenance-history").status_code == 200
        body = {
            "kind": "issued_revenue",
            "building_id": building,
            "category_id": CATEGORY,
            "from_date": "2020-01-01",
            "to_date": "2029-01-01",
            "idempotency_key": str(uuid4()),
        }
        export = c.post("/reports/exports", json=body)
        assert export.status_code == 201, export.text
        result = export.json()
        assert result["status"] == "ready" and result["downloadUrl"]
        assert (
            c.post("/reports/exports", json=body).json()["reportId"]
            == result["reportId"]
        )
        assert (
            c.get(f"/reports/exports/{result['reportId']}").json()["status"] == "ready"
        )
        content = c.get(result["downloadUrl"])
        assert content.status_code == 200 and content.content.startswith(b"PK")
    with client(database, "resident") as c:
        assert c.get(result["downloadUrl"]).status_code in (403, 404)
