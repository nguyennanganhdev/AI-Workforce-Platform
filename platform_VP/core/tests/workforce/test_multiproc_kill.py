"""Crash recovery proven with REAL kills (spec 13.25; contract 13.9 row 9, 14.3 item 8).

Two platform processes on one PostgreSQL and one Redis (mpkit.Fleet). One of them is ended with TerminateProcess /
SIGKILL at a chosen point and the outcome is read through the public API of the survivor only:

  (a) in the middle of the leader's model call
  (b) inside a partner action, after the intent row and before the partner answered
  (c) after the partner answered and before the result was written down
  (d) while parked on an approval (and: after the agent took the decision, while its tool runs)
  (e) between the commit of a public event and its delivery over SSE
  (f) while waiting for a provider event

What must hold each time: the partner carried the action out exactly once, no public message or event is there twice,
the sequences have no gap, and the request ends (completed, or the workflow needs attention with a public reason).

The model is the script of deploy/demo/fake_model.py and the partner the sample MCP server of deploy/demo/fake_mcp.py:
this proves the platform's bookkeeping under a kill, nothing about a real model or a real partner.
Run: docs/WORKFORCE_V1_VAN_HANH.md section 11.
"""
from __future__ import annotations

import threading
import time

import pytest

from mpkit import LEASE, Fleet, RowLock, World, audit, fleet, needs_fleet, one_effect, until  # noqa: F401 (fleet: fixture)

pytestmark = [pytest.mark.slow, pytest.mark.multiproc, needs_fleet]

BOOK = "Please book a repair visit for the leaking tap."
PENDING = "I asked for the visit on Monday; it is pending."
HANDLED = "Your request for a visit is being handled; I will tell you when it changes."
FINISHED = "The partner reports the work finished. Is everything right?"


def text(words: str) -> dict:
    return {"type": "text", "text": words}


def finish(w: World, flow, body: dict, started: dict, ref: str, i: int) -> None:
    """The rest of a booking through process i: the partner's backend reports, the leader asks, the partner closes."""
    conv, provider = started["conversation_id"], w.provider_on(i)
    r, _ = provider.send("job.assigned", ref=ref, data={"worker_name": "An"})
    assert r.status_code == 202, r.text
    r, _ = provider.send("job.completed", ref=ref)
    assert r.status_code == 202, r.text
    wf = w.until_state(flow, conv, "awaiting_confirmation")
    assert wf["next_action"] == "confirm_close"
    closed, _ = flow.close({"workflow_id": started["workflow_id"], "workflow_revision": wf["workflow_revision"]}, body)
    assert closed.status_code == 200 and closed.json()["state"] == "closed", closed.text


def reference(w: World, flow, conv: str) -> str:
    """The client_reference of the conversation's one operation, as the public log shows it."""
    def found():
        refs = {e["payload"]["client_reference"] for e in w.events(flow, conv) if e["event_type"] == "operation.status_changed"}
        return refs
    [ref] = until(found, 60, "the operation to show in the public log")
    return ref


# ---- (a) -------------------------------------------------------------------------------------------------------------
def test_a_kill_in_the_middle_of_the_leaders_model_call_and_the_other_process_finishes_the_request(fleet):
    w = World(fleet)
    a, b = w.on(0), w.on(1)
    fleet.hold_model("TKT-KILL")
    r, body = a.start(message=text("TKT-KILL the tap in the kitchen leaks"))
    assert r.status_code == 202 and r.json()["next_action"] == "watch_request"  # the turn hangs in the model
    conv = r.json()["conversation_id"]
    until(lambda: fleet.model_held() == 1, 30, "the model call to hang")

    assert fleet.running_the_turn() is fleet.api[0]  # the turn a message starts runs in the process that took it
    fleet.kill(fleet.api[0])
    fleet.hold_model("")

    done = w.settled(b, r)
    assert done["request_status"] == "completed" and done["workflow_state"] == "awaiting_user", done
    [said] = done["result"]["messages"]
    assert said["text"].startswith("Noted (TKT-KILL)")
    seen = audit(w, b, conv)
    assert seen.kinds.count("assistant.message") == 1 and seen.kinds.count("request.accepted") == 1
    # and the workflow goes on through the survivor, in the same session
    r2, _ = b.reply(body, r.json(), message=text("TKT-KILL it is the cold tap"))
    again = w.settled(b, r2)
    assert again["request_status"] == "completed" and again["workflow_id"] == r.json()["workflow_id"]
    assert audit(w, b, conv).kinds.count("assistant.message") == 2


def test_the_session_lock_a_killed_process_left_in_redis_is_released_after_its_lease_and_not_before(fleet):
    """The 'stuck Redis lock': AgentScope's session lock of the dead process has minutes to live. It is deleted by the
    survivor once the dead process's lease ran out (not earlier), and only that lock."""
    w = World(fleet)
    a, b = w.on(0), w.on(1)
    fleet.hold_model("TKT-LOCK")
    r, _ = a.start(message=text("TKT-LOCK the tap leaks"))
    conv = r.json()["conversation_id"]
    until(lambda: fleet.model_held() == 1, 30, "the model call to hang")
    [(key, (value, ttl))] = fleet.session_locks().items()
    assert ttl > 300  # AgentScope's lease of 600 s: this is how long the session would stay blocked

    assert fleet.running_the_turn() is fleet.api[0]  # the turn a message starts runs in the process that took it
    fleet.kill(fleet.api[0])
    killed = time.monotonic()
    time.sleep(LEASE / 3)
    assert fleet.session_locks()[key][0] == value  # within the lease the process may still be alive: nobody touches it
    fleet.hold_model("")

    done = w.settled(b, r, timeout=60)
    took = time.monotonic() - killed
    assert done["request_status"] == "completed" and done["workflow_state"] == "awaiting_user"
    assert LEASE / 3 < took < 45, f"recovered after {took:.1f} s"  # the lease and a sweep, not AgentScope's ten minutes
    assert fleet.session_locks().get(key, ("", 0))[0] != value  # the dead process's lock is gone
    assert audit(w, b, conv).kinds.count("assistant.message") == 1


def test_a_live_process_keeps_its_lock_and_its_job_however_long_its_turn_takes(fleet):
    """The other half of the safe release: a turn that outlasts several leases in a process that lives is never taken
    over. Its lock stays, its job is not run a second time, the resident hears one answer."""
    w = World(fleet)
    a, b = w.on(0), w.on(1)
    fleet.hold_model("TKT-SLOW")
    r, _ = a.start(message=text("TKT-SLOW the tap leaks"))
    conv = r.json()["conversation_id"]
    until(lambda: fleet.model_held() == 1, 30, "the model call to hang")
    [(key, (value, _))] = fleet.session_locks().items()
    before = fleet.model.http.get("/health").json()["requests"]

    time.sleep(LEASE * 2.5)  # several leases and several sweeps of both processes

    assert fleet.session_locks()[key][0] == value
    assert fleet.model.http.get("/health").json()["requests"] == before and fleet.model_held() == 1  # nobody started it again
    assert b.request(r.json()["request_id"]).json()["request_status"] in ("queued", "running")
    fleet.hold_model("")
    done = w.settled(b, r)
    assert done["request_status"] == "completed"
    assert audit(w, b, conv).kinds.count("assistant.message") == 1


# ---- (b) -------------------------------------------------------------------------------------------------------------
def held_in_the_partner(fleet: Fleet, w: World, flow, **over):
    """Start a booking whose tool call hangs at the partner: the intent row is written, the request is with the partner
    (its side effect is done), the answer has not come."""
    fleet.hold_partner(True)
    r, body = flow.start(message=text(BOOK), **over)
    assert r.status_code == 202, r.text
    until(lambda: fleet.partner()["held"] == 1, 30, "the tool call to hang at the partner")
    return r, body


def test_b_kill_inside_a_partner_action_before_the_partner_answered_and_the_action_happens_once(fleet):
    w = World(fleet, consent=False)
    a, b = w.on(0), w.on(1)
    r, body = held_in_the_partner(fleet, w, a)
    conv = r.json()["conversation_id"]

    assert fleet.running_the_turn() is fleet.api[0]  # the turn a message starts runs in the process that took it
    fleet.kill(fleet.api[0])
    fleet.hold_partner(False)

    done = w.settled(b, r)
    assert done["request_status"] == "completed", done
    # the survivor asks the partner again with the SAME reference (the tool is idempotent by it): no second visit
    until(lambda: fleet.partner()["book_repair_calls_by_reference"] and
          max(fleet.partner()["book_repair_calls_by_reference"].values()) == 2, 60, "the request to be sent again")
    ref = one_effect(fleet, calls=2)
    w.until_state(b, conv, "waiting_external_event")
    assert reference(w, b, conv) == ref
    finish(w, b, body, r.json(), ref, 1)
    seen = audit(w, b, conv)
    assert seen.texts.count(FINISHED) == 1 and (HANDLED in seen.texts or PENDING in seen.texts)
    assert one_effect(fleet, calls=2) == ref  # still one visit, after everything


def test_b_kill_inside_an_action_nobody_can_ask_about_ends_in_needs_attention_with_a_public_reason(fleet):
    """The tool has no idempotency argument and no status query: after the kill nobody can know whether the partner got
    the request, so it is NOT sent again and a person is asked (never 'active' for ever, never a second visit)."""
    w = World(fleet, consent=False, resend=False)
    a, b = w.on(0), w.on(1)
    r, _ = held_in_the_partner(fleet, w, a)
    conv = r.json()["conversation_id"]

    assert fleet.running_the_turn() is fleet.api[0]  # the turn a message starts runs in the process that took it
    fleet.kill(fleet.api[0])
    fleet.hold_partner(False)

    wf = w.until_state(b, conv, "needs_attention")
    assert wf["next_action"] == "resolve_attention"
    done = w.settled(b, r)
    assert done["request_status"] in ("completed", "failed")
    seen = audit(w, b, conv)
    [why] = [e["payload"] for e in seen.events if e["event_type"] == "workflow.needs_attention"]
    assert why["reason"] == "operation_unknown"
    one_effect(fleet, calls=1)  # the partner has the one request the dead process sent; nothing was sent after it
    listed = fleet.api[1].http.get("/platform/v1/wf/workflows", params={"state": "needs_attention"},
                                   headers={"Authorization": "Bearer adm-a"}).json()
    assert [x["attention_reason"] for x in listed["workflows"]] == ["operation_unknown"]


# ---- (c) -------------------------------------------------------------------------------------------------------------
def test_c_kill_after_the_partner_answered_and_before_the_answer_was_written_down(fleet):
    w = World(fleet, consent=False)
    a, b = w.on(0), w.on(1)
    r, body = held_in_the_partner(fleet, w, a)
    conv = r.json()["conversation_id"]
    lock = RowLock(fleet, conv)  # from here nobody can write this conversation: the answer cannot be recorded
    try:
        fleet.hold_partner(False)
        until(lambda: fleet.partner()["answered"] == 1, 30, "the partner to answer")
        time.sleep(1.0)  # the answer is back in the process, which waits for the lock to write it down
        assert "operation.status_changed" not in [e["event_type"] for e in w.events(b, conv)]  # not recorded
        assert fleet.running_the_turn() is fleet.api[0]  # the turn a message starts runs in the process that took it
        fleet.kill(fleet.api[0])
    finally:
        lock.release()

    done = w.settled(b, r)
    assert done["request_status"] == "completed", done
    until(lambda: max(fleet.partner()["book_repair_calls_by_reference"].values()) == 2, 60, "the request to be sent again")
    ref = one_effect(fleet, calls=2)
    w.until_state(b, conv, "waiting_external_event")
    finish(w, b, body, r.json(), ref, 1)
    seen = audit(w, b, conv)
    assert seen.texts.count(FINISHED) == 1
    moved = [e["payload"]["status"] for e in seen.events if e["event_type"] == "operation.status_changed"]
    assert moved == ["pending", "assigned", "completed"]  # each step once: the answer that was lost came back with the resend
    one_effect(fleet, calls=2)


# ---- (d) -------------------------------------------------------------------------------------------------------------
def parked(fleet: Fleet, w: World, flow):
    r, body = flow.start(message=text(BOOK))
    done = w.settled(flow, r)
    assert done["workflow_state"] == "awaiting_approval" and done["next_action"] == "submit_approval", done
    appr = w.approval(flow, done["conversation_id"])
    assert fleet.partner()["calls"].get("book_repair", 0) == 0  # nothing was sent before the resident agreed
    return body, done, appr


def test_d_kill_while_parked_on_an_approval_and_the_decision_arrives_on_the_other_process(fleet):
    w = World(fleet)
    a, b = w.on(0), w.on(1)
    body, started, appr = parked(fleet, w, a)
    conv = started["conversation_id"]

    fleet.kill(fleet.api[0])

    decision = b.decide_body(body, started, appr)
    d = b.decide(appr["approval_id"], decision)
    assert d.status_code == 202 and d.json()["status"] == "approved", d.text
    w.until_state(b, conv, "waiting_external_event")
    ref = one_effect(fleet, calls=1)
    again = b.decide(appr["approval_id"], decision)  # the partner sends the same decision again
    assert again.status_code == 202 and again.json() == d.json()
    finish(w, b, body, started, ref, 1)
    seen = audit(w, b, conv)
    assert seen.kinds.count("approval.required") == 1 and seen.kinds.count("approval.resolved") == 1
    assert seen.texts.count(PENDING) == 1 and seen.texts.count(FINISHED) == 1
    one_effect(fleet, calls=1)


def approved_call_hangs(fleet: Fleet, w: World):
    """The resident agreed, the agent took the decision and its tool call hangs at the partner. Returns what the test
    needs and the process the turn runs in: the decision goes to process 0, but the agent is woken through AgentScope's
    wake-up queue, which either process may take."""
    a = w.on(0)
    body, started, appr = parked(fleet, w, a)
    fleet.hold_partner(True)
    d = a.decide(appr["approval_id"], a.decide_body(body, started, appr))
    assert d.status_code == 202, d.text
    until(lambda: fleet.partner()["held"] == 1, 30, "the approved tool call to hang at the partner")
    return body, started, fleet.running_the_turn()


def test_d_kill_after_the_agent_took_the_decision_while_its_tool_runs(fleet):
    """R9 of the decisions: the approval row says the agent was woken (`resumed_at`), the process that runs its turn
    dies before the run is saved, so the session is still parked. The survivor hands the answer over again; the consent
    was used once, the ledger has the operation, and the visit is asked for once."""
    w = World(fleet)
    body, started, victim = approved_call_hangs(fleet, w)
    conv, survivor = started["conversation_id"], 1 - fleet.api.index(victim)
    b = w.on(survivor)

    fleet.kill(victim)
    fleet.hold_partner(False)

    w.until_state(b, conv, "waiting_external_event")
    until(lambda: max(fleet.partner()["book_repair_calls_by_reference"].values()) == 2, 60, "the request to be sent again")
    ref = one_effect(fleet, calls=2)
    finish(w, b, body, started, ref, survivor)
    seen = audit(w, b, conv)
    assert seen.kinds.count("approval.required") == 1 and seen.kinds.count("approval.resolved") == 1
    assert seen.texts.count(FINISHED) == 1
    one_effect(fleet, calls=2)


def test_d_kill_of_the_other_process_while_the_approved_tool_runs_changes_nothing_for_the_partner(fleet):
    """The process that does NOT run the turn is killed (it may be the one whose dispatcher sent the decision). The
    turn goes on where it runs, the partner answers it, and nothing is asked twice."""
    w = World(fleet)
    body, started, runs = approved_call_hangs(fleet, w)
    conv, survivor = started["conversation_id"], fleet.api.index(runs)
    b = w.on(survivor)

    fleet.kill(fleet.api[1 - survivor])
    fleet.hold_partner(False)

    w.until_state(b, conv, "waiting_external_event")
    ref = one_effect(fleet, calls=1)
    finish(w, b, body, started, ref, survivor)
    seen = audit(w, b, conv)
    assert seen.texts.count(PENDING) == 1 and seen.texts.count(FINISHED) == 1
    assert seen.kinds.count("approval.required") == 1 and seen.kinds.count("approval.resolved") == 1
    one_effect(fleet, calls=1)


# ---- (e) -------------------------------------------------------------------------------------------------------------
def test_e_kill_between_the_commit_of_events_and_their_delivery_and_the_client_resumes_with_last_event_id(fleet):
    w = World(fleet)
    a, b = w.on(0), w.on(1)
    r, body = b.start(message=text("TKT-SSE the tap leaks"))  # the turns run in process 1
    started = w.settled(b, r)
    conv = started["conversation_id"]
    before = w.events(b, conv)
    stream = w.stream(a, conv)  # the client reads its events from process 0
    got = stream.events(len(before), timeout=20)
    assert [f["id"] for f in got] == [e["event_id"] for e in before]

    fleet.freeze(fleet.api[0])  # from here process 0 delivers nothing
    r2, _ = b.reply(body, started, message=text("TKT-SSE it is the cold tap"))
    assert w.settled(b, r2)["request_status"] == "completed"
    log = w.events(b, conv)
    missing = log[len(before):]
    assert len(missing) >= 3  # committed, and not delivered:
    while (frame := stream.next(timeout=2.0)) is not None:
        assert "comment" in frame, f"a frozen process delivered {frame}"
    fleet.kill(fleet.api[0])
    assert stream.ended(15)

    resumed = w.stream(b, conv, last=got[-1]["id"])
    rest = resumed.events(len(missing), timeout=20)
    assert [f["id"] for f in rest] == [e["event_id"] for e in missing]  # nothing lost, nothing twice, in order
    assert [f["data"] for f in rest] == missing
    seqs = [f["data"]["sequence"] for f in got + rest]
    assert seqs == list(range(1, len(seqs) + 1))
    resumed.close()
    audit(w, b, conv)


# ---- (f) -------------------------------------------------------------------------------------------------------------
def test_f_kill_while_waiting_for_a_provider_event_that_then_arrives_on_the_other_process(fleet):
    w = World(fleet, consent=False)
    a, b = w.on(0), w.on(1)
    r, body = a.start(message=text(BOOK))
    started = w.settled(a, r)
    conv = started["conversation_id"]
    assert started["workflow_state"] == "waiting_external_event" and started["next_action"] == "watch_events", started
    ref = one_effect(fleet, calls=1)

    fleet.kill(fleet.api[0])

    finish(w, b, body, started, ref, 1)
    seen = audit(w, b, conv)
    assert seen.texts == [PENDING, "Worker An is on the way.", FINISHED]
    assert seen.kinds.count("workflow.closed") == 1
    one_effect(fleet, calls=1)


# ---- two processes that both live ------------------------------------------------------------------------------------
def test_a_request_waits_on_one_process_while_its_turn_runs_on_the_other(tmp_path):
    """The POST is accepted and run by process 0; the same POST again (the partner's retry) waits on process 1 and gets
    the frozen result the moment the turn that runs in process 0 has settled."""
    f = Fleet(tmp_path)
    try:
        f.ready(f.start_api(wait=False))
        f.start_api()
        w = World(f, wait_seconds=30)
        a, b = w.on(0), w.on(1)
        f.hold_model("TKT-WAIT")
        body = a.start_body(message=text("TKT-WAIT the tap leaks"))
        answers: dict = {}

        def post(name, flow):
            answers[name] = flow.post(body)

        first = threading.Thread(target=post, args=("a", a))
        first.start()
        until(lambda: f.model_held() == 1, 30, "the model call to hang")
        second = threading.Thread(target=post, args=("b", b))
        second.start()
        time.sleep(1.0)
        assert not answers  # both wait for the turn
        f.hold_model("")
        first.join(30)
        second.join(30)
        assert answers["a"].status_code == 200 and answers["b"].status_code == 200
        assert answers["a"].json() == answers["b"].json() and answers["a"].json()["request_status"] == "completed"
        assert audit(w, b, answers["a"].json()["conversation_id"]).kinds.count("assistant.message") == 1
    finally:
        f.close()


def test_a_post_on_one_process_wakes_the_stream_on_the_other_through_the_bus(tmp_path):
    """The streams of this fleet read the log only every 30 s by themselves: an event that arrives sooner came with the
    nudge over Redis. (That a stream is correct with no nudge at all is what the single-process suite proves.)"""
    f = Fleet(tmp_path, AWP_WF_SSE_POLL_SECONDS="30", AWP_WF_HEARTBEAT_SECONDS="60")
    try:
        f.ready(f.start_api(wait=False))
        f.start_api()
        w = World(f)
        a, b = w.on(0), w.on(1)
        r, body = a.start(message=text("TKT-BUS the tap leaks"))
        started = w.settled(a, r)
        conv = started["conversation_id"]
        stream = w.stream(b, conv)
        stream.events(len(w.events(a, conv)), timeout=20)
        sent = time.monotonic()
        r2, _ = a.reply(body, started, message=text("TKT-BUS it is the cold tap"))
        first = stream.events(1, timeout=10)[0]
        assert time.monotonic() - sent < 10 and first["event"] == "request.accepted"
        w.settled(a, r2)
        stream.close()
    finally:
        f.close()


def test_open_streams_are_counted_over_the_fleet_not_per_process(tmp_path):
    f = Fleet(tmp_path, AWP_WF_MAX_STREAMS="2")
    try:
        f.ready(f.start_api(wait=False))
        f.start_api()
        w = World(f)
        a, b = w.on(0), w.on(1)
        r, _ = a.start(message=text("TKT-COUNT the tap leaks"))
        conv = w.settled(a, r)["conversation_id"]
        one, two = w.stream(a, conv), w.stream(b, conv)
        assert one.status == 200 and two.status == 200
        for flow in (a, b):  # the third is refused whichever process it asks
            third = w.stream(flow, conv)
            assert third.status == 429, third.status
        one.close()
        ok = until(lambda: (lambda s: s if s.status == 200 else None)(w.stream(b, conv)), 20, "the freed place to be given")
        ok.close()
        two.close()
    finally:
        f.close()


def test_an_evaluation_started_on_one_process_is_not_disturbed_by_the_other(fleet):
    """A sandbox workflow is run by the process that runs its evaluation (the draft is in its memory). The other
    process's sweep sees the same queued jobs and must leave them."""
    http, adm = fleet.api[0].http, {"Authorization": "Bearer adm-a"}
    draft = {"key": "mp_leader", "name": "MP leader", "role": "leader", "mission": "the leader of a test route.",
             "model_tier": "strong", "instructions": "Answer in English."}
    assert http.post("/platform/v1/profiles", json=draft, headers=adm).status_code == 201
    r = http.post("/platform/v1/profiles/mp_leader/versions/1/evals", json={}, headers=adm)
    assert r.status_code == 202, r.text
    other = fleet.api[1].http

    def ended():
        runs = other.get("/platform/v1/profiles/mp_leader/versions/1/evals", headers=adm).json()["runs"]
        return runs[0] if runs and runs[0]["status"] != "running" else None
    run = until(ended, 120, "the evaluation to end")
    assert run["status"] == "passed", run
    assert all(c.get("error") is None for c in run["results"])
