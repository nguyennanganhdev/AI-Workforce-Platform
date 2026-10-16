"""Fixes after the S2 review: contract answers (failed requests, replays after a remap, GET request),
event-stream limits, residence and route grants."""
import asyncio
import itertools
import queue
import time

import pytest

from conftest import ADM, ALL_CUSTOMER, key_headers
from fake_engine import Plan
from flowkit import P, Flow, Stream
from test_wf_commands import counts
from test_wf_errors import assert_envelope

W = "/platform/v1/wf"


# ---- contract 9.1: a failed request never points back at a normal step ------------------------
@pytest.mark.parametrize("state", ["awaiting_user", "waiting_external_event", "awaiting_confirmation",
                                   "awaiting_approval", "needs_attention", "active"])
def test_a_failed_request_says_resolve_attention_wherever_the_workflow_rests(flow, state):
    reason = "needs_review" if state == "needs_attention" else None
    flow.engine.plan = Plan(state=state, reason=reason, say=(), fail={"code": "TURN_FAILED", "message": "x"})
    r, body = flow.start()
    j = r.json()
    assert r.status_code == 200 and j["request_status"] == "failed" and j["workflow_state"] == state
    assert j["next_action"] == "resolve_attention"
    assert flow.post(body).json()["next_action"] == "resolve_attention"  # the replay is the same
    assert flow.request(j["request_id"]).json()["next_action"] == "resolve_attention"


def test_a_failed_request_of_a_workflow_that_was_closed_since_says_none(flow):
    flow.engine.plan = Plan(state="awaiting_confirmation", say=(), fail={"code": "TURN_FAILED", "message": "x"})
    start, started = flow.begin()
    assert started["next_action"] == "resolve_attention"
    assert flow.close(started, start)[0].status_code == 200
    got = flow.request(started["request_id"]).json()
    assert (got["request_status"], got["workflow_state"], got["next_action"]) == ("failed", "closed", "none")


# ---- contract 9.3: the request keeps its result, the next step follows the workflow ---------------
def test_get_request_next_action_follows_the_workflow(flow):
    flow.engine.plan = Plan(state="awaiting_confirmation")
    start, started = flow.begin()
    assert started["next_action"] == "confirm_close"
    r, _ = flow.close(started, start)
    assert r.status_code == 200
    got = flow.request(started["request_id"]).json()
    assert (got["workflow_state"], got["next_action"], got["workflow_revision"]) == (
        "closed", "none", r.json()["revision"])
    assert got["result"] == started["result"] and got["completed_at"] == started["completed_at"]
    assert got["last_event_id"] == flow.history(started["conversation_id"]).json()["items"][-1]["event_id"]
    assert flow.post(start).json()["next_action"] == "confirm_close"  # the POST replay stays as it was frozen


# ---- contract 9.1 / 11.1: a lost answer is recovered by sending the same request again --------------
def test_a_replay_after_a_remap_reads_the_original_and_creates_nothing(make_flow):
    with make_flow() as f:
        start = f.start_body()
        first = f.post(start)
        assert first.status_code == 200
        old = f.route["route_id"]
        new = f.env.post(f"{W}/routes/{old}/replace", {"external_management_ref": "BQL-OP1-B"}).json()["route"]
        again = f.post(start)  # the new route is not even confirmed yet
        assert again.status_code == 200 and again.content == first.content
        assert f.env.confirm(f.key["api_key"], new).status_code == 200
        before = counts(f.env)
        again = f.post(start)
        assert again.status_code == 200 and again.content == first.content
        assert counts(f.env) == before  # no workflow under the new manager, no new turn
        # the same id with another body is a conflict, never a quiet new request
        other = dict(start, message={"type": "text", "text": "something else"})
        assert_envelope(f.post(other), 409, "IDEMPOTENCY_CONFLICT")
        # a new command under the old ref is still refused
        assert_envelope(f.post(f.start_body()), 403, "ROUTE_NOT_AUTHORIZED")
        assert counts(f.env) == before


def test_a_replay_needs_a_grant_on_the_route_the_request_ran_on(make_flow):
    with make_flow() as f:
        start = f.start_body()
        assert f.post(start).status_code == 200
        old = f.route["route_id"]
        new = f.env.post(f"{W}/routes/{old}/replace", {"external_management_ref": "BQL-OP1-B"}).json()["route"]
        assert f.env.confirm(f.key["api_key"], new).status_code == 200
        only_new = key_headers(f.env.key(f.client["client_id"], operations=ALL_CUSTOMER,
                                         routes=[new["route_id"]])["api_key"])
        before = counts(f.env)
        assert_envelope(f.post(start, headers=only_new), 403, "ROUTE_NOT_AUTHORIZED")
        assert_envelope(f.post(dict(start, message={"type": "text", "text": "x"}), headers=only_new),
                        403, "ROUTE_NOT_AUTHORIZED")  # not even a hint that the id exists
        assert counts(f.env) == before


# ---- a key may only change workflows of routes it is granted ------------------------------------
def test_a_key_scoped_to_the_new_route_does_not_change_a_workflow_of_the_old_one(make_flow):
    with make_flow() as f:
        start, started = f.begin()
        old = f.route["route_id"]
        new = f.env.post(f"{W}/routes/{old}/replace", {}).json()["route"]
        assert f.env.confirm(f.key["api_key"], new).status_code == 200
        only_new = key_headers(f.env.key(f.client["client_id"], operations=ALL_CUSTOMER,
                                         routes=[new["route_id"]])["api_key"])
        before = counts(f.env)
        assert_envelope(f.post(f.reply_body(started, start), headers=only_new), 403, "ROUTE_NOT_AUTHORIZED")
        assert f.env.sql("select state from wf_workflows where id=?", (started["workflow_id"],)) == [
            ("awaiting_user",)]
        assert counts(f.env) == before
        # the key that does cover the old route still blocks it, once
        assert_envelope(f.post(f.reply_body(started, start)), 403, "ROUTE_NOT_AUTHORIZED")
        assert f.env.sql("select state from wf_workflows where id=?", (started["workflow_id"],)) == [
            ("blocked_route_changed",)]


# ---- residence ----------------------------------------------------------------------------------
def test_a_residence_nobody_checked_is_not_kept_in_the_case(sf):
    r, _ = sf.start(residence_id="S9-9999-NOT-REGISTERED")  # this route does not ask for a residence
    assert r.status_code == 200
    [(meta,)] = sf.env.sql("select meta from awp_cases where external_ref=?", (r.json()["workflow_id"],))
    assert "S9-9999-NOT-REGISTERED" not in meta


# ---- the event stream -------------------------------------------------------------------------------
def test_a_revoked_key_stops_a_stream_that_always_has_something_to_send(make_flow, monkeypatch):
    from awp.workforce import stream as st
    seq = itertools.count(1000)

    async def endless(ctx, conversation_id, position):
        await asyncio.sleep(0.002)
        n = next(seq)
        return [{"event_id": f"evt_fake{n}", "sequence": n, "event_type": "assistant.message",
                 "occurred_at": 1.0, "recorded_at": 1.0, "conversation_id": conversation_id,
                 "external_ticket_id": None, "workflow_id": None, "ticket_id": None, "payload": {}}]

    with make_flow(live=True, wf_revalidate_seconds=0.3, wf_sse_poll_seconds=0.1) as f:
        _, started = f.begin()
        monkeypatch.setattr(st, "next_rows", endless)
        s = Stream(f.http, f"{P}/conversations/{started['conversation_id']}/events", f.h,
                   {"external_user_id": "resident-123"})
        try:
            assert s.next(5) is not None
            assert f.env.post(f"{W}/keys/{f.key['key_id']}/revoke").status_code == 200
            end, stop = False, time.monotonic() + 6
            while time.monotonic() < stop and not end:
                try:
                    kind, _ = s.frames.get(timeout=0.5)
                except queue.Empty:
                    continue
                end = kind in ("end", "error")
            assert end, "the stream outlived its revoked key while it had rows to send"
        finally:
            s.close()


def test_one_key_cannot_hold_more_streams_than_the_limit_and_frees_a_slot_when_one_ends(make_flow):
    with make_flow(live=True, wf_max_streams=2) as f:
        _, started = f.begin()
        url = f"{P}/conversations/{started['conversation_id']}/events"
        params = {"external_user_id": "resident-123"}
        a, b = Stream(f.http, url, f.h, params), Stream(f.http, url, f.h, params)
        try:
            assert (a.status, b.status) == (200, 200)
            third = Stream(f.http, url, f.h, params)
            assert third.status == 429 and third.headers.get("retry-after") == "5"
            assert b'"RATE_LIMITED"' in third.body and b'"retryable":true' in third.body
            other = key_headers(f.env.key(f.client["client_id"])["api_key"])  # another key has its own room
            c = Stream(f.http, url, other, params)
            assert c.status == 200
            c.close()
            a.close()
            deadline, freed = time.monotonic() + 8, None
            while time.monotonic() < deadline:
                freed = Stream(f.http, url, f.h, params)
                if freed.status == 200:
                    break
                freed.close()
                time.sleep(0.2)
            assert freed is not None and freed.status == 200, "the slot of the closed stream was never freed"
            freed.close()
        finally:
            a.close()
            b.close()


def test_slots_are_counted_per_key_and_a_release_counts_once():
    from awp.workforce.errors import WorkforceError
    from awp.workforce.stream import Slots
    s = Slots(2)
    r1, r2 = s.take("k"), s.take("k")
    with pytest.raises(WorkforceError) as e:
        s.take("k")
    assert e.value.http == 429 and e.value.headers == {"Retry-After": "5"}
    s.take("other")()
    r1()
    r1()  # twice: still one slot freed
    r3 = s.take("k")
    with pytest.raises(WorkforceError):
        s.take("k")
    r2()
    r3()
    assert not s.open
    free = Slots(0)  # 0 = no limit
    for _ in range(50):
        free.take("k")
