"""Approvals end to end on the real engine and the scripted model (slice S4): contract 13.1, the table of 13.2,
the refusal path, and the confirmation that only the partner's close can answer. Scripted model only."""
from __future__ import annotations

import hashlib

import consentkit as ck
import pytest
import scripts
from enginekit import hold_leader, world

from test_wf_errors import assert_envelope

from awp.workforce.approvals import args_hash, canonical

P = "/workforce/v1/partner"
TOOLS = dict(tools=[ck.factory], leader_tools=["hotel_search", "book_hotel"])


@pytest.fixture(autouse=True)
def _clean():
    ck.BOOKED.clear()
    yield
    ck.BOOKED.clear()


def text_of(s: str) -> dict:
    return {"type": "text", "text": s}


def texts(body: dict) -> list[str]:
    return [m["text"] for m in body["result"]["messages"]]


def types(w, conv: str) -> list[str]:
    return [e["event_type"] for e in w.flow.history(conv, limit=500).json()["items"]]


def trip(w):
    """Start the trip and let the resident choose: the workflow now waits for the consent to the booking."""
    ck.declare(w)
    start, first = w.flow.begin(message=text_of(ck.START))
    r = w.flow.reply(start, first, message=text_of(ck.CHOOSE))[0]
    assert r.status_code == 200, r.text
    return start, first, r.json()


def test_contract_13_1_lookup_choose_approve_book_confirm_close(tmp_path):
    with world(tmp_path, ck.trip, **TOOLS) as w:
        ck.declare(w)
        f = w.flow
        # 1. look-up: the options come back and the workflow waits for the resident
        start, first = f.begin(message=text_of(ck.START))
        assert list(first) == ["request_id", "request_status", "external_ticket_id", "conversation_id", "workflow_id",
                               "workflow_state", "next_action", "workflow_revision", "ticket_id", "result", "error",
                               "accepted_at", "completed_at", "status_url", "conversation_url", "event_stream_url"]
        assert (first["request_status"], first["workflow_state"], first["next_action"]) == (
            "completed", "awaiting_user", "submit_reply")
        assert texts(first) == ["Two options: Lotus 1500000 VND or Sunrise 1800000 VND. Which one?"]
        assert first["ticket_id"] is None and first["error"] is None and ck.BOOKED == []

        # 2. the resident chooses: the booking tool needs consent, so the run parks and the request settles with 200
        r = f.reply(start, first, message=text_of(ck.CHOOSE))[0]
        assert r.status_code == 200, r.text
        second = r.json()
        assert (second["request_status"], second["workflow_state"], second["next_action"]) == (
            "completed", "awaiting_approval", "submit_approval")
        assert second["result"] == {"messages": []} and second["workflow_revision"] > first["workflow_revision"]
        assert ck.BOOKED == []  # nothing was booked on the agent's say-so
        [appr] = f.approvals(second["conversation_id"])
        args = {"hotel": "Sunrise", "nights": 2, "price": "1800000"}
        assert appr["arguments_hash"] == "sha256:" + hashlib.sha256(canonical(args).encode()).hexdigest() == args_hash(args)
        assert (appr["status"], appr["tool_name"], appr["quote_ref"]) == ("pending", "book_hotel", None)
        assert appr["summary"] == {"text": "Book Sunrise for 2 nights at 1800000 VND", "tool": "book_hotel", "arguments": args}
        assert appr["expected_revision"] == second["workflow_revision"]
        required = [e for e in f.history(second["conversation_id"], limit=500).json()["items"]
                    if e["event_type"] == "approval.required"]
        assert len(required) == 1 and required[0]["payload"] == {
            "approval_id": appr["approval_id"], "summary": appr["summary"], "arguments_hash": appr["arguments_hash"],
            "quote_ref": None, "expires_at": appr["expires_at"], "expected_revision": appr["expected_revision"]}

        # 3. the resident decides: 202 with the fields of 9.8, and the agent that asked is woken
        body = f.decide_body(start, second, appr)
        d = f.decide(appr["approval_id"], body)
        assert d.status_code == 202, d.text
        assert list(d.json()) == ["approval_id", "status", "external_ticket_id", "workflow_id", "accepted_at"]
        assert d.json()["status"] == "approved" and d.json()["approval_id"] == appr["approval_id"]
        assert d.json()["external_ticket_id"] == start["external_ticket_id"] and d.json()["workflow_id"] == first["workflow_id"]
        w.wait_state(first["workflow_id"], "awaiting_confirmation")
        assert len(ck.BOOKED) == 1  # the tool ran exactly once, after the consent

        # the continuing turn belongs to the decision request: GET request shows what the agent said
        [(rid, status)] = w.sql("select id, status from wf_requests where external_request_id=?", (body["external_request_id"],))
        w.wait(lambda: w.sql("select status from wf_requests where id=?", (rid,)) == [("completed",)], what="the request")
        got = f.request(rid).json()
        assert (got["request_status"], got["workflow_state"], got["next_action"]) == ("completed", "awaiting_confirmation", "confirm_close")
        assert texts(got) == ["Booked: BK-77 at Sunrise. Is everything right?"]
        assert f.approvals(second["conversation_id"]) == []  # nothing waits any more
        kinds = types(w, second["conversation_id"])
        assert kinds.index("approval.required") < kinds.index("approval.resolved") < kinds.index("workflow.status_changed", kinds.index("approval.resolved"))
        assert kinds[-2:] == ["assistant.message", "workflow.status_changed"]
        resolved = [e for e in f.history(second["conversation_id"], limit=500).json()["items"] if e["event_type"] == "approval.resolved"]
        assert [e["payload"] for e in resolved] == [{"approval_id": appr["approval_id"], "status": "approved"}]

        # 4. only the partner's close ends it, once the resident has confirmed
        snap = f.snapshot(second["conversation_id"]).json()["workflows"][0]
        assert (snap["state"], snap["next_action"]) == ("awaiting_confirmation", "confirm_close")
        c = f.close({"workflow_id": first["workflow_id"], "workflow_revision": snap["revision"]}, start)[0]
        assert c.status_code == 200 and (c.json()["state"], c.json()["next_action"]) == ("closed", "none")
        assert len(ck.BOOKED) == 1
        again = f.decide(appr["approval_id"], body)  # a lost 202 is recovered by sending the same decision again
        assert again.status_code == 202 and again.json() == d.json() and len(ck.BOOKED) == 1


def test_contract_13_2_the_rows_that_exist_without_an_outside_provider(tmp_path):
    """Quote not chosen, consent needed and booking confirmed are the steps of 13.1 above. The others:"""
    for name in ("a", "b", "c"):
        (tmp_path / name).mkdir()
    with world(tmp_path / "a", scripts.lookup) as w:  # read-only, enough result, policy auto-close: closed / none
        _, r = w.flow.begin()
        assert (r["request_status"], r["workflow_state"], r["next_action"]) == ("completed", "closed", "none")
    with world(tmp_path / "b", scripts.lookup, route={"policy": {"auto_close_read_only": False}}) as w:
        _, r = w.flow.begin()  # the same answer, but the route wants the resident's word: awaiting_confirmation
        assert (r["workflow_state"], r["next_action"]) == ("awaiting_confirmation", "confirm_close")
    with world(tmp_path / "c", ck.trip, route={"wait_seconds": 0.3}, **TOOLS) as w:  # no result before the HTTP deadline
        gate = hold_leader()
        resp, _ = w.flow.start(message=text_of(ck.START))
        r = resp.json()
        assert resp.status_code == 202  # the state as it is now, and watch_request
        assert r["request_status"] in ("accepted", "queued", "running") and r["workflow_state"] in ("accepted", "active")
        assert (r["next_action"], r["result"], r["completed_at"]) == ("watch_request", None, None)
        gate.set()
        w.wait(lambda: w.flow.request(r["request_id"]).json()["request_status"] == "completed", what="the request")
        done = w.flow.request(r["request_id"]).json()
        assert (done["workflow_state"], done["next_action"]) == ("awaiting_user", "submit_reply") and texts(done)


def test_a_quote_the_resident_was_shown_must_come_back_with_the_decision(tmp_path):
    with world(tmp_path, ck.consenting(quote="quote_001"), route={"policy": {"approval_ttl_seconds": 120}}, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        [appr] = f.approvals(first["conversation_id"])
        assert appr["quote_ref"] == "quote_001"
        [(ttl,)] = w.sql("select expires_at - created_at from wf_approvals")
        assert round(ttl) == 120  # the route's policy, not the platform default (a day)
        required = [e["payload"] for e in f.history(first["conversation_id"], limit=500).json()["items"]
                    if e["event_type"] == "approval.required"]
        assert required[0]["quote_ref"] == "quote_001"
        for quote in (None, "quote_002"):
            assert_envelope(f.decide(appr["approval_id"], f.decide_body(start, first, appr, quote_ref=quote)), 409, "QUOTE_MISMATCH")
        assert f.decide(appr["approval_id"], f.decide_body(start, first, appr)).status_code == 202
        w.wait_state(first["workflow_id"], "awaiting_confirmation")
        assert any("quote quote_001" in str(row) for row in w.sql("select data from awp_case_items where kind='evidence'"))
