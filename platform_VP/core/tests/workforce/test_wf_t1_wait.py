"""A workflow that waits for the partner, and the tools that need the resident's consent (slice T1): the user's
test 1 (waiting for staff is never mistaken for a stall), closing with operations still open, consent before a
partner call, and what an operator does with a workflow that needs attention. Scripted model, a real MCP server."""
from __future__ import annotations

import time

import pytest
from enginekit import world
from partnerkit import Partner
from t1kit import ADM, SETTINGS, TOOLS, act, configure, event_types, ops, tools_of

from awp.workforce.reconcile import reconcile

STOP = {"stop_tracking_only": True, "reason": "resident_requested_stop_tracking"}


@pytest.fixture
def partner():
    with Partner() as p:
        yield p


def pending_world(tmp_path, partner, **over):
    script = act("partner_repair", {"slot": "mon"}, "I asked for a plumber; it is pending.")
    return world(tmp_path, script, **TOOLS, **{**SETTINGS, **over})


def test_user_test_1_waiting_for_staff_is_never_closed_or_failed_by_the_stall_rule(tmp_path, partner):
    """The real numbers are 'for 20 minutes' against case_stall_seconds=900 and request_timeout_hours=72; here the
    stall limit is 2 s and the external limit 5 s. Past the first and short of the second nothing happens."""
    with pending_world(tmp_path, partner, case_stall_seconds=2, request_timeout_hours=5 / 3600) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        wid = first["workflow_id"]
        assert first["workflow_state"] == "waiting_external_event"
        t0 = time.monotonic()
        while time.monotonic() - t0 < 3.4:  # past the stall limit, with several sweeps in between
            assert w.state(wid)[0] == "waiting_external_event"
            assert w.sql("select status from awp_cases") == [("open",)]
            time.sleep(0.2)
        assert w.state(wid) == (first["workflow_state"], first["workflow_revision"])  # nothing was touched
        # only the external limit ends the wait, and it needs a person
        w.wait_state(wid, "needs_attention", timeout=20)
        assert w.sql("select attention_reason from wf_workflows") == [("external_timeout",)]
        assert w.sql("select status from awp_cases") == [("open",)]
        assert ops(w)[0]["status"] == "pending"  # the operation is not touched either: it may still finish
        assert "workflow.needs_attention" in event_types(w, first["conversation_id"])


def test_a_workflow_with_an_open_operation_closes_only_when_tracking_is_stopped_and_nothing_is_cancelled(tmp_path, partner):
    with pending_world(tmp_path, partner) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        wid, _rev = first["workflow_id"], first["workflow_revision"]
        calls_before = len(partner.rpc)
        r, _ = w.flow.close(first, start)
        assert r.status_code == 409 and r.json()["error"]["code"] == "WORKFLOW_NOT_READY_TO_CLOSE"
        assert r.json()["error"]["details"] == {"open_operations": 1}
        r, _ = w.flow.close(first, start, reason="resident_confirmed_resolved", stop_tracking_only=True)  # wrong reason
        assert r.status_code == 409 and w.state(wid)[0] == "waiting_external_event"
        r, _ = w.flow.close(first, start, **STOP)
        assert r.status_code == 200 and (r.json()["state"], r.json()["next_action"]) == ("closed", "none")
        assert len(partner.rpc) == calls_before and len(partner.calls) == 1  # stop tracking calls nothing at the partner
        assert ops(w)[0]["status"] == "pending"  # the work itself is not cancelled
        assert w.sql("select status from awp_cases") == [("closed",)]


def test_a_closed_workflow_is_not_asked_about_any_more(tmp_path, partner):
    script = act("partner_repair_q", {"slot": "mon"}, "I asked for a plumber; it is pending.")
    with world(tmp_path, script, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        assert w.flow.close(first, start, **STOP)[0].status_code == 200
        assert w.run(lambda: reconcile(w.engine, poll=0.0)) == 0
        assert partner.of("repair_status") == []
        assert w.run(lambda: reconcile(w.engine, grace=0.0)) == 0


# ---- consent before a partner call -----------------------------------------------------------------------------------
def consent_world(tmp_path, partner):
    return world(tmp_path, act("partner_repair_consent", {"slot": "monday"}, "I asked for the visit on Monday; it is pending."),
                 **TOOLS, **SETTINGS)


def test_a_tool_that_needs_consent_parks_before_any_row_or_call_and_runs_once_after_approval(tmp_path, partner):
    with consent_world(tmp_path, partner) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        assert (first["workflow_state"], first["next_action"]) == ("awaiting_approval", "submit_approval")
        assert partner.calls == [] and ops(w) == [] and first["ticket_id"] is None  # nothing before the resident agrees
        [appr] = w.flow.approvals(first["conversation_id"])
        assert appr["tool_name"] == "partner_repair_consent"
        assert appr["summary"] == {"text": "Book a repair visit for monday", "tool": "partner_repair_consent",
                                   "arguments": {"slot": "monday"}}
        d = w.flow.decide(appr["approval_id"], w.flow.decide_body(start, first, appr))
        assert d.status_code == 202
        w.wait_state(first["workflow_id"], "waiting_external_event")
        [op] = ops(w)
        assert (op["status"], op["tool"], op["job"]) == ("pending", "partner_repair_consent", "JOB-1")
        assert len(partner.of("book_repair")) == 1
        assert w.sql("select used_at is not null from wf_approvals") == [(1,)]
        # a resume event delivered twice, or after a crash, would call the tool again: the ledger answers instead
        again = tools_of(w)["partner_repair_consent"].call
        out = w.run(lambda: again(slot="monday"))
        assert out.content[0].text.startswith("PENDING: this same request is already with the partner")
        assert len(partner.of("book_repair")) == 1 and len(ops(w)) == 1


def test_a_declined_consent_calls_nothing(tmp_path, partner):
    with consent_world(tmp_path, partner) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        [appr] = w.flow.approvals(first["conversation_id"])
        d = w.flow.decide(appr["approval_id"], w.flow.decide_body(start, first, appr, "reject"))
        assert d.status_code == 202
        w.quiet()
        assert partner.calls == [] and ops(w) == []
        assert w.sql("select status from wf_approvals") == [("rejected",)]


# ---- an operator and a workflow that needs attention ------------------------------------------------------------------
def unknown_world(tmp_path):
    return world(tmp_path, act("partner_nostatus", {"thing": "x"}, "I could not confirm that; a person will check.", "none",
                               cite=False), **TOOLS, **SETTINGS)


def test_an_operator_sees_the_workflow_and_resumes_it_and_the_unknown_operation_is_not_sent_again(tmp_path, partner):
    with unknown_world(tmp_path) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        wid = first["workflow_id"]
        assert first["workflow_state"] == "needs_attention"
        http = w.env.http
        [row] = http.get("/platform/v1/wf/workflows?state=needs_attention", headers=ADM).json()["workflows"]
        assert (row["workflow_id"], row["next_action"], row["attention_reason"]) == (wid, "resolve_attention", "operation_unknown")
        [op] = http.get(f"/platform/v1/wf/operations?workflow_id={wid}", headers=ADM).json()["operations"]
        assert (op["status"], op["tool"], op["reviewed"], op["sent"]) == ("unknown", "partner_nostatus", False, True)
        r = http.post(f"/platform/v1/wf/workflows/{wid}/resolve", json={"action": "resume"}, headers=ADM)
        assert r.status_code == 200 and r.json()["state"] == "active"
        w.wait_state(wid, "awaiting_user")  # the leader was told to go on; it says what is true and rests
        assert http.get(f"/platform/v1/wf/operations/{op['operation_id']}", headers=ADM).json()["reviewed"] is True
        assert len(partner.of("no_status_action")) == 1  # the operation was not sent again, however the leader tried
        assert w.sql("select count(*) from wf_jobs where kind='operator'") == [(1,)]
        assert "workflow.status_changed" in event_types(w, first["conversation_id"])


def test_an_operator_can_close_a_workflow_that_needs_attention_and_only_that(tmp_path, partner):
    with unknown_world(tmp_path) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        wid, http = first["workflow_id"], w.env.http
        r = http.post(f"/platform/v1/wf/workflows/{wid}/resolve", json={"action": "close"}, headers=ADM)
        assert r.status_code == 200 and (r.json()["state"], r.json()["next_action"]) == ("closed", "none")
        assert w.sql("select close_reason from wf_workflows") == [("operator_closed",)]
        assert w.sql("select status from awp_cases") == [("closed",)] and len(partner.calls) == 1  # nothing cancelled
        again = http.post(f"/platform/v1/wf/workflows/{wid}/resolve", json={"action": "close"}, headers=ADM)
        assert again.status_code == 409


def test_resolve_is_for_the_admins_own_tenant_and_a_workflow_that_needs_attention(tmp_path, partner):
    with pending_world(tmp_path, partner) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        wid, http = first["workflow_id"], w.env.http
        assert first["workflow_state"] == "waiting_external_event"
        assert http.post(f"/platform/v1/wf/workflows/{wid}/resolve", json={"action": "close"}, headers=ADM).status_code == 409
        other = {"Authorization": "Bearer adm-b"}
        assert http.post(f"/platform/v1/wf/workflows/{wid}/resolve", json={"action": "close"}, headers=other).status_code == 404
        assert http.get(f"/platform/v1/wf/workflows/{wid}", headers=other).status_code == 404
        assert http.get("/platform/v1/wf/workflows", headers=other).json() == {"workflows": []}
        assert http.get("/platform/v1/wf/operations", headers=other).json() == {"operations": []}
        assert http.get("/platform/v1/wf/approvals", headers=other).json() == {"approvals": []}
        assert http.post(f"/platform/v1/wf/workflows/{wid}/resolve", json={"action": "reopen"}, headers=ADM).status_code == 422
        assert w.state(wid)[0] == "waiting_external_event"
