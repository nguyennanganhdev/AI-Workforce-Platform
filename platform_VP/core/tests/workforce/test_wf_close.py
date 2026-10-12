"""POST /partner/workflows/{id}/close (contract 9.9): CAS, idempotency, readiness, races."""
import threading
import time

import pytest

from conftest import key_headers
from fake_engine import Plan
from test_wf_commands import counts, par
from test_wf_errors import assert_envelope

P = "/workforce/v1/partner"


def ready(sf, **plan):
    """A workflow resting in awaiting_confirmation. Returns (start body, post json)."""
    sf.engine.plan = Plan(state="awaiting_confirmation", **plan)
    return sf.begin()


def events(sf, conv):
    return sf.history(conv, limit=500).json()["items"]


def test_close_answers_with_exactly_the_fields_of_contract_9_9(sf):
    start, started = ready(sf)
    r, body = sf.close(started, start)
    assert r.status_code == 200
    j = r.json()
    assert list(j) == ["request_id", "request_status", "external_ticket_id", "conversation_id", "workflow_id",
                       "ticket_id", "state", "next_action", "revision", "reason", "closed_at"]
    assert j["request_id"].startswith("req_") and j["request_status"] == "completed"
    assert (j["state"], j["next_action"], j["reason"]) == ("closed", "none", "resident_confirmed_resolved")
    assert j["revision"] == started["workflow_revision"] + 1
    assert j["external_ticket_id"] == start["external_ticket_id"] and j["ticket_id"] is None
    assert (j["conversation_id"], j["workflow_id"]) == (started["conversation_id"], started["workflow_id"])
    assert j["closed_at"].endswith("Z")


def test_close_writes_state_event_and_case_together(sf):
    start, started = ready(sf)
    j = sf.close(started, start)[0].json()
    [(state, rev, reason, closed_at, case_id)] = sf.env.sql(
        "select state, revision, close_reason, closed_at, case_id from wf_workflows where id=?", (started["workflow_id"],))
    assert (state, rev, reason) == ("closed", j["revision"], "resident_confirmed_resolved") and closed_at
    assert sf.env.sql("select status, result from awp_cases where id=?", (case_id,))[0][0] == "closed"
    last = events(sf, started["conversation_id"])[-1]
    assert last["event_type"] == "workflow.closed" and last["workflow_id"] == started["workflow_id"]
    assert last["payload"] == {"state": "closed", "revision": j["revision"], "reason": "resident_confirmed_resolved",
                               "closed_at": j["closed_at"]}
    assert sf.snapshot(started["conversation_id"]).json()["workflows"][0]["state"] == "closed"
    g = sf.request(j["request_id"]).json()  # the close is readable like any other request
    assert (g["request_status"], g["workflow_state"], g["next_action"], g["workflow_revision"]) == (
        "completed", "closed", "none", j["revision"])
    assert g["last_event_id"] == last["event_id"]


def test_after_close_a_reply_is_refused_and_the_other_workflow_is_untouched(sf):
    a_start, a = ready(sf)
    b_start, b = ready(sf)
    sf.close(a, a_start)
    assert_envelope(sf.reply(a_start, a)[0], 409, "WORKFLOW_CLOSED")
    assert_envelope(sf.close(a, a_start, revision=a["workflow_revision"] + 1)[0], 409, "WORKFLOW_CLOSED")
    assert sf.reply(b_start, b)[0].status_code == 200
    assert sf.snapshot(b["conversation_id"]).json()["workflows"][0]["state"] != "closed"
    assert len(sf.snapshot(a["conversation_id"]).json()["messages"]) == 2  # the history is still there


def test_a_replay_returns_the_stored_result_even_with_the_old_revision(sf):
    start, started = ready(sf)
    r, body = sf.close(started, start)
    before = counts(sf.env)
    again = sf.http.post(f"{P}/workflows/{started['workflow_id']}/close", json=body, headers=sf.h)
    assert again.status_code == 200 and again.content == r.content  # idempotency is checked before the CAS
    assert counts(sf.env) == before
    assert sf.env.sql("select revision from wf_workflows where id=?", (started["workflow_id"],))[0][0] == r.json()["revision"]
    assert len([e for e in events(sf, started["conversation_id"]) if e["event_type"] == "workflow.closed"]) == 1


def test_the_same_id_with_another_body_is_an_idempotency_conflict(sf):
    start, started = ready(sf)
    r, body = sf.close(started, start)
    other = {**body, "reason": "something_else"}
    assert_envelope(sf.http.post(f"{P}/workflows/{started['workflow_id']}/close", json=other, headers=sf.h),
                    409, "IDEMPOTENCY_CONFLICT")
    # the namespace is shared with requests
    reused = sf.start_body(external_request_id=body["external_request_id"])
    assert_envelope(sf.post(reused), 409, "IDEMPOTENCY_CONFLICT")
    b_start, b = ready(sf)
    taken = sf.close(b, b_start, external_request_id=body["external_request_id"])[0]  # same id, another workflow
    assert_envelope(taken, 409, "IDEMPOTENCY_CONFLICT")


def test_a_wrong_revision_is_409_with_the_current_one_and_leaves_no_claim(sf):
    start, started = ready(sf)
    rev = started["workflow_revision"]
    before = counts(sf.env)
    r, body = sf.close(started, start, revision=rev - 1)
    err = assert_envelope(r, 409, "REVISION_CONFLICT")
    assert err["details"] == {"current_revision": rev}
    assert counts(sf.env) == before
    assert sf.env.sql("select state from wf_workflows where id=?", (started["workflow_id"],)) == [("awaiting_confirmation",)]
    # the same request id with the revision fixed goes through: the refusal consumed nothing
    ok = sf.http.post(f"{P}/workflows/{started['workflow_id']}/close", json={**body, "expected_revision": rev},
                      headers=sf.h)
    assert ok.status_code == 200 and ok.json()["revision"] == rev + 1


def test_a_reply_since_the_snapshot_makes_the_close_stale(sf):
    start, started = ready(sf)
    stale = started["workflow_revision"]
    sf.engine.plan = Plan(state="awaiting_confirmation")
    sf.reply(start, started)  # the workflow moved: revision is higher now
    err = assert_envelope(sf.close(started, start, revision=stale)[0], 409, "REVISION_CONFLICT")
    assert err["details"]["current_revision"] > stale


@pytest.mark.parametrize("what", ["user", "ticket", "conversation"])
def test_close_checks_the_binding(sf, what):
    start, started = ready(sf)
    over = {"user": dict(external_user_id="resident-999"), "ticket": dict(external_ticket_id="TICKET-OTHER"),
            "conversation": dict(external_conversation_id="CHAT-OTHER")}[what]
    before = counts(sf.env)
    assert_envelope(sf.close(started, start, **over)[0], 409, "WORKFLOW_BINDING_MISMATCH")
    assert counts(sf.env) == before
    assert sf.env.sql("select state from wf_workflows where id=?", (started["workflow_id"],)) == [("awaiting_confirmation",)]


def test_close_without_a_ticket_on_a_ticketed_route_is_422(sf):
    start, started = ready(sf)
    assert_envelope(sf.close(started, start, external_ticket_id=None)[0], 422, "EXTERNAL_TICKET_REQUIRED")


def test_close_of_an_unknown_or_foreign_workflow_is_a_404(sf):
    """Contract 6.3: a resource outside the caller's scope is 404, and a stranger cannot tell a real id from a made-up one."""
    start, started = ready(sf)
    body = sf.close_body(started, start)
    r = sf.http.post(f"{P}/workflows/wf_00000000000000000000000000000000/close", json=body, headers=sf.h)
    assert_envelope(r, 404, "NOT_FOUND")
    other = sf.env.client(domain="travel", name="Other")
    k = sf.env.key(other["client_id"])
    sf.env.active_route(other["client_id"], k["api_key"])
    r = sf.http.post(f"{P}/workflows/{started['workflow_id']}/close", json=body, headers=key_headers(k["api_key"]))
    assert_envelope(r, 404, "NOT_FOUND")
    assert sf.env.sql("select state from wf_workflows where id=?", (started["workflow_id"],)) == [("awaiting_confirmation",)]


def test_close_needs_its_operation_and_a_covered_route(sf):
    start, started = ready(sf)
    no_close = key_headers(sf.env.key(sf.client["client_id"], operations=["submit_request", "reply"])["api_key"])
    r = sf.http.post(f"{P}/workflows/{started['workflow_id']}/close", headers=no_close,
                     json=sf.close_body(started, start))
    assert_envelope(r, 403, "PERMISSION_DENIED")
    other = sf.env.route(sf.client["client_id"], "ELSEWHERE")
    narrow = key_headers(sf.env.key(sf.client["client_id"], routes=[other["route_id"]])["api_key"])
    r = sf.http.post(f"{P}/workflows/{started['workflow_id']}/close", headers=narrow, json=sf.close_body(started, start))
    assert_envelope(r, 403, "ROUTE_NOT_AUTHORIZED")
    assert_envelope(sf.http.post(f"{P}/workflows/{started['workflow_id']}/close", json={}), 401, "UNAUTHENTICATED")


@pytest.mark.parametrize("change", [
    {"reason": ""}, {"reason": "x" * 201}, {"reason": "a\nb"}, {"expected_revision": "3"}, {"expected_revision": -1},
    {"stop_tracking_only": "yes"}, {"schema_version": "2"}, {"extra": 1}])
def test_close_schema_is_strict(sf, change):
    start, started = ready(sf)
    before = counts(sf.env)
    assert_envelope(sf.close(started, start, **change)[0], 422, "VALIDATION_FAILED")
    assert counts(sf.env) == before


def test_the_reason_is_any_text_the_contract_sets_no_format(sf):
    start, started = ready(sf)
    r, _ = sf.close(started, start, reason="Resident OK, đã xong")
    assert r.status_code == 200 and r.json()["reason"] == "Resident OK, đã xong"


# ---- outside operations (contract 9.9, spec 7.2) ------------------------------------------------------------------
def add_operation(sf, wid, status, n=1):
    sf.env.sql("insert into wf_operations (id, workflow_id, route_id, tool_name, args_hash, client_reference, status, "
               "created_at, updated_at) values (?, ?, ?, 'call_tech', 'h', ?, ?, 1.0, 1.0)",
               (f"op_{wid}_{n}", wid, sf.route["route_id"], f"ref-{wid}-{n}", status))


@pytest.mark.parametrize("status", ["intent", "sent", "pending", "unknown"])
def test_an_open_operation_blocks_the_close_unless_tracking_is_stopped_explicitly(sf, status):
    start, started = ready(sf)
    add_operation(sf, started["workflow_id"], status)
    before = counts(sf.env)
    err = assert_envelope(sf.close(started, start)[0], 409, "WORKFLOW_NOT_READY_TO_CLOSE")
    assert err["details"] == {"open_operations": 1}
    assert counts(sf.env) == before
    r, _ = sf.close(started, start, reason="resident_requested_stop_tracking", stop_tracking_only=True)
    assert r.status_code == 200 and r.json()["reason"] == "resident_requested_stop_tracking"
    assert sf.env.sql("select status from wf_operations where workflow_id=?", (started["workflow_id"],)) == [(status,)]  # no cancel


@pytest.mark.parametrize("status", ["completed", "failed"])
def test_finished_operations_do_not_block_the_close(sf, status):
    start, started = ready(sf)
    add_operation(sf, started["workflow_id"], status)
    assert sf.close(started, start)[0].status_code == 200


def test_stop_tracking_needs_the_exact_reason(sf):
    start, started = ready(sf)
    add_operation(sf, started["workflow_id"], "pending")
    assert_envelope(sf.close(started, start, reason="resident_confirmed_resolved", stop_tracking_only=True)[0],
                    409, "WORKFLOW_NOT_READY_TO_CLOSE")  # contract 9.9: without both, an open operation is a 409
    assert_envelope(sf.close(started, start, reason="resident_requested_stop_tracking")[0],
                    409, "WORKFLOW_NOT_READY_TO_CLOSE")  # the reason alone is not the flag


# ---- what a close takes with it -----------------------------------------------------------------------------------
def test_a_close_cancels_pending_approvals_and_queued_work(sf):
    start, started = ready(sf)
    wid, cid, client = started["workflow_id"], started["conversation_id"], sf.client["client_id"]
    sf.env.sql("update wf_workflows set state='awaiting_approval' where id=?", (wid,))
    sf.env.sql("insert into wf_approvals (id, workflow_id, conversation_id, client_id, external_user_id, session_id, "
               "agent_id, tool_call_id, tool_name, arguments, arguments_hash, summary, status, workflow_revision, "
               "created_at) values ('appr_9', ?, ?, ?, 'resident-123', 's', 'a', 'c', 'book', '{}', 'sha256:x', '{}', "
               "'pending', 3, 1.0)", (wid, cid, client))
    sf.engine.paused = True
    queued = sf.http.post(f"{P}/requests", headers=sf.h, json=sf.reply_body(started, start))  # refused: approval waits
    assert_envelope(queued, 409, "APPROVAL_PENDING")
    r, _ = sf.close(started, start)
    assert r.status_code == 200
    assert sf.env.sql("select status from wf_approvals where id='appr_9'") == [("cancelled",)]
    last = [e for e in events(sf, cid) if e["event_type"] == "approval.resolved"]
    assert [e["payload"] for e in last] == [{"approval_id": "appr_9", "status": "cancelled"}]
    assert sf.snapshot(cid).json()["approvals"] == []


def test_a_close_settles_requests_still_waiting_and_cancels_their_jobs(sf):
    sf.engine.paused = True
    with sf.waiting(0.3):
        start, started = sf.begin()  # 202: the job is queued, no engine takes it
    assert started["request_status"] == "queued"
    rev = started["workflow_revision"]
    r, _ = sf.close(started, start, revision=rev)
    assert r.status_code == 200
    assert sf.env.sql("select status from wf_jobs where workflow_id=?", (started["workflow_id"],)) == [("failed",)]
    got = sf.request(started["request_id"]).json()
    assert got["request_status"] == "completed" and got["workflow_state"] == "closed" and got["next_action"] == "none"
    assert sf.post(start).json()["request_status"] == "completed"  # a replay of the POST now answers 200


# ---- races ----------------------------------------------------------------------------------------------------------
def test_identical_closes_in_parallel_close_once(sf):
    start, started = ready(sf)
    body = sf.close_body(started, start)
    out = par(lambda i: sf.http.post(f"{P}/workflows/{started['workflow_id']}/close", json=body, headers=sf.h), n=8)
    assert {r.status_code for r in out} == {200}
    assert len({r.content for r in out}) == 1
    assert len([e for e in events(sf, started["conversation_id"]) if e["event_type"] == "workflow.closed"]) == 1
    assert sf.env.sql("select revision from wf_workflows where id=?", (started["workflow_id"],))[0][0] == (
        started["workflow_revision"] + 1)


def test_close_racing_a_reply_never_leaves_a_chat_after_the_close(sf):
    """Either the close wins (the reply is 409 WORKFLOW_CLOSED) or the reply wins (the close is 409
    REVISION_CONFLICT). Never both, and nothing is written after the closed event."""
    outcomes = set()
    for _ in range(10):
        start, started = ready(sf)
        sf.engine.plan = Plan(state="awaiting_confirmation")
        gate = threading.Barrier(2)
        out = {}

        def do_close():
            gate.wait()
            out["close"] = sf.close(started, start)[0]

        def do_reply():
            gate.wait()
            out["reply"] = sf.reply(start, started)[0]

        ts = [threading.Thread(target=do_close), threading.Thread(target=do_reply)]
        [th.start() for th in ts]
        [th.join(30) for th in ts]
        c, r = out["close"], out["reply"]
        wid, cid = started["workflow_id"], started["conversation_id"]
        if c.status_code == 200:
            outcomes.add("close")
            assert r.status_code in (200, 202, 409), r.text  # the reply may have landed just before the close
            if r.status_code == 409:
                assert r.json()["error"]["code"] == "WORKFLOW_CLOSED"
        else:
            outcomes.add("reply")
            assert_envelope(c, 409, "REVISION_CONFLICT")
            assert r.status_code in (200, 202)
        log = events(sf, cid)
        closed_at = [e["sequence"] for e in log if e["event_type"] == "workflow.closed"]
        if c.status_code == 200:
            assert len(closed_at) == 1
            time.sleep(0.15)  # let any in-flight turn finish
            log = events(sf, cid)
            assert [e for e in log if e["sequence"] > closed_at[0]] == [], "an event after the close"
            [(state, queued)] = sf.env.sql(
                "select w.state, (select count(*) from wf_jobs j where j.workflow_id = w.id and j.status = 'queued') "
                "from wf_workflows w where w.id=?", (wid,))
            assert state == "closed" and queued == 0
            msgs = sf.env.sql("select max(sequence) from wf_messages where workflow_id=?", (wid,))[0][0]
            assert msgs <= closed_at[0]
        else:
            assert closed_at == [] and sf.env.sql("select state from wf_workflows where id=?", (wid,))[0][0] != "closed"
    assert outcomes  # (which side wins varies from run to run; both are checked above)
