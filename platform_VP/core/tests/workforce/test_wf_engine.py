"""The real engine on the scripted model: one resident message really runs the leader, and the public
result comes only through CaseSay / CaseFinalize (slice S3). Scripted model only; no real LLM."""
from __future__ import annotations

import scripts
from enginekit import hold_leader, world
from fake_llm import CALLS

REPLY = {"message": {"type": "text", "text": "Tôi rảnh từ 14 giờ."}}


def texts(body: dict) -> list[str]:
    return [m["text"] for m in body["result"]["messages"]]


def test_read_only_lookup_ends_closed_none_within_the_wait(tmp_path):
    with world(tmp_path, scripts.lookup) as w:
        _, r = w.flow.begin()
        assert (r["request_status"], r["workflow_state"], r["next_action"]) == ("completed", "closed", "none")
        assert texts(r) == [scripts.TICKET]
        close = w.sql("select close_reason from wf_workflows where id=?", (r["workflow_id"],))
        assert close == [("answered",)]
        assert w.sql("select status from awp_cases where id=(select case_id from wf_workflows where id=?)",
                     (r["workflow_id"],)) == [("closed",)]
        # the model's own words never reach the resident: only the CaseFinalize answer did
        assert [m[0] for m in w.messages(r["workflow_id"])] == ["user", "assistant"]


def test_interactive_flow_awaiting_user_then_reply_then_confirmation(tmp_path):
    with world(tmp_path, scripts.interactive) as w:
        start, first = w.flow.begin()
        assert (first["workflow_state"], first["next_action"]) == ("awaiting_user", "submit_reply")
        assert texts(first) == ["What time suits you?"]
        case = w.sql("select leader_session_id from awp_cases where id=(select case_id from wf_workflows)")
        r = w.flow.reply(start, first, **REPLY)[0]
        assert r.status_code == 200, r.text
        second = r.json()
        assert (second["workflow_state"], second["next_action"]) == ("awaiting_confirmation", "confirm_close")
        assert texts(second) == ["Noted: 14. Can you confirm?"]
        # one long-lived session: the second turn ran on the first one's context
        assert w.sql("select leader_session_id from awp_cases where id=(select case_id from wf_workflows)") == case
        shape = " ".join(str(x) for x in CALLS[-1]["shape"])
        assert "What time suits you?" in shape or "CaseSay" in shape
        assert shape.count('evidence="E') == 2  # one wrapper per message the resident sent; the quotes in the state block have none
        closed = w.flow.close(second, start, revision=second["workflow_revision"])[0]
        assert closed.status_code == 200 and closed.json()["state"] == "closed"


def test_a_worker_consult_wakes_the_leader_and_the_request_settles(tmp_path):
    with world(tmp_path, scripts.consult) as w:
        _, r = w.flow.begin()
        assert (r["request_status"], r["workflow_state"], r["next_action"]) == ("completed", "awaiting_user", "submit_reply")
        assert texts(r) == ["Ticket T-1001 is waiting for the plumber."]
        wid = r["workflow_id"]
        turns = w.sql("select trigger, job_id, status from wf_turns where workflow_id=? order by started_at", (wid,))
        assert len(turns) >= 2 and turns[0][1] is not None
        assert any(t[0] == "continue" and t[1] is None for t in turns)  # the report woke the leader: no job
        assert {t[2] for t in turns} == {"completed"}
        # the leader said nothing while it waited for the report, and nothing was nudged
        assert w.sql("select count(*) from wf_jobs where kind='nudge'") == [(0,)]


def test_an_ungrounded_figure_is_refused_and_never_reaches_the_resident(tmp_path):
    with world(tmp_path, scripts.ungrounded) as w:
        _, r = w.flow.begin()
        assert texts(r) == ["I cannot give a fee yet; a person will confirm it."]
        wid = r["workflow_id"]
        assert "2000000" not in " ".join(m[1] for m in w.messages(wid))
        assert w.sql("select count(*) from wf_events where cast(payload as text) like '%2000000%'") == [(0,)]
        # the model was told why, so it could fix the text
        assert any("Not sent, the resident has seen nothing" in " ".join(str(x) for x in c["shape"]) for c in CALLS)


def test_a_silent_leader_is_nudged_twice_then_the_workflow_needs_attention(tmp_path):
    rules = {"rules": {"safe_reply": "A person will follow up."}}
    with world(tmp_path, scripts.silent, route=rules) as w:
        _, r = w.flow.begin()
        assert (r["request_status"], r["workflow_state"], r["next_action"]) == ("completed", "needs_attention", "resolve_attention")
        assert texts(r) == ["A person will follow up."]  # the route's safe reply: the only thing the resident reads
        wid = r["workflow_id"]
        assert w.sql("select attention_reason from wf_workflows where id=?", (wid,)) == [("leader_silent",)]
        nudges = w.sql("select status from wf_jobs where kind='nudge'")
        assert nudges == [("done",), ("done",)]
        assert len([c for c in CALLS if "<platform-nudge" in str(c["shape"])]) >= 2
        events = w.sql("select event_type from wf_events where workflow_id=? order by sequence", (wid,))
        assert ("workflow.needs_attention",) in events


def test_a_nudge_that_works_ends_the_chain_without_a_second_one(tmp_path):
    with world(tmp_path, scripts.nudged_once) as w:
        _, r = w.flow.begin()
        assert (r["workflow_state"], texts(r)) == ("awaiting_user", ["Sorry, what do you need?"])
        assert w.sql("select count(*) from wf_jobs where kind='nudge'") == [(1,)]


def test_a_model_failure_needs_attention_and_fails_the_request_with_a_public_error(tmp_path):
    with world(tmp_path, scripts.lookup, wf_job_attempts=2) as w:
        from fake_llm import MODE
        MODE["leader_http"] = 400
        _, r = w.flow.begin()
        assert (r["request_status"], r["workflow_state"], r["next_action"]) == ("failed", "needs_attention", "resolve_attention")
        assert r["error"]["code"] == "engine_error" and "A person will follow up" in r["error"]["message"]
        assert r["result"]["messages"] == []
        wid = r["workflow_id"]
        assert w.sql("select attention_reason from wf_workflows where id=?", (wid,)) == [("engine_error",)]
        assert w.sql("select status, attempts from wf_jobs where workflow_id=?", (wid,)) == [("failed", 2)]
        turns = w.sql("select status from wf_turns where workflow_id=?", (wid,))
        assert turns == [("error",), ("error",)]
        assert "scripted failure" not in str(r)  # nothing of the model's failure leaks


def test_a_slow_turn_answers_202_then_the_result_comes_by_get_and_history(tmp_path):
    with world(tmp_path, scripts.interactive, wf_wait_seconds=0.4) as w:
        gate = hold_leader()
        r, sent = w.flow.start()
        assert r.status_code == 202
        pending = r.json()
        assert pending["request_status"] in ("queued", "running") and pending["next_action"] == "watch_request"
        assert pending["result"] is None
        gate.set()
        done = w.wait(lambda: (g := w.flow.request(pending["request_id"]).json())["request_status"] == "completed" and g,
                      what="the request to complete")
        assert texts(done) == ["What time suits you?"] and done["workflow_state"] == "awaiting_user"
        history = w.flow.history(pending["conversation_id"]).json()["items"]
        said = [e for e in history if e["event_type"] == "assistant.message"]
        assert [e["payload"]["text"] for e in said] == ["What time suits you?"]
        assert said[0]["payload"]["message_id"] == done["result"]["messages"][0]["message_id"]
        snap = w.flow.snapshot(pending["conversation_id"]).json()
        assert [m["text"] for m in snap["messages"] if m["sender"] == "assistant"] == ["What time suits you?"]
        # asking again returns the frozen result: the same message id, no new turn
        again = w.flow.post(sent)
        assert again.status_code == 200 and texts(again.json()) == ["What time suits you?"]
        assert w.sql("select count(*) from wf_turns") == [(1,)]


def test_a_reply_during_a_running_turn_queues_behind_it_and_both_requests_settle(tmp_path):
    with world(tmp_path, scripts.two_answers, wf_wait_seconds=0.3) as w:
        gate = hold_leader()
        r1, start = w.flow.start()
        first = r1.json()
        assert r1.status_code == 202
        r2, _ = w.flow.reply(start, first, message={"type": "text", "text": "SECOND message while you work"})
        assert r2.status_code == 202
        queued = r2.json()
        assert queued["workflow_state"] == "active" and queued["workflow_id"] == first["workflow_id"]
        gate.set()
        a = w.wait(lambda: (g := w.flow.request(first["request_id"]).json())["request_status"] == "completed" and g)
        b = w.wait(lambda: (g := w.flow.request(queued["request_id"]).json())["request_status"] == "completed" and g)
        assert texts(a) == ["First answer."] and texts(b) == ["Second answer."]  # each its own message
        assert a["workflow_state"] == b["workflow_state"] == "awaiting_user"
        turns = w.sql("select started_at, ended_at from wf_turns where workflow_id=? order by started_at",
                      (first["workflow_id"],))
        assert len(turns) == 2 and turns[1][0] >= turns[0][1]  # one turn at a time
        assert w.sql("select status from wf_jobs order by created_at") == [("done",), ("done",)]


def count_turns(w, msg_id=None) -> int:
    if msg_id:
        return w.sql("select count(*) from wf_turns where msg_id=?", (msg_id,))[0][0]
    return w.sql("select count(*) from wf_turns")[0][0]


def test_a_message_no_turn_took_is_sent_again_with_the_same_id(tmp_path):
    # The window decides two things here, and only the first may be a clock: how long the engine waits for the lost send
    # (2 s, then it sends again), and how long the send that did arrive has to show its turn. A first turn takes 0.44-0.70 s
    # to start on a quiet machine (most of it inside AgentScope's agent assembly) and seconds on a loaded one: with one
    # short window for both, the send that arrived was sometimes sent a third time and the count below raced. So the
    # second send gets a window no machine misses.
    with world(tmp_path, scripts.interactive, wf_ack_seconds=2.0) as w:
        real, sent = w.engine.client.say, []

        async def lossy(*a, **kw):
            sent.append(kw["msg_id"])
            if len(sent) == 1:
                return None  # the POST "worked" (a 200) but no turn ever ran: the P0 lost-message path
            object.__setattr__(w.engine.settings, "wf_ack_seconds", 120.0)  # frozen settings: the test's hand on the clock
            return await real(*a, **kw)

        w.engine.client.say = lossy
        _, r = w.flow.begin()
        assert r["workflow_state"] == "awaiting_user" and texts(r) == ["What time suits you?"]
        assert len(sent) == 2 and sent[0] == sent[1] and sent[0].startswith("job_")
        assert count_turns(w, sent[0]) == 1  # one turn, one model run, however often it was sent
        assert len([c for c in CALLS if "resident-message" in str(c["shape"])]) == 2  # CaseSay + closing text
        evidence = w.sql("select data from awp_case_items where kind='evidence' and author='resident'")
        assert len(evidence) == 1  # exactly once per job


def test_a_busy_session_is_waited_for_and_the_message_sent_again(tmp_path):
    from awp.agentscope_client import SessionBusy
    with world(tmp_path, scripts.interactive) as w:
        real, sent = w.engine.client.say, []

        async def busy_first(*a, **kw):
            sent.append(kw["msg_id"])
            if len(sent) == 1:
                raise SessionBusy("a worker's turn holds the session")  # 409: nothing was stored
            object.__setattr__(w.engine.settings, "wf_ack_seconds", 120.0)  # the count below is not a race with the clock
            return await real(*a, **kw)

        w.engine.client.say = busy_first
        _, r = w.flow.begin()
        assert texts(r) == ["What time suits you?"] and len(sent) == 2 and sent[0] == sent[1]
        assert count_turns(w) == 1


def test_each_resident_message_is_recorded_as_evidence_once(tmp_path):
    with world(tmp_path, scripts.interactive) as w:
        start, first = w.flow.begin()
        assert w.flow.reply(start, first, **REPLY)[0].status_code == 200
        rows = w.sql("select ref, data from awp_case_items where kind='evidence' order by id")
        assert [r[0] for r in rows] == ["E1", "E2"]
        import json
        data = [json.loads(r[1]) if isinstance(r[1], str) else r[1] for r in rows]
        assert [d["tool"] for d in data] == ["resident", "resident"]  # what the resident SAID, never a system record
        assert data[1]["text"] == "Tôi rảnh từ 14 giờ." and data[0]["job"] != data[1]["job"]


def test_a_slow_turn_result_arrives_over_sse(tmp_path):
    from flowkit import P, Stream
    with world(tmp_path, scripts.interactive, live=True, wf_wait_seconds=0.3) as w:
        gate = hold_leader()
        r, _ = w.flow.start()
        pending = r.json()
        assert r.status_code == 202
        stream = Stream(w.flow.http, f"{P}/conversations/{pending['conversation_id']}/events", w.flow.h,
                        {"external_user_id": "resident-123"})  # no cursor: replayed from the start, then live
        gate.set()  # the turn ends while the stream is open
        seen = []
        while "workflow.awaiting_user" not in seen:
            frame = stream.next(timeout=15)
            assert frame is not None, f"the stream ended or stalled after {seen}"
            if "data" in frame:
                seen.append(frame["data"]["event_type"])
                if frame["data"]["event_type"] == "assistant.message":
                    assert frame["data"]["payload"]["text"] == "What time suits you?"
        assert seen[0] == "request.accepted" and seen.index("assistant.message") < seen.index("workflow.awaiting_user")
        stream.close()
