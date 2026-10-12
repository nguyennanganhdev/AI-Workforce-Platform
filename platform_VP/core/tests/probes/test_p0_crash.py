"""P0 probe: what survives a hard crash in the middle of a turn, and what a restart sees.

Two real OS processes ("nodes") share the same SQLite files and workspace dir. Node 1 is killed
with TerminateProcess while a tool with a side effect is in flight. Node 2 starts fresh with a NEW
InMemoryMessageBus. The model is scripted (tests cannot say how a real model behaves).
"""
from __future__ import annotations

import time

import pytest

from p0_crash_helpers import (ADM, CALLS, SVC, FakeLLM, Node, case_items, confirm_body, effects, first_user_text,
                              free_port, intents, pending_tool_call, say, session_state, session_status, sql,
                              stored_messages, tool_calls, wait_for)


def intake_body(ref="TICKET-1"):
    return {"message_id": f"m-{ref}", "external_ref": ref, "summary": "Pipe leaking in unit A-12-05",
            "description": "Water under the sink since this morning."}


@pytest.fixture()
def llm():
    with FakeLLM() as f:
        yield f


def case_of(node: Node, case_id: str) -> dict:
    return node.http.get(f"/platform/v1/cases/{case_id}", headers=SVC).json()


class Crashed:
    """Instance 1 took a case, reached `point` inside the tool and was then killed."""

    def __init__(self, tmp_path, llm, point, before_kill=None, **over):
        self.root, self.llm = tmp_path, llm
        self.awp_db, self.as_db = str(tmp_path / "awp.db"), str(tmp_path / "as.db")
        self.over = over
        self.n1 = Node(tmp_path, "n1", llm.base_url, hang_at=point, **over).start()
        r = self.n1.http.post("/platform/v1/intake", headers=SVC, json=intake_body())
        assert r.status_code == 202, r.text
        self.case_id = r.json()["case_id"]
        wait_for(lambda: (tmp_path / "side" / f"reached_{point}").exists(), 60, what=f"tool at {point}")
        self.sid, self.aid = sql(self.awp_db, "select leader_session_id, leader_agent_id from awp_cases where id=?",
                                 (self.case_id,))[0]
        self.status_in_flight = self.n1.http.get(f"/sessions/{self.sid}/status", headers=ADM,
                                                 params={"agent_id": self.aid}).json()["status"]
        if before_kill:
            before_kill(self)
        self.state_in_flight = session_state(self.as_db, self.sid)
        self.messages_in_flight = stored_messages(self.as_db, self.sid)
        self.n1.kill()
        self.n2: Node | None = None

    def restart(self, **over) -> Node:
        cfg = {**self.over, "hang_at": ""}
        cfg.update(over)
        self.n2 = Node(self.root, "n2", self.llm.base_url, **cfg).start()
        return self.n2

    def finish(self):
        if self.n2:
            self.n2.kill()

    def wait_closed(self, node=None, timeout=60):
        node = node or self.n2
        return wait_for(lambda: case_of(node, self.case_id)["status"] != "open", timeout, what="case closed")


# ------------------------------------------------------------------ 1. what is on disk, what n2 sees
def test_hard_crash_state_and_restart_view(tmp_path, llm):
    c = Crashed(tmp_path, llm, "after_mark", guard=False)
    try:
        # --- while the tool is in flight (instance 1 alive) ---
        assert c.status_in_flight == "running"
        assert c.state_in_flight["context"] == []  # the turn's context is NOT saved until the turn ends
        assert [m[0] for m in c.messages_in_flight] == ["user"]  # only the incoming user message was saved
        assert len(effects(tmp_path)) == 1  # the side effect had already happened
        assert tool_calls(tmp_path)[0].startswith("CALL cr-")

        # --- after the hard kill: nothing changed on disk (no handler ran) ---
        assert session_state(c.as_db, c.sid) == c.state_in_flight
        assert stored_messages(c.as_db, c.sid) == c.messages_in_flight

        # --- instance 2, new InMemoryMessageBus ---
        n2 = c.restart()
        # The run lock lived in instance 1's memory: gone with the process. No stuck lock.
        st = n2.http.get(f"/sessions/{c.sid}/status", headers=ADM, params={"agent_id": c.aid})
        assert st.status_code == 200 and st.json()["status"] == "idle"
        # Our table: the case is still open, no tool evidence and no final, only what intake wrote.
        assert case_of(n2, c.case_id)["status"] == "open"
        kinds = [k for _r, k, _a in case_items(c.awp_db, c.case_id)]
        assert kinds == ["evidence"], kinds  # intake evidence only: the tool never returned
        # Nobody re-ran the interrupted turn: wait a moment, nothing new happened.
        n2_calls_before = len(CALLS)
        time.sleep(3)
        assert len(CALLS) == n2_calls_before == 1  # only instance 1's single model call exists
        assert len(effects(tmp_path)) == 1 and len(tool_calls(tmp_path)) == 1  # the tool was NOT re-executed

        # A new message to the session is accepted (no 409, no wait on a lock).
        r = say(n2, c.aid, c.sid, "Any news?")
        assert r.status_code == 200 and r.json()["status"] == "started", r.text
        c.wait_closed()
        # What the model of instance 2 was shown: the lost turn is simply absent.
        first_n2 = CALLS[1]
        assert first_n2["n_book_calls"] == 0 and first_n2["tool_call_ids"] == []
        assert first_n2["user_texts"][0] == "Any news?"  # the opening case message is NOT in the context either
        # ... so the model does the work again, and the tool call id is a new one.
        assert CALLS[1]["out"][0][0] == "book_plumber"
        assert CALLS[0]["issued_ids"] and CALLS[1]["issued_ids"]
        assert CALLS[0]["issued_ids"][0] != CALLS[1]["issued_ids"][0]  # tool_call_id is NOT stable across a crash
        # Unguarded: a second real booking with the same client_reference.
        e = effects(tmp_path)
        assert len(e) == 2 and e[0].split()[1] == e[1].split()[1]
        # The lost user message is still recoverable from the messages table.
        assert first_user_text(c.as_db, c.sid).startswith("<case id=")
    finally:
        c.finish()


# ------------------------------------------------------------------ 2. duplicate WITHOUT the guard
@pytest.mark.parametrize("recovery", ["redispatch_original", "new_message"])
def test_duplicate_side_effect_without_guard(tmp_path, llm, recovery):
    c = Crashed(tmp_path, llm, "after_mark", guard=False)
    try:
        n2 = c.restart()
        text = first_user_text(c.as_db, c.sid) if recovery == "redispatch_original" else "Any news?"
        assert say(n2, c.aid, c.sid, text).status_code == 200
        c.wait_closed()
        e = effects(tmp_path)
        assert len(e) == 2, e  # DUPLICATE: the plumber was booked twice
        assert e[0].split()[1] == e[1].split()[1]  # same client_reference, two different processes
        assert e[0].split()[2] != e[1].split()[2]
        assert intents(c.awp_db) == []  # no intent row existed to stop it
    finally:
        c.finish()


# ------------------------------------------------------------------ 3. none WITH the guard
@pytest.mark.parametrize("recovery", ["redispatch_original", "new_message"])
def test_no_duplicate_with_intent_guard_after_mark(tmp_path, llm, recovery):
    """Crash after the intent row says `sent`: n2's tool finds it and does not call the provider."""
    c = Crashed(tmp_path, llm, "after_mark", guard=True)
    try:
        assert [s for _r, s in intents(c.awp_db)] == ["sent"]  # the row survives the crash (our DB)
        n2 = c.restart()
        text = first_user_text(c.as_db, c.sid) if recovery == "redispatch_original" else "Any news?"
        assert say(n2, c.aid, c.sid, text).status_code == 200
        c.wait_closed()
        assert len(effects(tmp_path)) == 1, effects(tmp_path)
        log = tool_calls(tmp_path)
        assert len(log) == 3 and log[1].startswith("CALL") and log[2].startswith("SKIP")  # n2 called it, guard skipped
        assert [s for _r, s in intents(c.awp_db)] == ["sent"]
    finally:
        c.finish()


@pytest.mark.parametrize("point,effects_made", [("after_intent", 0), ("after_effect", 1)])
def test_intent_row_alone_cannot_tell_if_the_effect_happened(tmp_path, llm, point, effects_made):
    """A crash before the row says `sent` leaves status `intent` in both cases: our DB cannot tell
    "never sent" from "sent, answer lost". Hence retry only with the same client_reference."""
    c = Crashed(tmp_path, llm, point, guard=True, on_intent="unknown")
    try:
        assert [s for _r, s in intents(c.awp_db)] == ["intent"]
        assert len(effects(tmp_path)) == effects_made  # the provider is the only one who knows
        n2 = c.restart()
        assert say(n2, c.aid, c.sid, first_user_text(c.as_db, c.sid)).status_code == 200
        c.wait_closed()
        assert [s for _r, s in intents(c.awp_db)] == ["unknown"]  # strict policy: no retry, flag it
        assert len(effects(tmp_path)) == effects_made  # never a second effect, but also no action recovered
    finally:
        c.finish()


@pytest.mark.parametrize("point", ["after_intent", "after_effect"])
def test_retry_with_same_reference_is_safe_only_if_provider_is_idempotent(tmp_path, llm, point):
    # provider dedupes on client_reference: exactly one booking in both cases
    c = Crashed(tmp_path, llm, point, guard=True, on_intent="retry_same_ref", provider_dedupe=True)
    try:
        n2 = c.restart()
        say(n2, c.aid, c.sid, first_user_text(c.as_db, c.sid))
        c.wait_closed()
        assert len(effects(tmp_path)) == 1
        assert [s for _r, s in intents(c.awp_db)] == ["completed"]
    finally:
        c.finish()


def test_retry_with_same_reference_duplicates_if_provider_is_not_idempotent(tmp_path, llm):
    c = Crashed(tmp_path, llm, "after_effect", guard=True, on_intent="retry_same_ref", provider_dedupe=False)
    try:
        n2 = c.restart()
        say(n2, c.aid, c.sid, first_user_text(c.as_db, c.sid))
        c.wait_closed()
        assert len(effects(tmp_path)) == 2  # the guard alone is not enough in this window
    finally:
        c.finish()


# ------------------------------------------------------------------ 4. the 10 second offload
def test_tool_over_10_seconds_is_offloaded_then_lost_on_crash(tmp_path, llm):
    """A tool still running after 10 s is moved to a background task and the turn ends with a
    placeholder result that IS saved. A crash then loses the background task for good."""
    c = Crashed(tmp_path, llm, "after_mark", guard=True,
                before_kill=lambda self: wait_for(lambda: session_state(self.as_db, self.sid)["context"], 40,
                                                  what="turn saved with the placeholder"))
    try:
        flat = [b for _r, _n, blocks in c.state_in_flight["context"] for b in blocks]
        placeholder = [b for b in flat if b.startswith("tool_result:book_plumber")]
        # saved: the call counts as finished/success, with a placeholder that promises a notification
        assert len(placeholder) == 1 and ":success:" in placeholder[0] and "running in background" in placeholder[0]
        assert "tool_call:book_plumber:finished" in flat
        assert [s for _r, s in intents(c.awp_db)] == ["sent"]  # the operation is stuck: nobody will complete it
        assert len(effects(tmp_path)) == 1
        n2 = c.restart()
        st = n2.http.get(f"/sessions/{c.sid}/status", headers=ADM, params={"agent_id": c.aid}).json()["status"]
        assert st == "idle"
        time.sleep(3)
        # no notification ever arrives, nothing is re-executed, the operation stays `sent`
        assert len(effects(tmp_path)) == 1 and len(tool_calls(tmp_path)) == 1
        assert [s for _r, s in intents(c.awp_db)] == ["sent"]
    finally:
        c.finish()


# ------------------------------------------------------------------ 5. crash while an approved tool runs
class ParkedThenCrashed:
    """The resident approved; the tool started (side effect done); the process died before the turn was saved."""

    def __init__(self, tmp_path, llm, **over):
        self.root, self.llm, self.over = tmp_path, llm, over
        self.as_db, self.awp_db = str(tmp_path / "as.db"), str(tmp_path / "awp.db")
        self.n1 = Node(tmp_path, "n1", llm.base_url, approval=True, hang_at="after_mark", **over).start()
        self.case_id = self.n1.http.post("/platform/v1/intake", headers=SVC, json=intake_body()).json()["case_id"]
        self.sid, self.aid = sql(self.awp_db, "select leader_session_id, leader_agent_id from awp_cases where id=?",
                                 (self.case_id,))[0]
        wait_for(lambda: session_status(self.n1, self.aid, self.sid) == "awaiting_permission", 60, what="parked")
        self.parked_context = session_state(self.as_db, self.sid)["context"]
        self.reply_id, self.call = pending_tool_call(self.as_db, self.sid)
        self.body = confirm_body(self.aid, self.sid, self.reply_id, self.call)
        assert self.n1.http.post("/chat/", headers=ADM, json=self.body).status_code == 200
        wait_for(lambda: (tmp_path / "side" / "reached_after_mark").exists(), 60, what="approved tool running")
        self.status_in_flight = session_status(self.n1, self.aid, self.sid)
        self.context_in_flight = session_state(self.as_db, self.sid)["context"]
        self.n1.kill()
        self.n2 = Node(tmp_path, "n2", llm.base_url, approval=True, hang_at="", **over).start()

    def reconfirm(self):
        return self.n2.http.post("/chat/", headers=ADM, json=self.body)

    def close(self):
        self.n2.kill()


@pytest.mark.parametrize("guard,expected_effects", [(False, 2), (True, 1)])
def test_crash_while_approved_tool_runs(tmp_path, llm, guard, expected_effects):
    c = ParkedThenCrashed(tmp_path, llm, guard=guard)
    try:
        # the park WAS saved (it is the end of a turn); the approved execution was not
        assert [b for _r, _n, bl in c.parked_context for b in bl if b.startswith("tool_call")] == ["tool_call:book_plumber:asking"]
        assert c.status_in_flight == "running"
        assert c.context_in_flight == c.parked_context  # nothing of the resumed turn is saved
        assert len(effects(tmp_path)) == 1
        # n2 sees the session as still waiting for the approval; nothing re-runs on its own
        assert session_status(c.n2, c.aid, c.sid) == "awaiting_permission"
        time.sleep(3)
        assert len(effects(tmp_path)) == 1 and len(tool_calls(tmp_path)) == 1
        # the resident (or our API) approves again -> the framework executes the call again
        assert c.reconfirm().status_code == 200
        wait_for(lambda: case_of(c.n2, c.case_id)["status"] != "open", 60, what="case closed")
        assert len(tool_calls(tmp_path)) >= 2 and tool_calls(tmp_path)[1].startswith("CALL")  # tool re-executed
        assert len(effects(tmp_path)) == expected_effects, effects(tmp_path)
        if guard:
            assert any(x.startswith("SKIP") for x in tool_calls(tmp_path))
    finally:
        c.close()


def test_new_message_while_parked_after_crash(tmp_path, llm):
    """After the crash the session is `awaiting_permission`. A plain new message is accepted by POST
    /chat (200) but the run cannot start the model: the parked call blocks it (research doc 5, risk 2)."""
    c = ParkedThenCrashed(tmp_path, llm, guard=True)
    try:
        calls_before = len(CALLS)
        r = say(c.n2, c.aid, c.sid, "Any news?")
        assert r.status_code == 200 and r.json()["status"] == "started"  # accepted ...
        time.sleep(4)
        assert len(CALLS) == calls_before  # ... but no model call is ever made
        assert session_status(c.n2, c.aid, c.sid) == "awaiting_permission"  # still parked
        saved = [t for _r, _n, blocks in stored_messages(c.as_db, c.sid) for t in blocks]
        assert any("Any news?" in t for t in saved)  # the message is in the messages table ...
        ctx = [b for _r, _n, blocks in session_state(c.as_db, c.sid)["context"] for b in blocks]
        assert not any("Any news?" in t for t in ctx)  # ... but not in the agent context
    finally:
        c.close()


# ------------------------------------------------------------------ 6. contrast: a graceful interrupt DOES save the turn
def test_graceful_interrupt_saves_the_partial_turn_but_the_side_effect_stays(tmp_path, llm):
    """Not a crash: POST /sessions/{id}/interrupt cancels the in-flight tool cleanly. The turn is saved with the
    tool call closed as INTERRUPTED, yet the booking already happened and our row says `sent`."""
    awp_db, as_db = str(tmp_path / "awp.db"), str(tmp_path / "as.db")
    n1 = Node(tmp_path, "n1", llm.base_url, guard=True, hang_at="after_mark", case_stall_seconds=0).start()
    try:
        case_id = n1.http.post("/platform/v1/intake", headers=SVC, json=intake_body()).json()["case_id"]
        wait_for(lambda: (tmp_path / "side" / "reached_after_mark").exists(), 60, what="tool in flight")
        sid, aid = sql(awp_db, "select leader_session_id, leader_agent_id from awp_cases where id=?", (case_id,))[0]
        assert session_state(as_db, sid)["context"] == []
        r = n1.http.post(f"/sessions/{sid}/interrupt", headers=ADM, params={"agent_id": aid})
        assert r.status_code == 202, r.text
        wait_for(lambda: session_state(as_db, sid)["context"], 30, what="interrupted turn saved")
        flat = [b for _r, _n, bl in session_state(as_db, sid)["context"] for b in bl]
        assert any(b.startswith("tool_result:book_plumber:interrupted") for b in flat), flat
        assert len(effects(tmp_path)) == 1 and [s for _r, s in intents(awp_db)] == ["sent"]
    finally:
        n1.kill()


# ------------------------------------------------------------------ 7. Redis bus: the lock outlives the process
@pytest.fixture()
def redis_box():
    """A throw-away Redis (container awp-test-redis, removed afterwards). Skipped if docker cannot start it."""
    import shutil
    import subprocess
    if shutil.which("docker") is None:
        pytest.skip("docker not available")
    port = free_port()
    subprocess.run(["docker", "rm", "-f", "awp-test-redis"], capture_output=True)
    run = subprocess.run(["docker", "run", "-d", "--name", "awp-test-redis", "-p", f"127.0.0.1:{port}:6379",
                          "redis:7-alpine"], capture_output=True, text=True)
    if run.returncode != 0:
        pytest.skip(f"cannot start redis: {run.stderr[:200]}")
    try:
        import redis
        r = redis.Redis(host="127.0.0.1", port=port, decode_responses=True)
        for _ in range(60):
            try:
                if r.ping():
                    break
            except Exception:
                time.sleep(0.25)
        else:
            pytest.skip("redis did not answer")
        yield r, port
    finally:
        subprocess.run(["docker", "rm", "-f", "awp-test-redis"], capture_output=True)


def test_redis_bus_lock_survives_a_hard_crash(tmp_path, llm, redis_box):
    from agentscope.app.message_bus._keys import MessageBusKeys
    r, port = redis_box
    c = Crashed(tmp_path, llm, "after_mark", guard=True, redis=["127.0.0.1", port])
    try:
        lock = MessageBusKeys.session_lock(c.sid)
        events = MessageBusKeys.session_events(c.sid)
        assert c.status_in_flight == "running"
        # the dead process's lease is still in Redis, with a long TTL; its event log was never trimmed
        assert r.exists(lock) == 1
        assert 300 < r.ttl(lock) <= 600
        assert r.exists(events) == 1
        n2 = c.restart()
        # instance 2 (new process, same Redis) believes the session is running
        assert session_status(n2, c.aid, c.sid) == "running"
        before = len(CALLS)
        resp = say(n2, c.aid, c.sid, first_user_text(c.as_db, c.sid))
        assert resp.status_code == 200  # accepted: the run is queued behind the dead lock
        time.sleep(6)
        assert len(CALLS) == before  # no model call: the run waits for the lock (TTL up to 600 s)
        assert session_status(n2, c.aid, c.sid) == "running"
        assert len(effects(tmp_path)) == 1
        # operator action: release the dead lease (what a startup recovery step would have to do)
        r.delete(lock)
        c.wait_closed(timeout=60)
        assert len(effects(tmp_path)) == 1  # guard held: still one booking
        assert any(x.startswith("SKIP") for x in tool_calls(tmp_path))
    finally:
        c.finish()


# ------------------------------------------------------------------ 8. the old stall sweeper treats the orphan as dead
def test_old_stall_sweeper_fails_the_orphaned_case_after_restart(tmp_path, llm):
    """Nothing re-dispatches the lost turn, so `expire_stalled` (spec A9 reworks it) eventually fails the case.
    In the new design the wf_jobs lease/recovery must run first, or the case is lost as `failed`."""
    c = Crashed(tmp_path, llm, "after_mark", guard=True)
    try:
        n2 = c.restart(case_stall_seconds=3)
        end = wait_for(lambda: case_of(n2, c.case_id)["status"] == "failed" and case_of(n2, c.case_id), 40,
                       what="stalled case failed")
        assert end["result"]["unknowns"] == ["no activity for 3 seconds"]
        assert len(effects(tmp_path)) == 1  # and the booking stays in the world, with the case saying "failed"
    finally:
        c.finish()


# ------------------------------------------------------------------ 9. crash between our approval row and the park
def test_crash_between_our_approval_row_and_the_park_leaves_an_orphan(tmp_path, llm):
    """Spec 6.1 writes wf_approvals inside on_check_permission, before the turn parks and is saved.
    A crash in that window leaves a `pending` row of ours while AgentScope has nothing to resume."""
    awp_db, as_db = str(tmp_path / "awp.db"), str(tmp_path / "as.db")
    n1 = Node(tmp_path, "n1", llm.base_url, approval=True, gate_hang=True, guard=True).start()
    case_id = n1.http.post("/platform/v1/intake", headers=SVC, json=intake_body()).json()["case_id"]
    wait_for(lambda: (tmp_path / "side" / "reached_gate").exists(), 60, what="gate reached")
    sid, aid = sql(awp_db, "select leader_session_id, leader_agent_id from awp_cases where id=?", (case_id,))[0]
    n1.kill()
    n2 = Node(tmp_path, "n2", llm.base_url, approval=True, gate_hang=False, guard=True).start()
    try:
        assert sql(awp_db, "select status from p0_approvals") == [("pending",)]  # our row survived
        assert session_status(n2, aid, sid) == "idle"  # but the session is NOT awaiting_permission
        reply_id, call = pending_tool_call(as_db, sid)
        assert call is None  # nothing to confirm: a decision for this approval has no tool call to resume
        assert len(effects(tmp_path)) == 0
    finally:
        n2.kill()
