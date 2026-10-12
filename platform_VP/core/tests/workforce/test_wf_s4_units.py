"""Pieces of the approval machinery on their own (slice S4): the resolve step on a bare database, the resume event
built from a stored row, and the gate called by hand."""
from __future__ import annotations

import json
import time
from types import SimpleNamespace

import consentkit as ck
import pytest
import scripts
from agentscope.permission import PermissionBehavior
from dbkit import Lab
from enginekit import world
from sqlalchemy import insert, select
from test_wf_s3_guard import evidence
from test_wf_s4_flow import TOOLS

from awp.middleware.room import ToolGateMiddleware
from awp.protocol.consent import CaseAskConsent
from awp.workforce import tables as t
from awp.workforce.approvals import ConsentGate, args_hash, canonical, resolve
from awp.workforce.resume import event_for
from awp.workforce.workflows import bump, transition


@pytest.fixture
def lab(tmp_path):
    lab = Lab(tmp_path / "s4.db")
    yield lab
    lab.close()


def approval(lab, seed, n: int, revision: int) -> dict:
    row = dict(id=f"appr_{n}", workflow_id=seed["wf"]["id"], conversation_id=seed["conv"]["id"], client_id="cl_1",
               external_user_id="resident-1", session_id=f"s{n}", agent_id="a", tool_call_id=f"c{n}", tool_name="book",
               arguments="{}", arguments_hash="sha256:x", summary={}, status="pending", workflow_revision=revision,
               reply_id="r", created_at=time.time() + n)

    async def go():
        async with lab.db.engine.begin() as conn:
            await conn.execute(insert(t.approvals).values(**row))
    lab.run(go())
    return row


def do(lab, seed, fn):
    async def go():
        async with lab.db.engine.begin() as conn:
            wf = (await conn.execute(select(t.workflows).where(t.workflows.c.id == seed["wf"]["id"]))).mappings().one()
            return await fn(conn, wf)
    return lab.run(go())


def pending_revisions(lab) -> dict:
    return {r["id"]: r["workflow_revision"] for r in lab.rows(t.approvals, status="pending")}


def test_a_pending_approval_always_carries_the_revision_to_send_back(lab):
    seed = lab.seed("awaiting_approval", revision=5)
    approval(lab, seed, 1, 5)
    approval(lab, seed, 2, 5)
    do(lab, seed, lambda conn, wf: transition(conn, wf, "active", reason="x"))  # any change of state moves it
    assert pending_revisions(lab) == {"appr_1": 6, "appr_2": 6}
    do(lab, seed, lambda conn, wf: bump(conn, wf))  # and so does a change of the set alone
    assert pending_revisions(lab) == {"appr_1": 7, "appr_2": 7}
    assert lab.one(t.workflows, id=seed["wf"]["id"])["revision"] == 7 and lab.one(t.workflows, id=seed["wf"]["id"])["state"] == "active"


def test_resolving_one_of_two_approvals_keeps_the_state_and_the_last_one_makes_the_workflow_active(lab):
    seed = lab.seed("awaiting_approval", revision=5)
    wid, conv = seed["wf"]["id"], seed["conv"]["id"]
    approval(lab, seed, 1, 5)
    approval(lab, seed, 2, 5)

    def decide(n: int, status: str):
        async def fn(conn, wf):
            row = (await conn.execute(select(t.approvals).where(t.approvals.c.id == f"appr_{n}"))).mappings().one()
            return await resolve(conn, wf, row, status, request_id="req_9", reason="approval_decided")
        return do(lab, seed, fn)

    wf, job1 = decide(1, "approved")
    assert (wf["state"], wf["revision"]) == ("awaiting_approval", 6)  # another approval still waits for the resident
    assert pending_revisions(lab) == {"appr_2": 6}
    assert lab.one(t.approvals, id="appr_1")["status"] == "approved" and lab.one(t.approvals, id="appr_1")["decision_request_id"] == "req_9"
    wf, job2 = decide(2, "rejected")
    assert (wf["state"], wf["revision"], wf["current_request_id"]) == ("active", 7, "req_9")
    events = sorted(lab.rows(t.events, conversation_id=conv), key=lambda e: e["sequence"])
    assert [(e["event_type"], e["payload"]) for e in events] == [
        ("approval.resolved", {"approval_id": "appr_1", "status": "approved"}),
        ("approval.resolved", {"approval_id": "appr_2", "status": "rejected"}),
        ("workflow.status_changed", {"state": "active", "revision": 7, "reason": "approval_decided"})]
    jobs = {j["id"]: j for j in lab.rows(t.jobs, workflow_id=wid)}
    assert {j["kind"] for j in jobs.values()} == {"approval_resume"} and set(jobs) == {job1, job2}
    assert jobs[job1]["payload"] == {"approval_id": "appr_1"} and jobs[job1]["request_id"] == "req_9"
    assert all(j["status"] == "queued" for j in jobs.values())


def test_an_approval_is_decided_once(lab):
    seed = lab.seed("awaiting_approval", revision=5)
    approval(lab, seed, 1, 5)

    async def fn(conn, wf):
        row = (await conn.execute(select(t.approvals).where(t.approvals.c.id == "appr_1"))).mappings().one()
        await resolve(conn, wf, row, "approved", request_id=None, reason="x")
        from awp.workforce.workflows import StateConflict
        with pytest.raises(StateConflict):  # the second writer finds it no longer pending
            await resolve(conn, wf, row, "rejected", request_id=None, reason="x")
    do(lab, seed, fn)


def test_the_resume_event_is_built_from_the_stored_row_and_grants_nothing():
    row = dict(id="appr_1", status="approved", tool_call_id="call_7", tool_name="book_hotel",
               arguments=canonical(ck.BOOK), reply_id="reply_3")
    ok = event_for(row)
    [result] = ok.confirm_results
    assert (ok.id, ok.reply_id, result.confirmed, result.rules) == ("resume_appr_1", "reply_3", True, None)
    assert (result.tool_call.id, result.tool_call.name, result.tool_call.input) == ("call_7", "book_hotel", canonical(ck.BOOK))
    assert args_hash(json.loads(result.tool_call.input)) == args_hash(ck.BOOK)  # the gate will find the hash it stored
    no = event_for({**row, "status": "rejected"})
    assert no.confirm_results[0].confirmed is False and no.confirm_results[0].rules is None
    for status in ("expired", "cancelled"):  # these never confirm anything: the call is closed as interrupted
        gone = event_for({**row, "status": status})
        assert type(gone).__name__ == "UserInterruptEvent" and (gone.id, gone.reply_id) == ("resume_appr_1", "reply_3")


def fake_call(name: str, call_id: str = "c1", state: str = "pending"):
    return SimpleNamespace(name=name, id=call_id, state=state)


def test_the_gate_asks_once_per_tool_call_and_refuses_a_closed_workflow(tmp_path):
    with world(tmp_path, scripts.interactive, **TOOLS) as w:
        ck.declare(w)
        start, first = w.flow.begin()
        wid = first["workflow_id"]
        from test_wf_say import Room
        room = Room(w, wid)
        evidence(w, room, "hotel_search", ck.HOTELS)  # the prices the bookings below state
        gate, agent = ConsentGate(w.rt, room.b), SimpleNamespace(state=SimpleNamespace(reply_id="reply_1"))

        def check(call, args=ck.BOOK):
            return w.run(lambda: gate.check(agent, {"tool_call": call, "tool_input": args, "tool": None}))

        rev = w.state(wid)[1]
        for _ in range(3):  # the same call, asked again (a run that was repeated): one approval, one event, one bump
            assert check(fake_call("book_hotel")).behavior == PermissionBehavior.ASK
        assert w.sql("select count(*), min(workflow_revision), max(workflow_revision) from wf_approvals") == [(1, rev + 1, rev + 1)]
        assert w.state(wid) == ("awaiting_approval", rev + 1)
        assert w.sql("select count(*) from wf_events where event_type='approval.required'") == [(1,)]
        assert check(fake_call("book_hotel", "c2")).behavior == PermissionBehavior.ASK  # another call: another approval
        assert w.state(wid) == ("awaiting_approval", rev + 2) and w.sql("select count(*) from wf_approvals") == [(2,)]
        assert w.sql("select min(workflow_revision), max(workflow_revision) from wf_approvals") == [(rev + 2, rev + 2)]
        # a tool that needs no consent is not for the gate; an allow nobody asked about is refused
        assert check(fake_call("lookup_ticket")) is None
        assert "No consent was asked" in check(fake_call("book_hotel", "c3", "allowed")).message
        assert w.sql("select count(*) from wf_approvals") == [(2,)]
        # a closed workflow is asked nothing
        assert w.flow.close({"workflow_id": wid, "workflow_revision": w.state(wid)[1]}, start)[0].status_code == 200
        denied = check(fake_call("book_hotel", "c4"))
        assert denied.behavior == PermissionBehavior.DENY and "closed" in denied.message
        assert w.sql("select count(*) from wf_approvals") == [(2,)]


def test_an_own_tool_of_the_platform_does_not_slip_past_the_gate(tmp_path):
    """CaseAskConsent starts with "Case", which ToolGateMiddleware allows without asking anyone: the gate has to
    come first (P0 finding 1), and the numbers are checked before the resident is asked."""
    with world(tmp_path, scripts.interactive, **TOOLS) as w:
        start, first = w.flow.begin()
        from test_wf_say import Room
        room = Room(w, first["workflow_id"])
        hotels = evidence(w, room, "hotel_search", ck.HOTELS)
        total = evidence(w, room, "calc_sum", "sum of booking: 1890000 (from 2 amounts: 1800000, 90000)")
        profile = w.run(lambda: w.rt.profiles.get_published("ta", "supervisor")).profile
        mw = ToolGateMiddleware(w.rt, room.b, profile, "ta")
        agent = SimpleNamespace(state=SimpleNamespace(reply_id="reply_1"))
        tool = CaseAskConsent(w.rt, room.b)
        args = dict(summary="Book Sunrise for 2 nights", total="1890000", cites=[hotels, total], quote_ref="quote_001",
                    items=[{"label": "Sunrise 2 nights", "amount": "1800000"}, {"label": "Service fee", "amount": "90000"}])

        async def nxt(**kw):
            raise AssertionError("an approval gate never hands a consent tool to the engine")

        def check(**over):
            kw = {"tool_call": fake_call("CaseAskConsent"), "tool": tool, "tool_input": {**args, **over}}
            return w.run(lambda: mw.on_check_permission(agent, kw, nxt))

        wrong = check(total="1900000")
        assert wrong.behavior == PermissionBehavior.DENY and "is not the sum of the items (1890000)" in wrong.message
        assert w.sql("select count(*) from wf_approvals") == [(0,)]
        right = check()
        assert right.behavior == PermissionBehavior.ASK
        [(quote, summary)] = w.sql("select quote_ref, summary from wf_approvals")
        assert quote == "quote_001" and '"total": "1890000"' in summary
        again = check()
        assert again.behavior == PermissionBehavior.ASK and w.sql("select count(*) from wf_approvals") == [(1,)]
        # the same tool name from a case with no workflow stays what it was: an own tool, allowed
        old = w.run(lambda: w.rt.cases.create_case(tenant="ta", domain="test", external_ref="OLD-2", user_id="awp:ta", meta={}))
        stray = ToolGateMiddleware(w.rt, type(room.b)(old, "s", "a", "case-leader", "leader", "u"), profile, "ta")
        kw = {"tool_call": fake_call("CaseAskConsent"), "tool": tool, "tool_input": args}
        assert w.run(lambda: stray.on_check_permission(agent, kw, nxt)).behavior == PermissionBehavior.ALLOW
