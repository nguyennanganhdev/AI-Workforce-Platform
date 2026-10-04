"""The internal API the Supervisor runtime uses, against migrated, seeded PostgreSQL."""

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
            "mcp_tools": [{"server_id": "technical-tools", "name": tool} for tool in tools]})
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
            "action_id": "a", "channel": "draft", "operation": "plan"}).status_code == 409
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
                                            tools=("technical.get_active_outage", "apartment_entry.request"))
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
            "action_id": "a", "channel": "backend", "operation": "approval.requested"}).status_code == 409

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
