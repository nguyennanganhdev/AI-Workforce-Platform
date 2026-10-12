"""M4 and M5 additions: a leader's team and a route's leader are checked when they are written, the leader's choice of a
specialist is kept in the case file, an action asks the resident's consent unless a recorded waiver says why not, and a
pending approval that no agent is parked on is cancelled when the platform starts. Scripted model where one runs."""
from __future__ import annotations

import time

import consentkit as ck
import pytest
from conftest import ADM, ADM_B, publish as kit_publish
from enginekit import world
from fake_llm import CALLS
from flowkit import Flow
from partnerkit import Partner
from t1kit import SETTINGS, act, configure, lookup

W = "/platform/v1/wf"
P = "/platform/v1/profiles"
LEADER = {"key": "desk", "name": "Desk", "role": "leader", "mission": "leads a team."}
PLUMBER = {"key": "plumber", "name": "Plumber", "mission": "fixes pipes."}


def draft(env, body, headers=ADM):
    r = env.post(P, body, headers)
    assert r.status_code == 201, r.text
    return r.json()


def publish(env, key, version=1, headers=ADM):
    return kit_publish(env, key, version, headers, expect=None)  # these tests are about the team, not the evaluation gate


# ---- M4: the team of a leader ---------------------------------------------------------------------------------------------
def test_a_leader_is_published_only_when_its_team_are_specialists_of_the_tenant(env):
    draft(env, {**LEADER, "team": ["plumber", "ghost"]})
    r = publish(env, "desk")
    assert r.status_code == 422 and "ghost" in r.text and "plumber" in r.text  # neither exists yet
    draft(env, PLUMBER)
    r = publish(env, "desk")
    assert r.status_code == 422 and "ghost" in r.text and "'plumber'" not in r.text
    assert env.http.get(f"{P}?status=published", headers=ADM).json() == {"profiles": []}  # nothing was published on the way
    draft(env, {"key": "ghost", "name": "Second desk", "role": "leader", "mission": "also leads."})
    r = publish(env, "desk")
    assert r.status_code == 422 and "ghost" in r.text  # a leader is not a specialist


def test_a_team_member_that_is_not_published_yet_is_a_warning_not_a_refusal(env):
    draft(env, {**LEADER, "team": ["plumber"]})
    draft(env, PLUMBER)
    r = publish(env, "desk")
    assert r.status_code == 200 and r.json()["status"] == "published"
    [warning] = r.json()["warnings"]
    assert "plumber" in warning and "published" in warning
    assert publish(env, "plumber").json()["warnings"] == []  # a specialist has no team to check
    draft(env, {**LEADER, "team": ["plumber"], "mission": "leads a team, second version."})
    assert publish(env, "desk", 2).json()["warnings"] == []


def test_another_tenants_specialist_is_not_a_team_member(env):
    draft(env, PLUMBER, ADM_B)
    assert publish(env, "plumber", headers=ADM_B).status_code == 200
    draft(env, {**LEADER, "team": ["plumber"]})  # tenant ta names a key that only tenant tb has
    r = publish(env, "desk")
    assert r.status_code == 422 and "plumber" in r.text


# ---- M4: the leader of a route ------------------------------------------------------------------------------------------
def test_a_route_needs_a_leader_profile_that_exists_and_is_a_leader(env):
    c = env.client()
    body = {"external_management_ref": "R", "manager_id": env.default_manager(c["client_id"])}
    url = f"{W}/clients/{c['client_id']}/routes"
    draft(env, PLUMBER)
    draft(env, {**LEADER, "key": "their_desk"}, ADM_B)
    for bad in ("nobody", "plumber", "their_desk"):  # missing, a specialist, another tenant's leader
        r = env.post(url, {**body, "leader_profile": bad})
        assert r.status_code == 422 and "leader" in r.text, (bad, r.text)
    assert env.sql("select count(*) from wf_routes") == [(0,)]
    draft(env, LEADER)  # a draft is enough to make the route; running it needs the published profile
    made = env.post(url, {**body, "leader_profile": "desk"})
    assert made.status_code == 201, made.text
    rid = made.json()["route_id"]
    for bad in ("nobody", "plumber"):
        assert env.post(f"{W}/routes/{rid}/replace", {"leader_profile": bad}).status_code == 422
    assert env.sql("select status from wf_routes") == [("pending",)]  # the refused replacement replaced nothing
    assert env.post(f"{W}/routes/{rid}/replace", {"leader_profile": "desk"}).status_code == 201


# ---- M5: an action asks unless a waiver is recorded ----------------------------------------------------------------------
SERVER = {"servers": [{"name": "p", "url": "http://93.184.216.34/mcp"}]}
BOOK = {"name": "book", "server": "p", "mcp_tool": "book_repair", "kind": "action", "tracking": "none"}


def put_tools(env, rid, *tools):
    return env.http.put(f"{W}/routes/{rid}/tools", headers=ADM, json={"tools": list(tools)})


@pytest.fixture
def route(env):
    rid = env.route(env.client()["client_id"])["route_id"]
    assert env.http.put(f"{W}/routes/{rid}/mcp", headers=ADM, json=SERVER).status_code == 200
    return env, rid


def test_an_action_requires_consent_unless_told_otherwise_with_a_reason(route):
    env, rid = route
    r = put_tools(env, rid, BOOK)
    assert r.status_code == 200 and r.json()["tools"][0]["requires_consent"] is True  # nobody said: it asks
    assert r.json()["tools"][0]["consent_waiver"] is None
    r = put_tools(env, rid, {**BOOK, "requires_consent": False})
    assert r.status_code == 422 and "consent_waiver" in r.text  # off needs a reason
    assert put_tools(env, rid, {**BOOK, "requires_consent": False, "consent_waiver": ""}).status_code == 422
    assert put_tools(env, rid, {**BOOK, "requires_consent": False, "consent_waiver": "x" * 301}).status_code == 422
    assert put_tools(env, rid, {**BOOK, "requires_consent": True, "consent_waiver": "but why"}).status_code == 422
    why = "Reading the meter changes nothing the resident pays for."
    for body in ({**BOOK, "requires_consent": False, "consent_waiver": why}, {**BOOK, "consent_waiver": why}):
        r = put_tools(env, rid, body)
        assert r.status_code == 200, r.text
        assert (r.json()["tools"][0]["requires_consent"], r.json()["tools"][0]["consent_waiver"]) == (False, why)
    assert env.sql("select requires_consent, consent_waiver from wf_tools") == [(False, why)]  # the reason is on record
    look = {"name": "look", "server": "p", "mcp_tool": "lookup_ticket", "kind": "lookup", "read_only": True}
    assert put_tools(env, rid, {**look, "requires_consent": True}).status_code == 422  # a look-up asks nobody
    r = put_tools(env, rid, {**look, "consent_waiver": why})  # on a look-up: why a person calls the tool read-only
    assert r.status_code == 200 and (r.json()["tools"][0]["requires_consent"], r.json()["tools"][0]["consent_waiver"]) == (False, why)
    assert put_tools(env, rid, look).json()["tools"][0]["requires_consent"] is False


def test_patch_cannot_turn_consent_off_without_the_waiver_and_asking_again_ends_it(route):
    env, rid = route
    put_tools(env, rid, BOOK)
    patch = lambda **body: env.http.patch(f"{W}/routes/{rid}/tools/book", headers=ADM, json=body)  # noqa: E731
    assert patch(requires_consent=False).status_code == 422
    assert env.sql("select requires_consent from wf_tools") == [(True,)]
    r = patch(requires_consent=False, consent_waiver="agreed with the partner in writing")
    assert r.status_code == 200 and r.json()["consent_waiver"] == "agreed with the partner in writing"
    assert patch(call_timeout=5).json()["consent_waiver"] == "agreed with the partner in writing"  # another change keeps it
    r = patch(requires_consent=True)
    assert r.status_code == 200 and (r.json()["requires_consent"], r.json()["consent_waiver"]) == (True, None)
    assert env.sql("select requires_consent, consent_waiver from wf_tools") == [(True, None)]


def test_an_action_declared_without_a_word_about_consent_asks_the_resident_before_it_runs(tmp_path):
    plain = {"name": "partner_book", "server": "p", "mcp_tool": "book_repair", "kind": "action", "tracking": "events",
             "client_reference_arg": "client_reference"}  # not through t1kit.action: no waiver
    script = act("partner_book", {"slot": "mon"}, "It is booked.")
    with Partner() as partner, world(tmp_path, script, leader_tools=["partner_book"], **SETTINGS) as w:
        configure(w, partner, tools=[lookup(), plain])
        _, first = w.flow.begin()
        assert (first["workflow_state"], first["next_action"]) == ("awaiting_approval", "submit_approval")
        [appr] = w.flow.approvals(first["conversation_id"])
        assert (appr["tool_name"], appr["status"]) == ("partner_book", "pending")
        assert partner.of("book_repair") == [] and w.sql("select count(*) from wf_operations") == [(0,)]


# ---- M4: why a specialist was chosen ------------------------------------------------------------------------------------
def test_every_specialist_the_leader_creates_leaves_an_invite_in_the_case_file(tmp_path):
    with world(tmp_path, None, wf_wait_seconds=60.0) as w:  # the team scenario of fake_llm: the leader brings in tech and fin
        _, first = w.flow.begin()
        assert first["request_status"] == "completed", first
        case_id = w.sql("select case_id from wf_workflows where id=?", (first["workflow_id"],))[0][0]
        items = w.env.http.get(f"/platform/v1/cases/{case_id}/items", headers=ADM).json()["items"]
        invites = [i for i in items if i["kind"] == "invite"]
        assert [(i["ref"], i["author"], i["data"]["type"], i["data"]["name"]) for i in invites] == [
            ("I1", "case-leader", "tech", "tech"), ("I2", "case-leader", "fin", "fin")]
        assert invites[0]["data"]["task"] == "Look up ticket T-1001 and record what you find."
        assert invites[1]["data"]["task"] == "Find the repair cost and record it."
        assert all(i["data"]["candidates"] == ["tech", "fin"] for i in invites)  # what it could have chosen: its own team
        # an audit line, not room talk: no specialist was shown it
        shown = " ".join(str(c.get("shape")) for c in CALLS if 'key="tech"' in c["sys"] or 'key="fin"' in c["sys"])
        assert "Look up ticket T-1001 and record what you find." in shown  # (the task itself reaches the specialist)
        assert "I1 case-leader" not in shown and "I2 case-leader" not in shown


def test_a_specialist_the_leader_may_not_create_leaves_no_invite(tmp_path):
    def script(c):
        if c.called("TeamCreate") == 0:
            return [("TeamCreate", {"name": "t", "description": "d"})]
        if c.called("AgentCreate") == 0:
            return [("AgentCreate", {"name": "x", "description": "d", "subagent_type": "outsider", "prompt": "Do it."})]
        if c.after_user().called("CaseSay") == 0:
            return [("CaseSay", {"text": "I could not bring anyone in.", "expects": "reply", "cites": []})]
        return "Said."

    with world(tmp_path, script) as w:
        _, first = w.flow.begin()
        case_id = w.sql("select case_id from wf_workflows where id=?", (first["workflow_id"],))[0][0]
        assert w.sql("select count(*) from awp_case_items where case_id=? and kind='invite'", (case_id,)) == [(0,)]
        assert w.sql("select count(*) from awp_case_sessions where case_id=? and role='worker'", (case_id,)) == [(0,)]


# ---- M5: approvals at startup ----------------------------------------------------------------------------------------------
TOOLS = dict(tools=[ck.factory], leader_tools=["hotel_search", "book_hotel"])


@pytest.fixture(autouse=True)
def _clean():
    ck.BOOKED.clear()
    yield
    ck.BOOKED.clear()


def text_of(s: str) -> dict:
    return {"type": "text", "text": s}


def again(w2, old: Flow) -> Flow:
    """The first app's partner (client, key, route) talking to the second app on the same databases."""
    return Flow(w2.env, old.client, old.key, old.route, w2.engine, old._n)  # the same counter: no request id twice


def test_a_pending_approval_whose_agent_is_not_parked_is_cancelled_at_startup_and_the_leader_tells_the_resident(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        ck.declare(w)
        start, first = w.flow.begin(message=text_of(ck.START))
        wid, conv, old = first["workflow_id"], first["conversation_id"], w.flow
        assert first["workflow_state"] == "awaiting_user"
        w.quiet()
        # What a crash between writing the approval and saving the parked run leaves: the row says pending, the workflow
        # waits for the resident's consent, and the leader's session is idle (it asks for nothing).
        [(session, agent)] = w.sql("select leader_session_id, leader_agent_id from awp_cases where id=(select case_id from "
                                   "wf_workflows where id=?)", (wid,))
        w.sql("insert into wf_approvals (id, workflow_id, conversation_id, client_id, external_user_id, session_id, agent_id, "
              "tool_call_id, tool_name, arguments, arguments_hash, summary, status, workflow_revision, expires_at, reply_id, "
              "created_at) values ('appr_lost', ?, ?, ?, 'resident-123', ?, ?, 'call_lost', 'book_hotel', '{}', 'sha256:x', "
              "'{\"text\": \"Book Sunrise for 2 nights\"}', 'pending', ?, ?, 'reply_lost', ?)",
              (wid, conv, old.client["client_id"], session, agent, first["workflow_revision"] + 1, time.time() + 3600, time.time()))
        w.sql("update wf_workflows set state='awaiting_approval', revision=revision+1 where id=?", (wid,))
    CALLS.clear()
    with world(tmp_path, ck.trip, publish=False, **TOOLS) as w2:
        f = again(w2, old)
        w2.wait(lambda: w2.sql("select status from wf_approvals where id='appr_lost'") == [("cancelled",)], what="the cancel")
        w2.wait_state(wid, "awaiting_user")
        w2.quiet()
        assert w2.messages(wid)[-1][:2] == ("assistant", ck.EXPIRED)  # the leader told the resident
        told = [text for c in w2.model_calls() for role, text, _ in c.get("shape", []) if role == "user"]
        assert any("<platform-notice>" in t and "platform restarted" in t and "Book Sunrise for 2 nights" in t for t in told)
        events = [(e["event_type"], e["payload"].get("status")) for e in f.history(conv, limit=500).json()["items"]]
        assert ("approval.resolved", "cancelled") in events
        assert f.approvals(conv) == [] and ck.BOOKED == []
        late = f.decide("appr_lost", f.decide_body(start, first, {"expected_revision": w2.state(wid)[1], "arguments_hash": "sha256:x"}))
        assert late.status_code == 409 and late.json()["error"]["code"] == "APPROVAL_NOT_PENDING"
        # and the workflow goes on: the resident can still choose, and is asked properly this time
        r = f.reply(start, first, message=text_of(ck.CHOOSE))[0]
        assert r.status_code == 200 and r.json()["workflow_state"] == "awaiting_approval", r.text
        [real] = f.approvals(conv)
        assert real["approval_id"] != "appr_lost" and real["status"] == "pending"


def test_an_approval_whose_agent_is_parked_survives_the_restart_and_can_still_be_answered(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        ck.declare(w)
        start, first = w.flow.begin(message=text_of(ck.START))
        r = w.flow.reply(start, first, message=text_of(ck.CHOOSE))[0]
        assert r.status_code == 200 and r.json()["workflow_state"] == "awaiting_approval", r.text
        wid, conv, old = first["workflow_id"], first["conversation_id"], w.flow
        [appr] = w.flow.approvals(conv)
        w.quiet()
    with world(tmp_path, ck.trip, publish=False, **TOOLS) as w2:
        f = again(w2, old)
        w2.quiet()
        assert w2.sql("select status, resumed_at from wf_approvals") == [("pending", None)]  # left alone
        assert w2.state(wid)[0] == "awaiting_approval" and f.approvals(conv)[0]["approval_id"] == appr["approval_id"]
        assert w2.sql("select count(*) from wf_jobs where kind='approval_resume'") == [(0,)]
        done = f.decide(appr["approval_id"], f.decide_body(start, first, f.approvals(conv)[0]))
        assert done.status_code == 202, done.text
        w2.wait(lambda: ck.BOOKED == [ck.BOOK], what="the booking to run after the restart")
        w2.wait_state(wid, "awaiting_confirmation")
