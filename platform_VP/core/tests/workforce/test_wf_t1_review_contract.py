"""Review of slice T1, what the contract asks: a pending answer nobody can follow is not done (13.2, 14.3), work started by
the platform itself stops on a suspended or replaced route (13.9, spec 5), an event that cannot be matched is not waited
for (10.1, 13.6), a workflow with an operation not over keeps its log (12), and actions that all failed are not confirmed.
Scripted model only; a real MCP server."""
from __future__ import annotations

import json
import time

import pytest
import t1kit
from conftest import ADM, ADM_B
from enginekit import evidence_of, world
from fake_llm import Call
from mcp.server.fastmcp import Context
from partnerkit import Partner
from scripts import say
from t1kit import SERVER, SETTINGS, TOOLS, act, action, configure, event_types, ops, tool_texts, tools_of
from test_wf_t1_ledger import call, room, state, words

from awp.workforce.reconcile import reconcile
from awp.workforce.retention import DAY, purge_events

W = "/platform/v1/wf"
STOP = {"stop_tracking_only": True, "reason": "resident_requested_stop_tracking"}


@pytest.fixture
def partner():
    with Partner() as p:
        yield p


# ---- a pending answer nobody follows is not done ---------------------------------------------------------------------
def test_pending_from_an_untracked_action_is_neither_completed_nor_asked_to_be_confirmed(tmp_path, partner):
    tools = [*t1kit.STANDARD, action("partner_repair_untracked", "book_repair", tracking="none")]
    names = [x["name"] for x in tools]
    script = act("partner_repair_untracked", {"slot": "mon"}, "I asked for a plumber for Monday.")
    with world(tmp_path, script, leader_tools=names, worker_tools=names, **SETTINGS) as w:
        configure(w, partner, tools)
        start, first = w.flow.begin()
        [op] = ops(w)
        assert (op["status"], op["partner_status"], op["job"]) == ("unknown", "pending", "JOB-1")  # kept: a person follows it
        events = w.flow.history(first["conversation_id"], limit=500).json()["items"]
        assert [e["payload"]["status"] for e in events if e["event_type"] == "operation.status_changed"] == ["unknown"]
        assert (first["workflow_state"], first["next_action"]) == ("needs_attention", "resolve_attention")
        assert w.sql("select attention_reason from wf_workflows") == [("operation_unknown",)]
        told = [x for x in tool_texts() if x.startswith("UNKNOWN")]
        assert told and "not finished" in told[0] and "JOB-1" in told[0]  # the model is told what is true
        r, _ = w.flow.close(first, start)  # nobody confirms what is not over
        assert r.status_code == 409 and r.json()["error"]["code"] == "WORKFLOW_NOT_READY_TO_CLOSE"


def test_pending_from_an_untracked_action_is_still_pending_to_the_model_when_asked_again(tmp_path, partner):
    tools = [action("untracked", "book_repair", tracking="none")]
    with room(tmp_path, partner, tools=tools) as w:
        t = tools_of(w)["untracked"]
        assert words(call(w, t, slot="mon")).startswith("UNKNOWN: the partner accepted")
        again = words(call(w, t, slot="mon"))
        assert again.startswith("UNKNOWN: this same request was accepted") and "JOB-1" in again
        assert len(partner.of("book_repair")) == 1


# ---- an event that cannot be matched is not waited for ---------------------------------------------------------------
class Anon(Partner):
    def build(self):
        mcp = super().build()

        @mcp.tool()
        def book_noid(slot: str, ctx: Context) -> str:
            """Accepts the request; gives no job id."""
            self.calls.append({"tool": "book_noid", "args": {"slot": slot}, "auth": None})
            return json.dumps({"status": "pending"})
        return mcp


def test_tracking_events_needs_a_reference_to_send_so_that_an_event_can_be_matched(env):
    rid = env.route(env.client()["client_id"])["route_id"]
    base = {"name": "t", "server": "p", "mcp_tool": "book", "kind": "action", "tracking": "events"}
    env.http.put(f"{W}/routes/{rid}/mcp", headers=ADM, json={"servers": [{"name": "p", "url": "http://93.184.216.34/mcp"}]})
    r = env.http.put(f"{W}/routes/{rid}/tools", headers=ADM, json={"tools": [base]})
    assert r.status_code == 422 and "client_reference_arg or idempotency_arg" in r.text
    for ok in ({"client_reference_arg": "ref"}, {"idempotency_arg": "key"}):
        assert env.http.put(f"{W}/routes/{rid}/tools", headers=ADM, json={"tools": [{**base, **ok}]}).status_code == 200


def test_pending_with_no_job_id_and_no_reference_sent_is_unknown_not_a_wait(tmp_path):
    tool = {"name": "partner_noid", "server": SERVER, "mcp_tool": "book_noid", "kind": "action", "tracking": "none"}
    with Anon() as p, world(tmp_path, t1kit.quiet_leader, leader_tools=["partner_noid"], worker_tools=["partner_noid"],
                            **SETTINGS) as w:
        configure(w, p, [tool])
        w.flow.begin()
        w.sql("update wf_tools set tracking='events'")  # a row written before the admin check existed
        out = words(call(w, tools_of(w)["partner_noid"], slot="mon"))
        assert out.startswith("UNKNOWN: the partner accepted")
        [op] = ops(w)
        assert op["status"] == "unknown" and op["job"] is None
        assert json.loads(w.sql("select result from wf_operations")[0][0])["error"] == "uncorrelatable"


# ---- a suspended or replaced route does nothing by itself -------------------------------------------------------------
def moved(w, how: str) -> None:
    rid = w.flow.route["route_id"]
    r = w.env.http.post(f"{W}/routes/{rid}/{how}", headers=ADM, json={})
    assert r.status_code in (200, 201), r.text


def waiting(tmp_path, partner, script):
    return world(tmp_path, script, **TOOLS, **SETTINGS)


def poll_then_hotel(c: Call):
    turn = c.after_user()
    if "<provider-event" in c.last_user:  # news after the route was suspended: do one more thing at the partner
        if turn.called("partner_hotel") == 0:
            return [("partner_hotel", {"hotel": "Sunrise", "nights": 1})]
        return say("Also booked a hotel.", "none", []) if turn.called("CaseSay") == 0 else "Said."
    if turn.called("partner_repair_q") == 0:
        return [("partner_repair_q", {"slot": "mon"})]
    return say("Pending.", "none", []) if turn.called("CaseSay") == 0 else "Said."


def test_the_sweep_asks_nothing_and_wakes_nobody_for_a_suspended_route(tmp_path, partner):
    with waiting(tmp_path, partner, poll_then_hotel) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        assert first["workflow_state"] == "waiting_external_event"
        moved(w, "suspend")
        [op] = ops(w)
        partner.status_of[op["reference"]] = "completed"
        asked = len(partner.of("repair_status"))
        assert w.run(lambda: reconcile(w.engine, poll=0.0)) == 0  # not a row of a route that may work
        w.quiet()
        assert len(partner.of("repair_status")) == asked and partner.of("book_hotel") == []
        assert w.sql("select count(*) from wf_jobs where kind='provider_wake'") == [(0,)]


def test_a_job_claimed_on_a_suspended_route_blocks_the_workflow_and_calls_nothing(tmp_path, partner):
    with waiting(tmp_path, partner, poll_then_hotel) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        wid = first["workflow_id"]
        w.sql("insert into wf_jobs (id, workflow_id, kind, payload, status, attempts, created_at) values "
              "('job_late', ?, 'provider_wake', ?, 'queued', 0, ?)",
              (wid, json.dumps({"operation_id": "op", "status": "completed", "text": "done"}), time.time()))
        moved(w, "suspend")  # after the news was queued, before the engine took it

        async def kick():
            w.engine.notify(wid, "job_late")
        w.run(kick)
        w.wait_state(wid, "blocked_authorization")
        w.quiet()
        assert w.sql("select status from wf_jobs where id='job_late'") == [("failed",)]
        assert partner.of("book_hotel") == []
        assert "workflow.status_changed" in event_types(w, first["conversation_id"])


@pytest.mark.parametrize("how,blocked", [("suspend", "blocked_authorization"), ("replace", "blocked_route_changed")])
def test_an_action_on_a_route_that_moved_is_refused_and_blocks_the_workflow(tmp_path, partner, how, blocked):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_hotel"]
        moved(w, how)
        out = words(call(w, t, hotel="Sunrise", nights=2))
        assert out.startswith("The workflow is closed or blocked. Nothing was sent")
        assert partner.of("book_hotel") == [] and ops(w) == []
        assert state(w)[0] == blocked


# ---- a closed workflow with an operation that is not over keeps its log -----------------------------------------------
@pytest.mark.parametrize("kind", ["unknown", "pending"])
def test_events_of_a_closed_workflow_with_an_unfinished_operation_are_not_purged(tmp_path, partner, kind):
    tool, args = ("partner_nostatus", {"thing": "x"}) if kind == "unknown" else ("partner_repair", {"slot": "mon"})
    with world(tmp_path, act(tool, args, "Noted.", "none", cite=False), **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        assert ops(w)[0]["status"] == kind
        r, _ = w.flow.close(first, start, **STOP)
        assert r.status_code == 200
        long_ago = time.time() - 400 * DAY
        w.sql("update wf_workflows set closed_at=?", (long_ago,))
        w.sql("update wf_events set recorded_at=?, occurred_at=?", (long_ago, long_ago))
        before = w.sql("select count(*) from wf_events")[0][0]
        assert w.run(lambda: purge_events(w.rt.db, 90)) == {"conversations": 0, "events": 0}
        assert w.sql("select count(*) from wf_events")[0][0] == before
        w.sql("update wf_operations set status='completed'")  # once it is over, the log goes as usual
        assert w.run(lambda: purge_events(w.rt.db, 90))["conversations"] == 1


# ---- actions that all failed are not confirmed ------------------------------------------------------------------------
def test_a_resolved_answer_after_every_action_failed_needs_a_person_not_a_confirmation(tmp_path, partner):
    def script(c):
        turn = c.after_user()
        if turn.called("partner_reject") == 0:
            return [("partner_reject", {})]
        if turn.called("partner_lookup") == 0:
            return [("partner_lookup", {"ticket_id": "T-1001"})]
        ev = evidence_of(" ".join(turn.results("partner_lookup")))
        if turn.called("CaseFinalize") == 0:
            return [("CaseFinalize", {"answer": "Your request has been dealt with.", "outcome": "resolved", "cites": ev[:1]})]
        return "Done."

    with world(tmp_path, script, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        _, first = w.flow.begin()
        [op] = ops(w)
        assert op["status"] == "failed"
        assert (first["workflow_state"], first["next_action"]) == ("needs_attention", "resolve_attention")
        assert w.sql("select attention_reason from wf_workflows") == [("needs_human",)]


# ---- the admin check of a server asks whose route it is first, and tells nothing about the network ---------------------
def test_a_server_url_of_a_route_that_is_not_the_admins_is_not_looked_at(env):
    rid = env.route(env.client()["client_id"])["route_id"]
    body = {"servers": [{"name": "p", "url": "http://10.1.2.3/mcp"}]}
    assert env.http.put(f"{W}/routes/{rid}/mcp", headers=ADM_B, json=body).status_code == 404  # not 422
    assert env.http.put(f"{W}/routes/{rid}/mcp", headers=ADM, json=body).status_code == 422
