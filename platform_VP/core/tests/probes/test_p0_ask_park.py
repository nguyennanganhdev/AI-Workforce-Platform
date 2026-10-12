"""P0 probe: does an ASK from a middleware park the agent in dont_ask, and can we resume it ourselves?

Everything runs through the real AgentScope app (create_app) on a scripted model. It proves the
plumbing only; it says nothing about how a real model uses the tools.
"""
import json

import pytest
from fastapi.testclient import TestClient

import p0_ask_park_llm as llm
from p0_ask_park_gate import (ApprovalStore, Probe, args_hash, build_probe_app, canonical,
                              confirm_event_from_record)
from p0_ask_park_llm import FakeServer, n_calls, results_of


@pytest.fixture()
def probe(tmp_path):
    store = ApprovalStore()
    with FakeServer() as fake:
        app = build_probe_app(tmp_path, store)
        with TestClient(app) as client:
            yield Probe(client, fake.base_url, store, app)


def charge_once(sys, msgs, tools):
    """Leader: call Charge once, then answer in text once it has a result."""
    if n_calls(msgs, "Charge") == 0:
        return [("Charge", {"note": "x", "amount": 550000})]
    return "Charged."


def tool_result_states(sess) -> list[tuple[str, str]]:
    """(tool name, state) for every tool_result block in the persisted context."""
    out = []
    for m in sess.state.context:
        for b in m.get_content_blocks("tool_result"):
            out.append((b.name, str(b.state)))
    return out


def tool_call_states(sess) -> list[tuple[str, str]]:
    return [(b.name, str(b.state)) for m in sess.state.context for b in m.get_content_blocks("tool_call")]


# ---------------------------------------------------------------- 1. park

def test_control_engine_ask_in_dont_ask_is_denied_not_parked(probe):
    """Baseline: an ASK that comes from the engine/tool is turned into DENY by dont_ask."""
    llm.POLICY["fn"] = lambda sys, msgs, tools: (
        [("Refund", {"amount": 10})] if n_calls(msgs, "Refund") == 0 else "ok")
    aid, sid = probe.new_session()
    assert probe.say(aid, sid, "refund please").status_code == 200
    probe.wait_for(lambda: probe.store.turns and probe.store.turns[-1]["done"], what="turn end")
    assert probe.settle(aid, sid) == "idle"
    assert probe.store.executed == []
    sess = probe.stored_session(aid, sid)
    assert ("Refund", "denied") in tool_result_states(sess)
    turn = probe.store.turns[-1]
    assert turn["end"] and "completed" in turn["end"].lower() and not turn["parked"]


def test_middleware_ask_parks_in_dont_ask(probe):
    llm.POLICY["fn"] = charge_once
    aid, sid = probe.new_session()
    sess0 = probe.stored_session(aid, sid)
    assert sess0.state.permission_context.mode.value == "dont_ask"  # the mode the core sets

    assert probe.say(aid, sid, "please charge 550000").status_code == 200
    assert probe.wait_for(lambda: probe.store.pending(), what="approval row")
    st = probe.settle(aid, sid)

    # parked: status says so, the tool did not run, state ASKING is persisted
    assert st == "awaiting_permission"
    assert probe.store.executed == []
    sess = probe.stored_session(aid, sid)
    assert tool_call_states(sess) == [("Charge", "asking")]
    assert sess.state.permission_context.mode.value == "dont_ask"

    # what on_reply saw: the confirm request, no ReplyEndEvent; the last item is the 'waiting' Msg
    turn = probe.store.turns[-1]
    assert turn["parked"] is True and turn["end"] is None
    assert "RequireUserConfirmEvent" in turn["events"] and "ReplyEndEvent" not in turn["events"]
    assert turn["last_item"] not in (None, "ReplyEndEvent")
    assert turn["error"] is None and turn["done"]
    print("PARKED TURN EVENTS:", turn["events"], "last_item:", turn["last_item"])

    # one row, with what we need to resume
    (rec,) = probe.store.pending()
    assert rec.tool_name == "Charge" and json.loads(rec.arguments) == {"amount": 550000, "note": "x"}
    assert rec.arguments == canonical({"note": "x", "amount": 550000})
    assert rec.arguments_hash == args_hash(rec.arguments)
    assert rec.session_id == sid and rec.agent_id == aid and rec.reply_id
    # the model was called once and has not seen a tool result
    assert len(llm.CALLS) == 1


# ---------------------------------------------------------------- 2. resume: approve, reject

def _park(probe, system_prompt="You are a probe agent."):
    llm.POLICY["fn"] = charge_once
    aid, sid = probe.new_session(system_prompt)
    probe.say(aid, sid, "please charge 550000")
    probe.wait_for(lambda: probe.store.pending(), what="approval row")
    assert probe.settle(aid, sid) == "awaiting_permission"
    (rec,) = probe.store.pending()
    return aid, sid, rec


def test_resume_approve_via_post_chat_runs_tool_once_and_asks_once(probe):
    aid, sid, rec = _park(probe)
    probe.store.decide(rec, True)
    event = confirm_event_from_record(rec, True)
    assert event.confirm_results[0].rules is None
    r = probe.chat_event(aid, sid, event)
    assert r.status_code == 200 and r.json()["status"] == "started"

    probe.wait_for(lambda: probe.store.turns[-1]["done"] and probe.store.turns[-1]["input"] == "UserConfirmResultEvent",
                   what="resume turn end")
    assert probe.settle(aid, sid) == "idle"
    assert probe.store.executed == [{"tool": "Charge", "amount": 550000, "note": "x"}]  # exactly once

    # the gate saw the call twice (PENDING then ALLOWED), asked once, created one row
    seen = [(c["state"], c["decision"]) for c in probe.store.checks]
    assert seen == [("pending", "ask"), ("allowed", "pass")], seen
    assert len(probe.store.rows) == 1

    # the resume turn ended normally this time, and the model saw the tool result
    turn = probe.store.turns[-1]
    assert turn["input"] == "UserConfirmResultEvent" and turn["end"] and "completed" in turn["end"].lower()
    assert len(llm.CALLS) == 2 and "charged 550000" in " ".join(results_of(llm.CALLS[-1]["msgs"], "Charge"))
    sess = probe.stored_session(aid, sid)
    assert tool_call_states(sess) == [("Charge", "finished")]
    # no standing allow rule was left in the session's permission context
    assert not sess.state.permission_context.allow_rules


def test_resume_reject_returns_denied_and_tool_never_runs(probe):
    aid, sid, rec = _park(probe)
    probe.store.decide(rec, False)
    probe.chat_event(aid, sid, confirm_event_from_record(rec, False))
    probe.wait_for(lambda: probe.store.turns[-1]["done"] and probe.store.turns[-1]["input"] == "UserConfirmResultEvent")
    assert probe.settle(aid, sid) == "idle"
    assert probe.store.executed == []
    sess = probe.stored_session(aid, sid)
    assert ("Charge", "denied") in tool_result_states(sess)
    # the model was told it was denied
    assert "denied" in " ".join(results_of(llm.CALLS[-1]["msgs"], "Charge")).lower()
    # a rejected call never reaches on_check_permission again
    assert [c["state"] for c in probe.store.checks] == ["pending"]


def test_resume_via_enqueue_run_trigger(probe):
    """The in-process path: no HTTP, kind='resume' on the app's bus."""
    from agentscope.app._bus_ops import enqueue_run_trigger
    aid, sid, rec = _park(probe)
    probe.store.decide(rec, True)

    async def go():
        await enqueue_run_trigger(probe.app.state.message_bus, "awp:probe", sid, aid, kind="resume",
                                  inputs=confirm_event_from_record(rec, True))
    probe.c.portal.call(go)
    probe.wait_for(lambda: probe.store.executed, what="tool run")
    assert probe.settle(aid, sid) == "idle"
    assert len(probe.store.executed) == 1 and len(probe.store.rows) == 1


def test_tampered_resume_input_is_refused_by_the_gate(probe):
    """If someone resumes with other arguments than we showed, AgentScope would run them (it copies
    the event's input into the call); our gate must catch that on the ALLOWED pass."""
    aid, sid, rec = _park(probe)
    probe.store.decide(rec, True)
    evil = confirm_event_from_record(rec, True)
    evil.confirm_results[0].tool_call.input = json.dumps({"amount": 9999999, "note": "x"})
    probe.chat_event(aid, sid, evil)
    probe.wait_for(lambda: probe.store.turns[-1]["done"] and probe.store.turns[-1]["input"] == "UserConfirmResultEvent")
    assert probe.settle(aid, sid) == "idle"
    assert probe.store.executed == []
    assert [(c["state"], c["decision"]) for c in probe.store.checks] == [("pending", "ask"), ("allowed", "deny")]
    sess = probe.stored_session(aid, sid)
    assert ("Charge", "denied") in tool_result_states(sess)


# ---------------------------------------------------------------- 3. a normal message while parked

def test_user_message_while_parked_errors_is_persisted_and_stays_out_of_context(probe):
    aid, sid, rec = _park(probe)
    n_model_calls = len(llm.CALLS)
    before = probe.messages(aid, sid)
    live = probe.tail_events(sid)

    r = probe.say(aid, sid, "actually, ignore the charge and tell me a joke")
    print("POST /chat while parked ->", r.status_code, r.text)
    assert r.status_code == 200 and r.json()["status"] == "started"  # fire and forget: no error to the caller
    probe.wait_for(lambda: len(probe.store.turns) >= 2 and probe.store.turns[-1]["done"], what="second turn end")
    t2 = probe.store.turns[-1]
    print("TURN 2:", t2)

    # the exact failure, seen by our on_reply
    assert t2["input"] == "Msg"
    assert t2["error"] is not None and t2["error"].startswith("ValueError")
    assert "waiting for 1 tool calls" in t2["error"] and "received no event" in t2["error"]
    assert t2["events"] == []                    # nothing was emitted: no ReplyStart/End for the caller to see
    assert len(llm.CALLS) == n_model_calls       # the model was not called

    # what a stream subscriber (the SSE relay) sees: a synthetic start/end ERROR pair, new reply id
    probe.wait_for(lambda: any(e.get("type") == "REPLY_END" for e in live), what="synthetic reply_end")
    ends = [e for e in live if e.get("type") == "REPLY_END"]
    print("LIVE EVENTS:", [(e.get("type"), e.get("finished_reason"), (e.get("error") or {}).get("type")) for e in live])
    assert len(ends) == 1 and ends[0]["finished_reason"] == "error" and ends[0]["reply_id"] != rec.reply_id
    print("ERROR PAYLOAD:", ends[0]["error"])

    # still parked and still resumable
    assert probe.settle(aid, sid) == "awaiting_permission"
    sess = probe.stored_session(aid, sid)
    assert tool_call_states(sess) == [("Charge", "asking")]

    # the message was persisted in the messages table (user role) ...
    after = probe.messages(aid, sid)
    new = [m for m in after if m["id"] not in {x["id"] for x in before}]
    print("NEW PERSISTED MESSAGES:", [(m["role"], str(m["content"])[:80]) for m in new])
    assert any(m["role"] == "user" and "tell me a joke" in json.dumps(m["content"]) for m in new)
    # ... but it is NOT in the agent context
    assert "joke" not in json.dumps([m.model_dump(mode="json") for m in sess.state.context])
    # the parked reply's own message was not overwritten by the stub
    parked_msg = next(m for m in after if m["id"] == rec.reply_id)
    assert any(b.get("type") == "tool_call" for b in parked_msg["content"])

    # and the approval still works afterwards; the model never sees the stray message
    probe.store.decide(rec, True)
    probe.chat_event(aid, sid, confirm_event_from_record(rec, True))
    probe.wait_for(lambda: probe.store.executed, what="tool run")
    assert probe.settle(aid, sid) == "idle"
    assert "joke" not in json.dumps(llm.CALLS[-1]["msgs"])
    assert len(probe.store.executed) == 1


# ---------------------------------------------------------------- 4. a team member (worker) asks

def team_policy(sys, msgs, tools):
    if "a member of team" in sys:  # worker (AgentScope's default worker prompt)
        if n_calls(msgs, "Charge") == 0:
            return [("Charge", {"amount": 700000, "note": "worker"})]
        return "Charged by the worker."
    if n_calls(msgs, "TeamCreate") == 0:
        return [("TeamCreate", {"name": "t1", "description": "charge team"})]
    if n_calls(msgs, "AgentCreate") == 0:
        return [("AgentCreate", {"name": "w1", "description": "does the charge",
                                 "prompt": "Charge 700000 to the resident."})]
    return "Waiting for the team."


@pytest.mark.parametrize("via", ["worker", "leader"])
def test_worker_tool_call_parks_and_can_be_resumed(probe, via):
    llm.POLICY["fn"] = team_policy
    laid, lsid = probe.new_session("You are the leader.")
    live = probe.tail_events(lsid)
    probe.say(laid, lsid, "get it charged")
    rec = probe.wait_for(lambda: probe.store.pending() and probe.store.pending()[0], what="worker approval row")[0] \
        if False else probe.wait_for(lambda: (probe.store.pending() or [None])[0], what="worker approval row")
    assert rec.session_id != lsid and rec.agent_id != laid                    # it is the worker's call
    assert probe.settle(rec.agent_id, rec.session_id) == "awaiting_permission"  # worker parked
    probe.wait_for(lambda: probe.settle(laid, lsid) == "idle", what="leader idle")
    assert probe.store.executed == []
    wturn = [t for t in probe.store.turns if t["session"] == rec.session_id][-1]
    assert wturn["parked"] and wturn["end"] is None

    # AgentScope mirrors the worker's request onto the leader's channel
    mirrored = probe.wait_for(lambda: [e for e in live if e.get("name") == "subagent_require_user_confirm"],
                              what="mirrored card")
    print("LEADER SAW:", {k: v for k, v in mirrored[0]["value"].items() if k != "event"})
    assert mirrored[0]["value"]["worker_session_id"] == rec.session_id

    probe.store.decide(rec, True)
    ev = confirm_event_from_record(rec, True)
    if via == "worker":      # what the spec stores: the worker's own session and agent ids
        r = probe.chat_event(rec.agent_id, rec.session_id, ev)
    else:                    # the leader is the front door; AgentScope routes by reply_id
        r = probe.chat_event(laid, lsid, ev)
    print("RESUME via", via, "->", r.status_code, r.text)
    assert r.status_code == 200
    probe.wait_for(lambda: probe.store.executed, what="worker tool run")
    assert probe.settle(rec.agent_id, rec.session_id) == "idle"
    assert probe.store.executed == [{"tool": "Charge", "amount": 700000, "note": "worker"}]
    seen = [(c["session"] == rec.session_id, c["state"], c["decision"]) for c in probe.store.checks]
    assert seen == [(True, "pending", "ask"), (True, "allowed", "pass")], seen
    assert len(probe.store.rows) == 1
    # the card on the leader is cleared
    probe.wait_for(lambda: [e for e in live if e.get("name") == "subagent_user_confirm_result"], what="card cleared")


# ---------------------------------------------------------------- 5. ask must be idempotent; two calls; cancel

def test_asking_again_for_the_same_call_does_not_create_a_second_row(probe):
    """What a re-run of a lost turn would do: same (session, tool_call.id) -> same row."""
    from p0_ask_park_gate import ApprovalGate
    from agentscope.message import ToolCallBlock
    from types import SimpleNamespace
    import asyncio
    gate = ApprovalGate(probe.store, "a1", "s1")
    agent = SimpleNamespace(name="x", state=SimpleNamespace(reply_id="r1"))
    call = ToolCallBlock(id="tc1", name="Charge", input='{"amount": 1, "note": ""}')

    async def nxt(**kw):
        raise AssertionError("must not fall through")

    async def go():
        a = await gate.on_check_permission(agent, {"tool_call": call}, nxt)
        b = await gate.on_check_permission(agent, {"tool_call": call}, nxt)
        return a, b
    a, b = asyncio.run(go())
    assert a.behavior.value == b.behavior.value == "ask"
    assert len(probe.store.rows) == 1


def test_two_gated_calls_in_one_reply_park_one_at_a_time(probe):
    def two(sys, msgs, tools):
        if n_calls(msgs, "Charge") == 0:
            return [("Charge", {"amount": 1, "note": "first"}), ("Charge", {"amount": 2, "note": "second"})]
        return "Both done."
    llm.POLICY["fn"] = two
    aid, sid = probe.new_session()
    probe.say(aid, sid, "charge twice")
    probe.wait_for(lambda: probe.store.pending(), what="first row")
    assert probe.settle(aid, sid) == "awaiting_permission"
    assert [r.arguments for r in probe.store.pending()] == [canonical({"amount": 1, "note": "first"})]
    sess = probe.stored_session(aid, sid)
    print("STATES AFTER FIRST PARK:", tool_call_states(sess))

    first = probe.store.pending()[0]
    probe.store.decide(first, True)
    probe.chat_event(aid, sid, confirm_event_from_record(first, True))
    probe.wait_for(lambda: len(probe.store.pending()) == 1, what="second row")
    assert probe.settle(aid, sid) == "awaiting_permission"
    assert [e["note"] for e in probe.store.executed] == ["first"]
    second = probe.store.pending()[0]
    probe.store.decide(second, False)
    probe.chat_event(aid, sid, confirm_event_from_record(second, False))
    probe.wait_for(lambda: probe.store.turns[-1]["done"] and probe.store.turns[-1]["end"], what="end")
    assert probe.settle(aid, sid) == "idle"
    assert [e["note"] for e in probe.store.executed] == ["first"]
    assert len(probe.store.rows) == 2
    assert "completed" in probe.store.turns[-1]["end"].lower()
    assert ("Charge", "denied") in tool_result_states(probe.stored_session(aid, sid))


def test_cancel_a_parked_approval_with_user_interrupt(probe):
    """Expiry (spec A9): close the parked call with UserInterruptEvent; the session becomes usable again."""
    from agentscope.event import UserInterruptEvent
    from agentscope.app._bus_ops import enqueue_run_trigger
    aid, sid, rec = _park(probe)
    probe.store.decide(rec, False)
    n_model_calls = len(llm.CALLS)

    async def go():
        await enqueue_run_trigger(probe.app.state.message_bus, "awp:probe", sid, aid, kind="resume",
                                  inputs=UserInterruptEvent(reply_id=rec.reply_id))
    probe.c.portal.call(go)
    probe.wait_for(lambda: probe.store.turns[-1]["input"] == "UserInterruptEvent" and probe.store.turns[-1]["done"],
                   what="interrupt turn")
    assert probe.settle(aid, sid) == "idle"
    sess = probe.stored_session(aid, sid)
    print("AFTER INTERRUPT:", tool_result_states(sess), probe.store.turns[-1])
    assert probe.store.executed == []
    assert len(llm.CALLS) == n_model_calls                      # an interrupt does not reason
    assert probe.store.turns[-1]["end"].lower().endswith("interrupted")
    assert tool_result_states(sess) == [("Charge", "interrupted")]
    # now a normal message goes through
    llm.POLICY["fn"] = lambda s, m, t: "Hello again."
    probe.say(aid, sid, "hi")
    probe.wait_for(lambda: probe.store.turns[-1]["input"] == "Msg" and probe.store.turns[-1]["done"] and probe.store.turns[-1]["end"])
    assert probe.settle(aid, sid) == "idle"


# ---------------------------------------------------------------- 6. races, duplicates, ordering

def test_resume_posted_before_the_parked_turn_has_released_the_session(probe):
    """We may decide the instant the row exists, while the parked run is still finishing."""
    llm.POLICY["fn"] = charge_once
    aid, sid = probe.new_session()
    probe.say(aid, sid, "charge")
    rec = probe.wait_for(lambda: (probe.store.pending() or [None])[0], what="row")
    probe.store.decide(rec, True)
    assert probe.chat_event(aid, sid, confirm_event_from_record(rec, True)).status_code == 200
    probe.wait_for(lambda: probe.store.executed, what="tool run")
    assert probe.settle(aid, sid) == "idle"
    assert len(probe.store.executed) == 1


def test_same_approval_sent_twice_runs_the_tool_once(probe):
    """Backstop below our own idempotency: AgentScope rejects the second event for a call no longer ASKING."""
    aid, sid, rec = _park(probe)
    probe.store.decide(rec, True)
    ev = confirm_event_from_record(rec, True)
    probe.chat_event(aid, sid, ev)
    probe.chat_event(aid, sid, ev)
    probe.wait_for(lambda: len(probe.store.turns) >= 3 and probe.store.turns[-1]["done"] and probe.store.turns[-2]["done"],
                   what="both resume turns")
    assert probe.settle(aid, sid) == "idle"
    assert len(probe.store.executed) == 1
    resume_turns = [t for t in probe.store.turns if t["input"] == "UserConfirmResultEvent"]
    print("RESUME TURNS:", [(t["end"], t["error"]) for t in resume_turns])
    assert len(resume_turns) == 2
    assert sum(1 for t in resume_turns if t["error"]) == 1
    assert "not waiting for user confirmation" in [t["error"] for t in resume_turns if t["error"]][0]


def test_first_middleware_in_the_list_is_outermost_so_profile_denial_must_come_before_consent(tmp_path):
    """A DENY from a middleware ahead of the gate wins; a middleware behind it never sees an ASKed call.
    (This is why spec 6.1 puts the consent check inside ToolGateMiddleware, after its profile check.)"""
    from agentscope.middleware import MiddlewareBase
    from agentscope.permission import PermissionBehavior, PermissionDecision
    seen = []

    class ProfileDeny(MiddlewareBase):
        async def on_check_permission(self, agent, input_kwargs, next_handler):
            seen.append("outer")
            return PermissionDecision(behavior=PermissionBehavior.DENY, message="not in profile")

    store = ApprovalStore()
    with FakeServer() as fake:
        app = build_probe_app(tmp_path, store, before=[ProfileDeny()])
        with TestClient(app) as client:
            probe = Probe(client, fake.base_url, store, app)
            llm.POLICY["fn"] = charge_once
            aid, sid = probe.new_session()
            probe.say(aid, sid, "charge")
            probe.wait_for(lambda: probe.store.turns and probe.store.turns[-1]["done"], what="turn")
            assert probe.settle(aid, sid) == "idle"
    assert seen == ["outer"] and store.rows == {} and store.executed == []
