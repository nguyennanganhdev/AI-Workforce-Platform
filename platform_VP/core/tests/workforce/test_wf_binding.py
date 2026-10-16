"""Ticket binding, residences, route changes and isolation between chats (contract 6.3, 9.1.1, 13.3, 13.9)."""
import pytest

from conftest import ADM, key_headers
from fake_engine import Plan
from test_wf_commands import counts
from test_wf_errors import assert_envelope

W = "/platform/v1/wf"


def nothing_written(env, before):
    """A refused command dispatches nothing: no request, message, event, job or case."""
    assert counts(env) == before


# ---- the six binding errors ---------------------------------------------------------------------------
def test_start_without_a_ticket_on_a_ticketed_route_is_422_external_ticket_required(sf):
    body = sf.start_body(external_ticket_id=None)
    before = counts(sf.env)
    assert_envelope(sf.post(body), 422, "EXTERNAL_TICKET_REQUIRED")
    nothing_written(sf.env, before)


def test_reply_without_a_ticket_on_a_ticketed_route_is_422_external_ticket_required(sf):
    start, started = sf.begin()
    body = sf.reply_body(started, start)
    del body["external_ticket_id"]
    before = counts(sf.env)
    assert_envelope(sf.post(body), 422, "EXTERNAL_TICKET_REQUIRED")
    nothing_written(sf.env, before)


def test_a_second_start_for_the_same_ticket_is_409_ticket_already_bound(sf):
    start, started = sf.begin()
    again = sf.start_body(external_ticket_id=start["external_ticket_id"])  # new request id, new chat
    before = counts(sf.env)
    err = assert_envelope(sf.post(again), 409, "TICKET_ALREADY_BOUND")
    assert err["details"] == {"workflow_id": started["workflow_id"]}  # the way forward: workflow_reply
    nothing_written(sf.env, before)


def test_the_workflow_id_is_not_revealed_to_another_user_of_the_ticket(sf):
    start, started = sf.begin()
    other = sf.start_body(external_ticket_id=start["external_ticket_id"], external_user_id="resident-999")
    err = assert_envelope(sf.post(other), 409, "TICKET_ALREADY_BOUND")
    assert err["details"] == {}
    assert started["workflow_id"] not in sf.post(other).text


def test_a_closed_ticket_stays_bound(sf):
    start, started = sf.begin()
    assert sf.close(started, start)[0].status_code == 200
    again = sf.start_body(external_ticket_id=start["external_ticket_id"])
    assert_envelope(sf.post(again), 409, "TICKET_ALREADY_BOUND")  # never reused for a new matter


@pytest.mark.parametrize("what", ["other_ticket", "no_ticket_mode", "other_user"])
def test_a_new_ticket_in_a_used_chat_is_409_conversation_already_bound(sf, what):
    start, started = sf.begin()
    over = {"external_conversation_id": start["external_conversation_id"]}
    if what == "other_user":
        over["external_user_id"] = "resident-999"
    before = counts(sf.env)
    if what == "no_ticket_mode":
        env, cid = sf.env, sf.client["client_id"]
        env.active_route(cid, sf.key["api_key"], ref="FREE-CHAT", ticket_binding_mode="none")
        before = counts(env)
        r = sf.post(sf.start_body(external_management_ref="FREE-CHAT", external_ticket_id=None, **over))
    else:
        r = sf.post(sf.start_body(**over))
    assert_envelope(r, 409, "CONVERSATION_ALREADY_BOUND")
    nothing_written(sf.env, before)


def test_reusing_a_closed_chat_for_a_new_ticket_is_refused(sf):
    start, started = sf.begin()
    sf.close(started, start)
    r = sf.post(sf.start_body(external_conversation_id=start["external_conversation_id"]))
    assert_envelope(r, 409, "CONVERSATION_ALREADY_BOUND")


def test_a_mismatched_tuple_is_409_and_dispatches_nothing(sf):
    a_start, a = sf.begin()
    b_start, b = sf.begin()  # a second chat of the same resident
    other_user, _ = sf.begin(external_user_id="resident-777")

    variants = {
        "TICKET-A + CHAT-B": dict(external_conversation_id=b_start["external_conversation_id"]),
        "TICKET-A + wf_B": dict(workflow_id=b["workflow_id"]),
        "TICKET-B + CHAT-A": dict(external_ticket_id=b_start["external_ticket_id"]),
        "someone else's user": dict(external_user_id="resident-777"),
        "wrong user and chat": dict(external_user_id="resident-777",
                                    external_conversation_id=other_user["external_conversation_id"]),
        "unknown workflow": dict(workflow_id="wf_00000000000000000000000000000000"),
    }
    sf.engine.seen.clear()
    for name, over in variants.items():
        body = sf.reply_body(a, a_start, **over)
        before = counts(sf.env)
        err = assert_envelope(sf.post(body), 409, "WORKFLOW_BINDING_MISMATCH")
        assert err["details"] == {}, name
        nothing_written(sf.env, before)
    assert sf.engine.seen == []  # the engine was never asked anything


def test_a_workflow_of_another_partner_is_a_mismatch_not_a_leak(sf):
    start, started = sf.begin()
    other = sf.env.client(domain="travel", name="Other")
    k = sf.env.key(other["client_id"])
    sf.env.active_route(other["client_id"], k["api_key"])
    body = sf.reply_body(started, start)
    assert_envelope(sf.post(body, headers=key_headers(k["api_key"])), 409, "WORKFLOW_BINDING_MISMATCH")


def test_a_reply_into_a_closed_workflow_is_409_workflow_closed_and_writes_nothing(sf):
    start, started = sf.begin()
    assert sf.close(started, start)[0].status_code == 200
    body = sf.reply_body(started, start)
    before = counts(sf.env)
    assert_envelope(sf.post(body), 409, "WORKFLOW_CLOSED")
    nothing_written(sf.env, before)


def test_the_binding_is_checked_before_the_closed_state(sf):
    start, started = sf.begin()
    sf.close(started, start)
    wrong = sf.reply_body(started, start, external_user_id="resident-999")
    assert_envelope(sf.post(wrong), 409, "WORKFLOW_BINDING_MISMATCH")  # a stranger learns nothing about its state


def test_a_reply_while_an_approval_waits_is_409_approval_pending_and_dispatches_nothing(sf):
    start, started = sf.begin()
    wid, cid = started["workflow_id"], started["conversation_id"]
    sf.env.sql("update wf_workflows set state='awaiting_approval' where id=?", (wid,))
    sf.env.sql("insert into wf_approvals (id, workflow_id, conversation_id, client_id, external_user_id, "
               "session_id, agent_id, tool_call_id, tool_name, arguments, arguments_hash, summary, status, "
               "workflow_revision, created_at) values ('appr_1', ?, ?, ?, 'resident-123', 's', 'a', 'c1', "
               "'book', '{}', 'sha256:x', '{}', 'pending', 3, 1.0)", (wid, cid, sf.client["client_id"]))
    before = counts(sf.env)
    err = assert_envelope(sf.post(sf.reply_body(started, start)), 409, "APPROVAL_PENDING")
    assert err["details"] == {"approval_id": "appr_1"}
    nothing_written(sf.env, before)


# ---- non-ticketed routes ---------------------------------------------------------------------------------
def test_a_route_without_ticket_binding_takes_commands_with_and_without_a_ticket(sf):
    sf.env.active_route(sf.client["client_id"], sf.key["api_key"], ref="NO-TICKET", ticket_binding_mode="none")
    start, started = sf.begin(external_management_ref="NO-TICKET", external_ticket_id=None)
    assert started["external_ticket_id"] is None and started["request_status"] == "completed"
    r, _ = sf.reply(start, started)  # no ticket needed on the reply either
    assert r.status_code == 200 and r.json()["workflow_id"] == started["workflow_id"]
    wrong = sf.reply_body(started, start, external_ticket_id="SURPRISE")
    assert_envelope(sf.post(wrong), 409, "WORKFLOW_BINDING_MISMATCH")  # a ticket the workflow never had
    with_ticket, with_started = sf.begin(external_management_ref="NO-TICKET")  # a ticket is still honoured
    assert with_started["external_ticket_id"] == with_ticket["external_ticket_id"]
    again = sf.start_body(external_management_ref="NO-TICKET", external_ticket_id=with_ticket["external_ticket_id"])
    assert_envelope(sf.post(again), 409, "TICKET_ALREADY_BOUND")


# ---- two chats of one resident never mix (13.3) ------------------------------------------------------------
def test_two_tickets_of_one_user_keep_messages_events_and_state_apart(sf):
    def plan(text):
        return Plan(say=(f"answer to: {text}",), state="awaiting_confirmation" if "B2" in text else "awaiting_user")

    sf.engine.plan = plan
    a_start, a = sf.begin(message={"type": "text", "text": "A1 plumbing"})
    b_start, b = sf.begin(message={"type": "text", "text": "B1 hotel"})
    assert a["conversation_id"] != b["conversation_id"] and a["workflow_id"] != b["workflow_id"]
    ra = sf.reply(a_start, a, message={"type": "text", "text": "A2 gate B"})[0].json()
    rb = sf.reply(b_start, b, message={"type": "text", "text": "B2 two nights"})[0].json()
    assert [m["text"] for m in ra["result"]["messages"]] == ["answer to: A2 gate B"]
    assert [m["text"] for m in rb["result"]["messages"]] == ["answer to: B2 two nights"]
    assert (ra["workflow_state"], rb["workflow_state"]) == ("awaiting_user", "awaiting_confirmation")
    for conv, mine, theirs, ticket in ((a["conversation_id"], "A", "B", a_start["external_ticket_id"]),
                                       (b["conversation_id"], "B", "A", b_start["external_ticket_id"])):
        snap = sf.snapshot(conv).json()
        texts = " ".join(m["text"] for m in snap["messages"])
        assert f"{mine}1" in texts and f"{mine}2" in texts and f"{theirs}1" not in texts and f"{theirs}2" not in texts
        assert [w["external_ticket_id"] for w in snap["workflows"]] == [ticket]
        items = sf.history(conv).json()["items"]
        assert items and {i["conversation_id"] for i in items} == {conv}
        assert {i["external_ticket_id"] for i in items} == {ticket}
        assert theirs + "1" not in str([i["payload"] for i in items])
    sf.close(rb, b_start, revision=rb["workflow_revision"])
    assert sf.snapshot(a["conversation_id"]).json()["workflows"][0]["state"] == "awaiting_user"  # A untouched


def test_the_second_chat_sees_nothing_of_the_first_through_the_read_api(sf):
    a_start, a = sf.begin()
    b_start, b = sf.begin()
    sf.reply(a_start, a)
    first = sf.history(a["conversation_id"]).json()["items"]
    cursor_of_a = first[0]["event_id"]
    # a cursor from chat A is refused on chat B, and so is every other id of A
    assert sf.history(b["conversation_id"], after_cursor=cursor_of_a).status_code == 422
    assert sf.request(a["request_id"], user="resident-123").status_code == 200
    assert sf.snapshot(b["conversation_id"], user="someone-else").status_code == 404


# ---- residence rule -------------------------------------------------------------------------------------------------
def test_a_route_that_needs_a_residence_checks_it_on_start(sf):
    env, cid, key = sf.env, sf.client["client_id"], sf.key["api_key"]
    env.active_route(cid, key, ref="NEEDS-RES", residence_required=True)
    env.active_route(cid, key, ref="OTHER-OFFICE", residence_required=True)
    put = lambda rid, ref, user="resident-123", status="active": env.http.put(
        f"/workforce/v1/partner/residences/{rid}", headers=sf.h, json={
            "schema_version": "1", "external_user_id": user, "external_management_ref": ref, "status": status})
    ok_body = sf.start_body(external_management_ref="NEEDS-RES", residence_id="S1-0205")
    start = lambda **o: sf.post(sf.start_body(external_management_ref="NEEDS-RES", **o))
    before = counts(env)
    err = assert_envelope(start(), 422, "VALIDATION_FAILED")
    assert err["details"]["errors"] == [{"field": "residence_id", "reason": "required"}]
    err = assert_envelope(start(residence_id="S1-0205"), 403, "ROUTE_NOT_AUTHORIZED")  # not registered
    assert err["details"] == {"reason": "residence_not_registered"}
    assert put("S1-0205", "NEEDS-RES").status_code == 201
    assert put("S9-9999", "OTHER-OFFICE").status_code == 201
    assert put("S1-0300", "NEEDS-RES", user="resident-555").status_code == 201
    assert_envelope(start(residence_id="S9-9999"), 403, "ROUTE_NOT_AUTHORIZED")  # registered at another office
    assert_envelope(start(residence_id="S1-0300"), 403, "ROUTE_NOT_AUTHORIZED")  # registered to another resident
    nothing_written(env, before)
    ok = sf.post(ok_body)
    assert ok.status_code == 200
    assert env.sql("select meta from wf_workflows w join awp_cases c on c.id = w.case_id where w.id=?",
                   (ok.json()["workflow_id"],))[0][0].count("S1-0205") == 1
    inactive = env.http.put("/workforce/v1/partner/residences/S1-0205", headers=sf.h, json={
        "schema_version": "1", "external_user_id": "resident-123", "external_management_ref": "NEEDS-RES",
        "status": "inactive", "expected_revision": 1})
    assert inactive.status_code == 200
    assert_envelope(start(residence_id="S1-0205"), 403, "ROUTE_NOT_AUTHORIZED")
    # a reply carries no residence: the open workflow keeps working
    reply, _ = sf.reply({**sf.start_body(external_management_ref="NEEDS-RES"), "external_ticket_id": ok_body["external_ticket_id"],
                         "external_conversation_id": ok_body["external_conversation_id"]}, ok.json())
    assert reply.status_code == 200


def test_a_route_that_does_not_need_a_residence_ignores_the_field(sf):
    r, _ = sf.start(residence_id="anything")
    assert r.status_code == 200


# ---- routes suspended or replaced (spec 5, last paragraph) -------------------------------------------------------
def test_a_suspended_route_blocks_its_workflow_and_refuses_the_reply(make_flow):
    with make_flow() as f:
        start, started = f.begin()
        route_id = f.route["route_id"]
        assert f.env.post(f"{W}/routes/{route_id}/suspend").status_code == 200
        before = counts(f.env)
        body = f.reply_body(started, start)
        err = assert_envelope(f.post(body), 403, "ROUTE_NOT_AUTHORIZED")
        assert err["details"] == {"reason": "route_suspended"}
        # the workflow is now blocked, visibly, with one event and a bumped revision
        [wf] = f.snapshot(started["conversation_id"]).json()["workflows"]
        assert (wf["state"], wf["next_action"], wf["revision"]) == (
            "blocked_authorization", "resolve_attention", started["workflow_revision"] + 1)
        items = f.history(started["conversation_id"]).json()["items"]
        assert items[-1]["event_type"] == "workflow.status_changed"
        assert items[-1]["payload"] == {"state": "blocked_authorization", "revision": wf["revision"],
                                        "reason": "route_suspended"}
        after_first = counts(f.env)
        assert after_first["wf_events"] == before["wf_events"] + 1
        for k in ("wf_requests", "wf_messages", "wf_jobs", "wf_workflows", "wf_conversations"):
            assert after_first[k] == before[k], k
        # asking again changes nothing more
        assert_envelope(f.post(f.reply_body(started, start)), 403, "ROUTE_NOT_AUTHORIZED")
        assert counts(f.env) == after_first
        # a new start under the suspended ref is refused too
        err = assert_envelope(f.post(f.start_body()), 403, "ROUTE_NOT_AUTHORIZED")
        assert err["details"] == {"reason": "route_not_active"}
        # reading stays possible, and so does a replay of a request that ran (contract 11.1: a lost
        # answer is recovered by sending the same request again); it creates nothing and returns
        # the stored result
        assert f.snapshot(started["conversation_id"]).status_code == 200
        again = f.post(start)
        assert again.status_code == 200 and again.json()["request_id"] == started["request_id"]
        assert counts(f.env) == after_first


def test_a_replaced_route_leaves_the_old_workflow_on_the_old_route(make_flow):
    with make_flow() as f:
        start, started = f.begin()
        first = f.post(start)  # the same request again: a replay while the route is still active
        assert first.content == f.post(start).content
        old = f.route["route_id"]
        new = f.env.post(f"{W}/routes/{old}/replace", {}).json()["route"]
        # until the partner confirms the new route, the ref has no active route
        body = f.reply_body(started, start)
        err = assert_envelope(f.post(body), 403, "ROUTE_NOT_AUTHORIZED")
        assert err["details"] == {"reason": "route_replaced"}
        [wf] = f.snapshot(started["conversation_id"]).json()["workflows"]
        assert wf["state"] == "blocked_route_changed" and wf["next_action"] == "resolve_attention"
        # confirm the new route: the same ref now means another office
        assert f.env.confirm(f.key["api_key"], new).status_code == 200
        err = assert_envelope(f.post(f.reply_body(started, start)), 403, "ROUTE_NOT_AUTHORIZED")
        assert err["details"] == {"reason": "route_replaced"}
        fresh = f.post(f.start_body())
        assert fresh.status_code == 200
        new_wf = fresh.json()["workflow_id"]
        assert f.env.sql("select route_id from wf_workflows where id=?", (new_wf,)) == [(new["route_id"],)]
        assert f.env.sql("select route_id from wf_workflows where id=?", (started["workflow_id"],)) == [(old,)]
        # the retry of the original request returns the original result, never a workflow under the new office
        again = f.post(start)
        assert again.status_code == 200 and again.json()["workflow_id"] == started["workflow_id"]
        assert f.env.sql("select count(*) from wf_workflows where external_ticket_id=?",
                         (start["external_ticket_id"],)) == [(1,)]
        # history did not move to the new route's conversation
        assert f.snapshot(started["conversation_id"]).json()["messages"][0]["workflow_id"] == started["workflow_id"]


def test_a_workflow_reached_through_the_wrong_office_is_a_mismatch(sf):
    start, started = sf.begin()
    sf.env.active_route(sf.client["client_id"], sf.key["api_key"], ref="SECOND-OFFICE")
    body = sf.reply_body(started, start, external_management_ref="SECOND-OFFICE")
    assert_envelope(sf.post(body), 409, "WORKFLOW_BINDING_MISMATCH")


def test_a_key_that_does_not_cover_the_workflows_route_is_refused(sf):
    start, started = sf.begin()
    other = sf.env.route(sf.client["client_id"], "ANOTHER")
    narrow = sf.env.key(sf.client["client_id"], routes=[other["route_id"]])
    body = sf.reply_body(started, start)
    assert_envelope(sf.post(body, headers=key_headers(narrow["api_key"])), 403, "ROUTE_NOT_AUTHORIZED")
    [(state,)] = sf.env.sql("select state from wf_workflows where id=?", (started["workflow_id"],))
    assert state == "awaiting_user"  # someone else's key lacking rights does not block the workflow
