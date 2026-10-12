"""Regression tests of the S4 review that concern the life of a workflow around its approvals: a decision the engine
cannot deliver, the state after a booking, the order of the close events, two parked agents, and a tool that must
not run for a workflow closed after the resident agreed. Scripted model only."""
from __future__ import annotations

import time

import consentkit as ck
from enginekit import evidence_of, hold_leader, world
from fake_llm import CALLS, MODE
from scripts import say
from sqlalchemy import select
from test_wf_errors import assert_envelope
from test_wf_s4_flow import TOOLS, _clean, text_of, trip  # noqa: F401 - _clean is an autouse fixture
from test_wf_s4_gate import approval_rows, session_status

from awp.workforce import tables as t
from awp.workforce.close import shut
from awp.workforce.events import lock_conversation

BOTH = dict(leader_tools=["hotel_search", "book_hotel"], worker_tools=["book_hotel"], tools=[ck.factory])


# ---- a decision that cannot be delivered ---------------------------------------------------------------------------
def test_a_decision_the_engine_cannot_deliver_does_not_hold_back_the_next_reply(tmp_path):
    """The job that carries the answer fails for good: the workflow needs attention (a person looks), the agent that
    asked is closed as interrupted and the tool never runs, and a reply that comes later is not queued for ever."""
    with world(tmp_path, ck.trip, route={"wait_seconds": 3.0}, wf_job_attempts=1, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        wid, conv = first["workflow_id"], first["conversation_id"]
        [appr] = f.approvals(conv)
        client = w.engine.client
        real = client.confirm

        async def broken(*a, **k):
            raise RuntimeError("AgentScope /chat/ -> 500: scripted")
        client.confirm = broken
        assert f.decide(appr["approval_id"], f.decide_body(start, first, appr)).status_code == 202
        w.wait_state(wid, "needs_attention", timeout=30)
        client.confirm = real  # the outage is over
        w.wait(lambda: session_status(w, wid) == "idle" and approval_rows(w)[0][3], what="the parked agent to be freed")
        assert approval_rows(w) == [("approved", "book_hotel", False, True)] and ck.BOOKED == []
        w.quiet()
        r = f.reply(start, first, message=text_of("Hello? Is anybody there?"))[0]
        rid = r.json()["request_id"]
        w.wait(lambda: f.request(rid).json()["request_status"] == "completed", timeout=30, what="the reply to be answered")
        got = f.request(rid).json()
        assert (got["workflow_state"], got["next_action"], got["error"]) == ("awaiting_user", "submit_reply", None)
        assert w.sql("select count(*) from wf_jobs where status in ('queued','dispatched')") == [(0,)]


# ---- the state after a side effect -----------------------------------------------------------------------------------
def booked_then_inform(c):
    """Books (the gate asks first), then tells the resident with expects="none": a plain statement."""
    if ck.CHOOSE not in c.last_user:
        return ck.asking(c) or "Said."
    turn = c.after_user()
    if turn.called("book_hotel") == 0:
        return [("book_hotel", ck.BOOK)]
    got = " ".join(turn.results("book_hotel"))
    if turn.called("CaseSay") == 0:
        if "BK-77" in got:
            return say("Booked: BK-77 at Sunrise.", "none", evidence_of(got)[:1])
        return say("Understood, nothing was booked.", "none")
    return "Done."


def test_a_confirmed_booking_asks_for_the_close_whatever_the_leader_expects(tmp_path):
    with world(tmp_path, booked_then_inform, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        [appr] = f.approvals(first["conversation_id"])
        assert f.decide(appr["approval_id"], f.decide_body(start, first, appr)).status_code == 202
        w.wait_state(first["workflow_id"], "awaiting_confirmation")
        w.quiet()
        snap = f.snapshot(first["conversation_id"]).json()["workflows"][0]
        assert (snap["state"], snap["next_action"]) == ("awaiting_confirmation", "confirm_close")
        assert ck.BOOKED == [ck.BOOK]


def test_a_declined_booking_that_the_leader_reports_without_expecting_anything_is_not_a_confirmation(tmp_path):
    """Nothing happened: there is nothing for the resident to confirm."""
    with world(tmp_path, booked_then_inform, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        [appr] = f.approvals(first["conversation_id"])
        assert f.decide(appr["approval_id"], f.decide_body(start, first, appr, "reject")).status_code == 202
        w.wait_state(first["workflow_id"], "awaiting_user")
        w.quiet()
        assert ck.BOOKED == [] and w.state(first["workflow_id"])[0] == "awaiting_user"


# ---- the order of the events when a workflow with an approval is closed -----------------------------------------------
def test_the_approval_is_resolved_before_the_workflow_is_closed(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        [appr] = f.approvals(first["conversation_id"])
        c = f.close({"workflow_id": first["workflow_id"], "workflow_revision": appr["expected_revision"]}, start)[0]
        assert c.status_code == 200
        kinds = [e["event_type"] for e in f.history(first["conversation_id"], limit=500).json()["items"]]
        assert kinds[-2:] == ["approval.resolved", "workflow.closed"], kinds


# ---- two agents parked --------------------------------------------------------------------------------------------------
def test_the_expiry_of_a_specialists_approval_waits_for_the_leader_that_is_itself_parked(tmp_path):
    """A message sent to a parked session is lost (P0): the notice is held back until the leader is awake, and then
    it is delivered. Nothing fails, nothing is retried, the workflow keeps waiting for the resident."""
    with world(tmp_path, ck.both, wf_ack_seconds=1.0, **BOTH) as w:
        MODE["worker"] = ck.tech_books
        f = w.flow
        ck.declare(w)
        start, first = f.begin(message=text_of(ck.START))
        wid, conv = first["workflow_id"], first["conversation_id"]
        both = w.wait(lambda: len(f.approvals(conv)) == 2 and f.approvals(conv), what="both approvals")
        mine = {a["summary"]["arguments"]["hotel"]: a for a in both}
        w.wait(lambda: session_status(w, wid) == "awaiting_permission", what="the leader parked")
        w.sql("update wf_approvals set expires_at=? where id=?", (time.time() - 5, mine["Sunrise"]["approval_id"]))
        w.wait(lambda: w.sql("select 1 from wf_jobs where kind='notice' and status='queued'"), what="the notice to be held")
        time.sleep(3)  # the sweep had its chances to send it into the parked session
        assert w.state(wid)[0] == "awaiting_approval" and not w.sql("select 1 from wf_jobs where status='failed'")
        assert not [c for c in CALLS if "platform-notice" in str(c["shape"])]
        [left] = f.approvals(conv)
        assert left["approval_id"] == mine["Lotus"]["approval_id"]
        assert f.decide(left["approval_id"], f.decide_body(start, first, left)).status_code == 202
        w.wait(lambda: w.sql("select status from wf_jobs where kind='notice'") == [("done",)], timeout=40, what="the notice")
        w.quiet(30)
        assert [c for c in CALLS if "platform-notice" in str(c["shape"])]  # the leader was told, once it could hear
        assert not w.sql("select 1 from wf_jobs where status='failed'")


def test_a_reply_is_refused_while_the_other_approval_is_still_pending(tmp_path):
    """Deciding one of two approvals must not open a window in which the workflow takes a reply: the resident has
    still one decision to give."""
    with world(tmp_path, ck.both, route={"wait_seconds": 1.0}, **BOTH) as w:
        MODE["worker"] = ck.tech_books
        f = w.flow
        ck.declare(w)
        start, first = f.begin(message=text_of(ck.START))
        wid, conv = first["workflow_id"], first["conversation_id"]
        both = w.wait(lambda: len(f.approvals(conv)) == 2 and f.approvals(conv), what="both approvals")
        mine = {a["summary"]["arguments"]["hotel"]: a for a in both}
        gate = hold_leader()  # the leader's continuing turn takes as long as the test likes
        assert f.decide(mine["Lotus"]["approval_id"], f.decide_body(start, first, mine["Lotus"])).status_code == 202
        w.wait(lambda: w.sql("select 1 from wf_jobs where kind='approval_resume' and status='dispatched'"), what="the resume")
        assert w.state(wid)[0] == "awaiting_approval"  # the other approval is what the workflow waits for
        assert_envelope(f.reply(start, first, message=text_of("Also a late checkout."))[0], 409, "APPROVAL_PENDING")
        gate.set()
        w.wait(lambda: w.sql("select status from wf_jobs where kind='approval_resume'") == [("done",)], timeout=30, what="the resume")
        [left] = f.approvals(conv)  # the decision's own request ended with the resumed turn, not with the other decision
        w.wait(lambda: w.sql("select status from wf_requests where command_type='submit_consent'") == [("completed",)],
               what="the decision's request")
        assert w.state(wid)[0] == "awaiting_approval"
        assert left["approval_id"] == mine["Sunrise"]["approval_id"]


# ---- a consent is not a licence once the workflow is gone -------------------------------------------------------------
def test_a_tool_does_not_run_for_a_workflow_that_closed_after_the_decision(tmp_path):
    """The partner's close commits just as the engine hands the answer to the agent (forced here): the gate looks
    at the workflow again, with the same lock as the write that marks the consent used."""
    with world(tmp_path, ck.trip, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        wid = first["workflow_id"]
        [appr] = f.approvals(first["conversation_id"])
        client, db, rt = w.engine.client, w.engine.ctx.db, w.rt
        real = client.confirm

        async def close_then_send(*a, **k):
            async with db.engine.begin() as conn:
                wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == wid))).mappings().one()
                await lock_conversation(conn, wf["conversation_id"])
                wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == wid))).mappings().one()
                await shut(rt, conn, wf, "resident_confirmed_resolved")
            return await real(*a, **k)

        client.confirm = close_then_send
        assert f.decide(appr["approval_id"], f.decide_body(start, first, appr)).status_code == 202
        w.wait(lambda: w.sql("select resumed_at from wf_approvals")[0][0] is not None, what="the agent to take the answer")
        w.quiet()
        assert w.state(wid)[0] == "closed"
        assert ck.BOOKED == [] and not approval_rows(w)[0][2]  # the consent was not used
