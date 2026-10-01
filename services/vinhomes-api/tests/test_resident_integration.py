"""Opt-in HTTP integration against the isolated, migrated PostgreSQL V3 database.

Run VINHOMES_INTEGRATION_URL=http://127.0.0.1:8000 pytest tests/test_resident_integration.py.
Uses the backend's explicitly enabled local actors, not production login acceptance.
"""
import io
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from PIL import Image

URL = os.getenv("VINHOMES_INTEGRATION_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Isolated database integration URL not configured")


def call(method, path, actor="resident", expected=200, **kwargs):
    headers = {"X-Demo-Actor": actor, **kwargs.pop("headers", {})}
    response = httpx.request(method, f"{URL}{path}", headers=headers, timeout=20, **kwargs)
    assert response.status_code == expected, f"{method} {path}: {response.status_code} {response.text}"
    return response.json()


@pytest.fixture(scope="module", autouse=True)
def isolated():
    if not URL:
        return
    assert URL.startswith("http://127.0.0.1:"), "Never run write tests against a remote deployment"
    assert call("GET", "/health")["dataMode"] == "faker-database"
    assert call("GET", "/ready")["status"] == "ready"


def image_bytes():
    data = io.BytesIO()
    Image.new("RGB", (8, 8), "#557799").save(data, format="PNG")
    return data.getvalue()


def create_ticket():
    profile = call("GET", "/resident/me")
    unit = profile["units"][0]
    category = next(c for c in profile["categories"] if c["code"] == "technical")
    chat = call("POST", "/resident/chats", expected=201, json={"title": f"Integration {uuid4()}"})
    message = {"text": "Kiểm tra kết nối hai ứng dụng", "client_message_id": str(uuid4())}
    first = call("POST", f"/resident/chats/{chat['id']}/messages", expected=201, json=message)
    assert call("POST", f"/resident/chats/{chat['id']}/messages", expected=201, json=message)["id"] == first["id"]
    call("POST", f"/resident/chats/{chat['id']}/messages", expected=409, json={**message, "text": "Different"})
    key = str(uuid4())
    upload_path = f"/resident/chats/{chat['id']}/photos?filename=intake.png&mimeType=image/png"
    photo = call("POST", upload_path, expected=201, headers={"Idempotency-Key": key}, content=image_bytes())
    assert call("POST", upload_path, expected=201, headers={"Idempotency-Key": key}, content=image_bytes())["id"] == photo["id"]
    call("POST", upload_path, expected=422, headers={"Idempotency-Key": str(uuid4())}, content=b"not-an-image")
    body = {"domain_id": unit["domain_id"], "building_id": unit["building_id"], "unit_id": unit["id"],
            "category_id": category["id"], "title": "Integration: ổ điện cần kiểm tra", "description": "Ổ điện phòng khách không hoạt động.",
            "contact_name": profile["user"]["name"], "contact_phone": "0900000000", "location": "Phòng khách căn 1201",
            "request_kind": "incident", "file_ids": [photo["id"]]}
    key = str(uuid4())
    path = f"/resident/chats/{chat['id']}/tickets"
    call("POST", path, expected=403, headers={"Idempotency-Key": key}, json={**body,"unit_id":str(uuid4())})
    ticket = call("POST", path, expected=201, headers={"Idempotency-Key": key}, json=body)
    assert call("POST", path, expected=201, headers={"Idempotency-Key": key}, json=body) == ticket
    call("POST", path, expected=409, headers={"Idempotency-Key": key}, json={**body,"description":"Different request"})
    assert call("GET", f"/tickets/{ticket['id']}", actor="management")["ticket"]["id"] == ticket["id"]
    call("GET", f"/resident/tickets/{ticket['id']}", actor="security", expected=404)
    response = httpx.get(f"{URL}/resident/photos/{photo['id']}")
    assert response.status_code == 200 and response.content == image_bytes()
    assert httpx.get(f"{URL}/resident/photos/{photo['id']}",headers={"X-Demo-Actor":"security"}).status_code == 404
    assert call("GET", f"/resident/tickets/{ticket['id']}")["photos"][0]["id"] == photo["id"]
    return ticket["id"], category["id"]


def finish_work(ticket_id, category_id):
    ticket = call("GET", f"/tickets/{ticket_id}", actor="management")["ticket"]
    order = call("POST", f"/tickets/{ticket_id}/work-orders", actor="management", expected=201,
                 json={"category_id":category_id,"required_specialty_id":category_id,"description":"Kiểm tra và xử lý ổ điện","ticket_version":ticket["version"]})
    catalog = call("GET", "/catalogs", actor="management")
    staff = next(s for s in catalog["staff"] if s["user_id"] == "local-v3-technical")
    assignment = call("POST", f"/work-orders/{order['id']}/assignments", actor="management", expected=201,
        json={"staff_id":staff["id"],"work_order_version":order["version"],"offer_expires_at":(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()})
    call("POST", f"/assignments/{assignment['id']}/response", actor="security", expected=403,
         json={"status":"accepted","eta_at":datetime.now(timezone.utc).isoformat()})
    call("POST", f"/assignments/{assignment['id']}/response", actor="technical",
         json={"status":"accepted","eta_at":datetime.now(timezone.utc).isoformat()})
    for status in ["en_route","arrived"]:
        order = call("GET", f"/work-orders/{order['id']}", actor="technical")["workOrder"]
        call("PATCH", f"/work-orders/{order['id']}/status", actor="technical", json={"version":order["version"],"status":status,"note":status})
    order = call("GET", f"/work-orders/{order['id']}", actor="technical")["workOrder"]
    proposal = call("POST", f"/work-orders/{order['id']}/repair-proposal", actor="technical", expected=201,
                    json={"version":order["version"],"note":"Ki?m tra v? thay ? ?i?n b? h?ng."})
    ticket = call("GET", f"/resident/tickets/{ticket_id}")["ticket"]
    call("POST", f"/resident/approvals/{proposal['id']}/decision", headers={"Idempotency-Key":str(uuid4())},
         json={"version":ticket["version"],"approved":True,"note":"T?i ??ng ? ph??ng ?n s?a ch?a."})
    order = call("GET", f"/work-orders/{order['id']}", actor="technical")["workOrder"]
    call("PATCH", f"/work-orders/{order['id']}/status", actor="technical", json={"version":order["version"],"status":"in_progress","note":"B?t ??u x? l?"})
    order = call("GET", f"/work-orders/{order['id']}", actor="technical")["workOrder"]
    call("PATCH", f"/work-orders/{order['id']}/status", actor="technical", expected=409,
         json={"version":order["version"],"status":"completed","note":"Thiếu bằng chứng"})
    file = call("POST", f"/tickets/{ticket_id}/files?filename=after.png&mimeType=image/png&purpose=after", actor="technical", expected=201,
                content=image_bytes(), headers={"Content-Type":"application/octet-stream"})
    call("POST", f"/tickets/{ticket_id}/evidence", actor="technical", expected=201,
         json={"file_id":file["fileId"],"work_order_id":order["id"],"assignment_id":assignment["id"],"purpose":"after"})
    call("PATCH", f"/work-orders/{order['id']}/status", actor="technical", json={"version":order["version"],"status":"completed","note":"Đã xử lý và chụp ảnh"})
    assert call("GET", f"/resident/tickets/{ticket_id}")["ticket"]["status"] == "in_progress"
    call("POST", f"/work-orders/{order['id']}/qc", actor="technical", expected=403, json={"outcome":"pass","criteria":[]})
    call("POST", f"/work-orders/{order['id']}/qc", actor="management", expected=201,
         json={"outcome":"pass","criteria":[{"name":"Ổ điện hoạt động", "passed":True}]})
    assert call("GET", f"/resident/tickets/{ticket_id}")["ticket"]["status"] == "resolved"
    approval = next(a for a in call("GET", "/resident/approvals?limit=100")["items"] if a["ticket_id"] == ticket_id and a["status"] == "pending")
    return order["id"], approval["id"]


def test_full_confirmation_retry_and_concurrent_decisions():
    ticket, category = create_ticket()
    _, approval = finish_work(ticket, category)
    current = call("GET", f"/resident/tickets/{ticket}")["ticket"]
    body = {"approved":True,"note":"Tôi đã kiểm tra, mọi thứ hoạt động tốt.","version":current["version"]}
    call("POST", f"/resident/approvals/{approval}/decision", expected=409,
         headers={"Idempotency-Key":str(uuid4())},json={**body,"version":body["version"]-1})
    keys = [str(uuid4()), str(uuid4())]
    def decide(key):
        return httpx.post(f"{URL}/resident/approvals/{approval}/decision",headers={"Idempotency-Key":key},json=body,timeout=20)
    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(decide, keys))
    assert sorted(r.status_code for r in responses)==[200,409]
    winner=next(i for i,r in enumerate(responses) if r.status_code==200)
    assert decide(keys[winner]).json()==responses[winner].json()
    assert call("GET", f"/resident/tickets/{ticket}")["ticket"]["status"] == "closed"


def test_rework_preserves_history_and_returns_to_management():
    ticket, category = create_ticket()
    order, approval = finish_work(ticket, category)
    current = call("GET", f"/resident/tickets/{ticket}")["ticket"]
    call("POST", f"/resident/approvals/{approval}/decision", headers={"Idempotency-Key":str(uuid4())},
         json={"approved":False,"note":"Ổ điện vẫn chưa hoạt động ổn định.","version":current["version"]})
    assert call("GET", f"/tickets/{ticket}",actor="management")["ticket"]["status"] == "triaging"
    history = call("GET", f"/work-orders/{order}",actor="management")
    assert history["workOrder"]["status"] == "completed" and history["qcResults"][0]["outcome"] == "pass"
    assert call("GET", f"/tickets/{ticket}/evidence",actor="management")["items"]
