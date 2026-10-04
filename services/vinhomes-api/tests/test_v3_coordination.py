"""The internal API the Supervisor runtime uses, against migrated, seeded PostgreSQL."""

import json
import pytest
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from test_resident_contract import CATEGORY, TENANT, sql
from test_resident_contract import (
    database as database,  # noqa: PLC0414 -- pytest fixture export
)
from test_v3_agent_database import demo_client, operation
from vinhomes_api.main import create_app
from vinhomes_api.v3_config import V3Settings

TOKEN = "coordination-test-token-0123456789abcdef"
BASE = "/internal/coordination/v1"
SERVICE = {"Authorization": "Bearer " + TOKEN}


@contextmanager
def app(database, token=TOKEN):
    """The resident's own session, with the Coordination runtime configured."""
    settings = V3Settings("127.0.0.1", 8000, database["runtime"], TENANT, None, "local-v3-resident",
                          resident_allowed_origins=("http://testserver",), coordination_service_token=token)
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as c:
        yield c


def hand_over(c, title):
    """Reception files a request for the resident; the backend opens the team and stores ticket_submitted."""
    place = operation(c, "get_verified_resident_context")[0]["residences"][0]
    channel = c.post("/resident/chats", json={"title": title}).json()["id"]
    message = c.post(f"/resident/chats/{channel}/messages", json={"text": title, "client_message_id": str(uuid4())}).json()
    draft, _ = operation(c, "create_ticket_draft", {
        "channel_id": channel, "title": title, "description": "Vòi nước bếp bị rò từ sáng",
        "domain_id": place["domain_id"], "building_id": place["building_id"], "unit_id": place["unit_id"],
        "category_id": CATEGORY, "source_message_id": message["id"]})
    target = {"channel_id": channel, "draft_id": draft["draftId"]}
    operation(c, "update_ticket_incident", {**target, "fields": {"request_kind": "incident"}})
    operation(c, "submit_ticket_assessment", {**target, "assessment": {
        "priority": "normal", "severity": "minor", "reason": "Cư dân báo rò nước"}})
    assert operation(c, "resolve_management_destination", target)[0]["available"]
    handoff, _ = operation(c, "handoff_ticket", target)
    assert handoff["accepted"] and handoff["team"], handoff
    return handoff, channel


def result(verified, kind, text, **extra):
    """A V2 result as the Supervisor builds it: from the verified input and its own run."""
    m = verified["message"]
    return {"schema_version": "2.0", "message_id": str(uuid4()), "correlation_id": m["correlation_id"],
            "sent_at": datetime.now(UTC).isoformat(), "message_type": kind, "message": text,
            "tenant_id": m["tenant_id"], "workspace_id": m["workspace_id"], "team_id": m["team_id"],
            "ticket_id": m["ticket_id"], "ticket_code": m["ticket_code"],
            "ticket_generation": m["ticket_generation"], "ticket_version": m["ticket_version"],
            "supervisor_run_id": verified["supervisor_run_id"], **extra}


def publish_specialist(database, name, categories, tools=()):
    """Management drafts an agent in its room, records an evaluation, and an admin approves it."""
    room = f"/rooms/management-room/agents"
    with demo_client(database, "management") as management:
        agent = management.post(room, json={"name": name, "instructions": "Phân tích sự cố.",
                                            "idempotency_key": name}).json()["id"]
        configured = management.put(f"{room}/{agent}/configuration", json={
            "instructions": "Phân tích sự cố kỹ thuật và đề xuất cách xử lý.", "description": name,
            "service_categories": categories,
            "mcp_tools": [tool if isinstance(tool, dict) else {"server_id": "technical-tools", "name": tool} for tool in tools]})
        assert configured.status_code == 200, configured.text
        cases = [{"name": f"case-{n}", "input": "i", "expected": "e", "actual": "e", "passed": True,
                  "explanation": "ok"} for n in range(6)]
        review = management.post(f"{room}/{agent}/review-submissions", json={
            "configuration_hash": configured.json()["configurationHash"], "evaluator": "test", "round": 1, "cases": cases})
        assert review.status_code == 201, review.text
    with demo_client(database, "admin") as admin:
        decided = admin.post(f"/admin/agent-reviews/{review.json()['id']}/decision",
                             json={"decision": "approve", "version": review.json()["version"], "note": "Đạt"})
        assert decided.status_code == 200, decided.text
    return agent, decided.json()["versionId"]


def verified_team(c, database, title):
    handoff, _ = hand_over(c, title)
    team = handoff["team"]["id"]
    message = sql(database, "select message_id from vh_reception_supervisor_messages where team_id=$1", UUID(team))[0]["message_id"]
    assert c.post(BASE + "/reception/verify", headers=SERVICE, json={"team_id": team, "message_id": message}).status_code == 200
    return team


def test_only_the_configured_runtime_reaches_the_coordination_api(database):
    with app(database, token=None) as c:
        assert c.get(BASE + "/inbox", headers=SERVICE).status_code == 503
    with app(database) as c:
        assert c.get(BASE + "/inbox").status_code == 401                      # a resident session is not the runtime
        assert c.get(BASE + "/inbox", headers={"Authorization": "Bearer " + "x" * 40}).status_code == 401
        assert c.get(BASE + "/inbox", headers=SERVICE).status_code == 200


def test_the_supervisor_receives_a_ticket_and_accepts_it(database):
    with app(database) as c:
        handoff, resident_chat = hand_over(c, f"Vòi nước rò {uuid4().hex[:6]}")
        team, ticket = handoff["team"]["id"], handoff["ticket"]["id"]
        page = c.get(BASE + "/inbox?limit=100", headers=SERVICE).json()
        while page["items"] and not any(i["team_id"] == team for i in page["items"]):
            page = c.get(BASE + f"/inbox?limit=100&cursor={page['next_cursor']}", headers=SERVICE).json()
        submitted = next(i["message"] for i in page["items"] if i["team_id"] == team)
        assert submitted["message_type"] == "ticket_submitted" and submitted["ticket_id"] == ticket
        # Nothing after the cursor: a poll does not see the same message twice.
        assert not any(i["team_id"] == team for i in c.get(
            BASE + f"/inbox?cursor={page['next_cursor']}", headers=SERVICE).json()["items"])

        ask = {"team_id": team, "message_id": submitted["message_id"]}
        assert c.post(BASE + "/reception/verify", headers=SERVICE, json={**ask, "message_id": "unknown"}).status_code == 404
        assert c.post(BASE + "/reception/verify", headers=SERVICE, json={**ask, "team_id": str(uuid4())}).status_code == 403
        verified = c.post(BASE + "/reception/verify", headers=SERVICE, json=ask).json()
        assert verified["message"] == submitted
        context = verified["context"]
        assert context["ticket_id"] == ticket and context["run_id"] == verified["supervisor_run_id"]
        # The session and its run are rows of the backend, and stay the same for the whole session.
        assert c.post(BASE + "/reception/verify", headers=SERVICE, json=ask).json()["context"] == context
        run = sql(database, "select r.status,b.audience_kind,b.runtime_session_key,m.binding_id from agent_runs r "
                            "join runtime_session_bindings b on b.id=r.binding_id join team_members m on m.id=r.team_member_id "
                            "where r.id=$1", UUID(context["run_id"]))[0]
        assert run == {"status": "running", "audience_kind": "team", "runtime_session_key": "coordination:" + team,
                       "binding_id": UUID(context["binding_id"])}

        accepted = result(verified, "accepted", "Yêu cầu đã được tiếp nhận.")
        assert c.post(BASE + f"/teams/{team}/authorize", headers=SERVICE, json={
            "action_id": accepted["message_id"], "channel": "reception", "operation": "accepted"}).json() == {"authorized": True}
        assert c.post(BASE + f"/teams/{team}/authorize", headers=SERVICE, json={
            "action_id": "a", "channel": "backend", "operation": "assignment.offered"}).status_code == 409
        lookup = BASE + f"/teams/{team}/results/{accepted['message_id']}"
        assert c.get(lookup, headers=SERVICE).json()["found"] is False
        sent = c.post(BASE + "/reception/send", headers=SERVICE, json={"message": accepted})
        assert sent.status_code == 200 and sent.json() == {
            "message_id": accepted["message_id"], "status": "accepted", "replayed": False}, sent.text
        assert c.get(lookup, headers=SERVICE).json() == {"found": True, "message_id": accepted["message_id"], "status": "accepted"}
        # The same result again changes nothing; the same id with other content is refused.
        assert c.post(BASE + "/reception/send", headers=SERVICE, json={"message": accepted}).json()["replayed"] is True
        assert c.post(BASE + "/reception/send", headers=SERVICE,
                      json={"message": {**accepted, "message": "Nội dung khác"}}).status_code == 409
        stored = sql(database, "select created_by,created_by_agent_id from vh_reception_supervisor_messages "
                               "where message_id=$1", accepted["message_id"])[0]
        assert stored == {"created_by": None, "created_by_agent_id": "demo-supervisor"}
        room = sql(database, "select body->>'text' as text from messages where channel_id='management-room' "
                             "and body->>'sessionId'=$1", team)
        assert [m["text"] for m in room] == [f"{handoff['ticket']['code']}: Yêu cầu đã được tiếp nhận."]
        # Progress stays with management; the resident already heard from Reception.
        assert not sql(database, "select 1 from messages where channel_id=$1 and body->>'source'='supervisor'", resident_chat)

        c.post(BASE + f"/teams/{team}/status", headers=SERVICE, json={
            "phase": "paused", "pause_reason": "planner:no_specialist_available", "state_version": 3})
        seen = c.get(BASE + f"/teams/{team}/view", headers=SERVICE).json()
        assert seen["context"] == context and seen["team_status"] == "running" and seen["specialists"] == []
        assert seen["ticket_version"] == submitted["ticket_version"] and seen["pending_resident"] is None
    with demo_client(database, "management") as management:
        session = management.get(f"/tickets/{ticket}/session").json()["session"]
        assert session["status"] == "running" and session["supervisor"]["lastMessageType"] == "accepted"
        assert session["runtime"] == {"phase": "paused", "pauseReason": "planner:no_specialist_available", "stateVersion": 3}


def test_a_supervisor_question_reaches_the_resident_and_a_stale_team_is_refused(database):
    with app(database) as c:
        handoff, resident_chat = hand_over(c, f"Điều hòa không mát {uuid4().hex[:6]}")
        team, ticket = handoff["team"]["id"], handoff["ticket"]["id"]
        message = sql(database, "select message_id from vh_reception_supervisor_messages where team_id=$1", UUID(team))[0]["message_id"]
        verified = c.post(BASE + "/reception/verify", headers=SERVICE, json={"team_id": team, "message_id": message}).json()
        question = result(verified, "information_requested", "Điều hòa hỏng từ khi nào ạ?")
        assert c.post(BASE + "/reception/send", headers=SERVICE, json={"message": question}).status_code == 200
        told = sql(database, "select body->>'text' as text,sender_kind from messages where channel_id=$1 "
                             "and body->>'source'='supervisor'", resident_chat)
        assert told == [{"text": "Điều hòa hỏng từ khi nào ạ?", "sender_kind": "agent"}]
        assert sql(database, "select status from agent_teams where id=$1", UUID(team))[0]["status"] == "waiting"
        assert c.get(BASE + f"/teams/{team}/view", headers=SERVICE).json()["pending_resident"] == "information"
        # One question at a time: a second one is refused by the same rule as for an operator.
        again = result(verified, "information_requested", "Anh chị ở nhà lúc nào ạ?")
        assert c.post(BASE + "/reception/send", headers=SERVICE, json={"message": again}).status_code == 409

        # The ticket was reopened: the team belongs to the previous generation.
        sql(database, "update tickets set reopen_count=reopen_count+1 where id=$1 returning id", UUID(ticket))
        assert c.post(BASE + "/reception/verify", headers=SERVICE, json={"team_id": team, "message_id": message}).status_code == 409
        assert c.post(BASE + "/reception/send", headers=SERVICE,
                      json={"message": result(verified, "in_progress", "Đang xử lý.")}).status_code == 409
        assert c.get(BASE + f"/teams/{team}/view", headers=SERVICE).status_code == 409


def test_the_supervisor_is_offered_the_published_specialists_of_the_ticket_category(database):
    technical, version = publish_specialist(database, f"Kỹ thuật {uuid4().hex[:6]}", ["technical"])
    publish_specialist(database, f"An ninh {uuid4().hex[:6]}", ["security"])
    with app(database) as c:
        team = verified_team(c, database, f"Rò nước {uuid4().hex[:6]}")
        seen = c.get(BASE + f"/teams/{team}/view", headers=SERVICE).json()
        assert seen["category"] == "technical"
        offered = [s for s in seen["specialists"] if s["agent_id"] == technical]
        assert offered == [{"agent_version_id": version, "agent_id": technical, "name": offered[0]["name"],
                            "role": "technical", "description": offered[0]["name"], "service_categories": ["technical"], "tools": []}]
        # Another category's agent is published in the same room and is not offered for this ticket.
        assert all(s["service_categories"] == ["technical"] for s in seen["specialists"])

        with demo_client(database, "management") as management:
            assert management.post(f"/admin/agents/{technical}/release/revoke", json={"note": "x"}).status_code == 403
            assert management.get("/admin/agent-releases").status_code == 403
        with demo_client(database, "admin") as admin:
            listed = next(r for r in admin.get("/admin/agent-releases").json()["items"] if r["agent_id"] == technical)
            assert (listed["version_no"], listed["service_categories"], listed["tools"]) == (1, ["technical"], [])
            revoked = admin.post(f"/admin/agents/{technical}/release/revoke", json={"note": "Trả lời sai quy trình"})
            assert revoked.status_code == 200 and revoked.json()["versionId"] == version
            assert admin.post(f"/admin/agents/{technical}/release/revoke", json={"note": "x"}).status_code == 404
            assert not [r for r in admin.get("/admin/agent-releases").json()["items"] if r["agent_id"] == technical]
        after = c.get(BASE + f"/teams/{team}/view", headers=SERVICE).json()["specialists"]
        assert not [s for s in after if s["agent_id"] == technical]


def register_tools(database):
    """The tenant's tool catalogue, as scripts/setup_session_tools.py registers it."""
    sql(database, "insert into mcp_servers(id,title,vendor,url,tenant_id) values('technical-tools','Công cụ kỹ thuật',"
                  "'Team Quang','internal:/internal/technical/v1',$1) on conflict (id) do nothing returning id", TENANT)
    schema = '{"type": "object", "properties": {"building_id": {"type": "string"}}, "required": ["building_id"]}'
    for name, effect in (("technical.get_active_outage", "read"), ("apartment_entry.request", "request")):
        sql(database, "insert into mcp_tools(server_id,name,description,input_schema,effect,tenant_id) "
                      "values('technical-tools',$1,$2,cast($3 as jsonb),$4,$5) on conflict (server_id,name) do nothing "
                      "returning name", name, "Mô tả " + name, schema, effect, TENANT)


def test_a_configuration_naming_an_unknown_category_or_tool_is_refused(database):
    register_tools(database)
    key = uuid4().hex[:8]
    with demo_client(database, "management") as management:
        agent = management.post("/rooms/management-room/agents", json={
            "name": f"Nháp {key}", "instructions": "Phân tích sự cố.", "idempotency_key": key}).json()["id"]

        def configure(**fields):
            return management.put(f"/rooms/management-room/agents/{agent}/configuration", json={
                "instructions": "Phân tích sự cố.", "description": "Nháp", **fields}).status_code

        assert configure(service_categories=["plumbing"]) == 422
        assert configure(mcp_tools=[{"server_id": "technical-tools", "name": "shell.exec"}]) == 422
        assert configure(service_categories=["technical"], mcp_tools=[
            {"server_id": "technical-tools", "name": "technical.get_active_outage"}]) == 200


def test_a_published_specialist_enters_the_room_and_its_work_is_mirrored(database):
    name = f"Kỹ thuật {uuid4().hex[:6]}"
    register_tools(database)
    technical, version = publish_specialist(database, name, ["technical"],
                                            tools=("technical.get_active_outage",))
    _, security = publish_specialist(database, f"An ninh {uuid4().hex[:6]}", ["security"])
    with app(database) as c:
        team = verified_team(c, database, f"Rò nước {uuid4().hex[:6]}")
        code = sql(database, "select t.code from agent_teams tm join tickets t on t.id=tm.ticket_id where tm.id=$1",
                   UUID(team))[0]["code"]
        members = BASE + f"/teams/{team}/members"
        # Published, but for another category: the Supervisor cannot bring it into this room.
        assert c.post(members, headers=SERVICE, json={"agent_version_id": security}).status_code == 409
        member = c.post(members, headers=SERVICE, json={"agent_version_id": version}).json()
        assert (member["platform_agent_id"], member["role"], member["binding_generation"]) == (technical, "technical", 1)
        assert c.post(members, headers=SERVICE, json={"agent_version_id": version}).json() == member
        assert c.post(BASE + f"/teams/{team}/authorize", headers=SERVICE, json={
            "action_id": "a", "channel": "room", "operation": "open_room"}).json() == {"authorized": True}
        assert c.post(BASE + f"/teams/{team}/authorize", headers=SERVICE, json={
            "action_id": "a", "channel": "backend", "operation": "assignment.offered"}).status_code == 409

        one = members + f"/{member['member_id']}"
        run = c.post(one + "/runs", headers=SERVICE, json={"operation_id": "op-1"}).json()["run_id"]
        assert c.post(one + "/runs", headers=SERVICE, json={"operation_id": "op-1"}).json()["run_id"] == run
        parent = sql(database, "select p.idempotency_key from agent_runs r join agent_runs p on p.id=r.parent_run_id "
                               "where r.id=$1", UUID(run))[0]["idempotency_key"]
        assert parent == "supervisor-session:" + team
        released = c.get(one + "/release", headers=SERVICE).json()
        assert released["agent_version_id"] == version and released["binding_id"] == member["binding_id"]
        assert released["thread_id"] == f"coordination:{team}:{member['member_id']}"
        assert (released["published"], released["revoked"]) == (True, False)
        # The read tool it was approved with, under the name a model can call; the request tool stays closed.
        assert released["tool_descriptors"] == [{
            "name": "technical__get_active_outage", "description": "Mô tả technical.get_active_outage",
            "parameters": {"type": "object", "properties": {"building_id": {"type": "string"}}, "required": ["building_id"]}}]
        assert released["instructions"].startswith("Phân tích sự cố") and released["capabilities"] == ["technical"]

        mirror = {"tasks": [{"task_id": "t1", "description": "Xác định nguyên nhân rò nước",
                             "assignee_agent_version_id": version, "status": "in_progress"}],
                  "messages": [{"message_id": "m1", "sender_agent_version_id": version,
                                "content": "Khả năng cao do gioăng vòi.", "task_id": "t1"}],
                  "runs": [{"run_id": run, "status": "succeeded"}]}
        assert c.post(BASE + f"/teams/{team}/room", headers=SERVICE, json=mirror).json() == {"ok": True, "messages_stored": 1}
        mirror["tasks"][0]["status"] = "completed"
        # Sent again after the task finished: the reply is not stored twice, the task moves on.
        assert c.post(BASE + f"/teams/{team}/room", headers=SERVICE, json=mirror).json() == {"ok": True, "messages_stored": 0}
        assert sql(database, "select status,version,title from team_tasks where team_id=$1", UUID(team)) == [
            {"status": "done", "version": 1, "title": "Xác định nguyên nhân rò nước"}]
        said = sql(database, "select body->>'text' as text,sender_agent_id from messages where channel_id='management-room' "
                             "and body->>'sessionId'=$1 and body->>'kind'='specialist_reply'", team)
        assert said == [{"text": f"{code}: Khả năng cao do gioăng vòi.", "sender_agent_id": technical}]
        assert sql(database, "select status from agent_runs where id=$1", UUID(run))[0]["status"] == "succeeded"
        # Management reads who was invited, what they were asked and what they answered.
        ticket = sql(database, "select ticket_id from agent_teams where id=$1", UUID(team))[0]["ticket_id"]
        with demo_client(database, "management") as management:
            seen = management.get(f"/tickets/{ticket}/session").json()["room"]
        assert seen["members"] == [name]
        assert seen["tasks"] == [{"description": "Xác định nguyên nhân rò nước", "status": "done", "agent": name}]
        assert [(r["agent"], r["text"]) for r in seen["replies"]] == [(name, "Khả năng cao do gioăng vòi.")]
        # Management asks the agent a follow-up inside the session; the runtime picks it up and reports back.
        with demo_client(database, "technical") as staff:
            # A technician who is not on this ticket does not even see it.
            assert staff.post(f"/tickets/{ticket}/session/questions", json={
                "text": "x", "client_message_id": "q0"}).status_code == 404
        with demo_client(database, "management") as management:
            ask = {"text": "Có cần khóa van tổng không?", "client_message_id": f"q-{team}"}
            asked = management.post(f"/tickets/{ticket}/session/questions", json=ask)
            assert asked.status_code == 201 and asked.json()["status"] == "queued", asked.text
            assert management.post(f"/tickets/{ticket}/session/questions", json=ask).json() == {
                "id": asked.json()["id"], "status": "queued", "replayed": True}
            # One question at a time: the room runs one turn at a time.
            assert management.post(f"/tickets/{ticket}/session/questions", json={
                "text": "Câu khác", "client_message_id": "q2"}).status_code == 409
            assert management.post(f"/tickets/{ticket}/session/questions", json={
                "text": "x", "client_message_id": "q3", "agent_id": "demo-supervisor"}).status_code == 422
        queued = [m for m in c.get(BASE + "/mentions", headers=SERVICE).json()["items"] if m["team_id"] == team]
        assert [(m["message_id"], m["agent_id"], m["agent_version_id"], m["text"]) for m in queued] == [
            (asked.json()["id"], technical, version, "Có cần khóa van tổng không?")]
        assert queued[0]["context"]["ticket_id"] == str(ticket)
        done = BASE + f"/teams/{team}/mentions/{asked.json()['id']}"
        assert c.post(done, headers=SERVICE, json={"status": "done", "run_id": run}).json() == {"ok": True}
        assert not [m for m in c.get(BASE + "/mentions", headers=SERVICE).json()["items"] if m["team_id"] == team]
        with demo_client(database, "management") as management:
            [question] = management.get(f"/tickets/{ticket}/session").json()["room"]["questions"]
            assert (question["agent"], question["text"], question["status"]) == (name, "Có cần khóa van tổng không?", "done")
        outsider = {**mirror, "tasks": [{**mirror["tasks"][0], "assignee_agent_version_id": security}]}
        assert c.post(BASE + f"/teams/{team}/room", headers=SERVICE, json=outsider).status_code == 409

        # Revoked while the session runs: the next turn of that agent is refused.
        with demo_client(database, "admin") as admin:
            assert admin.post(f"/admin/agents/{technical}/release/revoke", json={"note": "Thu hồi"}).status_code == 200
        assert c.get(one + "/release", headers=SERVICE).status_code == 409
        assert c.post(one + "/runs", headers=SERVICE, json={"operation_id": "op-2"}).status_code == 409


@pytest.mark.parametrize('resident_decision', ['approve', 'reject', 'request_changes'])
def test_the_supervisor_proposes_a_plan_that_management_then_decides(database, resident_decision):
    with app(database) as c:
        handoff, resident_chat = hand_over(c, f"Vòi bếp rò {uuid4().hex[:6]}")
        team, ticket = handoff["team"]["id"], handoff["ticket"]["id"]
        message = sql(database, "select message_id from vh_reception_supervisor_messages where team_id=$1", UUID(team))[0]["message_id"]
        assert c.post(BASE + "/reception/verify", headers=SERVICE, json={"team_id": team, "message_id": message}).status_code == 200
        view = BASE + f"/teams/{team}/view"
        before = c.get(view, headers=SERVICE).json()
        assert before["plan"] is None
        draft = {"request_id": f"draft-{uuid4().hex}", "payload_hash": "a" * 64,
                 "ticket_version": before["ticket_version"], "target_plan_version": 1,
                 "plan": {"summary": "Thay gioăng vòi bếp và kiểm tra áp lực nước",
                          "steps": ["Khóa van nước căn hộ", "Thay gioăng vòi bếp"], "performer_role": "Kỹ thuật viên nước",
                          "expected_duration": "45 phút", "conditions": "Cư dân có mặt tại căn hộ",
                          "cost": {"amount": 150000.0, "currency": "VND", "kind": "estimate"},
                          "result_refs": ["task-1"], "attachment_ids": []}}
        plans = BASE + f"/teams/{team}/plans"
        assert c.post(BASE + f"/teams/{team}/authorize", headers=SERVICE, json={
            "action_id": draft["request_id"], "channel": "draft", "operation": "plan"}).json() == {"authorized": True}
        # A plan made for an earlier state of the ticket is refused.
        assert c.post(plans, headers=SERVICE, json={**draft, "ticket_version": "999"}).status_code == 409
        stored = c.post(plans, headers=SERVICE, json=draft)
        assert stored.status_code == 200, stored.text
        plan = stored.json()["canonical_id"]
        assert stored.json() == {"request_id": draft["request_id"], "status": "accepted", "payload_hash": "a" * 64,
                                 "canonical_id": plan, "ticket_version": str(int(before["ticket_version"]) + 1),
                                 "plan_version": 1}
        # The same request stores nothing new; its id with other content, or a second plan, is refused.
        assert c.post(plans, headers=SERVICE, json=draft).json() == stored.json()
        assert c.post(plans, headers=SERVICE, json={**draft, "payload_hash": "b" * 64}).status_code == 409
        assert c.post(plans, headers=SERVICE, json={
            **draft, "request_id": "another", "ticket_version": stored.json()["ticket_version"]}).status_code == 409

        row = sql(database, "select proposed_by,proposed_by_agent_id,status,title,steps,estimated_amount,proposal "
                            "from vh_ticket_plans where id=$1", UUID(plan))[0]
        assert (row["proposed_by"], row["proposed_by_agent_id"], row["status"]) == (None, "demo-supervisor", "management_pending")
        assert row["title"] == draft["plan"]["summary"] and row["estimated_amount"] == 150000
        steps, proposal = json.loads(row["steps"]), json.loads(row["proposal"])
        # One visit by one technician: the steps are one work order, and stay listed in the proposal.
        assert steps == [{"category_id": CATEGORY, "description": "1. Khóa van nước căn hộ\n2. Thay gioăng vòi bếp"}]
        assert proposal["performer_role"] == "Kỹ thuật viên nước" and proposal["plan_version"] == 1
        assert proposal["steps"] == draft["plan"]["steps"]
        event = sql(database, "select actor_kind,actor_user_id,actor_agent_id from ticket_events "
                              "where ticket_id=$1 and event_type='plan.proposed'", UUID(ticket))
        assert event == [{"actor_kind": "agent", "actor_user_id": None, "actor_agent_id": "demo-supervisor"}]

        seen = c.get(view, headers=SERVICE).json()
        assert seen["ticket_version"] == stored.json()["ticket_version"]
        assert seen["plan"]["plan_id"] == plan and seen["plan"]["status"] == "management_pending"
        assert seen["plan"]["management_recipient"].startswith("management-unit:")
        assert datetime.fromisoformat(seen["plan"]["approval_expires_at"]) > datetime.now(UTC)
        request = BASE + f"/teams/{team}/plans/{plan}/approval-request"
        assert c.post(BASE + f"/teams/{team}/authorize", headers=SERVICE, json={
            "action_id": "a", "channel": "backend", "operation": "approval.requested"}).json() == {"authorized": True}
        asked = {"approval_id": "approval-1", "plan_version": 1}
        assert c.post(request, headers=SERVICE, json=asked).json() == {"status": "accepted", "plan_id": plan}
        assert c.post(request, headers=SERVICE, json=asked).status_code == 200            # the same request again
        assert c.post(request, headers=SERVICE, json={**asked, "approval_id": "other"}).status_code == 409
        assert c.post(BASE + f"/teams/{team}/plans/{uuid4()}/approval-request", headers=SERVICE, json=asked).status_code == 404
        assert c.get(BASE + "/events", headers=SERVICE).json() == {"items": []}           # nobody decided yet

    with demo_client(database, "management") as management:
        shown = management.get(f"/tickets/{ticket}/session").json()["room"]["plan"]
        assert shown["id"] == plan and shown["status"] == "management_pending"
        assert shown["proposal"]["expected_duration"] == "45 phút" and len(shown["proposal"]["steps"]) == 2
        # The room's session list says who each session waits for, from the plan itself.
        listed = lambda: next(s for s in management.get("/rooms/management-room/teams").json()["items"] if s["id"] == team)
        assert (listed()["plan_status"], listed()["ticket_status"]) == ("management_pending", "open")
        decided = management.post(f"/plans/{plan}/management-decision",
                                  json={"decision": "approve", "version": shown["version"], "note": "Đồng ý phương án"})
        assert decided.status_code == 200 and decided.json()["status"] == "resident_pending", decided.text
        assert listed()["plan_status"] == "resident_pending"
    with app(database) as c:
        # Management decided. The runtime reads the decision as an answer to the request it made.
        [decision] = [e for e in c.get(BASE + "/events", headers=SERVICE).json()["items"] if e["team_id"] == team]
        assert decision["plan_id"] == plan and decision["context"] == before["context"]
        assert decision["event"]["event_type"] == "approval.responded" and decision["event"]["payload"] == {
            "approval_id": "approval-1", "plan_id": plan, "plan_version": 1, "stage": "management_plan",
            "decision": "approve", "comment": "Đồng ý phương án"}
        assert c.post(request, headers=SERVICE, json={"approval_id": "late", "plan_version": 1}).status_code == 409
        # The backend says who is asked next and in which words; the Supervisor sends exactly that.
        seen = c.get(view, headers=SERVICE).json()
        assert seen["plan"]["status"] == "resident_pending" and seen["plan"]["resident_approval_required"] is True
        assert seen["plan"]["resident_recipient"] == "local-v3-resident"
        assert seen["plan"]["resident_request_type"] == "plan_approval_requested"
        question = seen["plan"]["resident_request_message"]
        assert "1. Khóa van nước căn hộ\n2. Thay gioăng vòi bếp" in question and "Chi phí dự kiến: 150.000 VND" in question
        assert question.endswith("Anh/chị có đồng ý với phương án này không?")
        verified = c.post(BASE + "/reception/verify", headers=SERVICE, json={"team_id": team, "message_id": message}).json()
        sent = c.post(BASE + "/reception/send", headers=SERVICE, json={"message": result(
            verified, "plan_approval_requested", question, ticket_version=seen["ticket_version"])})
        assert sent.status_code == 200, sent.text
        told = sql(database, "select body->>'text' as text from messages where channel_id=$1 and body->>'source'='supervisor'",
                   resident_chat)
        assert [m["text"] for m in told] == [question]
        delivered = BASE + f"/teams/{team}/plans/{plan}/decision-delivered"
        assert c.post(delivered, headers=SERVICE).json() == {"ok": True}
        assert not [e for e in c.get(BASE + "/events", headers=SERVICE).json()["items"] if e["team_id"] == team]
        # Consumption is verified again after a restart, even if delivery was already acknowledged.
        checked = c.get(BASE + f"/teams/{team}/plans/{plan}/management-event", headers=SERVICE)
        assert checked.status_code == 200 and checked.json()["event"] == decision["event"]
        pending = next(i for i in c.get('/resident/supervisor-interactions').json()['items'] if i['ticket_id'] == ticket)
        response_body = {'decision': resident_decision, 'note': 'Ý kiến cư dân', 'ticket_version': pending['ticket_version'], 'request_id': str(uuid4())}
        unread = lambda: next(x for x in c.get('/resident/chats').json()['items'] if x['id'] == resident_chat)['unread_count']
        assert unread() > 0
        agreed = c.post(f"/resident/tickets/{ticket}/supervisor-response", json=response_body)
        assert agreed.status_code == 200, agreed.text
        assert unread() == 0                                                  # answering the question is reading it
        assert c.post(f"/resident/tickets/{ticket}/supervisor-response", json=response_body).status_code == 200
        assert c.post(f"/resident/tickets/{ticket}/supervisor-response", json={**response_body, 'note': 'Khác'}).status_code == 409
        assert not [i for i in c.get('/resident/supervisor-interactions').json()['items'] if i['ticket_id'] == ticket]
        kind = {'approve': 'plan_approved', 'reject': 'plan_rejected', 'request_changes': 'plan_change_requested'}[resident_decision]
        inputs = sql(database, "select message_type from vh_reception_supervisor_messages where ticket_id=$1 and message_type=$2", UUID(ticket), kind)
        assert len(inputs) == 1
        current = sql(database, 'select version from tickets where id=$1', UUID(ticket))[0]
        assert current['version'] == pending['ticket_version'] + 1
    orders = sql(database, "select description from work_orders where ticket_id=$1", UUID(ticket))
    assert [o["description"] for o in orders] == (["1. Khóa van nước căn hộ\n2. Thay gioăng vòi bếp"] if resident_decision == 'approve' else [])


def test_a_question_is_stored_and_versioned_before_the_resident_is_asked(database):
    with app(database) as c:
        team = verified_team(c, database, f"Rò nước {uuid4().hex[:6]}")
        before = c.get(BASE + f"/teams/{team}/view", headers=SERVICE).json()
        draft = {"request_id": uuid4().hex, "payload_hash": "a" * 64,
                 "ticket_version": before["ticket_version"], "question": "Nước rò ở vòi hay đường ống dưới bồn rửa?"}
        route = BASE + f"/teams/{team}/questions"
        stored = c.post(route, headers=SERVICE, json=draft)
        assert stored.status_code == 200, stored.text
        assert c.post(route, headers=SERVICE, json=draft).json() == stored.json()
        assert c.post(route, headers=SERVICE, json={**draft, "question": "Khác"}).status_code == 409
        assert c.post(route, headers=SERVICE, json={**draft, "request_id": "second"}).status_code == 409
        after = c.get(BASE + f"/teams/{team}/view", headers=SERVICE).json()
        assert after["resident_request_type"] == "information_requested"
        assert after["resident_request_message"] == draft["question"]
        assert int(after["ticket_version"]) == int(before["ticket_version"]) + 1
        assert after["ticket_version"] == stored.json()["ticket_version"]
        message = sql(database, "select message_id from vh_reception_supervisor_messages where team_id=$1 and message_type='ticket_submitted'", UUID(team))[0]['message_id']
        verified = c.post(BASE + '/reception/verify', headers=SERVICE, json={'team_id': team, 'message_id': message}).json()
        sent = c.post(BASE + '/reception/send', headers=SERVICE, json={'message': result(verified, 'information_requested', draft['question'], ticket_version=after['ticket_version'])})
        assert sent.status_code == 200, sent.text
        pending = next(i for i in c.get('/resident/supervisor-interactions').json()['items'] if i['ticket_id'] == after['context']['ticket_id'])
        answer = {'decision': 'information', 'note': 'Rò ở đường ống dưới bồn rửa.', 'ticket_version': pending['ticket_version'], 'request_id': str(uuid4())}
        route = f"/resident/tickets/{pending['ticket_id']}/supervisor-response"
        assert c.post(route, json={**answer, 'ticket_version': 999}).status_code == 409
        assert c.post(route, json={**answer, 'decision': 'approve'}).status_code == 422
        reply = c.post(route, json=answer)
        assert reply.status_code == 200, reply.text
        assert c.post(route, json=answer).status_code == 200


def test_bql_publication_revision_and_admin_override(database):
    register_tools(database)
    agent, v1 = publish_specialist(database, 'Versioned ' + uuid4().hex[:8], ['technical'])
    base = f'/rooms/management-room/agents/{agent}'
    cases = [{'name': f'case-{n}', 'input': 'i', 'expected': 'e', 'actual': 'e',
              'passed': True, 'explanation': 'ok'} for n in range(6)]
    with demo_client(database, 'management') as manager:
        config = {'instructions': 'Only analyze, do not execute actions.', 'description': 'Version 2',
                  'service_categories': ['technical'], 'revision_of': v1}
        blocked = manager.put(base + '/configuration', json={**config, 'mcp_tools': [
            {'server_id': 'technical-tools', 'name': 'apartment_entry.request'}]})
        assert blocked.status_code == 422
        saved = manager.put(base + '/configuration', json=config)
        assert saved.status_code == 200, saved.text
        review = manager.post(base + '/review-submissions', json={'configuration_hash': saved.json()['configurationHash'],
            'evaluator': 'test', 'round': 1, 'cases': cases}).json()
        # Fixture represents the service-verified result; arbitrary human records cannot attest it.
        payload = {'decision': 'approve', 'version': review['version'], 'note': 'Workspace approval'}
        assert manager.post(f"/rooms/management-room/agent-reviews/{review['id']}/decision", json=payload).status_code == 409
        sql(database, "update vh_agent_reviews set evaluation=evaluation||'{\"_runtime_verified\":true}'::jsonb where id=$1 returning id", UUID(review['id']))
        decision = manager.post(f"/rooms/management-room/agent-reviews/{review['id']}/decision",
            json={'decision': 'approve', 'version': review['version'], 'note': 'Workspace approval'})
        assert decision.status_code == 200, decision.text
        v2 = decision.json()['versionId']
        assert v1 != v2
        assert manager.get(base + '/versions').json()['items'][0]['version_no'] == 2
        # Reusing the old working draft cannot publish the same configuration again.
        assert manager.post(base + '/review-submissions', json={'configuration_hash': saved.json()['configurationHash'],
            'evaluator': 'test', 'round': 1, 'cases': cases}).status_code == 409
    with demo_client(database, 'technical') as staff:
        assert staff.get('/rooms/management-room/agent-management').status_code in (403, 404)
        assert staff.post(base + '/release/revoke', json={'note': 'Not authorized'}).status_code in (403, 404)
    with demo_client(database, 'admin') as admin:
        assert admin.post(f'/admin/agents/{agent}/release/revoke', json={'note': 'Platform override'}).status_code == 200
    with demo_client(database, 'management') as manager:
        assert not next(a for a in manager.get('/rooms/management-room/agent-management').json()['items'] if a['id'] == agent)['published']


def test_free_room_mentions_pinned_runs_real_reports_scope_and_revocation(database, monkeypatch):
    from vinhomes_api.v3_tool_gateway import catalogue
    monkeypatch.delenv('VINHOMES_API_REPAIR_CATEGORY_CODES', raising=False)
    for t in catalogue():
        sql(database, "insert into mcp_servers(id,title,vendor,url,tenant_id) values($1,$1,'first-party','internal:tools',$2) on conflict(id) do nothing returning id", t['server_id'], TENANT)
        sql(database, "insert into mcp_tools(server_id,name,description,input_schema,effect,tenant_id) values($1,$2,$3,cast($4 as jsonb),$5,$6) on conflict(server_id,name) do nothing returning name", t['server_id'], t['name'], t['description'], json.dumps(t['input_schema']), t['effect'], TENANT)
    reports = ('filter_report_scope', 'get_repair_bill_summary', 'get_ticket_frequency_summary', 'get_employee_star_summary')
    agent, version = publish_specialist(database, 'Room report ' + uuid4().hex[:8], ['technical'], tools=(
        *({'server_id': 'reporting', 'name': 'reporting.' + name} for name in reports),
        {'server_id': 'security-tools', 'name': 'security.camera.read'}))
    settings = V3Settings('127.0.0.1', 8000, database['runtime'], TENANT, None, None,
                          demo_mode=True, coordination_service_token=TOKEN)
    with TestClient(create_app(settings), client=('127.0.0.1', 50000), headers={'X-Demo-Actor': 'management'}) as c:
        posted = c.post('/rooms/management-room/messages', json={'text': 'Read the actual incident report.',
            'mention_agent_id': agent, 'client_message_id': str(uuid4())})
        assert posted.status_code == 201, posted.text
        message = posted.json()['id']
        assert any(str(i['message_id']) == message for i in c.get(BASE + '/room-mentions', headers=SERVICE).json()['items'])
        path = BASE + f'/room-mentions/{message}/{agent}'
        turn = c.post(path + '/turn', headers=SERVICE)
        assert turn.status_code == 200, turn.text
        assert {t['name'] for t in turn.json()['tools']} == {'reporting__' + name for name in reports} | {'security__camera__read'}
        run = turn.json()['run_id']
        assert c.post(path + '/turn', headers=SERVICE).json()['run_id'] == run
        b = sql(database, 'select building_id from tickets where building_id is not null limit 1')[0]['building_id']
        report = lambda name, **arguments: c.post(BASE + '/tools/call', headers=SERVICE,
            json={'run_id': run, 'tool': 'reporting.' + name, 'arguments': arguments}).json()
        period = {'scope_type': 'building', 'scope_id': str(b), 'from_date': '2020-01-01', 'to_date': '2029-01-01'}
        scopes = report('filter_report_scope')
        assert scopes['status'] == 'OK' and str(b) in {s['scope_id'] for s in scopes['data']['data']}, scopes
        good = report('get_ticket_frequency_summary', **period)
        assert good['status'] == 'OK' and good['data']['operation'] == 'get_ticket_frequency_summary', good
        counted = sql(database, "select count(*) n, count(*) filter (where request_kind='incident') incidents from tickets "
                                "where building_id=$1 and created_at>='2020-01-01' and created_at<'2029-01-01'", b)[0]
        assert (good['data']['data']['total_ticket_count'], good['data']['data']['incident_ticket_count']) == (counted['n'], counted['incidents'])
        # Which categories are repair work is the deployment's setting; without it no total is reported.
        unset = report('get_repair_bill_summary', **period)
        assert unset['status'] == 'TOOL_ERROR' and unset['data']['error'] == 'REPORT_REPAIR_CATEGORIES_REQUIRED', unset
        monkeypatch.setenv('VINHOMES_API_REPAIR_CATEGORY_CODES', 'technical')
        billed = sql(database, "select count(*) n, sum(i.grand_total) total from invoices i join tickets t on t.id=i.ticket_id "
                               "where t.building_id=$1 and i.status='issued'", b)[0]
        bills = report('get_repair_bill_summary', **period)
        assert bills['status'] == 'OK' and bills['data']['data']['items'] == [
            {'currency': 'VND', 'invoice_count': billed['n'], 'billed_amount': format(billed['total'], 'f')}], bills
        staff = sql(database, 'select id from staff_profiles limit 1')[0]['id']
        stars = report('get_employee_star_summary', **period, staff_ids=[str(staff)])
        assert stars['status'] == 'OK' and stars['data']['data']['items'][0]['staff_id'] == str(staff), stars
        outside = report('get_ticket_frequency_summary', **{**period, 'scope_id': str(uuid4())})
        assert outside['status'] == 'TOOL_ERROR' and outside['data']['error'] == 'REPORT_SCOPE_FORBIDDEN_OR_NOT_FOUND', outside
        forbidden = c.post(BASE + '/tools/call', headers=SERVICE, json={'run_id': run, 'tool': 'security.camera.read',
            'arguments': {'building_id': str(uuid4())}})
        assert forbidden.json()['status'] == 'FORBIDDEN'
        camera = c.post(BASE + '/tools/call', headers=SERVICE, json={'run_id': run, 'tool': 'security.camera.read', 'arguments': {'building_id': str(b)}})
        assert camera.json()['status'] == 'OK', camera.text
        content = {'run_id': run, 'status': 'done', 'content': 'A real agent answer, delivered once.'}
        assert c.post(path + '/outcome', headers=SERVICE, json=content).status_code == 200
        assert c.post(path + '/outcome', headers=SERVICE, json=content).json()['replayed']
        assert len(sql(database, 'select id from messages where run_id=$1', UUID(run))) == 1
        assert c.post(BASE + '/tools/call', headers=SERVICE, json={'run_id': run, 'tool': 'security.camera.read', 'arguments': {'building_id': str(b)}}).json()['status'] == 'FORBIDDEN'
        next_message = c.post('/rooms/management-room/messages', json={'text': 'Another question', 'mention_agent_id': agent,
            'client_message_id': str(uuid4())}).json()['id']
        next_path = BASE + f'/room-mentions/{next_message}/{agent}'
        active = c.post(next_path + '/turn', headers=SERVICE).json()['run_id']
        assert c.post(f'/rooms/management-room/agents/{agent}/release/revoke', json={'note': 'Revoked during the turn'}).status_code == 200
        assert c.post(BASE + '/tools/call', headers=SERVICE, json={'run_id': active, 'tool': 'security.camera.read', 'arguments': {'building_id': str(b)}}).json()['status'] == 'FORBIDDEN'
        assert c.post(next_path + '/outcome', headers=SERVICE, json={'run_id': active, 'status': 'done', 'content': 'Stale answer'}).status_code == 409


def test_the_tool_host_answer_reaches_the_agent_when_it_is_not_a_success(database, monkeypatch):
    """A tool host saying "nothing found" is an answer the agent must read; only a host that gives no answer is an outage."""
    import httpx
    from vinhomes_api import v3_tool_gateway
    register_tools(database)
    agent, _ = publish_specialist(database, 'Room SOP ' + uuid4().hex[:8], ['technical'], tools=(
        {'server_id': 'technical-tools', 'name': 'technical.get_active_outage'},))
    answers = []

    class Host:
        def __init__(self, **options): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *error): return False
        async def post(self, url, headers, json):
            assert url == 'http://tools.test/internal/technical/v1/call' and headers == {'Authorization': 'Bearer ' + 'h' * 40}
            return answers.pop(0)

    monkeypatch.setenv('VINHOMES_API_TECHNICAL_TOOLS_URL', 'http://tools.test/internal/technical/v1')
    monkeypatch.setenv('VINHOMES_API_TECHNICAL_TOOLS_TOKEN', 'h' * 40)
    monkeypatch.setattr(v3_tool_gateway.httpx, 'AsyncClient', Host)
    settings = V3Settings('127.0.0.1', 8000, database['runtime'], TENANT, None, None,
                          demo_mode=True, coordination_service_token=TOKEN)
    with TestClient(create_app(settings), client=('127.0.0.1', 50000), headers={'X-Demo-Actor': 'management'}) as c:
        message = c.post('/rooms/management-room/messages', json={'text': 'Is there an outage?', 'mention_agent_id': agent,
                                                                  'client_message_id': str(uuid4())}).json()['id']
        run = c.post(BASE + f'/room-mentions/{message}/{agent}/turn', headers=SERVICE).json()['run_id']
        building = sql(database, 'select building_id from tickets where building_id is not null limit 1')[0]['building_id']
        call = {'run_id': run, 'tool': 'technical.get_active_outage', 'arguments': {'building_id': str(building)}}
        missing = {'code': 'NOT_FOUND', 'message': 'No outage is recorded for that building.'}
        answers.append(httpx.Response(404, json={'status': 'NOT_FOUND', 'data': None, 'errors': [missing]}))
        told = c.post(BASE + '/tools/call', headers=SERVICE, json=call).json()
        assert told['status'] == 'NOT_FOUND' and told['errors'] == [missing]
        answers.append(httpx.Response(502, text='bad gateway'))
        down = c.post(BASE + '/tools/call', headers=SERVICE, json=call).json()
        assert down['status'] == 'INTERNAL_ERROR' and down['errors'][0]['retryable'] is True
    audited = sql(database, "select payload->>'status' as status from audit_events where event_type='agent.tool_called' "
                            "and target_id=$1 order by created_at", run)
    assert [a['status'] for a in audited] == ['NOT_FOUND', 'INTERNAL_ERROR']


def test_an_external_connection_is_allowed_by_the_admin_granted_to_an_agent_and_called_through_the_gateway(database, monkeypatch):
    """An administrator connects an MCP server for one group and allows a tool; management grants it to an
    agent; the call leaves through the tool host with the sealed token. The token is never returned."""
    import httpx
    from vinhomes_api import v3_connections
    seen, answers = [], []
    offered = [{'name': 'search', 'description': 'Search the handbook.', 'inputSchema': {'type': 'object', 'properties': {'building_id': {'type': 'string'}}}},
               {'name': 'wipe', 'description': 'Delete everything.', 'inputSchema': {'type': 'object'}, 'destructive': True}]

    class Host:
        def __init__(self, **options): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *error): return False
        async def post(self, url, headers, json):
            assert headers == {'Authorization': 'Bearer ' + 'h' * 40}
            path = url.removeprefix('http://tools.test/internal/technical/v1/connections')
            seen.append((path, json))
            if path == '/check':
                return httpx.Response(422, json={'error': 'An MCP server must be reached over https.'}) if json['url'].startswith('http:') else httpx.Response(200, json={'ok': True})
            if path == '/seal':
                return httpx.Response(200, json={'sealed': 'sealed:' + json['token'][::-1]})
            if path == '/tools':
                return httpx.Response(200, json={'tools': offered})
            return answers.pop(0)

    monkeypatch.setenv('VINHOMES_API_TECHNICAL_TOOLS_URL', 'http://tools.test/internal/technical/v1')
    monkeypatch.setenv('VINHOMES_API_TECHNICAL_TOOLS_TOKEN', 'h' * 40)
    monkeypatch.setattr(v3_connections.httpx, 'AsyncClient', Host)
    workspace = sql(database, "select workspace_id from channels where id='management-room'")[0]['workspace_id']
    with demo_client(database, 'management') as management:
        assert management.get('/admin/connections').status_code == 403
    with demo_client(database, 'admin') as admin:
        plain = admin.post('/admin/connections', json={'title': 'Sổ tay', 'url': 'http://handbook.example/mcp'})
        assert plain.status_code == 422 and 'https' in plain.json()['detail']
        made = admin.post('/admin/connections', json={'title': 'Sổ tay vận hành Đông', 'url': 'https://handbook.example/mcp',
                                                      'token': 'secret-token-value', 'workspace_id': str(workspace)})
        assert made.status_code == 201, made.text
        code = made.json()['id']
        assert code == 'sotayvanhanhdong'
        listing = admin.get('/admin/connections')
        assert 'secret-token-value' not in listing.text and 'sealed' not in listing.text
        row = next(i for i in listing.json()['items'] if i['id'] == code)
        assert row['has_token'] and row['tools'] == [] and str(row['workspace_id']) == str(workspace)
        checked = admin.post(f'/admin/connections/{code}/check').json()
        assert checked['ok'] and [(t['tool'], t['destructive'], t['allowed']) for t in checked['tools']] == [('search', False, False), ('wipe', True, False)]
        assert admin.put(f'/admin/connections/{code}/tools', json={'names': [code + '.wipe']}).status_code == 422
        assert admin.put(f'/admin/connections/{code}/tools', json={'names': [code + '.missing']}).status_code == 422
        assert admin.put(f'/admin/connections/{code}/tools', json={'names': [code + '.search']}).status_code == 200
    stored = sql(database, "select c.encrypted_value,c.kind::text,c.scope_kind from credentials c join mcp_servers s on s.credential_id=c.id where s.id=$1", code)[0]
    assert stored['encrypted_value'] == 'sealed:' + 'secret-token-value'[::-1] and (stored['kind'], stored['scope_kind']) == ('mcp', 'workspace')
    with demo_client(database, 'management') as management:
        catalogue = management.get('/rooms/management-room/agent-management').json()['tools']
        assert [(t['server_title'], t['external']) for t in catalogue if t['name'] == code + '.search'] == [('Sổ tay vận hành Đông', True)]
    agent, _ = publish_specialist(database, 'Room handbook ' + uuid4().hex[:8], [], tools=({'server_id': code, 'name': code + '.search'},))
    settings = V3Settings('127.0.0.1', 8000, database['runtime'], TENANT, None, None, demo_mode=True, coordination_service_token=TOKEN)
    with TestClient(create_app(settings), client=('127.0.0.1', 50000), headers={'X-Demo-Actor': 'management'}) as c:
        message = c.post('/rooms/management-room/messages', json={'text': 'What does the handbook say?', 'mention_agent_id': agent,
                                                                  'client_message_id': str(uuid4())}).json()['id']
        turn = c.post(BASE + f'/room-mentions/{message}/{agent}/turn', headers=SERVICE).json()
        assert [t['name'] for t in turn['tools']] == [code + '__search']
        # The server's own argument names are passed as they are, also one that looks like ours.
        call = {'run_id': turn['run_id'], 'tool': code + '.search', 'arguments': {'building_id': 'tower-a', 'q': 'thang máy'}}
        answers.append(httpx.Response(200, json={'text': 'Bảo trì thang máy mỗi quý.', 'isError': False, 'truncated': False}))
        good = c.post(BASE + '/tools/call', headers=SERVICE, json=call).json()
        assert good['status'] == 'OK' and good['data']['data']['text'] == 'Bảo trì thang máy mỗi quý.'
        assert seen[-1] == ('/call', {'url': 'https://handbook.example/mcp', 'sealed': stored['encrypted_value'],
                                      'tool': 'search', 'arguments': call['arguments']})
        answers.append(httpx.Response(200, json={'text': 'Query too short.', 'isError': True, 'truncated': False}))
        bad = c.post(BASE + '/tools/call', headers=SERVICE, json=call).json()
        assert bad['status'] == 'TOOL_ERROR' and bad['errors'][0]['message'] == 'Query too short.'
        answers.append(httpx.Response(502, json={'error': 'The vendor answered 500.'}))
        assert c.post(BASE + '/tools/call', headers=SERVICE, json=call).json()['status'] == 'INTERNAL_ERROR'
        # A withdrawn credential: the call is refused before anything leaves.
        calls = len(seen)
        sql(database, "update credentials set revoked_at=now() where id=(select credential_id from mcp_servers where id=$1) returning id", code)
        assert c.post(BASE + '/tools/call', headers=SERVICE, json=call).json()['status'] == 'FORBIDDEN' and len(seen) == calls
        sql(database, "update credentials set revoked_at=null where id=(select credential_id from mcp_servers where id=$1) returning id", code)
    audited = sql(database, "select payload->>'status' as status from audit_events where event_type='agent.tool_called' "
                            "and target_id=$1 order by created_at", turn['run_id'])
    assert [a['status'] for a in audited] == ['OK', 'TOOL_ERROR', 'INTERNAL_ERROR', 'FORBIDDEN']
    with demo_client(database, 'admin') as admin:
        kept = admin.put(f'/admin/connections/{code}/tools', json={'names': []})
        assert kept.status_code == 409 and kept.json()['detail']['agents'][0].startswith('Room handbook')
        assert admin.delete(f'/admin/connections/{code}').status_code == 409
        assert admin.post(f'/admin/agents/{agent}/release/revoke', json={'note': 'Ngừng dùng sổ tay'}).status_code == 200
        assert admin.delete(f'/admin/connections/{code}').status_code == 200
    assert sql(database, "select 1 from mcp_servers where id=$1", code) == []
    assert sql(database, "select revoked_at is not null as revoked from credentials where provider=$1", code)[0]['revoked']
    events = sql(database, "select event_type from audit_events where target_type='mcp_server' and target_id=$1 order by created_at", code)
    assert [e['event_type'] for e in events] == ['connection.created', 'connection.tools_allowed', 'connection.removed']
