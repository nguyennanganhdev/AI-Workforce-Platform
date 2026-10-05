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
        assessment = {"priority": "high", "severity": "major", "reason": "Resident-reported overflow"}
        operation(c, "submit_ticket_assessment", {**target, "assessment": assessment})
        # A title and a description written for the resident are not a report: nothing is handed over.
        refused, _ = operation(c, "handoff_ticket", target)
        assert refused["accepted"] is False and refused["missingFields"] == ["incident_symptom"]
        assert sql(database, "select count(*) as n from tickets")[0]["n"] == before
        source = message.json()["id"]
        cited, _ = operation(c, "update_ticket_incident", {**target, "fields": {"facts": [
            {"key": "symptom", "value": "is overflowing", "source": "customer_report", "source_message_id": source},
            {"key": "item", "value": "Bathroom", "source": "customer_report", "source_message_id": source},
            # Not in the message: dropped, and it cannot stand for a detail the resident gave.
            {"key": "cause", "value": "a burst pipe in the wall", "source": "customer_report", "source_message_id": source},
        ]}})
        stored = cited["incidents"][0]["fields"]
        assert stored["title"] == stored["description"] == "Bathroom is overflowing"
        assert [fact["key"] for fact in stored["facts"]] == ["symptom", "item"]
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
                "channel_id": channel, "domain_id": place["domain_id"], "building_id": place["building_id"],
                "unit_id": place["unit_id"], "category_id": CATEGORY})
            target = {"channel_id": channel, "draft_id": draft["draftId"]}
            operation(c, "update_ticket_incident", {**target, "fields": {"source_message_id": message["id"], "facts": [
                {"key": "symptom", "value": "is broken", "source": "customer_report", "source_message_id": message["id"]},
                {"key": "item", "value": "Light", "source": "customer_report", "source_message_id": message["id"]}]}})
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


def test_chat_list_shows_what_each_conversation_is_about(database):
    with client(database) as c:
        empty = c.post("/resident/chats", json={"title": "Hội thoại mới"}).json()["id"]
        talked, _ = resident_message(c, "Hội thoại mới", "Vòi nước bếp bị rò từ sáng nay, nước chảy xuống tủ.")
        filed, _ = resident_message(c, "Hội thoại mới", "Ổ điện hỏng")
        me = c.get("/resident/me").json()
        unit = me["units"][0]
        ticket = c.post(f"/resident/chats/{filed}/tickets", headers={"Idempotency-Key": str(uuid4())}, json={
            "domain_id": unit["domain_id"], "building_id": unit["building_id"], "unit_id": unit["id"],
            "category_id": CATEGORY, "title": "Ổ điện phòng khách không có điện", "description": "Ổ điện hỏng từ sáng.",
            "contact_name": "Cư dân", "contact_phone": "0900000000", "location": "Phòng khách", "request_kind": "incident"})
        assert ticket.status_code == 201, ticket.text
        chats = {x["id"]: x for x in c.get("/resident/chats?limit=100").json()["items"]}
        # No ticket yet: the resident's own first words name the conversation.
        assert chats[talked]["title"] == "Vòi nước bếp bị rò từ sáng nay, nước chảy xuống tủ."
        assert chats[talked]["last_message"] == "Vòi nước bếp bị rò từ sáng nay, nước chảy xuống tủ."
        # With a ticket: its title, and the code and status to show under it.
        assert chats[filed]["title"] == "Ổ điện phòng khách không có điện"
        assert chats[filed]["ticket_code"].startswith("VH-") and chats[filed]["ticket_status"] == "open"
        assert chats[empty]["title"] == "Hội thoại mới" and chats[empty]["last_message"] is None


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


def test_knowledge_authorization_follows_the_residents_home(database, monkeypatch):
    monkeypatch.setenv("RECEPTION_DELEGATION_KEY", "ef" * 32)
    path = "/internal/reception/v1/knowledge-authorization"
    scopes = {(row["kind"], row["code"]): str(row["id"]) for row in sql(database, """
        select a.id, a.kind, coalesce(b.code, z.code, s.code) as code from access_scopes a
        left join buildings b on b.id=a.building_id left join zones z on z.id=a.zone_id left join sites s on s.id=a.site_id
        where a.kind in ('site','zone','building')""")}
    with client(database) as c:
        channel, message_id = resident_message(c, "Knowledge")
        bearer = {"Authorization": "Bearer " + delegate(c, channel, message_id)["token"]}
        knowledge_base = sql(database, """
            insert into knowledge_bases(tenant_id,domain_id,code,name,status)
            select tenant_id,domain_id,'authorization-test','Test','active' from sites limit 1 returning id""")[0]["id"]
        ask = {"knowledgeBaseId": str(knowledge_base)}
        # A resident session is not enough, and neither is a delegation without a grant.
        assert c.post(path, json=ask).status_code == 401
        assert c.post(path, headers=bearer, json=ask).status_code == 403
        sql(database, """
            insert into agent_knowledge_grants(tenant_id,agent_id,knowledge_base_id,granted_by)
            select tenant_id,id,$1,'local-v3-management' from agents where purpose='reception'""", knowledge_base)

        granted = c.post(path, headers=bearer, json=ask)
        assert granted.status_code == 200, granted.text
        context = granted.json()["context"]
        # The demo resident lives in S1.01: that building, its area and the urban site, nothing else.
        assert context["targetScopeId"] == scopes[("building", "S1.01")]
        assert set(context["ancestorScopeIds"]) == {scopes[("zone", "sapphire")], scopes[("site", "ocean-park-1")]}
        assert context["userId"] == "local-v3-resident" and context["roleCodes"] == ["resident"]
        # Another operator's area, or another building, cannot be asked for.
        for elsewhere in (("zone", "masteri-waterfront"), ("building", "P1")):
            assert c.post(path, headers=bearer, json={**ask, "scopeId": scopes[elsewhere]}).status_code == 403


def test_a_question_without_a_source_becomes_a_session_that_management_answers(database, monkeypatch):
    monkeypatch.setenv("RECEPTION_DELEGATION_KEY", "0a" * 32)
    question, answer = "Phòng sinh hoạt cộng đồng có cho thuê không?", "Có, bạn đăng ký tại lễ tân sảnh trước 3 ngày."
    with client(database) as c:
        channel, message_id = resident_message(c, "Inquiry", question)
        path = f"/internal/reception/chats/{channel}/inquiries"
        assert c.post(path, json={"message_id": message_id}).status_code == 401
        bearer = {"Authorization": "Bearer " + delegate(c, channel, message_id)["token"]}
        opened = c.post(path, headers=bearer, json={"message_id": message_id})
        assert opened.status_code == 201, opened.text
        assert opened.json()["accepted"] is True
        session = opened.json()["sessionId"]
        # Asking again about the same message does not open a second session.
        assert c.post(path, headers=bearer, json={"message_id": message_id}).json()["sessionId"] == session
    # The session has no ticket and the management group chat shows the question.
    team = sql(database, "select status,ticket_id,request_message_id,channel_id from agent_teams where id=$1", UUID(session))[0]
    assert team["status"] == "queued" and team["ticket_id"] is None and str(team["request_message_id"]) == message_id
    room = sql(database, "select body->>'text' as text from messages where channel_id=$1 order by seq desc limit 1", team["channel_id"])[0]
    assert question in room["text"]

    with demo_client(database, "technical") as staff:
        assert staff.get("/sessions/inquiries").json()["items"] == []
        assert staff.post(f"/sessions/{session}/answer", json={"version": 0, "text": answer}).status_code == 403
    with demo_client(database, "management") as management:
        item = next(i for i in management.get("/sessions/inquiries").json()["items"] if i["id"] == session)
        assert item["question"] == question and item["status"] == "queued" and item["unit_code"] == "1201"
        body = {"version": item["state_version"], "text": answer}
        done = management.post(f"/sessions/{session}/answer", json=body)
        assert done.status_code == 200, done.text
        assert done.json()["status"] == "completed"
        # A retry is the same answer; a different answer to an answered question is refused.
        assert management.post(f"/sessions/{session}/answer", json=body).json() == done.json()
        assert management.post(f"/sessions/{session}/answer", json={**body, "text": "Khác"}).status_code == 409
        assert all(i["id"] != session for i in management.get("/sessions/inquiries").json()["items"])
    with client(database) as c:
        last = c.get(f"/resident/chats/{channel}/messages?limit=100").json()["items"][-1]
        assert last["sender_kind"] == "agent" and answer in last["body"]["text"]
        assert next(x for x in c.get("/resident/chats?limit=100").json()["items"] if x["id"] == channel)["unread_count"] == 1


def test_an_answer_becomes_knowledge_only_after_it_is_judged_or_approved(database, monkeypatch):
    from vinhomes_api.v3_learning import decide

    # The curator's verdict is advice; these rules are the decision.
    general = {"personal_data": False, "generalizable": True, "risk": "none"}
    assert decide(general, "Nhận hàng ở đâu?", "Tại quầy lễ tân sảnh.")[0] == "approved"
    assert decide(general, "Phí gửi xe?", "100.000 đồng mỗi tháng.")[0] == "pending"       # a fee, whatever the model says
    assert decide({**general, "risk": "fee_rule_safety"}, "Quy định?", "Không nuôi chó lớn.")[0] == "pending"
    assert decide({**general, "personal_data": True}, "q", "a")[0] == "rejected"
    assert decide({**general, "generalizable": False}, "q", "a")[0] == "rejected"

    monkeypatch.setenv("RECEPTION_DELEGATION_KEY", "2c" * 32)
    with client(database) as c:
        channel, message_id = resident_message(c, "Learn", "Nhận bưu phẩm ở đâu?")
        bearer = {"Authorization": "Bearer " + delegate(c, channel, message_id)["token"]}
        session = c.post(f"/internal/reception/chats/{channel}/inquiries", headers=bearer, json={"message_id": message_id}).json()["sessionId"]
    with demo_client(database, "management") as management:
        item = next(i for i in management.get("/sessions/inquiries").json()["items"] if i["id"] == session)
        management.post(f"/sessions/{session}/answer", json={"version": item["state_version"], "text": "Tại quầy lễ tân sảnh tòa."})
        # No curator is configured in this test, so the candidate waits for a person.
        candidate = next(i for i in management.get("/knowledge/candidates").json()["items"] if i["question"] == "Nhận bưu phẩm ở đâu?")
        assert candidate["answer"] == "Tại quầy lễ tân sảnh tòa." and candidate["status"] == "pending"
        with demo_client(database, "technical") as staff:
            assert staff.get("/knowledge/candidates").json()["items"] == []
            assert staff.post(f"/knowledge/candidates/{candidate['id']}/decision", json={"decision": "approve"}).status_code == 403
        approved = management.post(f"/knowledge/candidates/{candidate['id']}/decision", json={"decision": "approve"})
        assert approved.status_code == 200 and approved.json()["status"] == "approved"
        assert management.post(f"/knowledge/candidates/{candidate['id']}/decision", json={"decision": "reject"}).status_code == 409
        assert all(i["id"] != candidate["id"] for i in management.get("/knowledge/candidates").json()["items"])
    row = sql(database, "select c.status,c.pii_redacted,s.kind,r.decision from memory_candidates c "
                        "join access_scopes s on s.id=c.scope_id join knowledge_reviews r on r.memory_candidate_id=c.id "
                        "where c.id=$1", UUID(candidate["id"]))[0]
    # Published to the asker's area, with the approval on record.
    assert row == {"status": "approved", "pii_redacted": True, "kind": "zone", "decision": "approve"}


def test_emergency_guidance_reaches_a_resident_only_after_management_approves(database, monkeypatch, tmp_path):
    import asyncio
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "propose_emergency_guidance", Path(__file__).parents[1] / "scripts/propose_emergency_guidance.py")
    propose = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(propose)
    gas = "Anh chị không bật công tắc điện, mở cửa nếu an toàn."
    document = ("# Xử lý việc phát sinh\n\n## 1. Có mùi gas thì làm gì?\n\n" + gas + "\n\n"
                "## 2. Khi cháy có được đi thang máy không?\n\nKhông. Anh chị đi thang bộ.\n\n"
                "## 3. Thang máy kẹt thì sao?\n\n- Bấm chuông trong cabin:\n")
    # The text is the document's own answer; a yes/no opener is dropped and a list is not proposed.
    assert propose.drafts(document) == {"gas": ("Có mùi gas thì làm gì?", gas),
                                        "fire": ("Khi cháy có được đi thang máy không?", "Anh chị đi thang bộ.")}
    # The demo resident lives in Sapphire, so that area's document is the one that applies.
    folder = tmp_path / "01-vinhomes" / "sapphire"
    folder.mkdir(parents=True)
    (folder / propose.FILE).write_text(document, encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", database["admin"])
    asyncio.run(propose.main(tmp_path))
    asyncio.run(propose.main(tmp_path))  # proposing again adds nothing
    assert sql(database, "select count(*) as n from memory_candidates where evidence ? 'emergencyKind'")[0]["n"] == 2

    monkeypatch.setenv("RECEPTION_DELEGATION_KEY", "4e" * 32)
    policy, smell = "/internal/reception/policy/evaluate", {"message_text": "Bếp nhà tôi có mùi gas", "assessment": None}
    with client(database) as c:
        channel, message_id = resident_message(c, "Guidance")
        c.headers["Authorization"] = "Bearer " + delegate(c, channel, message_id)["token"]
        proposed = c.post(policy, json=smell).json()
        assert proposed["emergency"] and "safety_guidance" not in proposed  # proposed is not approved
        with demo_client(database, "technical") as staff:
            assert staff.get("/knowledge/candidates").json()["items"] == []
        with demo_client(database, "management") as management:
            candidate = next(i for i in management.get("/knowledge/candidates").json()["items"] if "mùi gas" in i["question"])
            assert candidate["answer"] == gas
            decided = management.post(f"/knowledge/candidates/{candidate['id']}/decision", json={"decision": "approve"})
            assert decided.status_code == 200, decided.text
        guide = c.post(policy, json=smell).json()["safety_guidance"]
        assert guide["approved"] is True and guide["answer"] == gas
        assert guide["citations"][0]["documentId"] == candidate["id"]
        # Fire guidance is still waiting for management, so a fire gets none.
        fire = c.post(policy, json={"message_text": "Bếp nhà tôi đang cháy", "assessment": None}).json()
        assert fire["emergency"] and "safety_guidance" not in fire


def test_management_reads_what_the_resident_said_about_a_ticket(database):
    with client(database) as c:
        channel, _ = resident_message(c, "Conversation", "Ổ điện hỏng")
        unit = c.get("/resident/me").json()["units"][0]
        ticket = c.post(f"/resident/chats/{channel}/tickets", headers={"Idempotency-Key": str(uuid4())}, json={
            "domain_id": unit["domain_id"], "building_id": unit["building_id"], "unit_id": unit["id"],
            "category_id": CATEGORY, "title": "Ổ điện hỏng", "description": "Ổ điện hỏng từ sáng.",
            "contact_name": "Cư dân", "contact_phone": "0900000000", "location": "Phòng khách", "request_kind": "incident"}).json()
        c.post(f"/resident/chats/{channel}/messages", json={"text": "Bổ sung: ổ nằm cạnh tivi.", "client_message_id": str(uuid4())})
    ticket_id = ticket["ticket"]["id"] if "ticket" in ticket else ticket["id"]
    with demo_client(database, "management") as management:
        items = management.get(f"/tickets/{ticket_id}/conversation").json()["items"]
        assert [m["text"] for m in items if m["sender_kind"] == "user"] == ["Ổ điện hỏng", "Bổ sung: ổ nằm cạnh tivi."]
    with demo_client(database, "security") as other:
        # Staff without this ticket cannot read the resident's conversation.
        assert other.get(f"/tickets/{ticket_id}/conversation").status_code == 404


def test_runs_record_usage_and_a_stale_run_is_closed(database, monkeypatch):
    from vinhomes_api.reception_delegation import finish_run
    from vinhomes_api.v3_reception_runtime import _resident_transaction

    monkeypatch.setenv("RECEPTION_DELEGATION_KEY", "3d" * 32)
    with client(database) as c:
        channel, first = resident_message(c, "Usage")
        run = delegate(c, channel, first)["context"]["runId"]

        async def finish():
            async with _resident_transaction(c.app, "local-v3-resident") as db:
                await finish_run(db, run, True, {"input_tokens": 1200, "output_tokens": 80})

        c.portal.call(finish)
        row = sql(database, "select status,input_tokens,output_tokens from agent_runs where id=$1", UUID(run))[0]
        assert row == {"status": "succeeded", "input_tokens": 1200, "output_tokens": 80}

        # A run left running by a crash is closed when the conversation's next turn opens.
        second = c.post(f"/resident/chats/{channel}/messages", json={"text": "Lượt hai", "client_message_id": str(uuid4())}).json()
        stale = delegate(c, channel, second["id"])
        sql(database, "update agent_runs set started_at=now()-interval '20 minutes' where id=$1", UUID(stale["context"]["runId"]))
        third = c.post(f"/resident/chats/{channel}/messages", json={"text": "Lượt ba", "client_message_id": str(uuid4())}).json()
        delegate(c, channel, third["id"])
        status = sql(database, "select status,error_code from agent_runs where id=$1", UUID(stale["context"]["runId"]))[0]
        assert status == {"status": "failed", "error_code": "abandoned"}
        assert c.get("/internal/reception/catalog", headers={"Authorization": "Bearer " + stale["token"]}).status_code == 403


def test_a_resident_cannot_flood_the_assistant(database):
    # Other tests share this database and resident, so the limit is three more than already sent.
    sent = sql(database, "select count(*) as n from messages where sender_user_id='local-v3-resident' "
                         "and sender_kind='user' and created_at>now()-interval '1 minute'")[0]["n"]
    settings = V3Settings("127.0.0.1", 8000, database["runtime"], TENANT, None, "local-v3-resident",
                          resident_allowed_origins=("http://testserver",), resident_messages_per_minute=sent + 3)
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as c:
        channel = c.post("/resident/chats", json={"title": "Flood"}).json()["id"]
        send = lambda: c.post(f"/resident/chats/{channel}/messages", json={"text": "a", "client_message_id": str(uuid4())})  # noqa: E731
        assert [send().status_code for _ in range(3)] == [201, 201, 201]
        limited = send()
        assert limited.status_code == 429 and limited.headers["Retry-After"] == "60"


def test_reception_reads_the_conversation_and_its_open_request(database, monkeypatch):
    monkeypatch.setenv("RECEPTION_DELEGATION_KEY", "1b" * 32)
    with client(database) as c:
        channel, first = resident_message(c, "Context", "Ổ điện hỏng")
        other, _ = resident_message(c, "Other", "Chuyện khác")
        bearer = {"Authorization": "Bearer " + delegate(c, channel, first)["token"]}
        path = f"/internal/reception/chats/{channel}/context"
        assert c.get(path).status_code == 401
        assert c.get(f"/internal/reception/chats/{other}/context", headers=bearer).status_code == 403
        before = c.get(path, headers=bearer).json()
        assert [(m["role"], m["text"]) for m in before["history"]] == [("resident", "Ổ điện hỏng")]
        assert before["open_request"] is None
        unit = c.get("/resident/me").json()["units"][0]
        c.post(f"/resident/chats/{channel}/tickets", headers={"Idempotency-Key": str(uuid4())}, json={
            "domain_id": unit["domain_id"], "building_id": unit["building_id"], "unit_id": unit["id"],
            "category_id": CATEGORY, "title": "Ổ điện hỏng", "description": "Ổ điện hỏng từ sáng.",
            "contact_name": "Cư dân", "contact_phone": "0900000000", "location": "Phòng khách", "request_kind": "incident"})
        after = c.get(path, headers=bearer).json()
        request = after["open_request"]
        assert request["title"] == "Ổ điện hỏng" and request["status"] == "open" and request["code"].startswith("VH-")
        # Long-term memory is the resident's own earlier requests, never anyone else's or the open one.
        mine = {str(row["id"]) for row in sql(database, "select id from tickets where requester_user_id='local-v3-resident'")}
        assert after["past_requests"] and len(after["past_requests"]) <= 5
        assert {r["id"] for r in after["past_requests"]} <= mine - {request["id"]}
        assert all(set(r) == {"id", "title", "status", "category", "created_on"} for r in after["past_requests"])


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
