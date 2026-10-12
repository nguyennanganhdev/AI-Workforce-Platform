"""The cost flow of the user's tests 2, 3 and 4 and decisions D6 and D9, on provider events (slice T2): the leader
starts a piece of work, the provider reports its progress, a cost, and that it is done; the resident agrees to the cost
and confirms the end; only the partner's close ends the workflow. Scripted model, a real MCP server."""
from __future__ import annotations

import re

import pytest
from enginekit import evidence_of
from fake_llm import CALLS
from partnerkit import Partner
from scripts import say
from t2kit import ITEMS, pending_world, wait_status

PENDING_TEXT = "I asked for a plumber; it is pending."
DONE_TEXT = "The plumber reports the visit finished. Is everything right?"


@pytest.fixture
def partner():
    with Partner() as p:
        yield p


def cost_leader(total_in_args: str | None = None, wrong_ok: bool = False):
    """The leader of the cost flow. First turn: the action. A cost report: add the items with calc_sum, ask the resident
    to agree with CaseAskConsent (with `total_in_args`, the provider's own total, when given: the model trusts it). A
    report that the work is done: ask for confirmation."""
    def script(c):
        if "<provider-event" not in c.last_user:
            turn = c.after_user()
            if turn.called("partner_repair") == 0:
                return [("partner_repair", {"slot": "mon"})]
            return say(PENDING_TEXT, "none") if turn.called("CaseSay") == 0 else "Said."
        turn, kind = c.after_user(), re.search(r'type="([^"]+)"', c.last_user).group(1)
        ev = (re.search(r'evidence="(E\d+)"', c.last_user) or [None, None])[1]
        if kind == "x.cost_reported":
            if turn.called("calc_sum") == 0:
                return [("calc_sum", {"label": "repair", "values": [str(i["amount"]) for i in ITEMS]})]
            calc = evidence_of(" ".join(turn.results("calc_sum")))[0]
            asked = turn.called("CaseAskConsent")
            if asked == 0:
                return [("CaseAskConsent", {
                    "summary": "The repair work", "cites": [ev, calc], "total": total_in_args or "550000",
                    "items": [{"label": i["label"], "amount": str(i["amount"])} for i in ITEMS]})]
            got = turn.results("CaseAskConsent")[-1]
            if turn.called("CaseSay") == 0:
                if "The resident agreed" in got:
                    return say("Thank you, you agreed to 550000 VND.", "none", evidence_of(got)[:1])
                if got.startswith("Not asked"):
                    return say("The costs from the plumber do not add up, so I did not ask you to agree. "
                               "I will ask the plumber to send them again.", "none")
                return say("Understood, nothing will be charged.", "reply")
            return "Said."
        if kind == "x.completed":
            return say(DONE_TEXT, "confirmation", [ev]) if turn.called("CaseSay") == 0 else "Said."
        return say("Noted.", "none") if turn.called("CaseSay") == 0 else "Said."
    return script


def cost_event(p, total: int = 550000):
    return p.send("x.cost_reported", job=p.job, version=3, data={"items": ITEMS, "total": total})


def test_user_tests_2_and_4_the_whole_cost_flow_ends_closed_only_after_the_partners_close(tmp_path, partner):
    with pending_world(tmp_path, partner, cost_leader(), case_stall_seconds=2) as (w, prov, p):
        f = w.flow
        assert (p.first["workflow_state"], p.first["next_action"]) == ("waiting_external_event", "watch_events")
        w.quiet()
        calls = len(CALLS)

        # progress that needs no model: the resident's app learns it, the leader is not asked
        p.applied("x.assigned", version=1, job=p.job, data={"worker_name": "An", "eta_minutes": 20})
        p.applied("x.on_the_way", version=2, data={"eta_minutes": 5})
        assert len(CALLS) == calls and p.jobs() == 0

        # a cost: it wakes the leader exactly once, which checks the total and asks the resident to agree
        rid, _ = cost_event(p)
        wait_status(w, prov, rid)
        w.wait_state(p.wid, "awaiting_approval")
        assert len(CALLS) > calls and p.jobs() == 1
        assert w.sql("select count(*) from wf_turns where msg_id in (select id from wf_jobs where kind='provider_wake')") == [(1,)]
        [appr] = f.approvals(p.conv)
        assert appr["tool_name"] == "CaseAskConsent" and appr["summary"]["total"] == "550000"
        assert [i["amount"] for i in appr["summary"]["items"]] == ["300000", "250000"]
        rev = w.state(p.wid)[1]
        assert appr["expected_revision"] == rev

        # the resident agrees: the leader goes on, and the workflow waits for the work again
        body = f.decide_body(p.start, p.first, appr)
        assert f.decide(appr["approval_id"], body).status_code == 202
        w.wait_state(p.wid, "waiting_external_event")
        assert w.messages(p.wid)[-1][1] == "Thank you, you agreed to 550000 VND."
        assert w.sql("select status from wf_approvals") == [("approved",)] and p.jobs() == 1  # the cost woke it once, still

        # the work is done: the leader asks for confirmation; nothing closes the workflow
        rid, _ = p.send("x.completed", version=4, job=p.job, data={"summary": "Pipe replaced"})
        wait_status(w, prov, rid)
        w.wait_state(p.wid, "awaiting_confirmation")
        assert w.messages(p.wid)[-1][1] == DONE_TEXT and p.jobs() == 2
        assert p.op_row()[:2] == ("completed", "completed")
        snap = f.snapshot(p.conv).json()["workflows"][0]
        assert (snap["state"], snap["next_action"]) == ("awaiting_confirmation", "confirm_close")
        w.quiet()
        assert w.sql("select status from awp_cases") == [("open",)]  # the leader's "is everything right" closed nothing

        # an old event after the end of the work changes nothing
        rid, _ = p.send("x.on_the_way", version=2, data={"eta_minutes": 1})
        assert wait_status(w, prov, rid, "rejected")["error"]["code"] == "STALE_EVENT"
        assert w.state(p.wid)[0] == "awaiting_confirmation"

        # only the partner's close ends it
        wf = {"workflow_id": p.wid, "workflow_revision": w.state(p.wid)[1]}
        r = f.close(wf, p.start, reason="resident_confirmed", stop_tracking_only=False)[0]
        assert r.status_code == 200 and r.json()["state"] == "closed"
        assert w.sql("select status from awp_cases") == [("closed",)]
        kinds = p.kinds()
        assert kinds[-1] == "workflow.closed" and kinds.count("approval.required") == 1 and kinds.count("approval.resolved") == 1


def test_user_test_3_a_wrong_total_from_the_provider_is_refused_and_the_resident_is_never_asked(tmp_path, partner):
    with pending_world(tmp_path, partner, cost_leader(total_in_args="600000")) as (w, prov, p):
        w.quiet()
        rid, _ = cost_event(p, total=600000)  # the provider says 600000; its own lines add up to 550000
        wait_status(w, prov, rid)
        w.wait(lambda: any("do not add up" in m[1] for m in w.messages(p.wid)), what="the leader to say it")
        w.quiet()
        refusals = [text for c in CALLS for role, text, _ in c.get("shape", []) if text.startswith("Not asked")]
        assert refusals and "not the sum of the items (550000)" in refusals[0]
        assert w.sql("select count(*) from wf_approvals") == [(0,)] and "approval.required" not in p.kinds()
        assert w.flow.approvals(p.conv) == []
        said = w.messages(p.wid)[-1][1]
        assert "do not add up" in said and "600000" not in said  # the resident is told nothing false, and nothing was asked
        assert "The resident agreed" not in " ".join(m[1] for m in w.messages(p.wid))
        w.wait_state(p.wid, "waiting_external_event")  # settle follows the turn; the work is still being waited for
        assert p.jobs() == 1


def test_a_cost_the_resident_refuses_is_not_charged_and_the_leader_says_so(tmp_path, partner):
    with pending_world(tmp_path, partner, cost_leader()) as (w, prov, p):
        w.quiet()
        rid, _ = cost_event(p)
        wait_status(w, prov, rid)
        w.wait_state(p.wid, "awaiting_approval")
        [appr] = w.flow.approvals(p.conv)
        body = w.flow.decide_body(p.start, p.first, appr, decision="reject")
        assert w.flow.decide(appr["approval_id"], body).status_code == 202
        w.wait(lambda: w.sql("select status from wf_approvals") == [("rejected",)] and p.state() != "awaiting_approval", what="the refusal")
        w.quiet()
        assert w.messages(p.wid)[-1][1] == "Understood, nothing will be charged."
        assert "The resident agreed" not in " ".join(m[1] for m in w.messages(p.wid))
