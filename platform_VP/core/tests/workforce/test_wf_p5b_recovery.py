"""Several processes on one database, seen from one (slice P5b; spec 9, 13.25): who owns a job, an operation and a
parked agent, and what another process may do about them and when.

One process is real here (the app of the test); the other is the rows a process leaves: its `node:<id>` row in
`wf_leases`, its name on a job and on an operation. That is all a second process ever is to the first, so the rules can
be tested without one. The same rules under real kills of real processes: test_multiproc_kill.py. Scripted model only.
"""
from __future__ import annotations

import time

import pytest

import consentkit as ck
import scripts
from enginekit import hold_leader, world
from fake_llm import CALLS
from partnerkit import Partner
from t1kit import SETTINGS, TOOLS, configure, ops, quiet_leader, tools_of

from awp.workforce import ledger, nodes
from awp.workforce.reconcile import reconcile
from awp.workforce.recover import orphan_approvals, orphan_parks

OTHER = "nother0000000000"  # a second process: only ever its name


def other_lives(w, seconds: float = 60.0) -> None:
    w.sql("delete from wf_leases where name=?", ("node:" + OTHER,))
    w.sql("insert into wf_leases (name, owner, lease_until, last_run_at) values (?,?,?,?)",
          ("node:" + OTHER, OTHER, time.time() + seconds, time.time()))


def other_died(w) -> None:
    w.sql("update wf_leases set lease_until=1 where name=?", ("node:" + OTHER,))


def node_rows(w) -> list:
    return w.sql("select name, owner from wf_leases where name like 'node:%' order by name")


def said(w, wid: str) -> list[str]:
    return [text for sender, text, _ in w.messages(wid) if sender == "assistant"]


# ---- the mark of a process, and its jobs -------------------------------------------------------------------------
def test_an_engine_marks_its_process_keeps_the_mark_alive_and_removes_it_on_a_clean_stop(tmp_path):
    with world(tmp_path, scripts.interactive, wf_lease_seconds=1.0) as w:
        me = w.engine.node
        assert node_rows(w) == [("node:" + me, me)]
        [(first,)] = w.sql("select lease_until from wf_leases where name=?", ("node:" + me,))
        w.wait(lambda: w.sql("select lease_until from wf_leases where name=?", ("node:" + me,))[0][0] > first, 5, "the next beat")
        assert first <= time.time() + 1.1
    with world(tmp_path, scripts.interactive, publish=False) as w2:  # the next process is another node; nothing is left of the first
        assert w2.engine.node != me and node_rows(w2) == [("node:" + w2.engine.node, w2.engine.node)]


def test_a_job_names_the_process_that_runs_it_and_its_lease_is_renewed_for_as_long_as_the_turn_takes(tmp_path):
    with world(tmp_path, scripts.interactive, wf_lease_seconds=1.0, wf_wait_seconds=0.3) as w:
        gate = hold_leader()
        r, _ = w.flow.start()
        assert r.status_code == 202
        [(owner, first)] = w.wait(lambda: w.sql("select lease_owner, lease_until from wf_jobs where status='dispatched'"),
                                  10, "the job to be running")
        assert owner == w.engine.node and first <= time.time() + 1.1
        time.sleep(3.0)  # three leases, and a sweep or two: a job whose lease had run out would have been given back
        [(status, attempts, until)] = w.sql("select status, attempts, lease_until from wf_jobs")
        assert (status, attempts) == ("dispatched", 1) and until > first + 1.5
        gate.set()
        w.quiet()
        assert w.sql("select status, attempts, lease_owner from wf_jobs") == [("done", 1, None)]
        assert said(w, r.json()["workflow_id"]) == ["What time suits you?"] and len(w.sql("select 1 from wf_turns")) == 1


def left_by_the_other(w, wid: str) -> str:
    """What a process that died in the middle of a turn leaves: its job dispatched under its name, its turn running."""
    [(jid,)] = w.sql("select id from wf_jobs where workflow_id=?", (wid,))
    w.sql("update wf_jobs set status='dispatched', lease_owner=?, lease_until=? where id=?", (OTHER, time.time() + 60, jid))
    w.sql("update wf_turns set status='running', ended_at=null, started_at=? where workflow_id=?", (time.time(), wid))
    return jid


def test_the_job_of_a_process_that_lives_is_left_alone_and_after_its_lease_ran_out_it_is_run_again(tmp_path):
    with world(tmp_path, scripts.interactive, sweep_every=3600) as w:
        _, first = w.flow.begin()
        w.quiet()
        wid, calls = first["workflow_id"], len(CALLS)
        other_lives(w)
        jid = left_by_the_other(w, wid)
        # the turn of a live process holds the session's lock; here the lock is in this process's memory, so hold it
        from agentscope.app.message_bus import MessageBusKeys
        [(session,)] = w.sql("select leader_session_id from awp_cases")
        held = w.run(lambda: w.rt.bus.try_lock(MessageBusKeys.session_lock(session)))
        assert held
        for _ in range(2):
            w.run(w.engine.sweep)
        assert w.sql("select status, attempts, lease_owner from wf_jobs where id=?", (jid,)) == [("dispatched", 1, OTHER)]
        assert w.sql("select status from wf_turns") == [("running",)] and len(CALLS) == calls  # nothing was touched
        assert ("node:" + OTHER, OTHER) in node_rows(w)

        # the process dies: its lease and its job's lease run out, and its lock is gone
        other_died(w)
        w.sql("update wf_jobs set lease_until=1 where id=?", (jid,))
        w.run(lambda: w.rt.bus.unlock(MessageBusKeys.session_lock(session)))
        w.run(w.engine.sweep)
        w.wait(lambda: w.sql("select status, attempts from wf_jobs where id=?", (jid,)) == [("done", 2)], 20, "the job to run again")
        assert w.sql("select lease_owner from wf_jobs where id=?", (jid,)) == [(None,)]
        assert ("node:" + OTHER, OTHER) not in node_rows(w)  # buried
        assert said(w, wid) == ["What time suits you?"] and len(CALLS) > calls


def test_a_job_whose_turn_died_after_the_leader_had_spoken_is_not_run_again(tmp_path):
    """The resident already read what the dead turn said. Running the job again would say it a second time (a real
    model would not even use the same words), so the job ends and the workflow settles on what was said."""
    with world(tmp_path, scripts.interactive, sweep_every=3600) as w:
        _, first = w.flow.begin()
        w.quiet()
        wid, calls = first["workflow_id"], len(CALLS)
        [(jid,)] = w.sql("select id from wf_jobs")
        # the turn began, the leader spoke, and the process died before the turn ended
        w.sql("update wf_jobs set status='dispatched', lease_owner=?, lease_until=1 where id=?", (OTHER, jid))
        w.sql("update wf_turns set status='running', ended_at=null")
        w.sql("update wf_workflows set state='active' where id=?", (wid,))
        w.sql("update wf_requests set status='running', response=null, completed_at=null")
        w.run(w.engine.sweep)
        w.wait(lambda: w.sql("select status, attempts from wf_jobs where id=?", (jid,)) == [("done", 1)], 20, "the job to end")
        w.wait_state(wid, "awaiting_user")
        w.quiet()
        assert said(w, wid) == ["What time suits you?"] and len(CALLS) == calls  # not one more model call
        assert w.sql("select status from wf_turns") == [("interrupted",)]
        assert w.sql("select status from wf_requests") == [("completed",)]


def test_burying_a_dead_process_releases_its_locks_and_never_those_of_one_that_lives(tmp_path):
    with world(tmp_path, scripts.interactive, sweep_every=3600) as w:
        asked: list[str] = []

        async def release_of(node):
            asked.append(node)
            return ["agentscope:session:lock:x"]

        w.rt.bus.release_of = release_of  # what a bus the fleet shares has (bus.FleetBus)
        try:
            other_lives(w)
            w.run(w.engine.sweep)
            assert asked == [] and ("node:" + OTHER, OTHER) in node_rows(w)  # alive: nothing of it is touched
            other_died(w)
            w.run(w.engine.sweep)
            assert asked == [OTHER] and node_rows(w) == [("node:" + w.engine.node, w.engine.node)]
            w.run(w.engine.sweep)
            assert asked == [OTHER]  # once: it is forgotten
        finally:
            del w.rt.bus.release_of


# ---- approvals -------------------------------------------------------------------------------------------------------
TRIP = dict(tools=[ck.factory], leader_tools=["hotel_search", "book_hotel"])


@pytest.fixture(autouse=True)
def _clean():
    ck.BOOKED.clear()
    yield
    ck.BOOKED.clear()


def text_of(s: str) -> dict:
    return {"type": "text", "text": s}


def parked_trip(w) -> tuple:
    ck.declare(w)
    start, first = w.flow.begin(message=text_of(ck.START))
    r = w.flow.reply(start, first, message=text_of(ck.CHOOSE))[0]
    assert r.status_code == 200 and r.json()["workflow_state"] == "awaiting_approval", r.text
    w.quiet()
    return start, first, w.flow.approvals(first["conversation_id"])[0]


def test_an_agent_that_died_after_it_was_handed_the_decision_is_handed_it_again_and_the_tool_runs_once(tmp_path):
    """R9 of the decisions: `resumed_at` says the agent took the answer, but the process died before the run was saved,
    so the session is still parked. Nothing would ever wake it: every later message to it would be lost."""
    with world(tmp_path, ck.trip, sweep_every=3600, **TRIP) as w:
        start, first, appr = parked_trip(w)
        wid = first["workflow_id"]
        # the decision was recorded and the agent "woken" by a process that then died: no job is left for it
        w.sql("update wf_approvals set status='approved', decided_at=?, resumed_at=? where id=?",
              (time.time(), time.time(), appr["approval_id"]))
        w.sql("update wf_workflows set state='active', revision=revision+1 where id=?", (wid,))
        [who] = w.sql("select agent_id, session_id from wf_approvals")
        assert w.run(lambda: w.engine.client.status("ta", *who)) == "awaiting_permission"

        assert w.run(lambda: orphan_parks(w.engine)) == 1
        w.wait(lambda: ck.BOOKED == [ck.BOOK], 20, "the booking the resident agreed to")
        w.wait_state(wid, "awaiting_confirmation")
        w.quiet()
        assert ck.BOOKED == [ck.BOOK] and w.sql("select used_at is not null, resumed_at is not null from wf_approvals") == [(True, True)]
        assert w.run(lambda: orphan_parks(w.engine)) == 0  # put right: nothing to do a second time
        assert said(w, wid)[-1].startswith("Booked: BK-77")


def test_a_parked_agent_whose_approval_is_still_open_is_not_touched_by_the_reconcile(tmp_path):
    with world(tmp_path, ck.trip, sweep_every=3600, **TRIP) as w:
        _, first, appr = parked_trip(w)
        assert w.run(lambda: orphan_parks(w.engine)) == 0 and w.run(lambda: orphan_approvals(w.engine)) == 0
        assert w.sql("select status, resumed_at from wf_approvals") == [("pending", None)]
        assert w.state(first["workflow_id"])[0] == "awaiting_approval" and ck.BOOKED == []


def lost_approval(w, first: dict) -> None:
    """A crash between writing the approval and saving the parked run: the row says pending, the session is idle."""
    wid, conv = first["workflow_id"], first["conversation_id"]
    [(session, agent)] = w.sql("select leader_session_id, leader_agent_id from awp_cases")
    w.sql("insert into wf_approvals (id, workflow_id, conversation_id, client_id, external_user_id, session_id, agent_id, "
          "tool_call_id, tool_name, arguments, arguments_hash, summary, status, workflow_revision, expires_at, reply_id, "
          "created_at) values ('appr_lost', ?, ?, ?, 'resident-123', ?, ?, 'call_lost', 'book_hotel', '{}', 'sha256:x', "
          "'{\"text\": \"Book Sunrise for 2 nights\"}', 'pending', ?, ?, 'reply_lost', ?)",
          (wid, conv, w.flow.client["client_id"], session, agent, first["workflow_revision"] + 1, time.time() + 3600, time.time()))
    w.sql("update wf_workflows set state='awaiting_approval', revision=revision+1 where id=?", (wid,))


def test_a_lost_approval_is_cancelled_without_a_word_when_the_turn_that_asked_is_going_to_run_again(tmp_path):
    """The process died in the middle of the turn that asked: its job is still there and will be run again from its
    message, and asks again by itself. Telling the leader 'your request was cancelled' as well would make it speak of
    the same thing twice."""
    with world(tmp_path, ck.trip, sweep_every=3600, **TRIP) as w:
        ck.declare(w)
        _, first = w.flow.begin(message=text_of(ck.START))
        w.quiet()
        wid, conv = first["workflow_id"], first["conversation_id"]
        lost_approval(w, first)
        other_lives(w)
        w.sql("update wf_jobs set status='dispatched', lease_owner=?, lease_until=?", (OTHER, time.time() + 60))

        assert w.run(lambda: orphan_approvals(w.engine)) == 1
        assert w.sql("select status from wf_approvals where id='appr_lost'") == [("cancelled",)]
        assert w.sql("select count(*) from wf_jobs where kind='approval_resume'") == [(0,)]  # nobody is told: the job says it
        kinds = [(e["event_type"], e["payload"].get("status")) for e in w.flow.history(conv, limit=500).json()["items"]]
        assert ("approval.resolved", "cancelled") in kinds and w.state(wid)[0] == "active"


def test_a_lost_approval_with_no_turn_left_to_run_is_cancelled_and_the_leader_is_told(tmp_path):
    with world(tmp_path, ck.trip, sweep_every=3600, **TRIP) as w:
        ck.declare(w)
        _, first = w.flow.begin(message=text_of(ck.START))
        w.quiet()
        lost_approval(w, first)
        assert w.run(lambda: orphan_approvals(w.engine)) == 1
        w.wait_state(first["workflow_id"], "awaiting_user")
        w.quiet()
        assert said(w, first["workflow_id"])[-1] == ck.EXPIRED


# ---- operations ------------------------------------------------------------------------------------------------------
@pytest.fixture
def partner():
    with Partner() as p:
        yield p


def sent_by(w, tool: str, node: str, **args) -> dict:
    """The row a process leaves while its call is out: written, marked sent under its name, nothing recorded yet."""
    from t1kit import workflow_row

    wf = workflow_row(w)

    async def go():
        begun = await ledger.begin(w.rt.db, wf["id"], wf["route_id"], tool, args)
        assert begun.fresh and await ledger.mark_sent(w.rt.db, begun.op["id"], node)
        return begun.op["id"]
    op_id = w.run(go)
    w.sql("update wf_operations set updated_at=? where id=?", (time.time() - 5, op_id))
    return {"id": op_id}


def test_the_operation_a_live_process_is_sending_is_never_taken_for_the_leftover_of_a_crash(tmp_path, partner):
    """Across processes the live call and the answer in hand (ledger.INFLIGHT, HELD) are in the memory of the process
    that made the call. The row names it, and while it lives nobody else acts on the row."""
    with world(tmp_path, quiet_leader, sweep_every=3600, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        w.flow.begin()
        other_lives(w)
        sent_by(w, "partner_repair_keyed", OTHER, slot="mon")
        for _ in range(2):
            assert w.run(lambda: reconcile(w.engine, grace=0.0)) == 1  # looked at
        assert ops(w)[0]["status"] == "sent" and partner.of("book_repair") == []  # and left alone
        assert w.sql("select node from wf_operations") == [(OTHER,)]

        other_died(w)  # its answer, if it had one, died with it: now the others find out
        assert w.run(lambda: reconcile(w.engine, grace=0.0)) == 1
        [op] = ops(w)
        assert op["status"] == "pending" and len(partner.of("book_repair")) == 1 and partner.effects == ["repair"]
        assert partner.of("book_repair")[0]["args"]["client_reference"] == op["reference"]  # the same request, the same reference
        assert w.sql("select node from wf_operations") == [(w.engine.node,)]  # whoever took it over holds it now


def test_an_operation_this_process_left_itself_is_still_reconciled_at_once(tmp_path, partner):
    with world(tmp_path, quiet_leader, sweep_every=3600, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        w.flow.begin()
        sent_by(w, "partner_repair_keyed", w.engine.node, slot="mon")
        assert w.run(lambda: reconcile(w.engine, grace=0.0)) == 1
        assert ops(w)[0]["status"] == "pending" and len(partner.of("book_repair")) == 1


def test_of_two_processes_that_see_the_same_leftover_one_takes_it(tmp_path, partner):
    with world(tmp_path, quiet_leader, sweep_every=3600, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        w.flow.begin()
        op = sent_by(w, "partner_repair_keyed", None, slot="mon")
        seen = time.time() - 1  # both read the row as stale at this moment

        async def both():
            first = await ledger.touch(w.rt.db, op["id"], "sent", ("intent", "sent"), before=seen, node="na")
            second = await ledger.touch(w.rt.db, op["id"], "sent", ("intent", "sent"), before=seen, node="nb")
            return first, second
        assert w.run(both) == (True, False)
        assert w.sql("select node from wf_operations") == [("na",)]


def test_alive_says_whether_a_process_still_marks_its_row(tmp_path):
    with world(tmp_path, scripts.interactive, sweep_every=3600) as w:
        db = w.rt.db
        assert w.run(lambda: nodes.alive(db, w.engine.node)) is True
        assert w.run(lambda: nodes.alive(db, OTHER)) is False and w.run(lambda: nodes.alive(db, None)) is False
        other_lives(w)
        assert w.run(lambda: nodes.alive(db, OTHER)) is True and OTHER in w.run(lambda: nodes.living(db))
        other_died(w)
        assert w.run(lambda: nodes.alive(db, OTHER)) is False and w.run(lambda: nodes.dead(db)) == [OTHER]
