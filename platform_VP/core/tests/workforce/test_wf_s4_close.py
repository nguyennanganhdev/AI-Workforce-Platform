"""The resident's confirmation is the only end, and what closes, expires or races an approval (slice S4)."""
from __future__ import annotations

import threading
import time

import consentkit as ck
import pytest
from enginekit import world
from fake_llm import CALLS, MODE
from test_wf_errors import assert_envelope
from test_wf_s4_flow import TOOLS, _clean, text_of, trip  # noqa: F401 - _clean is an autouse fixture
from test_wf_s4_gate import approval_rows, session_status


# ---- the resident's confirmation is the only end ----------------------------------------------------------------------
@pytest.mark.parametrize("kind", ["finalize", "closed"])
def test_nothing_the_leader_says_closes_a_workflow_after_side_effects(tmp_path, kind):
    (tmp_path / kind).mkdir()
    with world(tmp_path / kind, ck.after_booking(kind), **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        wid = first["workflow_id"]
        [appr] = f.approvals(first["conversation_id"])
        assert f.decide(appr["approval_id"], f.decide_body(start, first, appr)).status_code == 202
        want = "awaiting_confirmation"  # a booking that happened is the resident's to confirm, however the leader words it
        w.wait_state(wid, want)
        w.quiet()
        assert ck.BOOKED == [ck.BOOK]
        assert w.state(wid)[0] == want != "closed"
        assert w.sql("select status from awp_cases where id=(select case_id from wf_workflows)") == [("open",)]
        assert w.sql("select count(*) from wf_events where event_type='workflow.closed'") == [(0,)]
        said = [m[1] for m in w.messages(wid) if m[0] == "assistant"]
        assert any("BK-77" in m for m in said)
        assert not any("closed" in m for m in said)  # the resident is never told what is not true
        snap = f.snapshot(first["conversation_id"]).json()["workflows"][0]
        assert snap["next_action"] != "none"
        # the partner's close, and only that, ends it
        closed = f.close({"workflow_id": wid, "workflow_revision": snap["revision"]}, start)[0]
        assert closed.status_code == 200 and closed.json()["state"] == "closed"


def test_a_resident_who_says_it_is_not_fixed_reopens_the_work_and_the_close_obeys_the_revision(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        wid = first["workflow_id"]
        [appr] = f.approvals(first["conversation_id"])
        f.decide(appr["approval_id"], f.decide_body(start, first, appr))
        w.wait_state(wid, "awaiting_confirmation")
        w.quiet()
        asked = w.state(wid)
        # "it is not fixed": the word goes to the leader, the workflow is active again, then it rests where the leader leaves it
        r = f.reply(start, first, message=text_of("It is not right, the room is wrong."))[0]
        assert r.status_code == 200 and r.json()["workflow_revision"] > asked[1]
        types_ = [e["event_type"] for e in f.history(first["conversation_id"], limit=500).json()["items"]]
        assert "workflow.awaiting_user" in types_[-3:] or r.json()["workflow_state"] == "awaiting_user"
        assert any("room is wrong" in str(c["shape"]) for c in CALLS)  # the leader read it
        # a close sent with the revision of "please confirm" is refused: the resident has said something since
        stale = f.close({"workflow_id": wid, "workflow_revision": asked[1]}, start)[0]
        assert_envelope(stale, 409, "REVISION_CONFLICT")
        assert w.state(wid)[0] != "closed"
        fresh = f.close({"workflow_id": wid, "workflow_revision": w.state(wid)[1]}, start)[0]
        assert fresh.status_code == 200


# ---- close, expiry and their races -----------------------------------------------------------------------------------------
def test_closing_a_workflow_cancels_its_approval_and_leaves_no_session_parked(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        wid, conv = first["workflow_id"], first["conversation_id"]
        [appr] = f.approvals(conv)
        assert session_status(w, wid) == "awaiting_permission"
        c = f.close({"workflow_id": wid, "workflow_revision": appr["expected_revision"]}, start)[0]
        assert c.status_code == 200 and c.json()["state"] == "closed"
        assert approval_rows(w)[0][0] == "cancelled" and f.approvals(conv) == []
        resolved = [e["payload"] for e in f.history(conv, limit=500).json()["items"] if e["event_type"] == "approval.resolved"]
        assert resolved == [{"approval_id": appr["approval_id"], "status": "cancelled"}]
        w.wait(lambda: session_status(w, wid) == "idle", what="the parked session to be closed")
        w.wait(lambda: approval_rows(w)[0][3], what="the agent to take the interrupt")
        assert ck.BOOKED == []
        # a decision that comes too late finds a closed workflow
        err = assert_envelope(f.decide(appr["approval_id"], f.decide_body(start, first, appr)), 409, "WORKFLOW_CLOSED")
        assert w.sql("select count(*) from wf_jobs where kind='approval_resume'") == [(0,)]


def test_decision_and_close_at_the_same_moment_one_wins_and_nothing_is_left_parked(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        f = w.flow
        ck.declare(w)
        wins = []
        for _ in range(3):
            start, first = f.begin(message=text_of(ck.START))
            r = f.reply(start, first, message=text_of(ck.CHOOSE))[0].json()
            [appr] = f.approvals(first["conversation_id"])
            gate, out = threading.Barrier(2), {}

            def decide():
                gate.wait()
                out["d"] = f.decide(appr["approval_id"], f.decide_body(start, first, appr))

            def close():
                gate.wait()
                out["c"] = f.close({"workflow_id": first["workflow_id"], "workflow_revision": appr["expected_revision"]}, start)[0]
            ts = [threading.Thread(target=decide), threading.Thread(target=close)]
            [x.start() for x in ts]
            [x.join(30) for x in ts]
            pair = (out["d"].status_code, out["c"].status_code)
            assert pair in ((202, 409), (409, 200)), (pair, out["d"].text, out["c"].text)
            wins.append(pair[0] == 202)
            w.quiet()
            if pair[0] == 202:  # the decision won: the booking happens, the close saw a revision that moved
                assert out["c"].json()["error"]["code"] == "REVISION_CONFLICT"
                w.wait_state(first["workflow_id"], "awaiting_confirmation")
            else:  # the close won: no booking, no parked agent
                assert out["d"].json()["error"]["code"] == "WORKFLOW_CLOSED"
                w.wait(lambda: session_status(w, first["workflow_id"]) == "idle", what="the session to be closed")
        w.quiet()
        assert len(ck.BOOKED) == sum(wins)
        assert all(s != "pending" for (s, *_rest) in approval_rows(w))


def test_an_approval_that_runs_out_is_expired_the_agent_is_interrupted_and_the_leader_tells_the_resident(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        wid, conv = first["workflow_id"], first["conversation_id"]
        [appr] = f.approvals(conv)
        w.sql("update wf_approvals set expires_at=?", (time.time() - 5,))
        # late is late: the decision is refused and the approval stays as it was until the sweep expires it
        assert_envelope(f.decide(appr["approval_id"], f.decide_body(start, first, appr)), 409, "APPROVAL_EXPIRED")
        seen = len(CALLS)
        w.wait_state(wid, "awaiting_user")  # the sweep: expired, interrupted, told
        w.quiet()
        assert approval_rows(w) == [("expired", "book_hotel", False, True)] and ck.BOOKED == []
        resolved = [e["payload"] for e in f.history(conv, limit=500).json()["items"] if e["event_type"] == "approval.resolved"]
        assert resolved == [{"approval_id": appr["approval_id"], "status": "expired"}]
        assert [m[1] for m in w.messages(wid) if m[0] == "assistant"][-1] == ck.EXPIRED
        # the interrupt did not call the model: every model call since was the leader reading the notice
        assert CALLS[seen:] and all("<platform-notice" in c["last_user"] for c in CALLS[seen:])
        turns = w.sql("select status, msg_id from wf_turns where workflow_id=? order by started_at", (wid,))
        assert ("interrupted", f"resume_{appr['approval_id']}") in turns
        assert session_status(w, wid) == "idle"
        assert_envelope(f.decide(appr["approval_id"], f.decide_body(start, first, appr, expected_revision=w.state(wid)[1])),
                        409, "APPROVAL_NOT_PENDING")
        # and the resident can go on: the session takes a message again
        r = f.reply(start, first, message=text_of(ck.CHOOSE))[0]
        assert r.status_code == 200 and r.json()["workflow_state"] == "awaiting_approval"  # a new approval, a new call


def test_a_decision_that_comes_first_beats_the_sweep_and_the_sweep_first_beats_the_decision(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        f = w.flow
        a = trip(w)
        b = trip(w)
        [appr_a] = f.approvals(a[1]["conversation_id"])
        [appr_b] = f.approvals(b[1]["conversation_id"])
        # A: decided, then the clock runs out: nothing to expire
        assert f.decide(appr_a["approval_id"], f.decide_body(a[0], a[1], appr_a)).status_code == 202
        w.sql("update wf_approvals set expires_at=? where id=?", (time.time() - 5, appr_a["approval_id"]))
        assert w.run(lambda: w.engine.sweep()) is None
        w.wait_state(a[1]["workflow_id"], "awaiting_confirmation")
        assert w.sql("select status from wf_approvals where id=?", (appr_a["approval_id"],)) == [("approved",)]
        # B: the clock runs out, the sweep wins, the decision finds it no longer pending
        w.sql("update wf_approvals set expires_at=? where id=?", (time.time() - 5, appr_b["approval_id"]))
        out = {}
        gate = threading.Barrier(2)

        def decide():
            gate.wait()
            out["d"] = f.decide(appr_b["approval_id"], f.decide_body(b[0], b[1], appr_b))

        def sweep():
            gate.wait()
            w.run(lambda: w.engine.sweep())
        ts = [threading.Thread(target=decide), threading.Thread(target=sweep)]
        [x.start() for x in ts]
        [x.join(30) for x in ts]
        assert out["d"].status_code == 409 and out["d"].json()["error"]["code"] in ("APPROVAL_EXPIRED", "APPROVAL_NOT_PENDING")
        w.wait_state(b[1]["workflow_id"], "awaiting_user")
        assert w.sql("select status from wf_approvals where id=?", (appr_b["approval_id"],)) == [("expired",)]
        assert ck.BOOKED == [ck.BOOK]  # only A's


# ---- the tool gate for a case with no workflow and for tools that need no consent ------------------------------------------------------------
def test_the_tool_gate_is_unchanged_for_tools_that_need_no_consent(tmp_path):
    from agentscope.permission import PermissionBehavior

    from awp.middleware.room import ToolGateMiddleware
    from awp.runtime import Binding

    class Call:  # the part of a tool call the gate reads
        def __init__(self, name, state="pending"):
            self.name, self.state, self.id = name, state, "c1"

    async def nxt(**kw):
        return "next"

    with world(tmp_path, ck.trip, **TOOLS) as w:
        ck.declare(w)
        start, first = w.flow.begin(message=text_of(ck.START))
        case_id = w.sql("select case_id from wf_workflows")[0][0]
        stray = w.run(lambda: w.rt.cases.create_case(tenant="ta", domain="test", external_ref="OLD-1", user_id="awp:ta", meta={}))
        profile = w.run(lambda: w.rt.profiles.get_published("ta", "supervisor")).profile

        def decide(case, name, role="leader"):
            gate = ToolGateMiddleware(w.rt, Binding(case, "s", "a", "case-leader", role, "awp:ta"), profile, "ta")
            return w.run(lambda: gate.on_check_permission(None, {"tool_call": Call(name), "tool": None, "tool_input": {}}, nxt))

        for case in (case_id, stray):  # a workflow case and a case with no workflow alike
            assert decide(case, "lookup_ticket") == "next"  # granted by the profile, decided by AgentScope
            assert decide(case, "CaseRead").behavior == PermissionBehavior.ALLOW
            assert decide(case, "TeamSay").behavior == PermissionBehavior.ALLOW
            assert decide(case, "not_granted").behavior == PermissionBehavior.DENY
        assert decide(stray, "book_hotel") == "next"  # a case with no workflow has no consent: the tool is the engine's business
        assert decide(stray, "CaseAskConsent").behavior == PermissionBehavior.ALLOW  # and an own tool stays allowed
        assert w.sql("select count(*) from wf_approvals") == [(0,)]  # none of that asked anybody


def parked_specialist(w):
    """A workflow whose technician (not the leader) is parked on the booking: (start, first, approval, agent, session)."""
    MODE["worker"] = ck.tech_books
    ck.declare(w)
    start, first = w.flow.begin(message=text_of(ck.START))
    assert (first["workflow_state"], first["next_action"]) == ("awaiting_approval", "submit_approval")
    [appr] = w.flow.approvals(first["conversation_id"])
    [(agent, sess)] = w.sql("select agent_id, session_id from wf_approvals")
    assert (sess,) != w.sql("select leader_session_id from awp_cases where id=(select case_id from wf_workflows)")[0]
    # the request settled when the approval was written; the technician's own run is still finishing its park
    w.wait(lambda: status_of(w, agent, sess) == "awaiting_permission", what="the technician to be parked")
    return start, first, appr, agent, sess


def status_of(w, agent_id: str, session_id: str) -> str:
    client = w.engine.client
    r = w.run(lambda: client._http.get(f"/sessions/{session_id}/status", headers=client._h("ta"),
                                       params={"agent_id": agent_id}))
    return r.json()["status"]


def test_a_specialist_parked_on_an_approval_is_not_left_parked_by_a_close(tmp_path):
    with world(tmp_path, ck.via_tech, leader_tools=["hotel_search"], worker_tools=["book_hotel"], tools=[ck.factory]) as w:
        start, first, appr, agent, sess = parked_specialist(w)
        c = w.flow.close({"workflow_id": first["workflow_id"], "workflow_revision": appr["expected_revision"]}, start)[0]
        assert c.status_code == 200
        w.wait(lambda: status_of(w, agent, sess) == "idle" and approval_rows(w)[0][3], what="the specialist to be freed")
        assert approval_rows(w) == [("cancelled", "book_hotel", False, True)] and ck.BOOKED == []


def test_the_approval_of_a_specialist_that_runs_out_frees_it_and_the_leader_tells_the_resident(tmp_path):
    with world(tmp_path, ck.via_tech, leader_tools=["hotel_search"], worker_tools=["book_hotel"], tools=[ck.factory]) as w:
        start, first, appr, agent, sess = parked_specialist(w)
        w.sql("update wf_approvals set expires_at=?", (time.time() - 5,))
        w.wait_state(first["workflow_id"], "awaiting_user")
        w.quiet()
        assert status_of(w, agent, sess) == "idle"  # the interrupt closed the technician's pending call
        assert approval_rows(w) == [("expired", "book_hotel", False, True)] and ck.BOOKED == []
        assert [m[1] for m in w.messages(first["workflow_id"]) if m[0] == "assistant"][-1] == ck.EXPIRED
