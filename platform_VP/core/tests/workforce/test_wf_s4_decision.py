"""POST /partner/approvals/{id}/decision (contract 9.8): every check, in order, and what a refusal leaves behind
(nothing); idempotency; the approvals of other residents and other chats; the reject path (slice S4)."""
from __future__ import annotations

import threading

import consentkit as ck
from conftest import key_headers
from enginekit import world
from fake_llm import CALLS
from test_wf_commands import counts
from test_wf_errors import assert_envelope
from test_wf_s4_flow import TOOLS, _clean, text_of, texts, trip  # noqa: F401 - _clean is an autouse fixture

P = "/workforce/v1/partner"


def picture(w, wid: str) -> tuple:
    """Everything a refused decision must leave as it was."""
    return (counts(w.env), w.sql("select state, revision from wf_workflows where id=?", (wid,)),
            w.sql("select status, used_at, resumed_at from wf_approvals order by id"), list(ck.BOOKED))


def test_a_refused_decision_checks_in_order_and_leaves_nothing_behind(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        wid, conv = first["workflow_id"], first["conversation_id"]
        [appr] = f.approvals(conv)
        aid = appr["approval_id"]
        sealed = picture(w, wid)
        wrong = [
            (dict(arguments_hash="sha256:" + "0" * 64), 409, "ARGUMENTS_HASH_MISMATCH"),
            (dict(quote_ref="quote_9"), 409, "QUOTE_MISMATCH"),
            (dict(expected_revision=appr["expected_revision"] + 1), 409, "REVISION_CONFLICT"),
            (dict(expected_revision=0), 409, "REVISION_CONFLICT"),
            (dict(external_user_id="resident-999"), 403, "PERMISSION_DENIED"),  # another resident's approval
            (dict(external_ticket_id="TICKET-OTHER"), 409, "WORKFLOW_BINDING_MISMATCH"),
            (dict(external_ticket_id=None), 422, "EXTERNAL_TICKET_REQUIRED"),
            (dict(external_conversation_id="CHAT-OTHER"), 409, "WORKFLOW_BINDING_MISMATCH"),
            (dict(workflow_id="wf_other"), 409, "WORKFLOW_BINDING_MISMATCH"),
            (dict(decision="maybe"), 422, "VALIDATION_FAILED"),
            (dict(schema_version="2"), 422, "VALIDATION_FAILED"),
            (dict(expected_revision="3"), 422, "VALIDATION_FAILED"),
            (dict(extra_field=1), 422, "VALIDATION_FAILED"),
            (dict(arguments_hash=None), 422, "VALIDATION_FAILED"),
        ]
        for over, status, code in wrong:
            body = f.decide_body(start, first, appr, external_request_id="rq-reused", **over)  # None drops a field
            err = assert_envelope(f.decide(aid, body), status, code)
            assert "Sunrise" not in str(err) and appr["arguments_hash"] not in str(err)
            assert picture(w, wid) == sealed, (over, code)
        err = assert_envelope(f.decide(aid, f.decide_body(start, first, appr, expected_revision=99)), 409, "REVISION_CONFLICT")
        assert err["details"] == {"current_revision": appr["expected_revision"]}

        # the id of a refused decision can be used again: it left no request behind
        ok = f.decide(aid, f.decide_body(start, first, appr, external_request_id="rq-reused"))
        assert ok.status_code == 202
        w.wait_state(wid, "awaiting_confirmation")
        assert len(ck.BOOKED) == 1


def test_who_may_decide(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        wid, conv = first["workflow_id"], first["conversation_id"]
        [appr] = f.approvals(conv)
        aid, body = appr["approval_id"], f.decide_body(start, first, appr)
        sealed = picture(w, wid)
        assert_envelope(f.decide("appr_" + "0" * 32, body), 404, "NOT_FOUND")  # no such approval
        # a key of another client finds nothing; a key without the operation or the route is refused
        other = w.env.client(name="Other")
        theirs = key_headers(w.env.key(other["client_id"])["api_key"])
        assert_envelope(f.decide(aid, body, theirs), 404, "NOT_FOUND")
        no_op = key_headers(w.env.key(f.client["client_id"], operations=["reply", "read_result"])["api_key"])
        assert_envelope(f.decide(aid, body, no_op), 403, "PERMISSION_DENIED")
        elsewhere = w.env.active_route(f.client["client_id"], f.key["api_key"], ref="OTHER-OFFICE")
        only_other = key_headers(w.env.key(f.client["client_id"], routes=[elsewhere["route_id"]])["api_key"])
        assert_envelope(f.decide(aid, body, only_other), 403, "ROUTE_NOT_AUTHORIZED")
        assert_envelope(f.decide(aid, body, {}), 401, "UNAUTHENTICATED")
        assert picture(w, wid) == sealed and ck.BOOKED == []


def test_a_decision_on_a_suspended_route_blocks_the_workflow_like_a_reply_does(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        wid = first["workflow_id"]
        [appr] = f.approvals(first["conversation_id"])
        assert w.env.post(f"/platform/v1/wf/routes/{f.route['route_id']}/suspend").status_code == 200
        err = assert_envelope(f.decide(appr["approval_id"], f.decide_body(start, first, appr)), 403, "ROUTE_NOT_AUTHORIZED")
        assert err["details"] == {"reason": "route_suspended"}
        assert w.state(wid)[0] == "blocked_authorization" and ck.BOOKED == []
        assert w.sql("select status from wf_approvals") == [("pending",)]  # nothing was decided
        assert w.sql("select count(*) from wf_jobs where kind='approval_resume'") == [(0,)]
        again = assert_envelope(f.decide(appr["approval_id"], f.decide_body(start, first, appr)), 403, "ROUTE_NOT_AUTHORIZED")
        assert again["details"] == {"reason": "route_suspended"}


def test_the_approval_of_one_chat_cannot_decide_for_another(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        f = w.flow
        a, a1, a2 = trip(w)
        b, b1, b2 = trip(w)
        [appr_a] = f.approvals(a1["conversation_id"])
        [appr_b] = f.approvals(b1["conversation_id"])
        assert appr_a["approval_id"] != appr_b["approval_id"] and appr_a["arguments_hash"] == appr_b["arguments_hash"]
        # A's approval with B's ticket, chat and workflow; and B's approval with A's
        for aid, mine, theirs, ap in ((appr_a, b, b1, appr_b), (appr_b, a, a1, appr_a)):
            body = f.decide_body(mine, theirs, ap)
            assert_envelope(f.decide(aid["approval_id"], body), 409, "WORKFLOW_BINDING_MISMATCH")
        # the right pair works, and only on its own chat
        assert f.decide(appr_a["approval_id"], f.decide_body(a, a1, appr_a)).status_code == 202
        w.wait_state(a1["workflow_id"], "awaiting_confirmation")
        assert w.state(b1["workflow_id"])[0] == "awaiting_approval" and len(ck.BOOKED) == 1
        assert [x["approval_id"] for x in f.approvals(b1["conversation_id"])] == [appr_b["approval_id"]]


def test_duplicate_decisions(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        [appr] = f.approvals(first["conversation_id"])
        aid, body = appr["approval_id"], f.decide_body(start, first, appr)
        one = f.decide(aid, body)
        assert one.status_code == 202
        w.wait_state(first["workflow_id"], "awaiting_confirmation")
        # the same id and body (a lost 202): the stored answer, nothing runs again
        n = counts(w.env)
        again = f.decide(aid, body)
        assert again.status_code == 202 and again.json() == one.json() and counts(w.env) == n
        # the same id with another body: a conflict
        assert_envelope(f.decide(aid, {**body, "decision": "reject"}), 409, "IDEMPOTENCY_CONFLICT")
        assert_envelope(f.decide(aid, {**body, "quote_ref": "q"}), 409, "IDEMPOTENCY_CONFLICT")
        # another id for the same approval: it is decided already
        err = assert_envelope(f.decide(aid, {**body, "external_request_id": "rq-second"}), 409, "APPROVAL_NOT_PENDING")
        assert err["details"] == {"status": "approved"}
        # the namespace is shared with requests: a decision id is not a reply id, and the other way round
        stranger = f.post(f.reply_body(first, start, external_request_id=body["external_request_id"]))
        assert_envelope(stranger, 409, "IDEMPOTENCY_CONFLICT")
        assert len(ck.BOOKED) == 1


def test_two_identical_decisions_at_once_decide_once(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        [appr] = f.approvals(first["conversation_id"])
        body = f.decide_body(start, first, appr)
        out: list = []
        threads = [threading.Thread(target=lambda: out.append(f.decide(appr["approval_id"], body))) for _ in range(6)]
        [x.start() for x in threads]
        [x.join() for x in threads]
        assert sorted(r.status_code for r in out) == [202] * 6 and len({r.text for r in out}) == 1
        w.wait_state(first["workflow_id"], "awaiting_confirmation")
        assert len(ck.BOOKED) == 1
        assert w.sql("select count(*) from wf_jobs where kind='approval_resume'") == [(1,)]
        assert w.sql("select count(*) from wf_events where event_type='approval.resolved'") == [(1,)]


def test_a_rejection_tells_the_agent_denied_and_the_tool_never_runs(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        [appr] = f.approvals(first["conversation_id"])
        d = f.decide(appr["approval_id"], f.decide_body(start, first, appr, "reject"))
        assert d.status_code == 202 and d.json()["status"] == "rejected"
        w.wait_state(first["workflow_id"], "awaiting_user")
        w.quiet()
        assert ck.BOOKED == []
        assert w.sql("select status from wf_approvals") == [("rejected",)]
        mine = w.sql("select r.id from wf_requests r join wf_approvals a on a.decision_request_id=r.id")
        got = f.request(mine[0][0]).json()
        assert texts(got) == ["Understood, nothing was booked. Anything else?"]
        assert (got["workflow_state"], got["next_action"]) == ("awaiting_user", "submit_reply")
        shape = " ".join(str(x) for x in CALLS[-1]["shape"])
        assert "denied by user" in shape  # what the model was told
        resolved = [e["payload"] for e in f.history(first["conversation_id"], limit=500).json()["items"]
                    if e["event_type"] == "approval.resolved"]
        assert resolved == [{"approval_id": appr["approval_id"], "status": "rejected"}]
        # the resident can go on talking in the same ticket
        r = f.reply(start, first, message=text_of("Never mind."))[0]
        assert r.status_code == 200 and r.json()["workflow_state"] in ("awaiting_user", "active")
