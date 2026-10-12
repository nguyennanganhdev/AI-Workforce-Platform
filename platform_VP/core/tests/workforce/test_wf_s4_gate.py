"""The approval gate and CaseAskConsent (slice S4): what parks, what runs, what can never run twice, two approvals
in one reply, a specialist that asks, an approval that runs out or is cancelled, and the tool gate for a case with no workflow."""
from __future__ import annotations

import threading
import time

import consentkit as ck
import scripts
from enginekit import hold_leader, world
from fake_llm import CALLS, MODE
from test_wf_commands import counts
from test_wf_errors import assert_envelope
from test_wf_s3_guard import evidence
from test_wf_s4_flow import TOOLS, _clean, text_of, texts, trip  # noqa: F401 - _clean is an autouse fixture

from awp.protocol.consent import CaseAskConsent
from awp.workforce import tables as t
from awp.workforce.approvals import ConsentGate, canonical
from awp.workforce.resume import event_for


def session_status(w, wid: str) -> str:
    """AgentScope's own word for the leader's session: idle, running or awaiting_permission."""
    agent_id, session_id = w.sql("select leader_agent_id, leader_session_id from awp_cases where id="
                                 "(select case_id from wf_workflows where id=?)", (wid,))[0]
    client = w.engine.client
    r = w.run(lambda: client._http.get(f"/sessions/{session_id}/status", headers=client._h("ta"),
                                       params={"agent_id": agent_id}))
    return r.json()["status"]


def approval_rows(w) -> list[tuple]:
    return w.sql("select status, tool_name, used_at is not null, resumed_at is not null from wf_approvals order by created_at")


# ---- the gate parks, and nothing runs on the agent's say-so --------------------------------------------------------
def test_the_gate_parks_the_run_writes_one_approval_and_asks_once(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        start, first, second = trip(w)
        wid = first["workflow_id"]
        assert approval_rows(w) == [("pending", "book_hotel", False, False)]
        assert round(w.sql("select expires_at - created_at from wf_approvals")[0][0]) == 24 * 3600  # the platform default
        assert session_status(w, wid) == "awaiting_permission"  # parked, not finished
        assert w.sql("select status from wf_turns where workflow_id=? order by started_at desc limit 1", (wid,)) == [("parked",)]
        [(row,)] = w.sql("select arguments from wf_approvals")
        assert row == canonical(ck.BOOK)  # the canonical JSON, keys sorted: what the hash covers
        [(sess, agent, reply, rev)] = w.sql("select session_id, agent_id, reply_id, workflow_revision from wf_approvals")
        lead = w.sql("select leader_session_id, leader_agent_id from awp_cases where id=(select case_id from wf_workflows)")
        assert lead == [(sess, agent)] and reply  # the leader asked; the parked reply is remembered
        assert w.state(wid) == ("awaiting_approval", rev)  # one bump: the state and the approval changed together
        assert ck.BOOKED == []
        # the agent never asks twice for the same call: a re-evaluation finds the row
        gate_calls = w.sql("select count(*) from wf_events where event_type='approval.required'")
        assert gate_calls == [(1,)]


def test_a_workflow_with_a_pending_approval_takes_no_reply_and_sends_nothing_to_agentscope(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        wid = first["workflow_id"]
        [appr] = f.approvals(first["conversation_id"])
        seen, before = len(CALLS), counts(w.env)
        body = f.reply_body(first, start)
        for _ in range(2):  # and again with the same id: nothing was stored, so nothing is replayed
            err = assert_envelope(f.post(body), 409, "APPROVAL_PENDING")
            assert err["details"] == {"approval_id": appr["approval_id"]}
        assert counts(w.env) == before and len(CALLS) == seen
        assert session_status(w, wid) == "awaiting_permission"  # still parked: AgentScope was never called
        # a reply that was accepted before the approval is replayed from its stored result, not refused
        rq = w.sql("select external_request_id from wf_requests where id=?", (second["request_id"],))[0][0]
        replay = f.post(f.reply_body(first, start, external_request_id=rq, message=text_of(ck.CHOOSE)))
        assert replay.status_code == 200 and replay.json()["request_id"] == second["request_id"]


def test_a_reply_accepted_while_the_agent_works_waits_for_the_answer_instead_of_reaching_the_parked_agent(tmp_path):
    """The reply is accepted (the workflow is still active), then the run parks: the engine sends the answer to the
    approval first and the reply after it, never the reply to a parked session (P0: such a message is lost)."""
    with world(tmp_path, ck.trip, route={"wait_seconds": 2.0}, **TOOLS) as w:
        f = w.flow
        ck.declare(w)
        start, first = f.begin(message=text_of(ck.START))
        gate = hold_leader()
        out: dict = {}
        t1 = threading.Thread(target=lambda: out.update(a=f.reply(start, first, message=text_of(ck.CHOOSE))[0]))
        t1.start()
        w.wait(lambda: w.sql("select 1 from wf_turns where status='running'"), what="the model to be thinking about the booking")
        t2 = threading.Thread(target=lambda: out.update(b=f.reply(start, first, message=text_of("Also a late checkout."))[0]))
        t2.start()
        t1.join(30)
        t2.join(30)
        gate.set()
        wid = first["workflow_id"]
        w.wait(lambda: len(f.approvals(first["conversation_id"])) == 1, what="the approval")
        time.sleep(2.5)  # the engine had every chance to send the second reply
        for k in "ab":  # the workflow waits for the resident: both requests say so, the held-back one too
            got = f.request(out[k].json()["request_id"]).json()
            assert (got["request_status"], got["workflow_state"], got["next_action"]) == (
                "completed", "awaiting_approval", "submit_approval"), (k, got)
        assert w.sql("select status from wf_jobs where kind='resident_message' order by created_at") == [
            ("done",), ("done",), ("queued",)]
        assert session_status(w, wid) == "awaiting_permission" and not [c for c in CALLS if "late checkout" in str(c["shape"])]
        [appr] = f.approvals(first["conversation_id"])
        assert f.decide(appr["approval_id"], f.decide_body(start, first, appr)).status_code == 202
        w.wait_state(wid, "awaiting_user")
        w.quiet()
        assert ck.BOOKED == [ck.BOOK] and w.sql("select status from wf_jobs where kind='resident_message'") == [("done",)] * 3
        turns = w.sql("select msg_id from wf_turns where workflow_id=? order by started_at", (wid,))
        order = [m[0].split("_")[0] for m in turns if m[0]]
        assert order.index("resume") < len(order) - 1  # the answer was taken before the late reply
        assert w.sql("select status from wf_requests order by accepted_at") == [("completed",)] * 4


# ---- what the gate lets through ----------------------------------------------------------------------------------
def test_a_replayed_resume_event_cannot_run_the_tool_twice(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        [appr] = f.approvals(first["conversation_id"])
        assert f.decide(appr["approval_id"], f.decide_body(start, first, appr)).status_code == 202
        w.wait_state(first["workflow_id"], "awaiting_confirmation")
        w.quiet()
        assert ck.BOOKED == [ck.BOOK] and approval_rows(w) == [("approved", "book_hotel", True, True)]

        # the engine's event arrives again (a crash before it noted the job done): the agent is not waiting any more
        [row] = w.run(lambda: _rows(w))
        lead = w.sql("select leader_agent_id, leader_session_id from awp_cases where id=(select case_id from wf_workflows)")[0]
        w.run(lambda: w.engine.client.confirm("ta", lead[0], lead[1], event_for(row)))
        w.quiet()
        time.sleep(1.0)
        assert ck.BOOKED == [ck.BOOK]

        # and if AgentScope did take it (its state lost in the crash), the row is what refuses: used once
        gate = ConsentGate(w.rt, None)
        w.sql("update wf_approvals set used_at=NULL")
        [row] = w.run(lambda: _rows(w))
        assert w.run(lambda: gate._existing(row, row["arguments_hash"])) is None  # the first pass
        refused = w.run(lambda: gate._existing(row, row["arguments_hash"]))
        assert refused is not None and "already used" in refused.message


async def _rows(w):
    async with w.rt.db.engine.connect() as conn:
        from sqlalchemy import select
        return [dict(r) for r in (await conn.execute(select(t.approvals))).mappings().all()]


def test_the_gate_lets_through_only_what_the_resident_approved(tmp_path):
    """AgentScope copies the arguments of the resume event into the call: an allow nobody decided on, or a call whose
    arguments are not the ones the resident saw, is denied and the tool does not run."""
    with world(tmp_path, ck.trip, **TOOLS) as w:
        f = w.flow
        ck.declare(w)
        for case in ("undecided", "changed"):
            start, first, second = trip(w)
            wid = first["workflow_id"]
            [row] = [r for r in w.run(lambda: _rows(w)) if r["workflow_id"] == wid]
            if case == "changed":  # the row says approved, the event carries other arguments
                w.sql("update wf_approvals set status='approved' where id=?", (row["id"],))
                row = {**row, "status": "approved"}
            event = event_for({**row, "status": "approved"})
            if case == "changed":
                event.confirm_results[0].tool_call.input = canonical({**ck.BOOK, "price": "1"})
            w.run(lambda: w.engine.client.confirm("ta", row["agent_id"], row["session_id"], event))
            w.wait(lambda: w.sql("select count(*) from wf_turns where msg_id=? and status != 'running'",
                                 (f"resume_{row['id']}",)) == [(1,)], what="the denied turn")
            assert ck.BOOKED == [], case
            mine = w.sql("select status, used_at is not null from wf_approvals where id=?", (row["id"],))
            assert mine == [("approved" if case == "changed" else "pending", False)], case
            why = {"undecided": "has not agreed to this call", "changed": "differ from the ones the resident agreed to"}
            assert why[case] in " ".join(str(x) for x in CALLS[-1]["shape"])  # the model is told why


def test_a_wrong_total_is_refused_and_asks_nobody(tmp_path):
    with world(tmp_path, ck.consenting(total="1900000"), **TOOLS) as w:
        f = w.flow
        ck.declare(w)
        start, first = f.begin(message=text_of(ck.START))
        r = f.reply(start, first, message=text_of(ck.CHOOSE))[0].json()
        assert texts(r) == ["I cannot confirm the total yet; a person will follow up."]
        assert (r["workflow_state"], r["next_action"]) == ("awaiting_user", "submit_reply")
        assert w.sql("select count(*) from wf_approvals") == [(0,)]  # the resident was never asked
        assert w.sql("select count(*) from wf_events where event_type='approval.required'") == [(0,)]
        shape = " ".join(str(x) for x in CALLS[-1]["shape"])
        assert "is not the sum of the items (1890000)" in shape  # the model was told why, and could fix it
        assert w.sql("select count(*) from awp_case_items where kind='evidence' and cast(data as text) like '%resident approved%'") == [(0,)]
        assert w.state(first["workflow_id"])[0] == "awaiting_user"


def test_consent_to_a_cost_is_recorded_as_evidence_and_a_refusal_is_denied(tmp_path):
    with world(tmp_path, ck.consenting(total="1900000", retry="1890000"), **TOOLS) as w:
        f = w.flow
        ck.declare(w)
        start, first = f.begin(message=text_of(ck.START))
        r = f.reply(start, first, message=text_of(ck.CHOOSE))[0].json()
        assert r["workflow_state"] == "awaiting_approval"
        assert w.sql("select count(*) from wf_approvals") == [(1,)]  # the wrong total made none; the right one did
        [appr] = f.approvals(first["conversation_id"])
        assert appr["tool_name"] == "CaseAskConsent" and appr["quote_ref"] is None
        assert appr["summary"] == {"text": "Book Sunrise for 2 nights", "total": "1890000", "items": [
            {"label": "Sunrise 2 nights", "amount": "1800000"}, {"label": "Service fee", "amount": "90000"}]}
        assert w.sql("select count(*) from awp_case_items where kind='evidence' and cast(data as text) like '%resident approved%'") == [(0,)]
        d = f.decide(appr["approval_id"], f.decide_body(start, first, appr))
        assert d.status_code == 202
        w.wait_state(first["workflow_id"], "awaiting_confirmation")
        [(data,)] = w.sql("select data from awp_case_items where kind='evidence' and cast(data as text) like '%resident approved%'")
        assert "resident approved the consent request, total 1890000" in data  # our words, not the model's summary
        assert "CaseAskConsent" in data and "Sunrise" not in data
        got = f.request(w.sql("select id from wf_requests where command_type='submit_consent'")[0][0]).json()
        assert texts(got) == ["Thank you, you agreed to 1890000 VND."]


def test_a_consent_the_resident_refuses_is_denied_and_leaves_no_evidence(tmp_path):
    with world(tmp_path, ck.consenting(), **TOOLS) as w:
        f = w.flow
        ck.declare(w)
        start, first = f.begin(message=text_of(ck.START))
        f.reply(start, first, message=text_of(ck.CHOOSE))
        [appr] = f.approvals(first["conversation_id"])
        assert f.decide(appr["approval_id"], f.decide_body(start, first, appr, "reject")).status_code == 202
        w.wait_state(first["workflow_id"], "awaiting_user")
        assert w.sql("select count(*) from awp_case_items where kind='evidence' and cast(data as text) like '%resident approved%'") == [(0,)]
        assert "denied by user" in " ".join(str(x) for x in CALLS[-1]["shape"])


def test_review_of_a_consent_names_every_defect_before_the_resident_is_asked(tmp_path):
    with world(tmp_path, scripts.interactive) as w:
        _, r = w.flow.begin()
        from test_wf_say import Room
        room = Room(w, r["workflow_id"])
        hotels = evidence(w, room, "hotel_search", ck.HOTELS)
        ok_total = evidence(w, room, "calc_sum", "sum of booking: 1890000 (from 2 amounts: 1800000, 90000)")
        items = [{"label": "Sunrise 2 nights", "amount": "1800000"}, {"label": "Service fee", "amount": "90000"}]
        good = dict(summary="Book Sunrise for 2 nights", items=items, total="1890000", cites=[hotels, ok_total])

        def review(who=None, **over):
            tool = CaseAskConsent(w.rt, who or room.b)
            return w.run(lambda: tool.review(**{**good, **over}))

        assert review() == (None, {"text": "Book Sunrise for 2 nights", "items": items, "total": "1890000"})
        assert review(total=1890000)[0] is None  # a number is as good as a string
        for over, why in (
                (dict(total="1900000"), "is not the sum of the items (1890000)"),
                (dict(total="1,890,000"), None),  # separators are fine
                (dict(total="abc"), "not an amount"),
                (dict(total="NaN", items=[{"label": "a", "amount": "NaN"}]), "not an amount"),
                (dict(total="Infinity", items=[{"label": "a", "amount": "Infinity"}]), "not an amount"),
                (dict(total="7", items=[{"label": "a", "amount": "1E+5000"}]), "not an amount"),
                (dict(items=[{"label": "a" * 121, "amount": "1800000"}, items[1]], total="1890000"), "label is at most"),
                (dict(items=[]), "items must be a list"),
                (dict(items=["x"]), "items must be a list"),
                (dict(items=[{"label": "", "amount": "1"}]), "needs a label"),
                (dict(items=[{"label": "a", "amount": "-5"}], total="-5"), "not an amount"),
                (dict(items=[{"label": "a", "amount": "0"}], total="0"), "above zero"),
                (dict(cites=[]), "cite the evidence"),
                (dict(cites=["E99"]), "cannot cite"),
                (dict(cites=[hotels]), "figures not found in the cited evidence: 1890000"),  # the sum is not cited
                (dict(cites=[ok_total]), "calc_sum whose amounts are not stated"),  # a sum alone proves nothing
                (dict(summary="  "), "summary is wrong"),
                (dict(summary="Book it for two million"), "written in words"),
                (dict(summary="Book Sunrise for 3 nights"), "figures not found"),
                (dict(quote_ref="x" * 81), "quote_ref"),
                (dict(quote_ref="QX-9917"), "is in none of the items you cite")):
            err, shown = review(**over)
            if why is None:
                assert err is None, (over, err)
            else:
                assert err and why in err and shown == {}, (over, err)
        worker = review(who=type(room.b)(room.b.case_id, "s", "a", "tech", "worker", "u"))
        assert worker[0] == "Only the leader can do this."
        w.run(lambda: w.rt.cases.update_case(room.case_id, status="closed"))
        assert "closed" in review()[0]
        old = w.run(lambda: w.rt.cases.create_case(tenant="ta", domain="test", external_ref="OLD-9", user_id="awp:ta", meta={}))
        stray = type(room.b)(old, "s", "a", "case-leader", "leader", "u")
        assert review(who=stray)[0] == "CaseAskConsent works only inside a workflow."


# ---- two approvals in one reply, and a specialist that asks ------------------------------------------------------------
def test_two_tools_that_need_consent_in_one_reply_park_one_after_the_other(tmp_path):
    with world(tmp_path, ck.two_books, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        wid, conv = first["workflow_id"], first["conversation_id"]
        [one] = f.approvals(conv)
        assert one["summary"]["arguments"] == ck.BOOK and approval_rows(w) == [("pending", "book_hotel", False, False)]
        d1 = f.decide(one["approval_id"], f.decide_body(start, first, one))
        assert d1.status_code == 202
        two = w.wait(lambda: [a for a in f.approvals(conv) if a["approval_id"] != one["approval_id"]], what="the second approval")[0]
        assert two["summary"]["arguments"] == ck.BOOK2 and two["expected_revision"] > one["expected_revision"]
        assert w.state(wid) == ("awaiting_approval", two["expected_revision"])  # parked again, one more revision
        assert ck.BOOKED == [ck.BOOK]  # the first ran once, the second waits
        # the request of the first decision settled: its answer is "decide the next one"
        w.wait(lambda: w.sql("select status from wf_requests where command_type='submit_consent'") == [("completed",)], what="the request")
        rid = w.sql("select id from wf_requests where command_type='submit_consent'")[0][0]
        got = f.request(rid).json()
        assert (got["workflow_state"], got["next_action"], got["result"]) == ("awaiting_approval", "submit_approval", {"messages": []})
        # the old revision no longer fits, the new one does
        late = f.decide_body(start, first, two, expected_revision=one["expected_revision"])
        assert_envelope(f.decide(two["approval_id"], late), 409, "REVISION_CONFLICT")
        assert f.decide(two["approval_id"], f.decide_body(start, first, two)).status_code == 202
        w.wait_state(wid, "awaiting_confirmation")
        assert ck.BOOKED == [ck.BOOK, ck.BOOK2]
        assert approval_rows(w) == [("approved", "book_hotel", True, True)] * 2


def test_a_specialist_that_asks_is_woken_in_its_own_session(tmp_path):
    with world(tmp_path, ck.via_tech, leader_tools=["hotel_search"], worker_tools=["book_hotel"], tools=[ck.factory]) as w:
        MODE["worker"] = ck.tech_books
        f = w.flow
        ck.declare(w)
        start, first = f.begin(message=text_of(ck.START))
        assert (first["workflow_state"], first["next_action"]) == ("awaiting_approval", "submit_approval")
        [(sess, agent, name)] = w.sql("select a.session_id, a.agent_id, s.agent_name from wf_approvals a "
                                      "join awp_case_sessions s on s.session_id=a.session_id")
        lead = w.sql("select leader_session_id, leader_agent_id from awp_cases where id=(select case_id from wf_workflows)")
        assert name == "tech" and (sess, agent) != lead[0]  # the specialist asked, not the leader
        [appr] = f.approvals(first["conversation_id"])
        assert f.decide(appr["approval_id"], f.decide_body(start, first, appr)).status_code == 202
        r = w.wait_state(first["workflow_id"], "awaiting_confirmation")
        assert ck.BOOKED == [ck.BOOK] and approval_rows(w) == [("approved", "book_hotel", True, True)]
        assert [m[1] for m in w.messages(first["workflow_id"])][-1] == "Booked: BK-77 at Sunrise. Is everything right?"


def test_a_leader_and_a_specialist_parked_at_once_are_decided_one_by_one(tmp_path):
    with world(tmp_path, ck.both, leader_tools=["hotel_search", "book_hotel"], worker_tools=["book_hotel"], tools=[ck.factory]) as w:
        MODE["worker"] = ck.tech_books
        f = w.flow
        ck.declare(w)
        start, first = f.begin(message=text_of(ck.START))
        wid, conv = first["workflow_id"], first["conversation_id"]
        both = w.wait(lambda: len(f.approvals(conv)) == 2 and f.approvals(conv), what="both approvals")
        mine = {a["summary"]["arguments"]["hotel"]: a for a in both}  # Lotus: the leader's, Sunrise: the technician's
        assert set(mine) == {"Lotus", "Sunrise"} and len({a["expected_revision"] for a in both}) == 1
        assert w.state(wid) == ("awaiting_approval", both[0]["expected_revision"]) and ck.BOOKED == []
        assert w.sql("select count(*) from wf_events where event_type='approval.required'") == [(2,)]
        # the leader's is decided: the technician's still waits, so the workflow still asks the resident
        assert f.decide(mine["Lotus"]["approval_id"], f.decide_body(start, first, mine["Lotus"])).status_code == 202
        w.wait(lambda: ck.BOOKED == [ck.BOOK2], what="the leader's booking")
        left = w.wait(lambda: [a for a in f.approvals(conv)] if len(f.approvals(conv)) == 1 and w.state(wid)[0] == "awaiting_approval" else None,
                      what="the technician's approval to be the only one")
        assert left[0]["approval_id"] == mine["Sunrise"]["approval_id"] and left[0]["expected_revision"] == w.state(wid)[1]
        w.quiet()
        late = f.decide_body(start, first, mine["Sunrise"], expected_revision=mine["Sunrise"]["expected_revision"])
        assert_envelope(f.decide(mine["Sunrise"]["approval_id"], late), 409, "REVISION_CONFLICT")  # it moved twice since
        assert f.decide(left[0]["approval_id"], f.decide_body(start, first, left[0])).status_code == 202
        w.wait_state(wid, "awaiting_confirmation")
        assert ck.BOOKED == [ck.BOOK2, ck.BOOK]
        assert approval_rows(w) == [("approved", "book_hotel", True, True)] * 2
