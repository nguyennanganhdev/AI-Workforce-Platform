"""Fixes after the S3 review: what the engine does when the leader only informs, repeats itself, fails or
is cut short, and what the resident can and cannot be told. Scripted model only."""
from __future__ import annotations

import re
import threading
import time
from unittest import mock

import dbtest
import pytest
import scripts
from enginekit import hold_leader, world
from fake_llm import CALLS, MODE
from scripts import say

REPLY = {"message": {"type": "text", "text": "Tôi rảnh từ 14 giờ."}}
SAFE = {"rules": {"safe_reply": "A person will follow up."}}


def texts(body: dict) -> list[str]:
    return [m["text"] for m in body["result"]["messages"]]


def said(w, wid: str) -> list[str]:
    return [m[1] for m in w.messages(wid) if m[0] == "assistant"]


def completed(w, request_id: str, timeout: float = 15.0):
    return w.wait(lambda: (g := w.flow.request(request_id).json())["request_status"] == "completed" and g,
                  timeout, f"request {request_id} to complete")


# ---- a leader that only informs is not a silent leader -----------------------------------------------
def test_a_leader_that_only_informs_rests_and_is_not_nudged(tmp_path):
    def inform(c):
        return "Said." if c.after_user().called("CaseSay") else say("Thanks, I have noted your request.", "none")

    with world(tmp_path, inform, route=SAFE) as w:
        start, r = w.flow.begin()
        assert (r["workflow_state"], r["next_action"]) == ("awaiting_user", "submit_reply")
        assert texts(r) == ["Thanks, I have noted your request."]  # once: no nudge, no safe reply on top
        assert w.sql("select count(*) from wf_jobs where kind='nudge'") == [(0,)]
        awaiting = [e for e in w.flow.history(r["conversation_id"]).json()["items"]
                    if e["event_type"] == "workflow.awaiting_user"]
        assert awaiting and awaiting[-1]["payload"]["reason"] == "informed"
        # and the conversation goes on: the resident answers, the same workflow takes it
        again = w.flow.reply(start, r, **REPLY)[0]
        assert again.status_code == 200 and again.json()["workflow_state"] == "awaiting_user"


def test_a_question_followed_by_an_informing_line_still_waits_for_the_answer(tmp_path):
    def script(c):
        n = c.after_user().called("CaseSay")
        if n == 0:
            return say("What time suits you?", "reply")
        if n == 1:
            return say("Our office closes in the evening.", "none")
        return "Said."

    with world(tmp_path, script) as w:
        _, r = w.flow.begin()
        assert texts(r) == ["What time suits you?", "Our office closes in the evening."]
        assert (r["workflow_state"], r["next_action"]) == ("awaiting_user", "submit_reply")


def test_a_leader_that_said_nothing_is_still_nudged(tmp_path):
    with world(tmp_path, scripts.silent, route=SAFE) as w:
        _, r = w.flow.begin()
        assert r["workflow_state"] == "needs_attention" and texts(r) == ["A person will follow up."]
        assert w.sql("select count(*) from wf_jobs where kind='nudge'") == [(2,)]


# ---- explicit confirmation closes only through POST close ---------------------------------------------
def test_a_workflow_that_asked_for_confirmation_is_not_closed_by_the_engine(tmp_path):
    def script(c):
        if "14 gi" not in c.last_user:
            return "Said." if c.after_user().called("CaseSay") else say("Is the issue resolved? Please confirm.", "confirmation")
        return scripts.lookup(c)

    with world(tmp_path, script) as w:
        start, first = w.flow.begin()
        assert (first["workflow_state"], first["next_action"]) == ("awaiting_confirmation", "confirm_close")
        second = w.flow.reply(start, first, message={"type": "text", "text": "Yes, 14 giờ ok."})[0].json()
        assert (second["workflow_state"], second["next_action"]) == ("awaiting_confirmation", "confirm_close")
        assert texts(second) == [scripts.TICKET]
        closed = w.flow.close(second, start, revision=second["workflow_revision"])[0]  # the partner's close still works
        assert closed.status_code == 200 and closed.json()["state"] == "closed"


# ---- a failed attempt does not repeat what the resident already read ------------------------------------
def test_a_turn_that_fails_after_the_leader_spoke_is_not_repeated(tmp_path):
    def script(c):
        if c.after_user().called("CaseSay"):
            MODE["leader_http"] = 0
            return "Said."
        MODE["leader_http"] = 400  # the next model call of this turn fails
        return say("What time suits you?", "reply")

    with world(tmp_path, script, wf_job_attempts=3) as w:
        _, r = w.flow.begin()
        assert r["request_status"] == "completed" and (r["workflow_state"], texts(r)) == (
            "awaiting_user", ["What time suits you?"])
        assert said(w, r["workflow_id"]) == ["What time suits you?"]
        assert w.sql("select attempts, status from wf_jobs") == [(1, "done")]  # not tried again
        assert w.sql("select count(*) from wf_events where event_type='assistant.message'") == [(1,)]


def test_a_turn_that_fails_before_the_leader_spoke_is_tried_again(tmp_path):
    def script(c):
        return "Said." if c.after_user().called("CaseSay") else say("What time suits you?", "reply")

    def heal():  # the model fails once, then works
        end = time.monotonic() + 30
        while time.monotonic() < end:
            if any(str(c.get("out", "")).startswith("http") for c in CALLS):
                MODE["leader_http"] = 0
                return
            time.sleep(0.002)

    with world(tmp_path, script, wf_job_attempts=3, wf_wait_seconds=20) as w:
        MODE["leader_http"] = 400
        threading.Thread(target=heal, daemon=True).start()
        _, r = w.flow.begin()
        assert said(w, r["workflow_id"]) == ["What time suits you?"]
        assert w.sql("select attempts from wf_jobs") == [(2,)]


# ---- what the partner sends reaches the leader --------------------------------------------------------
def test_the_timezone_of_the_partner_reaches_the_leader(tmp_path):
    seen = []

    def script(c):
        seen.append("Asia/Ho_Chi_Minh" in c.last_user)
        return scripts.interactive(c)

    with world(tmp_path, script) as w:
        r, _ = w.flow.start(timezone="Asia/Ho_Chi_Minh")
        assert r.status_code == 200 and seen and seen[0]


def test_the_timezone_of_the_route_is_the_default(tmp_path):
    seen = []

    def script(c):
        seen.append("Europe/Paris" in c.last_user)
        return scripts.interactive(c)

    with world(tmp_path, script, route={"timezone": "Europe/Paris"}) as w:
        w.flow.start()
        assert seen and seen[0]


def test_a_long_message_reaches_the_leader_whole(tmp_path):
    detail = "THE-KEY-DETAIL-AT-THE-END"
    long = "word " * 1800 + detail  # 9000 characters: the contract accepts up to 20000

    def script(c):
        script.seen.append(detail in c.last_user and "[cut]" not in c.last_user)
        return scripts.interactive(c)

    script.seen = []
    with world(tmp_path, script) as w:
        w.flow.start(message={"type": "text", "text": long})
        assert script.seen and script.seen[0]


# ---- the engine does not wait for a timer when its own bookkeeping fails -----------------------------------
def test_a_settle_that_failed_is_done_by_the_next_sweep(tmp_path):
    import awp.workforce.runner as runner
    real, calls = runner.settle, {"n": 0}

    async def flaky(eng, wid):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("database is locked")
        return await real(eng, wid)

    with mock.patch.object(runner, "settle", flaky):
        with world(tmp_path, scripts.interactive, wf_wait_seconds=1.0, case_stall_seconds=900) as w:
            r, _ = w.flow.start()
            body = completed(w, r.json()["request_id"], 15)
            assert (body["workflow_state"], texts(body)) == ("awaiting_user", ["What time suits you?"])
            assert calls["n"] >= 2


def test_a_turn_row_left_running_by_a_crash_does_not_hold_the_workflow(tmp_path):
    with world(tmp_path, scripts.interactive, wf_turn_timeout_seconds=300.0, wf_wait_seconds=1.0) as w:
        start, first = w.flow.begin()
        wid = first["workflow_id"]
        w.quiet()
        w.sql("insert into wf_turns (id, workflow_id, trigger, status, started_at) values ('turn_orphan', ?, 'message', 'running', ?)",
              (wid, time.time() - 1))
        t0 = time.monotonic()
        r = w.flow.reply(start, first, **REPLY)[0]
        body = completed(w, r.json()["request_id"], 20)
        assert time.monotonic() - t0 < 20 and body["workflow_state"] == "awaiting_confirmation"
        assert w.sql("select status from wf_turns where id='turn_orphan'") == [("interrupted",)]


def test_a_restart_closes_the_turns_the_old_process_left_running(tmp_path):
    with world(tmp_path, scripts.interactive) as w:
        _, first = w.flow.begin()
        w.quiet()
        w.sql("insert into wf_turns (id, workflow_id, trigger, status, started_at) values ('turn_dead', ?, 'message', 'running', ?)",
              (first["workflow_id"], time.time()))
        w.run(w.engine.start)
        assert w.sql("select status from wf_turns where id='turn_dead'") == [("interrupted",)]


class FailsFinishing:
    """finish_job raises for its first `n` calls: the turn is over and answered, only the bookkeeping fails."""

    def __init__(self, n: int) -> None:
        import awp.workforce.runner as runner
        self.runner, self.real, self.calls, self.n = runner, runner.finish_job, 0, n

    async def __call__(self, conn, jid, status="done", **how):
        self.calls += 1
        if self.calls <= self.n:
            raise RuntimeError("connection reset")
        return await self.real(conn, jid, status, **how)


def test_a_dispatcher_that_died_after_the_turn_does_not_block_the_next_reply(tmp_path):
    import awp.workforce.runner as runner
    with mock.patch.object(runner, "finish_job", FailsFinishing(3)):
        with world(tmp_path, scripts.interactive, wf_wait_seconds=1.0) as w:
            start, first = w.flow.begin()
            completed(w, first["request_id"], 15)
            first = w.flow.request(first["request_id"]).json()
            r = w.flow.reply(start, first, **REPLY)[0]
            body = completed(w, r.json()["request_id"], 15)
            assert texts(body) == ["Noted: 14. Can you confirm?"]


def test_a_job_whose_turn_ended_is_finished_not_sent_again(tmp_path):
    import awp.workforce.runner as runner
    with mock.patch.object(runner, "finish_job", FailsFinishing(3)):
        with world(tmp_path, scripts.interactive, wf_wait_seconds=1.0) as w:
            r, _ = w.flow.start()
            wid = w.sql("select id from wf_workflows")[0][0]
            w.wait(lambda: not w.sql("select 1 from wf_jobs where status in ('queued','dispatched')"), 15, "the job to end")
            assert said(w, wid) == ["What time suits you?"]
            assert w.sql("select status, attempts from wf_jobs") == [("done", 1)]
            assert w.sql("select count(*) from wf_turns") == [(1,)]  # the leader ran once


def test_a_job_whose_turn_died_with_the_process_runs_again(tmp_path):
    """The opposite of the test above: a turn that never ended (the process died) did not answer anything,
    so after a restart its job is sent again, once."""
    with world(tmp_path, scripts.interactive, wf_wait_seconds=1.0) as w:
        _, r = w.flow.begin()
        w.quiet()
        jid = w.sql("select id from wf_jobs")[0][0]
        w.sql("update wf_jobs set status='dispatched', lease_until=1 where id=?", (jid,))
        # (the turn "began" now, after the words of the finished one: a dead turn that had already spoken is another case,
        # test_wf_p5b_recovery.py)
        w.sql("update wf_turns set status='running', ended_at=null, started_at=?", (time.time(),))
        w.run(w.engine.start)
        w.wait(lambda: w.sql("select status, attempts from wf_jobs") == [("done", 2)], 20, "the job to run again")
        assert w.sql("select count(*) from wf_turns") == [(2,)]
        assert said(w, r["workflow_id"]) == ["What time suits you?"]  # the resident is not told twice (same chain, same words)


def test_a_stopped_engine_hands_its_job_back_at_once(tmp_path):
    with world(tmp_path, scripts.interactive, wf_wait_seconds=0.3) as w:
        hold_leader()  # the turn cannot end before the engine is stopped
        r, _ = w.flow.start()
        assert r.status_code == 202
        w.wait(lambda: w.sql("select 1 from wf_jobs where status='dispatched'"), 10, "the job to be running")
        w.run(w.engine.stop)
        assert w.sql("select status, lease_until from wf_jobs")[0][1] == 0


def test_an_engine_stopped_in_the_bookkeeping_after_a_turn_hands_the_job_back_too(tmp_path):
    """The stop used to release the job only while its turn ran. Caught a moment later, between the end of the turn
    and the write that marks the job done, the job stayed `dispatched` until its lease ran out (seen on PostgreSQL,
    where that moment is longer: the next process waited a minute for a job nobody had)."""
    import asyncio

    from awp.workforce import runner

    with world(tmp_path, scripts.interactive, wf_wait_seconds=0.3) as w:
        reached = threading.Event()

        async def never(conn, jid, *a, **k):
            reached.set()
            await asyncio.Event().wait()  # the write that marks the job done never comes back

        with mock.patch.object(runner, "finish_job", never):
            r, _ = w.flow.start()
            assert r.status_code in (200, 202)
            assert reached.wait(20), "the turn to end and the bookkeeping to begin"
            w.run(w.engine.stop)
        assert w.sql("select status, lease_until from wf_jobs") == [("dispatched", 0)]


def test_a_failing_turn_record_is_tried_again_so_the_message_is_not_sent_twice(tmp_path):
    from awp.workforce.turns import TurnRecorder
    real, calls = TurnRecorder._insert, {"n": 0}

    async def flaky(self, turn_id, trigger, msg_id):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("database is locked")
        return await real(self, turn_id, trigger, msg_id)

    with mock.patch.object(TurnRecorder, "_insert", flaky):
        with world(tmp_path, scripts.interactive, wf_ack_seconds=2.0) as w:
            _, r = w.flow.begin()
            assert said(w, r["workflow_id"]) == ["What time suits you?"]
            assert w.sql("select count(*) from wf_turns") == [(1,)]


# ---- a workflow that is blocked while its turn runs ---------------------------------------------------------
def test_nothing_is_said_once_the_workflow_is_blocked_and_its_request_ends(tmp_path):
    with world(tmp_path, scripts.topics, wf_wait_seconds=0.3) as w:
        gate = hold_leader()  # the first turn is still running while the route is suspended
        r1, start = w.flow.start()
        first = r1.json()
        assert r1.status_code == 202
        assert w.env.post(f"/platform/v1/wf/routes/{w.flow.route['route_id']}/suspend").status_code == 200
        r2, _ = w.flow.reply(start, first, message={"type": "text", "text": "hello again"})
        assert r2.status_code == 403
        w.wait_state(first["workflow_id"], "blocked_authorization")
        gate.set()  # now the leader answers, late
        w.quiet()
        assert said(w, first["workflow_id"]) == []  # the leader's late answer was refused
        # the job being over does not yet mean the settle ran: wait for the request to end, then look at it
        w.wait(lambda: w.flow.request(first["request_id"]).json()["request_status"] == "blocked", what="the request to end blocked")
        got = w.flow.request(first["request_id"]).json()
        assert got["request_status"] == "blocked" and got["next_action"] == "resolve_attention"


# ---- the leader cannot flood the resident ---------------------------------------------------------------------
def test_a_looping_leader_cannot_flood_the_resident(tmp_path):
    def flood(c):
        n = c.after_user().called("CaseSay")
        return say("Update number " + "x" * n, "none") + say("Another update " + "y" * n, "none")

    with world(tmp_path, flood, wf_job_attempts=1) as w:
        w.flow.start()
        w.quiet(60)
        wid = w.sql("select id from wf_workflows")[0][0]
        assert len(said(w, wid)) == 5


def test_the_leader_cannot_say_the_same_thing_twice_in_a_row(tmp_path):
    def repeat(c):
        return say("Same line.", "none") if c.after_user().called("CaseSay") < 3 else "Done."

    with world(tmp_path, repeat) as w:
        _, r = w.flow.begin()
        assert texts(r) == ["Same line."]
        results = [x for call in CALLS for x in [str(call["shape"])] if "You already said exactly this" in x]
        assert results


# ---- workers that stop without reporting ---------------------------------------------------------------------------
def consult_and_wait(c):
    if c.called("TeamCreate") == 0:
        return [("TeamCreate", {"name": "case-team", "description": "Check"})]
    if c.called("AgentCreate") == 0:
        return [("AgentCreate", {"name": "tech", "description": "Checks", "subagent_type": "tech",
                                 "prompt": "Look up ticket T-1001."})]
    if ("hit an error" in c.blob or "finished without" in c.blob) and not c.after_user().called("CaseSay"):
        return say("The technician could not check the ticket; a person will follow up.", "reply")
    return "Waiting for the specialists."


def test_a_worker_whose_model_failed_does_not_keep_the_request_waiting(tmp_path):
    with world(tmp_path, consult_and_wait, wf_wait_seconds=30, case_stall_seconds=900) as w:
        MODE["worker_http"] = 400
        _, r = w.flow.begin()
        assert r["request_status"] == "completed" and r["workflow_state"] == "awaiting_user"
        assert texts(r) == ["The technician could not check the ticket; a person will follow up."]
        reports = w.sql("select data from awp_case_items where kind='report'")
        assert len(reports) == 1 and "error" in str(reports[0][0])


def test_a_worker_that_ends_without_a_report_wakes_the_leader(tmp_path):
    with world(tmp_path, consult_and_wait, wf_wait_seconds=30, case_stall_seconds=900) as w:
        MODE["worker"] = lambda c: "I looked at it and have nothing to report."
        _, r = w.flow.begin()
        assert r["request_status"] == "completed" and r["workflow_state"] == "awaiting_user"
        assert texts(r) == ["The technician could not check the ticket; a person will follow up."]


def test_a_worker_that_reports_is_left_alone(tmp_path):
    with world(tmp_path, scripts.consult, wf_wait_seconds=30) as w:
        _, r = w.flow.begin()
        assert texts(r) == ["Ticket T-1001 is waiting for the plumber."]
        reports = w.sql("select data from awp_case_items where kind='report'")
        assert len(reports) == 1 and "ended" not in str(reports[0][0])


def test_a_resolved_answer_is_refused_while_a_specialist_has_not_reported(tmp_path):
    def early(c):
        if c.called("TeamCreate") == 0:
            return [("TeamCreate", {"name": "case-team", "description": "Check"})]
        if c.called("AgentCreate") == 0:
            return [("AgentCreate", {"name": "tech", "description": "Checks", "subagent_type": "tech",
                                     "prompt": "Look up ticket T-1001 and record what you find."})]
        if c.called("CaseFinalize") == 0:
            return [("CaseFinalize", {"answer": "Your request is being handled.", "outcome": "resolved", "cites": ["E1"]})]
        facts = re.findall(r"\b(F\d+) tech:", c.blob)
        if facts and not c.after_user().called("CaseSay"):
            return say("Ticket T-1001 is waiting for the plumber.", "reply", facts[:1])
        return "Waiting."

    with world(tmp_path, early, wf_wait_seconds=30) as w:
        _, r = w.flow.begin()
        refused = [x for call in CALLS for x in [str(call["shape"])] if "Not finalized: your team has not finished" in x]
        assert refused
        assert (r["workflow_state"], texts(r)) == ("awaiting_user", ["Ticket T-1001 is waiting for the plumber."])
        assert w.sql("select count(*) from awp_case_items where kind='final'") == [(0,)]


# ---- two residents of one partner share nothing ------------------------------------------------------------------------
def test_two_residents_get_a_workspace_each(tmp_path):
    from awp.agentscope_client import owner_of

    with world(tmp_path, scripts.topics) as w:
        w.flow.begin(external_user_id="resident-A", message={"type": "text", "text": "Please fix the pipe"})
        w.flow.begin(external_user_id="resident-B", message={"type": "text", "text": "Please book a hotel"})
        rows = w.sql("select tenant, leader_agent_id, leader_session_id from awp_cases where leader_session_id is not null")

        async def spaces():
            return [(await w.rt.storage.get_session(owner_of(t), a, s)).config.workspace_id for t, a, s in rows]

        a, b = w.run(spaces)
        assert len(rows) == 2 and a != b


def test_long_term_memory_is_kept_per_workflow(tmp_path, monkeypatch):
    import enginekit

    real_profiles = enginekit.profiles

    def with_memory():
        out = real_profiles()
        out[0].memory.enabled = True
        return out

    monkeypatch.setattr(enginekit, "profiles", with_memory)
    with world(tmp_path, scripts.topics) as w:
        w.flow.begin(external_user_id="resident-A", message={"type": "text", "text": "Please fix the pipe"})
        w.flow.begin(external_user_id="resident-B", message={"type": "text", "text": "Please book a hotel"})
        ids = [x[0] for x in w.sql("select id from wf_workflows")]
    base = tmp_path / "ws" / "memory" / "ta" / "supervisor"
    assert len(ids) == 2 and all((base / wid).is_dir() for wid in ids)  # one folder each, none shared above them


# ---- the engine's database copes with a run cut off in the middle of a statement ------------------------------------------
@pytest.mark.skipif(dbtest.IS_PG, reason="the write-ahead log is a SQLite journal mode; PostgreSQL always has one")
def test_the_file_database_uses_a_write_ahead_log(tmp_path):
    with world(tmp_path, scripts.interactive) as w:
        assert w.sql("pragma journal_mode") == [("wal",)]


@pytest.mark.parametrize("pause", [0.0, 0.1, 0.25])
def test_a_close_that_lands_during_a_turn_leaves_nothing_behind(tmp_path, pause):
    """The close interrupts the running leader (cancelling its task wherever it is). The database stays usable,
    no turn stays running, no job stays dispatched, no request stays waiting."""
    with world(tmp_path, scripts.interactive, wf_wait_seconds=0.3) as w:
        start, first = w.flow.begin()
        w.quiet()
        first = w.flow.request(first["request_id"]).json()
        MODE["leader_delay"] = 0.4
        out = {}

        def reply():
            out["reply"] = w.flow.reply(start, first, **REPLY)[0]

        th = threading.Thread(target=reply)
        th.start()
        time.sleep(pause)
        rev = w.state(first["workflow_id"])[1]
        out["close"] = w.flow.close(first, start, revision=rev)[0]
        th.join()
        w.quiet(30)
        w.wait(lambda: not w.sql("select 1 from wf_requests where status in ('accepted','queued','running')"),
               20, "every request to be settled")
        assert not w.sql("select 1 from wf_turns where status='running'")
        if out["close"].status_code == 200:
            assert w.state(first["workflow_id"])[0] == "closed"


@pytest.mark.slow
def test_replies_racing_a_close_never_lock_the_database(tmp_path, caplog):
    """The race that used to wedge SQLite ('could not close turn ... database is locked', two runs in eight):
    a reply and a close land together on a running turn, over and over. Nothing is left running and nothing
    logged as locked."""
    import logging
    import random

    caplog.set_level(logging.WARNING, logger="awp.workforce")
    rnd = random.Random(7)
    with world(tmp_path, scripts.interactive, wf_wait_seconds=0.3) as w:
        for i in range(8):
            MODE["leader_delay"] = 0.0
            start, first = w.flow.begin()
            first = completed(w, first["request_id"])
            MODE["leader_delay"] = 0.4
            out = {}

            def reply():
                time.sleep(rnd.random() * 0.1)
                out["reply"] = w.flow.reply(start, first, **REPLY)[0]

            def close():
                time.sleep(rnd.random() * 0.5)
                out["close"] = w.flow.close(first, start, revision=w.state(first["workflow_id"])[1])[0]

            threads = [threading.Thread(target=reply), threading.Thread(target=close)]
            [th.start() for th in threads]
            [th.join() for th in threads]
            w.quiet(30)
            w.wait(lambda: not w.sql("select 1 from wf_requests where status in ('accepted','queued','running')"),
                   20, f"every request to be settled (round {i})")
            assert not w.sql("select 1 from wf_turns where status='running'"), i
            if out["close"].status_code == 200:
                assert w.state(first["workflow_id"])[0] == "closed"
        bad = [r.getMessage() for r in caplog.records if "locked" in r.getMessage() or "could not" in r.getMessage()]
        assert not bad, bad[:3]
