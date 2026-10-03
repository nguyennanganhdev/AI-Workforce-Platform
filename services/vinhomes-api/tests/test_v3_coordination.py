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


def publish_specialist(database, name, categories):
    """Management drafts an agent in its room, records an evaluation, and an admin approves it."""
    room = f"/rooms/management-room/agents"
    with demo_client(database, "management") as management:
        agent = management.post(room, json={"name": name, "instructions": "Phân tích sự cố.",
                                            "idempotency_key": name}).json()["id"]
        configured = management.put(f"{room}/{agent}/configuration", json={
            "instructions": "Phân tích sự cố kỹ thuật và đề xuất cách xử lý.", "description": name,
            "service_categories": categories})
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
            "action_id": "a", "channel": "room", "operation": "open_room"}).status_code == 409
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
    with demo_client(database, "management") as management:
        assert management.put("/rooms/management-room/agents/none/configuration", json={
            "instructions": "x", "description": "x", "service_categories": ["plumbing"]}).status_code == 404
    technical, version = publish_specialist(database, f"Kỹ thuật {uuid4().hex[:6]}", ["technical"])
    publish_specialist(database, f"An ninh {uuid4().hex[:6]}", ["security"])
    with app(database) as c:
        team = verified_team(c, database, f"Rò nước {uuid4().hex[:6]}")
        seen = c.get(BASE + f"/teams/{team}/view", headers=SERVICE).json()
        assert seen["category"] == "technical"
        offered = [s for s in seen["specialists"] if s["agent_id"] == technical]
        assert offered == [{"agent_version_id": version, "agent_id": technical, "name": offered[0]["name"],
                            "description": offered[0]["name"], "service_categories": ["technical"], "tools": []}]
        # Another category's agent is published in the same room and is not offered for this ticket.
        assert all(s["service_categories"] == ["technical"] for s in seen["specialists"])

        with demo_client(database, "management") as management:
            assert management.post(f"/admin/agents/{technical}/release/revoke", json={"note": "x"}).status_code == 403
        with demo_client(database, "admin") as admin:
            revoked = admin.post(f"/admin/agents/{technical}/release/revoke", json={"note": "Trả lời sai quy trình"})
            assert revoked.status_code == 200 and revoked.json()["versionId"] == version
            assert admin.post(f"/admin/agents/{technical}/release/revoke", json={"note": "x"}).status_code == 404
        after = c.get(BASE + f"/teams/{team}/view", headers=SERVICE).json()["specialists"]
        assert not [s for s in after if s["agent_id"] == technical]
