"""Customer identity/case isolation on disposable restricted PostgreSQL."""

import base64
import hashlib
import hmac
import json
import re
import time
from uuid import UUID, uuid4

from test_account_administration import door
from test_resident_contract import TENANT, CATEGORY, sql
from test_resident_contract import database as database  # noqa: F401
from vinhomes_api.platform_customers import pkce

CLIENT = "offline-platform"
SECRET = "offline-client-secret-for-fixtures-only"
REDIRECT = "https://platform.invalid/connections/callback/vinhomes"


def register(database):
    sql(database, """INSERT INTO platform_customer_clients(tenant_id,client_id,secret_hash,redirect_uri,issuer,active)
        VALUES($1,$2,$3,$4,'https://domain.invalid',true) ON CONFLICT(tenant_id,client_id) DO UPDATE SET active=true""",
        TENANT, CLIENT, hashlib.sha256(SECRET.encode()).hexdigest(), REDIRECT)


def link(c, database, monkeypatch, platform_user=None):
    platform_user = platform_user or "offline-customer"
    register(database)
    async def resident(request):
        return {"id": "local-v3-resident", "name": "Test Resident"}
    monkeypatch.setattr("vinhomes_api.password_auth.authenticated_user", resident)
    verifier = base64.urlsafe_b64encode(b"offline-verifier-material-only-1234567890").decode().rstrip("=")
    params = {"client_id": CLIENT, "redirect_uri": REDIRECT, "state": uuid4().hex,
        "code_challenge": pkce(verifier), "platform_user_id": platform_user}
    page = c.get("/platform/link/authorize", params=params)
    assert page.status_code == 200, page.text
    transaction = re.search(r'name="transaction" value="([^"]+)"', page.text)[1]
    csrf = re.search(r'name="csrf" value="([^"]+)"', page.text)[1]
    result = c.post("/platform/link/authorize", data={"transaction": transaction, "csrf": csrf, "decision": "allow"}, follow_redirects=False)
    assert result.status_code == 303, result.text
    from urllib.parse import parse_qs, urlsplit
    code = parse_qs(urlsplit(result.headers["location"]).query)["code"][0]
    body = {"grant_type": "authorization_code", "client_id": CLIENT, "client_secret": SECRET,
        "code": code, "code_verifier": verifier, "redirect_uri": REDIRECT, "platform_user_id": platform_user}
    response = c.post("/platform/link/token", json=body)
    assert response.status_code == 200, response.text
    assert c.post("/platform/link/token", json=body).status_code == 401
    return response.json(), body


def test_link_pkce_case_ticket_origin_and_revoke(database, monkeypatch):
    monkeypatch.setenv("VINHOMES_CUSTOMER_PLATFORM_ENABLED", "true")
    monkeypatch.setenv("VINHOMES_API_PLATFORM_MCP_TOKEN", "offline-control-plane-token-0123456789")
    with door(database) as c:
        linked, _ = link(c, database, monkeypatch)
        credential = {"client_id": CLIENT, "client_secret": SECRET, "link_token": linked["link_token"]}
        issued = c.post("/platform/customer/grants", json=credential)
        assert issued.status_code == 200, issued.text
        headers = {"Authorization": "Bearer " + issued.json()["access_token"], "Idempotency-Key": uuid4().hex}
        profile = c.get("/platform/customer/me", headers=headers)
        assert profile.status_code == 200, profile.text
        request = {"apartmentId": profile.json()["apartments"][0]["id"], "description": "Vòi nước dưới bồn rửa đang rò liên tục.",
            "location": {"description": "Bếp, dưới bồn rửa"}, "photoIds": []}
        body = {"platform_case_id": uuid4().hex, "platform_workflow_id": uuid4().hex, "request": request}
        created = c.post("/platform/customer/requests", json=body, headers=headers)
        assert created.status_code == 201, created.text
        assert c.post("/platform/customer/requests", json=body, headers=headers).json() == created.json()
        ident = created.json()["id"]
        material = {"category_id": CATEGORY, "expected_version": created.json()["version"]}
        material_headers = {**headers, "Idempotency-Key": uuid4().hex}
        ticket = c.post(f"/platform/customer/requests/{ident}/tickets", json=material, headers=material_headers)
        assert ticket.status_code == 201, ticket.text
        assert c.post(f"/platform/customer/requests/{ident}/tickets", json=material, headers=material_headers).json() == ticket.json()
        ticket_id = UUID(ticket.json()["ticket_id"])
        binding = sql(database, "SELECT origin,workflow_id FROM platform_links WHERE ticket_id=$1", ticket_id)[0]
        assert binding == {"origin": "platform", "workflow_id": body["platform_workflow_id"]}
        assert sql(database, "SELECT count(*) AS n FROM platform_commands WHERE ticket_id=$1", ticket_id)[0]["n"] == 0
        assert len(sql(database, "SELECT * FROM vh_resident_case_tickets WHERE case_id=$1", UUID(ident))) == 1
        grant_body = {"ticket_id": str(ticket_id), "tools": ["vh_ticket_get", "vh_work_order_dispatch"]}
        grant = c.post(f"/platform/customer/requests/{ident}/ticket-grants", json=grant_body, headers=headers)
        assert grant.status_code == 200, grant.text
        bad = c.post(f"/platform/customer/requests/{ident}/ticket-grants", json={**grant_body, "tools": ["vh_ticket_cancel"]}, headers=headers)
        assert bad.status_code == 403
        assert c.get(f"/platform/customer/requests/{uuid4()}", headers=headers).status_code == 404
        from test_platform_mcp_v2 import rpc, call
        c.headers["host"] = "127.0.0.1:8000"
        assert call(c, grant.json()["bearer_token"], "vh_ticket_get", {"ticket_id": str(ticket_id)})["ticket_id"] == str(ticket_id)
        snapshot = c.get(f"/platform/customer/requests/{ident}", headers=headers).json()
        ack_body = {"canonical_version": snapshot["canonical_version"], "content_hash": snapshot["projection_hash"]}
        assert c.post(f"/platform/customer/requests/{ident}/projection-acks", headers=headers, json={**ack_body, "content_hash": "0" * 64}).status_code == 409
        assert c.post(f"/platform/customer/requests/{ident}/projection-acks", headers=headers, json=ack_body).json()["ingestion_status"] == "applied"
        source = uuid4().hex
        intent = {"action": "cancel", "expected_version": snapshot["version"], "payload": {"reason": "Resident no longer needs this request"},
            "platform_case_id": body["platform_case_id"], "source_event_id": source}
        proof = {**intent, "client_id": CLIENT, "platform_user_id": linked["platform_user_id"],
            "domain_link_id": linked["link_id"], "request_id": ident, "expires_at": int(time.time()) + 300}
        signature = hmac.new(hashlib.sha256(SECRET.encode()).digest(), json.dumps(proof, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(), hashlib.sha256).hexdigest()
        intent = {**intent, "intent_proof": proof, "intent_signature": signature}
        decided_headers = {**headers, "Idempotency-Key": uuid4().hex}
        assert c.post(f"/platform/customer/requests/{ident}/decisions", headers=decided_headers, json={**intent, "intent_signature": "0" * 64}).status_code == 403
        decided = c.post(f"/platform/customer/requests/{ident}/decisions", headers=decided_headers, json=intent)
        assert decided.status_code == 200, decided.text
        assert decided.json()["status"] == "confirmed", decided.text
        assert c.post(f"/platform/customer/requests/{ident}/decisions", headers=decided_headers, json=intent).json() == decided.json()
        assert sql(database, "SELECT count(*) AS n FROM platform_commands WHERE ticket_id=$1", ticket_id)[0]["n"] == 0
        page = c.get(f"/platform/customer/requests/{ident}/events", headers=headers, params={"limit": 1}).json()
        assert page["items"][0]["sequence"] == 1 and page["has_more"] is True
        next_page = c.get(f"/platform/customer/requests/{ident}/events", headers=headers, params={"after": page["next_cursor"]}).json()
        assert next_page["items"][0]["sequence"] == 2
        assert c.post("/platform/customer/revoke", json=credential).status_code == 200
        assert c.get(f"/platform/customer/requests/{ident}", headers=headers).status_code == 401
        assert rpc(c, grant.json()["bearer_token"], "tools/list").status_code == 401


def test_feature_disabled_and_redirect_csrf_fail_closed(database, monkeypatch):
    with door(database) as c:
        assert c.post("/platform/customer/grants", json={"client_id": CLIENT, "client_secret": SECRET, "link_token": "x" * 40}).status_code == 503
    monkeypatch.setenv("VINHOMES_CUSTOMER_PLATFORM_ENABLED", "true")
    register(database)
    with door(database) as c:
        params = {"client_id": CLIENT, "redirect_uri": "https://evil.invalid", "state": "x" * 32,
            "code_challenge": "x" * 43, "platform_user_id": "alice"}
        assert c.get("/platform/link/authorize", params=params).status_code == 400
        assert c.post("/platform/link/authorize", data={"transaction": str(uuid4()), "csrf": "forged", "decision": "allow"}).status_code == 403


def test_customer_dispatch_is_received_by_domain_staff_and_progress_returns(database, monkeypatch):
    from test_resident_contract import client
    from test_platform_mcp_v2 import call
    from datetime import datetime, timezone
    monkeypatch.setenv("VINHOMES_CUSTOMER_PLATFORM_ENABLED", "true")
    monkeypatch.setenv("VINHOMES_API_PLATFORM_MCP_TOKEN", "offline-control-plane-token-0123456789")
    staff = sql(database, "UPDATE staff_profiles SET availability='available',max_concurrent_jobs=99 WHERE user_id='local-v3-technical' RETURNING id")[0]["id"]
    sql(database, "INSERT INTO staff_shifts(tenant_id,staff_id,starts_at,ends_at,status) VALUES($1,$2,now()-interval '1 hour',now()+interval '1 hour','available')", TENANT, staff)
    with door(database) as c:
        linked, _ = link(c, database, monkeypatch)
        credential = {"client_id": CLIENT, "client_secret": SECRET, "link_token": linked["link_token"]}
        subject = c.post("/platform/customer/grants", json=credential).json()["access_token"]
        headers = {"Authorization": "Bearer " + subject, "Idempotency-Key": uuid4().hex}
        apartment = c.get("/platform/customer/me", headers=headers).json()["apartments"][0]["id"]
        created = c.post("/platform/customer/requests", headers=headers, json={"platform_case_id": uuid4().hex,
            "platform_workflow_id": uuid4().hex, "request": {"apartmentId": apartment, "description": "Vòi nước rò rỉ cần nhân viên kỹ thuật kiểm tra.",
                "location": {"description": "Dưới bồn rửa bếp"}, "photoIds": []}}).json()
        ident = created["id"]
        material = c.post(f"/platform/customer/requests/{ident}/tickets", headers={**headers, "Idempotency-Key": uuid4().hex},
            json={"category_id": CATEGORY, "expected_version": created["version"]})
        assert material.status_code == 201, material.text
        ticket = material.json()["ticket_id"]
        grant = c.post(f"/platform/customer/requests/{ident}/ticket-grants", headers=headers,
            json={"ticket_id": ticket, "tools": ["vh_ticket_get", "vh_work_order_dispatch"]}).json()["bearer_token"]
        c.headers["host"] = "127.0.0.1:8000"
        version = sql(database, "SELECT version FROM tickets WHERE id=$1", UUID(ticket))[0]["version"]
        dispatched = call(c, grant, "vh_work_order_dispatch", {"ticket_id": ticket, "client_reference": uuid4().hex,
            "description": "Kiểm tra vòi nước dưới bồn rửa bếp", "staff_id": str(staff), "expected_ticket_version": version})
        assert dispatched["status"] == "pending", dispatched
        with client(database, "technical") as worker:
            job = next(j for j in worker.get("/my-work-orders").json()["items"] if str(j["ticket_id"]) == ticket)
            accepted = worker.post(f"/assignments/{job['assignment_id']}/response", json={"status": "accepted", "eta_at": datetime.now(timezone.utc).isoformat()})
            assert accepted.status_code == 200, accepted.text
        feed = c.get(f"/platform/customer/requests/{ident}/events", headers=headers).json()
        assert any(e["event_type"] == "resident.case.progress" for e in feed["items"])
        assert [e["sequence"] for e in feed["items"]] == list(range(1, len(feed["items"]) + 1))
        from test_platform_tools import photo
        with client(database, "technical") as worker:
            photo(worker, ticket, str(job["id"]), str(job["assignment_id"]), "after")
        evidence = sql(database, "SELECT file_id FROM evidence_items WHERE work_order_id=$1 AND purpose='after'", UUID(str(job["id"])))[0]["file_id"]
        # Isolate the media-publication contract; business QC is covered by the staff suite.
        sql(database, "UPDATE work_orders SET status='completed' WHERE id=$1", UUID(str(job["id"])))
        snapshot = c.get(f"/platform/customer/requests/{ident}", headers=headers).json()
        assert str(evidence) in [p["id"] for p in snapshot["result_photos"]]
        media = f"/platform/customer/requests/{ident}/photos/{evidence}"
        assert c.get(media, headers=headers).status_code == 409
        ack = c.post(f"/platform/customer/requests/{ident}/projection-acks", headers=headers,
            json={"canonical_version": snapshot["canonical_version"], "content_hash": snapshot["projection_hash"]})
        assert ack.status_code == 200, ack.text
        image = c.get(media, headers=headers)
        assert image.status_code == 200 and image.headers["content-type"] == "image/png", image.text
        assert sql(database, "SELECT count(*) AS n FROM platform_commands WHERE ticket_id=$1", UUID(ticket))[0]["n"] == 0
