"""Opt-in end to end: resident chat -> backend -> Reception runtime -> backend, over real HTTP.

Needs the backend (local actors), the Reception runtime and tests/runtime/fake_llm.py running:
RECEPTION_E2E_BACKEND_URL=http://127.0.0.1:8011 RECEPTION_E2E_TOKEN=... pytest tests/runtime/test_resident_chat_e2e.py
The same tests hold for both agents: run them once against a runtime started with
RECEPTION_AGENT=graph and once against one started with RECEPTION_AGENT=loop.
"""

import os
import time
from uuid import uuid4

import httpx
import pytest

URL = os.getenv("RECEPTION_E2E_BACKEND_URL")
TOKEN = os.getenv("RECEPTION_E2E_TOKEN", "")
pytestmark = pytest.mark.skipif(not URL, reason="Reception end-to-end services are not configured")


def call(method, path, actor="resident", expected=200, **kwargs):
    response = httpx.request(method, URL + path, headers={"X-Demo-Actor": actor}, timeout=30, **kwargs)
    assert response.status_code == expected, f"{method} {path}: {response.status_code} {response.text}"
    return response.json()


def say(chat, text, client_message_id=None):
    """Send one resident message and wait for Reception's stored reply to it."""
    body = {"text": text, "client_message_id": client_message_id or str(uuid4())}
    sent = call("POST", f"/resident/chats/{chat}/messages", expected=201, json=body)
    deadline = time.time() + 25
    while time.time() < deadline:
        items = call("GET", f"/resident/chats/{chat}/messages?limit=100")["items"]
        replies = [m for m in items if m["sender_kind"] == "agent" and m["seq"] > sent["seq"]]
        if replies:
            return replies[0]["body"]["text"], body
        time.sleep(0.5)
    raise AssertionError("Reception did not reply within 60 seconds")


def test_incident_chat_creates_a_ticket_management_can_work_on():
    chat = call("POST", "/resident/chats", expected=201, json={"title": f"E2E {uuid4()}"})["id"]
    reply, sent = say(chat, "Ổ điện phòng khách bị hỏng, không có điện từ sáng nay.")
    # The request code is for staff; the resident follows the request in the app.
    assert "VH-" not in reply
    # A retried send must not make Reception answer, or open a ticket, twice.
    call("POST", f"/resident/chats/{chat}/messages", expected=201, json=sent)
    time.sleep(3)
    messages = call("GET", f"/resident/chats/{chat}/messages?limit=100")["items"]
    assert len([m for m in messages if m["sender_kind"] == "agent"]) == 1

    ticket_id = next(c for c in call("GET", "/resident/chats")["items"] if c["id"] == chat)["ticket_id"]
    detail = call("GET", f"/tickets/{ticket_id}", actor="management")
    ticket = detail["ticket"]
    assert ticket["status"] == "open" and ticket["title"].startswith("Ổ điện phòng khách")
    created = next(e for e in detail["events"] if e["event_type"] == "ticket.created")
    assert "requiresPlan" not in created["payload"] and created["payload"]["assessment"]["priority"] == "normal"
    # The seeded management unit has a Supervisor, so the handoff opened the coordination session.
    # It waits ("queued") until a Supervisor runtime accepts it ("running").
    assert call("GET", f"/tickets/{ticket_id}/session", actor="management")["session"]["status"] in ("queued", "running")
    # Direct flow: management can dispatch without a plan approval step.
    call("POST", f"/tickets/{ticket_id}/work-orders", actor="management", expected=201,
         json={"category_id": ticket["category_id"], "required_specialty_id": ticket["category_id"],
               "description": "Kiểm tra ổ điện", "ticket_version": ticket["version"]})

    reply, _ = say(chat, "Cho tôi hỏi tiến độ xử lý đến đâu rồi?")
    # The graph answers in general terms; the model-led agent reports the status the backend holds.
    assert "đang được xử lý" in reply or "đã giao cho nhân viên" in reply


def test_a_model_guess_among_the_facts_does_not_lose_the_request():
    chat = call("POST", "/resident/chats", expected=201, json={"title": f"E2E {uuid4()}"})["id"]
    say(chat, "Ổ điện bếp bị hỏng, có vẻ do chập.")
    assert next(c for c in call("GET", "/resident/chats")["items"] if c["id"] == chat)["ticket_id"]


def test_an_emergency_is_filed_at_emergency_level_with_the_fixed_reply():
    chat = call("POST", "/resident/chats", expected=201, json={"title": f"E2E {uuid4()}"})["id"]
    reply, _ = say(chat, "Ổ điện phòng khách có khói bốc ra và mùi khét.")
    assert reply.startswith("Mình đã chuyển yêu cầu của bạn đến Ban quản lý ở mức khẩn cấp.")
    ticket_id = next(c for c in call("GET", "/resident/chats")["items"] if c["id"] == chat)["ticket_id"]
    assert call("GET", f"/tickets/{ticket_id}", actor="management")["ticket"]["priority"] == "critical"


def test_an_emergency_reply_carries_the_safety_guidance_management_approved():
    """The backend's database needs the guidance proposed from tests/runtime/fixtures/guidance
    (services/vinhomes-api/scripts/propose_emergency_guidance.py); without it the test is skipped."""
    guidance = "Anh chị không bật công tắc điện, mở cửa nếu an toàn, rồi gọi an ninh và đơn vị gas."
    pending = [item for item in call("GET", "/knowledge/candidates", actor="management")["items"] if item["answer"] == guidance]
    for item in pending:
        call("POST", f"/knowledge/candidates/{item['id']}/decision", actor="management", json={"decision": "approve"})
    chat = call("POST", "/resident/chats", expected=201, json={"title": f"E2E {uuid4()}"})["id"]
    reply, _ = say(chat, "Bếp nhà tôi có mùi gas rất nặng.")
    if not pending and guidance not in reply:
        pytest.skip("No gas guidance was proposed in this database")
    assert reply.splitlines() == ["Mình đã chuyển yêu cầu của bạn đến Ban quản lý ở mức khẩn cấp.", guidance]


def test_a_question_without_a_source_goes_to_management_and_the_answer_comes_back():
    chat = call("POST", "/resident/chats", expected=201, json={"title": f"E2E {uuid4()}"})["id"]
    before = len(call("GET", "/resident/tickets")["items"])
    question = f"Bể bơi mở cửa lúc mấy giờ? ({uuid4().hex[:6]})"
    reply, _ = say(chat, question)
    # Reception does not guess and does not open a request: the question becomes a management session.
    assert "chuyển câu hỏi của bạn tới Ban quản lý" in reply
    assert len(call("GET", "/resident/tickets")["items"]) == before
    inquiry = next(i for i in call("GET", "/sessions/inquiries", actor="management")["items"] if i["question"] == question)
    call("POST", f"/sessions/{inquiry['id']}/answer", actor="management",
         json={"version": inquiry["state_version"], "text": "Bể bơi mở từ 6 giờ đến 21 giờ."})
    last = call("GET", f"/resident/chats/{chat}/messages?limit=100")["items"][-1]
    assert last["sender_kind"] == "agent" and "6 giờ đến 21 giờ" in last["body"]["text"]


def test_information_question_is_answered_from_cited_passages():
    chat = call("POST", "/resident/chats", expected=201, json={"title": f"E2E {uuid4()}"})["id"]
    reply, _ = say(chat, "Phí quản lý hiện nay là bao nhiêu?")
    assert "12.000 đồng" in reply


def test_reception_routes_need_a_run_delegation():
    path = URL + "/internal/reception/catalog"
    # Neither a resident session nor the backend-to-runtime service token is a delegation.
    assert httpx.get(path, headers={"X-Demo-Actor": "resident"}).status_code == 401
    assert httpx.get(path, headers={"Authorization": "Bearer " + TOKEN, "X-Acting-User": "local-v3-resident"}).status_code == 401
    call = {"operation": "get_verified_resident_context", "input": {}, "context": {}, "idempotency_key": str(uuid4())}
    assert httpx.post(URL + "/internal/reception/v1/execute", headers={"Authorization": "Bearer " + TOKEN}, json=call).status_code == 401


@pytest.mark.skipif(not os.getenv("RECEPTION_E2E_DOWN_BACKEND_URL"), reason="No backend with an unreachable runtime")
def test_resident_is_told_when_the_runtime_is_down():
    down = os.environ["RECEPTION_E2E_DOWN_BACKEND_URL"]
    headers = {"X-Demo-Actor": "resident"}
    chat = httpx.post(down + "/resident/chats", headers=headers, json={"title": f"E2E {uuid4()}"}).json()["id"]
    sent = httpx.post(down + f"/resident/chats/{chat}/messages", headers=headers,
                      json={"text": "Điều hòa bị hỏng", "client_message_id": str(uuid4())})
    assert sent.status_code == 201
    deadline = time.time() + 25
    while time.time() < deadline:
        items = httpx.get(down + f"/resident/chats/{chat}/messages?limit=100", headers=headers).json()["items"]
        replies = [m["body"]["text"] for m in items if m["sender_kind"] == "agent"]
        if replies:
            assert "biểu mẫu" in replies[0] and len(replies) == 1
            return
        time.sleep(0.5)
    raise AssertionError("No fallback reply was stored")


@pytest.mark.skipif(not os.getenv("RECEPTION_E2E_SUPERVISOR"), reason="No Supervisor runtime (agent-coordination) in this stack")
def test_the_supervisor_receives_the_ticket_reception_handed_over():
    """Also needs `python -m vinhomes` (agent-coordination) pointed at the same backend."""
    chat = call("POST", "/resident/chats", expected=201, json={"title": f"E2E {uuid4()}"})["id"]
    say(chat, "Ổ điện phòng ngủ bị hỏng, không cắm được thiết bị nào.")
    ticket_id = next(c for c in call("GET", "/resident/chats")["items"] if c["id"] == chat)["ticket_id"]
    session, deadline = {}, time.time() + 30
    while time.time() < deadline and not (session.get("runtime") and session.get("status") == "running"):
        time.sleep(0.5)
        session = call("GET", f"/tickets/{ticket_id}/session", actor="management")["session"]
    # The Supervisor accepted the ticket under a run the backend allocated, then handed it to management.
    assert session["status"] == "running" and session["supervisor"]["lastMessageType"] == "accepted"
    assert session["runtime"]["phase"] == "paused"
    assert session["runtime"]["pauseReason"] == "planner:no_specialist_available"
    results = call("GET", f"/api/domains/vinhomes/resident/reception-supervisor/tickets/{ticket_id}/results")["items"]
    assert [r["message_type"] for r in results] == ["accepted"]
    assert results[0]["supervisor_run_id"] == session["supervisor"]["runId"]
    # Acceptance is a note for management; the resident hears from Reception once.
    messages = call("GET", f"/resident/chats/{chat}/messages?limit=100")["items"]
    assert len([m for m in messages if m["sender_kind"] == "agent"]) == 1
