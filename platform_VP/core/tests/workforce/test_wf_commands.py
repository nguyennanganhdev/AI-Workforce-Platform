"""POST /partner/requests: order of checks, schema, idempotency, the wait, frozen results (contract 9.1, 9.2, 11)."""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from conftest import key_headers
from fake_engine import Plan
from test_wf_errors import assert_envelope

TABLES = ("wf_requests", "wf_conversations", "wf_workflows", "wf_messages", "wf_events", "wf_jobs", "awp_cases")


def counts(env) -> dict:
    return {name: env.sql(f"select count(*) from {name}")[0][0] for name in TABLES}


def until(check, timeout: float = 20.0, what: str = "the condition"):
    """Poll `check()` until it is truthy (a generous ceiling: it returns the moment the condition holds)."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = check()
        if got:
            return got
        time.sleep(0.02)
    raise AssertionError(f"timed out waiting for {what}")


def par(fn, n=8):
    with ThreadPoolExecutor(n) as ex:
        return [f.result() for f in [ex.submit(fn, i) for i in range(n)]]


def only_keys(env, flow, operations):
    return key_headers(env.key(flow.client["client_id"], operations=operations)["api_key"])


# ---- the happy path: contract 9.1 ---------------------------------------------------------------
def test_start_answers_200_with_exactly_the_fields_of_contract_9_1(sf):
    r, body = sf.start()
    assert r.status_code == 200
    j = r.json()
    assert list(j) == ["request_id", "request_status", "external_ticket_id", "conversation_id", "workflow_id",
                       "workflow_state", "next_action", "workflow_revision", "ticket_id", "result", "error",
                       "accepted_at", "completed_at", "status_url", "conversation_url", "event_stream_url"]
    assert j["request_status"] == "completed" and j["external_ticket_id"] == body["external_ticket_id"]
    assert j["request_id"].startswith("req_") and j["conversation_id"].startswith("conv_")
    assert j["workflow_id"].startswith("wf_")
    assert (j["workflow_state"], j["next_action"], j["workflow_revision"]) == ("awaiting_user", "submit_reply", 3)
    assert j["ticket_id"] is None and j["error"] is None  # spec A5 is a later slice
    [m] = j["result"]["messages"]
    assert list(m) == ["message_id", "workflow_id", "sender", "text", "created_at"]
    assert m["message_id"].startswith("msg_") and m["sender"] == "assistant" and m["workflow_id"] == j["workflow_id"]
    assert j["accepted_at"].endswith("Z") and j["completed_at"].endswith("Z")
    assert j["status_url"] == f"/workforce/v1/partner/requests/{j['request_id']}"
    assert j["conversation_url"] == f"/workforce/v1/partner/conversations/{j['conversation_id']}"
    assert j["event_stream_url"] == j["conversation_url"] + "/events"


def test_start_writes_request_workflow_case_message_events_and_job_together(sf):
    r, body = sf.start()
    j = r.json()
    env = sf.env
    [(client, route, state, rev, case_id, user, ticket)] = env.sql(
        "select client_id, route_id, state, revision, case_id, external_user_id, external_ticket_id "
        "from wf_workflows where id=?", (j["workflow_id"],))
    assert (state, rev, user, ticket) == ("awaiting_user", 3, "resident-123", body["external_ticket_id"])
    [(tenant, domain, ref, cstatus, cuser)] = env.sql(
        "select tenant, domain, external_ref, status, user_id from awp_cases where id=?", (case_id,))
    assert (tenant, domain, ref, cstatus, cuser) == ("ta", "homes", j["workflow_id"], "open", "resident-123")
    [(rstatus, ctype, fp)] = env.sql("select status, command_type, fingerprint from wf_requests where id=?",
                                     (j["request_id"],))
    assert (rstatus, ctype) == ("completed", "start_workflow") and fp.startswith("sha256:")
    users = env.sql("select sender, text from wf_messages where workflow_id=? order by sequence", (j["workflow_id"],))
    assert users == [("user", body["message"]["text"]), ("assistant", "Noted.")]
    [(kind, jstatus, jreq)] = env.sql("select kind, status, request_id from wf_jobs where workflow_id=?",
                                      (j["workflow_id"],))
    assert (kind, jstatus, jreq) == ("resident_message", "done", j["request_id"])
    types = [e[0] for e in env.sql("select event_type from wf_events where conversation_id=? order by sequence",
                                   (j["conversation_id"],))]
    assert types == ["request.accepted", "workflow.status_changed", "assistant.message", "workflow.awaiting_user"]


def test_the_job_is_queued_with_the_message_it_carries(sf):
    sf.engine.paused = True
    with sf.waiting(0.3):
        r, body = sf.start()
    assert r.status_code == 202
    j = r.json()
    [(kind, status, req, payload)] = sf.env.sql("select kind, status, request_id, payload from wf_jobs "
                                                "where workflow_id=?", (j["workflow_id"],))
    mid = json.loads(payload)["message_id"]
    assert (kind, status, req) == ("resident_message", "queued", j["request_id"])
    assert sf.env.sql("select text, sender from wf_messages where id=?", (mid,)) == [(body["message"]["text"], "user")]


def test_a_reply_continues_the_same_workflow_and_the_message_text_is_kept_as_sent(sf):
    start, started = sf.begin()
    text = "Nhờ báo thợ đi vào cổng B giúp tôi.\nCảm ơn <b>nhiều</b>."
    sf.engine.plan = Plan(say=("Đã ghi nhận.", "Tôi sẽ báo thợ."), state="awaiting_confirmation")
    r, body = sf.reply(start, started, message={"type": "text", "text": text})
    assert r.status_code == 200
    j = r.json()
    assert j["request_id"] != started["request_id"]
    assert (j["workflow_id"], j["conversation_id"], j["external_ticket_id"]) == (
        started["workflow_id"], started["conversation_id"], started["external_ticket_id"])
    assert (j["workflow_state"], j["next_action"], j["workflow_revision"]) == ("awaiting_confirmation", "confirm_close", 5)
    assert [m["text"] for m in j["result"]["messages"]] == ["Đã ghi nhận.", "Tôi sẽ báo thợ."]  # in order
    assert sf.engine.seen[-1][1] == text
    assert sf.env.sql("select count(*) from awp_cases where external_ref=?", (started["workflow_id"],)) == [(1,)]


def test_a_reply_puts_a_resting_workflow_back_to_active_and_counts_the_revision_once(sf):
    start, started = sf.begin()
    assert started["workflow_revision"] == 3  # accepted 1 -> active 2 -> awaiting_user 3
    sf.engine.plan = Plan(state="awaiting_user", start_active=False)
    sf.reply(start, started)
    types = [e[0] for e in sf.env.sql("select event_type from wf_events where conversation_id=? order by sequence",
                                      (started["conversation_id"],))]
    assert types[4:] == ["request.accepted", "workflow.status_changed", "assistant.message", "workflow.awaiting_user"]
    assert sf.env.sql("select revision from wf_workflows where id=?", (started["workflow_id"],)) == [(5,)]


@pytest.mark.parametrize("state,action,reason", [
    ("awaiting_user", "submit_reply", None), ("awaiting_confirmation", "confirm_close", None),
    ("waiting_external_event", "watch_events", None), ("needs_attention", "resolve_attention", "leader_silent"),
    ("closed", "none", "answered")])
def test_the_resting_state_decides_next_action(sf, state, action, reason):
    sf.engine.plan = Plan(state=state, reason=reason)
    r, _ = sf.start()
    j = r.json()
    assert r.status_code == 200 and (j["workflow_state"], j["next_action"]) == (state, action)


def test_a_turn_without_a_message_still_completes_with_an_empty_result(sf):
    sf.engine.plan = Plan(say=(), state="waiting_external_event")
    j = sf.start()[0].json()
    assert j["request_status"] == "completed" and j["result"] == {"messages": []}


def test_a_failed_turn_is_http_200_with_a_public_error_and_resolve_attention(sf):
    sf.engine.plan = Plan(say=("A person will follow up.",), state="needs_attention", reason="leader_silent",
                          fail={"code": "TURN_FAILED", "message": "The assistant could not finish."})
    r, _ = sf.start()
    j = r.json()
    assert r.status_code == 200 and j["request_status"] == "failed"
    assert (j["workflow_state"], j["next_action"]) == ("needs_attention", "resolve_attention")
    assert j["error"] == {"code": "TURN_FAILED", "message": "The assistant could not finish."}
    assert [m["text"] for m in j["result"]["messages"]] == ["A person will follow up."]
    assert sf.request(j["request_id"]).json()["error"] == j["error"]


# ---- 202: the turn outlives the wait --------------------------------------------------------------
def test_a_slow_turn_answers_202_with_ids_and_the_result_arrives_through_get_and_history(sf):
    gate = threading.Event()
    sf.engine.plan = Plan(say=("Technician booked.",), hold=gate)  # the turn does not end until the test lets it
    try:
        with sf.waiting(0.3):
            r, body = sf.start()
        assert r.status_code == 202  # the POST gave up waiting; it did not wait for the turn
        j = r.json()
        assert list(j) == ["request_id", "request_status", "external_ticket_id", "conversation_id", "workflow_id",
                           "workflow_state", "next_action", "workflow_revision", "ticket_id", "result", "error",
                           "accepted_at", "completed_at", "status_url", "conversation_url", "event_stream_url"]
        assert j["request_status"] in ("queued", "running") and j["result"] is None and j["completed_at"] is None
        assert j["next_action"] == "watch_request" and j["workflow_state"] in ("accepted", "active")
        assert j["external_ticket_id"] == body["external_ticket_id"] and j["workflow_id"].startswith("wf_")
        mid = sf.request(j["request_id"]).json()
        assert mid["request_status"] in ("queued", "running") and mid["result"] is None
    finally:
        gate.set()
    mid = until(lambda: (g := sf.request(j["request_id"]).json())["request_status"] == "completed" and g, what="the turn")
    assert mid["request_status"] == "completed" and mid["next_action"] == "submit_reply"
    [m] = mid["result"]["messages"]
    assert m["text"] == "Technician booked."
    items = sf.history(j["conversation_id"]).json()["items"]
    assert [i["payload"]["message_id"] for i in items if i["event_type"] == "assistant.message"] == [m["message_id"]]
    snap = sf.snapshot(j["conversation_id"]).json()
    assert m["message_id"] in [x["message_id"] for x in snap["messages"]]
    assert mid["last_event_id"] == items[-1]["event_id"]


def test_without_an_engine_the_job_waits_in_the_table_and_the_post_answers_202(sf):
    sf.engine.paused = True
    with sf.waiting(0.3):
        r, _ = sf.start()
    j = r.json()
    assert r.status_code == 202 and j["request_status"] == "queued" and j["workflow_state"] == "accepted"
    assert j["next_action"] == "watch_request" and j["workflow_revision"] == 1
    assert sf.env.sql("select status from wf_jobs where workflow_id=?", (j["workflow_id"],)) == [("queued",)]


def test_wait_seconds_zero_never_waits(make_flow):
    gate = threading.Event()
    with make_flow(route={"wait_seconds": 0}) as f:  # the settings would wait 20 s: the route's 0 is what counts
        f.engine.plan = Plan(hold=gate)
        try:
            t0 = time.monotonic()
            r, _ = f.start()
            assert r.status_code == 202 and time.monotonic() - t0 < 10
        finally:
            gate.set()


def test_the_wait_ends_as_soon_as_the_request_settles(make_flow):
    gate = threading.Event()
    with make_flow(route={"wait_seconds": 60}) as f:
        f.engine.plan = Plan(hold=gate)
        threading.Timer(0.3, gate.set).start()  # the turn ends 0.3 s after the POST starts waiting
        t0 = time.monotonic()
        r, _ = f.start()
        assert r.status_code == 200 and time.monotonic() - t0 < 30  # not the whole window of 60 s


def test_the_wait_holds_no_database_connection(make_flow):
    gate = threading.Event()
    with make_flow(route={"wait_seconds": 30}) as f:
        f.engine.plan = Plan(hold=gate)
        pool = f.env.app.state.wf.db.engine.pool
        out = []
        th = threading.Thread(target=lambda: out.append(f.start()))
        th.start()
        try:
            until(lambda: f.engine.seen, what="the fake agent to take the job")  # the POST is waiting, the agent "thinks"
            samples = []
            for _ in range(10):
                samples.append(pool.checkedout())
                time.sleep(0.05)
            assert min(samples) == 0, samples  # polling borrows a connection for a moment, never for the wait
        finally:
            gate.set()
            th.join(30)
        assert out[0][0].status_code == 200


def test_a_reply_while_the_turn_runs_queues_behind_it_and_the_turns_run_one_at_a_time(sf):
    gate = threading.Event()

    def plan(text):
        if "ống nước" in text:
            return Plan(say=("first",), hold=gate)
        return Plan(say=("second",), state="awaiting_confirmation")

    sf.engine.plan = plan
    try:
        with sf.waiting(0.3):
            start, started = sf.begin()  # 202: the first turn is held
            assert started["request_status"] in ("queued", "running")
            r, _ = sf.reply(start, started)
            assert r.status_code == 202 and r.json()["workflow_id"] == started["workflow_id"]
            assert r.json()["workflow_state"] == "active"  # busy stays busy: no extra revision, no new state
        assert [text for _, text in sf.engine.seen] == [start["message"]["text"]]  # the second turn has not begun
    finally:
        gate.set()
    ids = (started["request_id"], r.json()["request_id"])
    until(lambda: all(sf.request(x).json()["request_status"] == "completed" for x in ids), what="both requests")
    got = {x: sf.request(x).json() for x in ids}  # read again once both are done: where the workflow is NOW
    first, second = got[ids[0]], got[ids[1]]
    assert [m["text"] for m in first["result"]["messages"]] == ["first"]
    assert [m["text"] for m in second["result"]["messages"]] == ["second"]
    assert [text for _, text in sf.engine.seen] == [start["message"]["text"], "Tôi rảnh từ 14 giờ."]
    # a GET shows where the workflow is now (contract 9.3), which is where the second turn left it
    assert first["workflow_state"] == second["workflow_state"] == "awaiting_confirmation"
    assert sf.env.sql("select count(*) from wf_jobs where workflow_id=? and status='done'",
                      (started["workflow_id"],)) == [(2,)]


# ---- idempotency -----------------------------------------------------------------------------------
def test_a_replay_returns_the_same_bytes_and_creates_nothing(sf):
    body = sf.start_body()
    first = sf.post(body)
    before = counts(sf.env)
    again = sf.post(body)
    assert first.status_code == again.status_code == 200
    assert again.content == first.content  # same message ids, same text, same times
    assert counts(sf.env) == before
    assert len(sf.engine.seen) == 1  # the model was asked once


def test_a_replay_is_the_same_after_the_workflow_moved_on(sf):
    body = sf.start_body()
    first = sf.post(body)
    j = first.json()
    sf.engine.plan = Plan(state="awaiting_confirmation")
    assert sf.reply(body, j)[0].status_code == 200
    assert sf.post(body).content == first.content
    got = sf.request(j["request_id"]).json()  # the result stays as it was; what to do next follows the workflow
    assert got["result"] == j["result"] and got["completed_at"] == j["completed_at"]
    assert (got["workflow_state"], got["next_action"]) == ("awaiting_confirmation", "confirm_close")


def test_a_replay_of_a_slow_request_is_202_with_the_same_ids_then_200_once_done(sf):
    gate = threading.Event()
    sf.engine.plan = Plan(say=("done",), hold=gate)
    body = sf.start_body()
    try:
        with sf.waiting(0.3):
            a = sf.post(body)
            b = sf.post(body)  # waits again, still running
        assert a.status_code == b.status_code == 202
        assert a.json()["request_id"] == b.json()["request_id"] and a.json()["workflow_id"] == b.json()["workflow_id"]
        assert sf.env.sql("select count(*) from wf_jobs where request_id=?", (a.json()["request_id"],)) == [(1,)]
    finally:
        gate.set()
    until(lambda: sf.request(a.json()["request_id"]).json()["request_status"] == "completed", what="the turn")
    c = sf.post(body)
    assert c.status_code == 200 and c.json()["request_id"] == a.json()["request_id"]
    assert c.json()["result"]["messages"][0]["text"] == "done"
    assert sf.post(body).content == c.content
    assert len(sf.engine.seen) == 1


def test_same_id_with_a_different_body_is_409_and_changes_nothing(sf):
    body = sf.start_body()
    sf.post(body)
    before = counts(sf.env)
    for change in ({"message": {"type": "text", "text": "another thing"}},
                   {"external_user_id": "resident-999"}, {"external_ticket_id": "T-other"},
                   {"external_conversation_id": "C-other"}, {"timezone": "Asia/Tokyo"}):
        r = sf.post({**body, **change})
        assert_envelope(r, 409, "IDEMPOTENCY_CONFLICT")
    assert counts(sf.env) == before


def test_the_idempotency_namespace_is_shared_by_start_and_reply(sf):
    start, started = sf.begin()
    reused = sf.reply_body(started, start, external_request_id=start["external_request_id"])
    assert_envelope(sf.post(reused), 409, "IDEMPOTENCY_CONFLICT")


def test_ids_are_scoped_to_the_partner_client(sf):
    body = sf.start_body()
    first = sf.post(body)
    other = sf.env.client(domain="travel", name="Other")
    k = sf.env.key(other["client_id"])
    sf.env.active_route(other["client_id"], k["api_key"])
    r = sf.post(body, headers=key_headers(k["api_key"]))
    assert r.status_code == 200 and r.json()["request_id"] != first.json()["request_id"]


def test_a_replay_still_works_after_the_workflow_is_closed(sf):
    body = sf.start_body()
    first = sf.post(body)
    assert sf.close(first.json(), body)[0].status_code == 200
    assert sf.post(body).content == first.content


def test_concurrent_identical_requests_create_exactly_one_request_workflow_and_job(sf):
    sf.engine.plan = Plan(delay=0.2)
    body = sf.start_body()
    before = counts(sf.env)
    out = par(lambda i: sf.post(body), n=8)
    assert {r.status_code for r in out} <= {200, 202}
    assert len({r.json()["request_id"] for r in out}) == 1 and len({r.json()["workflow_id"] for r in out}) == 1
    after = counts(sf.env)
    for name in ("wf_requests", "wf_conversations", "wf_workflows", "wf_jobs", "awp_cases"):
        assert after[name] == before[name] + 1, name
    assert after["wf_messages"] == before["wf_messages"] + 2  # the resident's and the one answer
    assert len(sf.engine.seen) == 1
    done = [r for r in out if r.status_code == 200]
    assert len({r.content for r in done}) == 1


def test_concurrent_requests_for_one_ticket_leave_one_workflow_and_clean_refusals(sf):
    base = sf.start_body()
    def go(i):
        return sf.post({**base, "external_request_id": f"race-{base['external_request_id']}-{i}"})
    out = par(go, n=6)
    ok = [r for r in out if r.status_code in (200, 202)]
    refused = [r for r in out if r.status_code == 409]
    assert len(ok) == 1 and len(refused) == 5
    assert {r.json()["error"]["code"] for r in refused} == {"TICKET_ALREADY_BOUND"}
    assert sf.env.sql("select count(*) from wf_workflows where external_ticket_id=?",
                      (base["external_ticket_id"],)) == [(1,)]
    assert sf.env.sql("select count(*) from wf_requests where external_request_id like ?",
                      (f"race-{base['external_request_id']}-%",)) == [(1,)]


# ---- order of checks (spec 7.2) -----------------------------------------------------------------------
def test_credential_is_checked_before_the_body(sf):
    r = sf.http.post("/workforce/v1/partner/requests", content=b"{not json", headers={"content-type": "application/json"})
    assert_envelope(r, 401, "UNAUTHENTICATED")
    r = sf.http.post("/workforce/v1/partner/requests", json={"x": 1},
                     headers=key_headers("dp_deadbeefdeadbeef.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"))
    assert_envelope(r, 401, "UNAUTHENTICATED")


def test_the_operation_depends_on_the_command_and_is_checked_before_the_schema(sf):
    reply_only = only_keys(sf.env, sf, ["reply", "read_result"])
    submit_only = only_keys(sf.env, sf, ["submit_request", "read_result"])
    neither = only_keys(sf.env, sf, ["read_result", "close_workflow"])
    garbage = {"command_type": "start_workflow", "junk": True}  # would be a 422 on its own
    assert assert_envelope(sf.post(garbage, headers=reply_only), 403, "PERMISSION_DENIED")["details"] == {
        "operation": "submit_request"}
    assert assert_envelope(sf.post({"command_type": "workflow_reply"}, headers=submit_only), 403,
                           "PERMISSION_DENIED")["details"] == {"operation": "reply"}
    assert_envelope(sf.post({"command_type": "start_workflow"}, headers=neither), 403, "PERMISSION_DENIED")
    assert_envelope(sf.post({"command_type": "teleport"}, headers=neither), 403, "PERMISSION_DENIED")
    assert_envelope(sf.post(garbage, headers=submit_only), 422, "VALIDATION_FAILED")
    start, started = sf.begin()
    body = sf.reply_body(started, start)
    assert sf.post(body, headers=reply_only).status_code == 200  # a reply-only key can reply
    assert_envelope(sf.post(sf.start_body(), headers=reply_only), 403, "PERMISSION_DENIED")


def test_a_non_json_body_is_400(sf):
    h = {**sf.h, "content-type": "application/json"}
    assert_envelope(sf.http.post("/workforce/v1/partner/requests", content=b"{nope", headers=h), 400, "INVALID_REQUEST")
    assert_envelope(sf.http.post("/workforce/v1/partner/requests", content=b"[1]", headers=h), 400, "INVALID_REQUEST")


@pytest.mark.parametrize("change,status,code", [
    ({"command_type": "teleport"}, 422, "VALIDATION_FAILED"),
    ({"command_type": None}, 422, "VALIDATION_FAILED"),
    ({"schema_version": "2"}, 422, "VALIDATION_FAILED"),
    ({"schema_version": None}, 422, "VALIDATION_FAILED"),
    ({"workflow_id": "wf_123"}, 400, "INVALID_REQUEST"),  # a start never names a workflow
    ({"message": {"type": "image", "asset_id": "ast_1"}}, 422, "UNSUPPORTED_MESSAGE_PART"),
    ({"message": {"type": "file", "name": "x.pdf"}}, 422, "UNSUPPORTED_MESSAGE_PART"),
    ({"message": "just a string"}, 422, "VALIDATION_FAILED"),
    ({"message": {"type": "text"}}, 422, "VALIDATION_FAILED"),
    ({"message": {"type": "text", "text": ""}}, 422, "VALIDATION_FAILED"),
    ({"message": {"type": "text", "text": "  \n "}}, 422, "VALIDATION_FAILED"),
    ({"message": {"type": "text", "text": "x" * 20001}}, 422, "VALIDATION_FAILED"),
    ({"message": {"type": "text", "text": "hi", "asset_ids": ["a"]}}, 422, "VALIDATION_FAILED"),
    ({"external_request_id": None}, 422, "VALIDATION_FAILED"),
    ({"external_request_id": ""}, 422, "VALIDATION_FAILED"),
    ({"external_request_id": "x" * 201}, 422, "VALIDATION_FAILED"),
    ({"external_request_id": "bad\u0007id"}, 422, "VALIDATION_FAILED"),
    ({"external_user_id": None}, 422, "VALIDATION_FAILED"),
    ({"external_conversation_id": None}, 422, "VALIDATION_FAILED"),
    ({"external_management_ref": None}, 422, "VALIDATION_FAILED"),
    ({"timezone": "Mars/Base"}, 422, "VALIDATION_FAILED"),
    ({"ticket_id": "ticket_1"}, 422, "VALIDATION_FAILED"),  # ids the partner may not send
    ({"group_id": "g1"}, 422, "VALIDATION_FAILED"),
    ({"route_id": "route_1"}, 422, "VALIDATION_FAILED"),
    ({"agent_id": "a1"}, 422, "VALIDATION_FAILED"),
    ({"conversation_id": "conv_1"}, 422, "VALIDATION_FAILED"),
])
def test_schema_problems_are_refused_before_anything_is_written(sf, change, status, code):
    body = {**sf.start_body(), **change}
    body = {k: v for k, v in body.items() if v is not None}
    before = counts(sf.env)
    assert_envelope(sf.post(body), status, code)
    assert counts(sf.env) == before


def test_a_reply_without_workflow_id_is_422_workflow_reference_required(sf):
    start, started = sf.begin()
    body = sf.reply_body(started, start)
    del body["workflow_id"]
    before = counts(sf.env)
    assert_envelope(sf.post(body), 422, "WORKFLOW_REFERENCE_REQUIRED")
    assert counts(sf.env) == before


def test_the_message_limit_follows_the_setting(make_flow):
    with make_flow(wf_text_limit=50) as f:
        assert f.post(f.start_body(message={"type": "text", "text": "x" * 50})).status_code == 200
        assert_envelope(f.post(f.start_body(message={"type": "text", "text": "x" * 51})), 422, "VALIDATION_FAILED")


def test_schema_is_checked_before_the_route(sf):
    body = sf.start_body(external_management_ref="NO-SUCH-REF", message={"type": "text", "text": ""})
    assert_envelope(sf.post(body), 422, "VALIDATION_FAILED")
    assert_envelope(sf.post(sf.start_body(external_management_ref="NO-SUCH-REF")), 403, "ROUTE_NOT_AUTHORIZED")


def test_the_route_must_exist_be_active_and_allowed_for_the_key(sf):
    env, cid = sf.env, sf.client["client_id"]
    before = counts(env)
    assert_envelope(sf.post(sf.start_body(external_management_ref="NO-SUCH-REF")), 403, "ROUTE_NOT_AUTHORIZED")
    pending = env.route(cid, "PENDING-REF")  # onboarded but never confirmed by the partner
    r = sf.post(sf.start_body(external_management_ref="PENDING-REF"))
    err = assert_envelope(r, 403, "ROUTE_NOT_AUTHORIZED")
    assert err["details"] == {"reason": "route_not_active"}
    other_client = env.client(domain="travel", name="Other")
    ok = env.key(other_client["client_id"])
    env.active_route(other_client["client_id"], ok["api_key"], ref="THEIRS")
    err = assert_envelope(sf.post(sf.start_body(external_management_ref="THEIRS")), 403, "ROUTE_NOT_AUTHORIZED")
    assert err["details"] == {}  # another partner's office is indistinguishable from none
    narrow = env.key(cid, routes=[pending["route_id"]])  # a key limited to another route
    assert_envelope(sf.post(sf.start_body(), headers=key_headers(narrow["api_key"])), 403, "ROUTE_NOT_AUTHORIZED")
    assert counts(env) == before


def test_an_atomic_failure_leaves_no_trace(sf, monkeypatch):
    before = counts(sf.env)
    cases = sf.env.app.state.wf.rt.cases

    async def boom(*a, **k):
        raise RuntimeError("database went away")

    monkeypatch.setattr(cases, "create_case", boom)
    r = sf.post(sf.start_body())
    assert_envelope(r, 500, "INTERNAL_ERROR")
    assert counts(sf.env) == before  # request, conversation, workflow, events, message, job: none


def test_a_failure_while_writing_events_leaves_the_reply_unrecorded(sf, monkeypatch):
    start, started = sf.begin()
    body = sf.reply_body(started, start)
    before = counts(sf.env)
    import awp.workforce.commands as cmd

    async def boom(*a, **k):
        raise RuntimeError("event log is down")

    monkeypatch.setattr(cmd, "emit", boom)
    assert_envelope(sf.post(body), 500, "INTERNAL_ERROR")
    assert counts(sf.env) == before
    monkeypatch.undo()
    assert sf.post(body).status_code == 200  # the same id works once the fault is gone


def test_the_engine_is_told_after_the_commit_and_a_broken_engine_does_not_fail_the_post(sf):
    class Broken:
        def notify(self, *a):
            raise RuntimeError("engine fell over")

    real = sf.env.app.state.wf.engine
    sf.env.app.state.wf.engine = Broken()
    try:
        with sf.waiting(0.3):
            r, _ = sf.start()
    finally:
        sf.env.app.state.wf.engine = real
    assert r.status_code == 202  # recorded; the job is waiting for an engine
    assert sf.env.sql("select count(*) from wf_jobs where status='queued'")[0][0] >= 1
