"""C07 plans use resident-safe fields and their own revision, with real PG."""

import hashlib
import hmac
import json
import time
from uuid import UUID, uuid4

import pytest

from test_account_administration import door
from test_platform_customers import CLIENT, SECRET, link
from test_resident_contract import CATEGORY, client, sql
from test_resident_contract import database as database  # noqa: F401


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_customer_plan_projection_ack_and_independent_revision(database, monkeypatch, decision):
    monkeypatch.setenv("VINHOMES_CUSTOMER_PLATFORM_ENABLED", "true")
    with door(database) as customer:
        linked, _ = link(customer, database, monkeypatch)
        grant = customer.post("/platform/customer/grants", json={"client_id": CLIENT,
            "client_secret": SECRET, "link_token": linked["link_token"]})
        assert grant.status_code == 200, grant.text
        headers = {"Authorization": "Bearer " + grant.json()["access_token"], "Idempotency-Key": uuid4().hex}
        home = customer.get("/platform/customer/me", headers=headers).json()["apartments"][0]["id"]
        command = {"platform_case_id": uuid4().hex, "platform_workflow_id": uuid4().hex,
            "request": {"apartmentId": home, "description": "Voi nuoc can sua theo phuong an rieng.",
                "location": {"description": "Bep trong can ho"}, "photoIds": []}}
        created = customer.post("/platform/customer/requests", headers=headers, json=command)
        assert created.status_code == 201, created.text
        ident = created.json()["id"]
        material = customer.post(f"/platform/customer/requests/{ident}/tickets", headers={**headers, "Idempotency-Key": uuid4().hex},
            json={"category_id": CATEGORY, "expected_version": created.json()["version"]})
        assert material.status_code == 201, material.text
        ticket = material.json()["ticket_id"]
        base = f"/platform/customer/requests/{ident}"
        before = customer.get(base, headers=headers).json()
        assert before["plans"] == []

        # The existing Domain workflow proposes and approves a plan; no new
        # Platform management approval bridge is introduced by this contract.
        with client(database, "management") as staff:
            current = staff.get("/tickets/" + ticket).json()["ticket"]
            proposed = staff.post(f"/tickets/{ticket}/plans", json={"title": "Repair plan",
                "ticket_version": current["version"], "idempotency_key": uuid4().hex,
                "estimated_amount": "120000.00", "steps": [{"category_id": CATEGORY, "description": "Replace seal"}]})
            assert proposed.status_code == 201, proposed.text
            plan_id = proposed.json()["id"]
            # Management-only proposals must not be visible to the resident.
            assert customer.get(base, headers=headers).json()["plans"] == []
            approved = staff.post(f"/plans/{plan_id}/management-decision", json={
                "version": proposed.json()["version"], "decision": "approve", "note": "INTERNAL-MANAGEMENT-NOTE"})
            assert approved.status_code == 200, approved.text

        snapshot = customer.get(base, headers=headers).json()
        plan = snapshot["plans"][0]
        assert plan == {"id": plan_id, "title": "Repair plan", "status": "resident_pending",
            "version": approved.json()["version"], "estimatedAmount": "120000.00",
            "steps": ["Replace seal"], "canDecide": True}
        assert snapshot["service_status"] == "waiting_for_customer"
        assert snapshot["projection_hash"] != before["projection_hash"]
        assert "INTERNAL-MANAGEMENT-NOTE" not in json.dumps(snapshot)
        assert customer.get(f"/platform/customer/requests/{uuid4()}", headers=headers).status_code == 404
        ack = {"canonical_version": snapshot["canonical_version"], "content_hash": snapshot["projection_hash"]}
        assert customer.post(base + "/projection-acks", headers=headers, json=ack).status_code == 200

        def intent(plan_version, case_version):
            body = {"action": "plan-decision", "expected_version": case_version,
                "payload": {"plan_id": plan_id, "expectedVersion": plan_version, "decision": decision, "note": "Resident choice"},
                "platform_case_id": command["platform_case_id"], "source_event_id": uuid4().hex}
            proof = {**body, "client_id": CLIENT, "platform_user_id": linked["platform_user_id"],
                "domain_link_id": linked["link_id"], "request_id": ident, "expires_at": int(time.time()) + 300}
            signature = hmac.new(hashlib.sha256(SECRET.encode()).digest(),
                json.dumps(proof, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(), hashlib.sha256).hexdigest()
            return {**body, "intent_proof": proof, "intent_signature": signature}

        for plan_version, case_version in ((plan["version"] - 1, snapshot["canonical_version"]),
                (plan["version"], snapshot["canonical_version"] - 1)):
            stale = customer.post(base + "/decisions", headers={**headers, "Idempotency-Key": uuid4().hex},
                json=intent(plan_version, case_version))
            assert stale.status_code == 409, stale.text
        body = intent(plan["version"], snapshot["canonical_version"])
        decision_headers = {**headers, "Idempotency-Key": uuid4().hex}
        response = customer.post(base + "/decisions", headers=decision_headers, json=body)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == ("approved" if decision == "approve" else "rejected")
        assert customer.post(base + "/decisions", headers=decision_headers, json=body).json() == response.json()
        refreshed = customer.get(base, headers=headers).json()
        assert not refreshed["plans"][0]["canDecide"]
        assert refreshed["projection_hash"] != snapshot["projection_hash"]
        assert sql(database, "SELECT count(*) AS n FROM work_orders WHERE ticket_id=$1", UUID(ticket))[0]["n"] == (1 if decision == "approve" else 0)
