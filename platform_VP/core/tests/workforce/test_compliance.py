"""Contract compliance suite (phase P4): one test for each row of contract 13.9 and each bullet of 14.3.

Every test drives the real HTTP API end to end on the real engine, with the scripted model (tests/fake_llm.py) and
the fakes: a real MCP server for the partner's tools, a signing provider. They prove the platform side only: nothing
here says how a real model, a real partner or a real network behaves. A bullet that belongs to the partner or needs
real infrastructure is an explicit skip with its reason. The table of rows, test ids and status is
docs/WORKFORCE_V1_KIEM_THU_TUAN_THU.md; the scenarios shared by a row and a bullet are in compkit.py.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import consentkit as ck
import compkit
import pytest
import scripts
import t1kit
from compkit import counts, events_of, kinds_of
from conftest import ADM, key_headers
from enginekit import world
from fake_llm import CALLS
from flowkit import Flow
from partnerkit import Partner
from scripts import say
from t1kit import SETTINGS, TOOLS, act, configure
from t2kit import Provider, pending_world, sent_ok, wait_status
from test_wf_errors import assert_envelope
from test_wf_sse import open_stream
from test_wf_t2_apply import DATA, close as close_pending, leader_only_notes

W = "/platform/v1/wf"
CK = dict(tools=[ck.factory], leader_tools=["hotel_search", "book_hotel"])


def said(body: dict) -> list[dict]:
    return body["result"]["messages"]


def text_part(s: str) -> dict:
    return {"type": "text", "text": s}


@pytest.fixture
def partner():
    with Partner() as p:
        yield p


@pytest.fixture(autouse=True)
def _no_bookings_left_over():
    ck.BOOKED.clear()
    yield
    ck.BOOKED.clear()


# The scenarios that a row of 13.9 and a bullet of 14.3 both read: run once for the module.
@pytest.fixture(scope="module")
def replay(tmp_path_factory):
    with Partner() as p:
        return compkit.replayed_post(tmp_path_factory.mktemp("replay"), p)


@pytest.fixture(scope="module")
def slow(tmp_path_factory):
    return compkit.slow_first_turn(tmp_path_factory.mktemp("slow"))


@pytest.fixture(scope="module")
def early(tmp_path_factory):
    with Partner() as p:
        return compkit.events_before_sse(tmp_path_factory.mktemp("early"), p)


@pytest.fixture(scope="module")
def noise(tmp_path_factory):
    with Partner() as p:
        return compkit.provider_noise(tmp_path_factory.mktemp("noise"), p)


@pytest.fixture(scope="module")
def restart(tmp_path_factory):
    with Partner() as p:
        return compkit.restart_while_waiting(tmp_path_factory.mktemp("restart"), p)


@pytest.fixture(scope="module")
def tracking(tmp_path_factory):
    with Partner() as p:
        return compkit.tracking_flow(tmp_path_factory.mktemp("tracking"), p)


# ======================================================================================================================
# 13.9 Các tình huống phải kiểm tra
# ======================================================================================================================
def test_13_9_01_a_post_retried_after_a_lost_response_gets_the_same_result_and_no_second_plumber(replay):
    r = replay
    assert r.again.status_code == 200 and r.again.json() == r.first
    assert r.third.content == r.again.content  # byte for byte, as often as it is asked
    ids = [m["message_id"] for m in said(r.first)]
    assert ids and [m["message_id"] for m in said(r.again.json())] == ids
    assert r.partner_calls == 1 and r.effects == ["repair"]  # the provider was asked to send a plumber once
    assert (r.requests, r.workflows, r.ops) == ([(1,)], [(1,)], 1)


def test_13_9_02_a_first_turn_that_outlives_the_wait_is_202_with_ids_and_the_result_comes_later(slow):
    assert slow.status == 202
    p = slow.pending
    assert p["request_status"] in ("queued", "running") and p["result"] is None and p["next_action"] == "watch_request"
    assert p["conversation_id"] and p["workflow_id"] and p["external_ticket_id"] == slow.body["external_ticket_id"]
    msg = said(slow.by_get)[0]
    assert slow.by_get["workflow_state"] == "awaiting_user" and msg["text"] == "What time suits you?"
    # the same message, by every road the contract offers
    assert slow.by_sse["message_id"] == msg["message_id"] and slow.by_sse["text"] == msg["text"]
    assert [m["message_id"] for m in slow.by_history] == [msg["message_id"]]
    assert [m["message_id"] for m in slow.by_snapshot] == [msg["message_id"]]


def test_13_9_03_events_that_came_before_the_first_sse_are_replayed_from_the_durable_log(early):
    assert [f["id"] for f in early.frames] == [e["event_id"] for e in early.persisted]
    assert [f["data"]["sequence"] for f in early.frames] == list(range(1, len(early.frames) + 1))  # no gap, from 1
    types = [f["event"] for f in early.frames]
    assert types.count("ticket.status_changed") == 2 and "operation.status_changed" in types
    assert types.index("request.accepted") < types.index("ticket.status_changed")
    assert any("Worker An is assigned" in f["data"]["payload"]["text"] for f in early.frames if f["event"] == "assistant.message")


def test_13_9_04_the_same_message_by_post_and_by_sse_has_one_message_id_and_makes_one_bubble(tmp_path):
    with world(tmp_path, scripts.interactive, live=True) as w:
        start, first = w.flow.begin()
        [msg] = said(first)
        s = open_stream(w.flow, first["conversation_id"])
        try:
            frames = s.events(len(events_of(w, first["conversation_id"])))
        finally:
            s.close()
        by_sse = [f["data"]["payload"] for f in frames if f["event"] == "assistant.message"]
        assert [m["message_id"] for m in by_sse] == [msg["message_id"]] and by_sse[0]["text"] == msg["text"]
        bubbles = {m["message_id"] for m in said(first)} | {m["message_id"] for m in by_sse}  # what a client that dedupes shows
        assert len(bubbles) == 1
        snap = w.flow.snapshot(first["conversation_id"]).json()["messages"]
        assert [m["message_id"] for m in snap if m["sender"] == "assistant"] == [msg["message_id"]]


def test_13_9_05_a_reply_continues_the_same_workflow_ticket_conversation_and_context(tmp_path):
    with world(tmp_path, scripts.interactive) as w:
        start, first = w.flow.begin()
        r = w.flow.reply(start, first, message=text_part("Tôi rảnh từ 14 giờ."))[0]
        second = r.json()
        assert r.status_code == 200 and second["request_id"] != first["request_id"]
        for key in ("workflow_id", "conversation_id", "external_ticket_id"):
            assert second[key] == first[key], key
        assert second["workflow_revision"] > first["workflow_revision"]
        assert w.sql("select count(*) from wf_workflows") == [(1,)] and w.sql("select count(*) from awp_cases") == [(1,)]
        assert w.sql("select count(*) from awp_case_sessions where role='leader'") == [(1,)]  # one agent session, kept
        context = str(CALLS[-1]["shape"])  # what the model was shown on the second turn: the first turn is in it
        assert start["message"]["text"] in context and "What time suits you?" in context
        assert [m["text"] for m in said(second)] == ["Noted: 14. Can you confirm?"]


def test_13_9_06_two_chat_boxes_of_one_user_have_their_own_ticket_conversation_workflow_messages_and_sse(tmp_path):
    with world(tmp_path, scripts.topics, live=True) as w:
        f = w.flow
        a_start, a = f.begin(external_ticket_id="TICKET-A", external_conversation_id="CHAT-A",
                             message=text_part("My pipe leaks."))
        b_start, b = f.begin(external_ticket_id="TICKET-B", external_conversation_id="CHAT-B",
                             message=text_part("Please book a hotel."))
        assert len({a["workflow_id"], b["workflow_id"]}) == len({a["conversation_id"], b["conversation_id"]}) == 2
        assert [m["text"] for m in said(a)] == ["Pipe: we will send a plumber."]
        assert [m["text"] for m in said(b)] == ["Hotel: which night do you want?"]
        streams = {c: open_stream(f, c) for c in (a["conversation_id"], b["conversation_id"])}
        try:
            for conv, ticket, other in ((a["conversation_id"], "TICKET-A", "Hotel"), (b["conversation_id"], "TICKET-B", "Pipe")):
                frames = streams[conv].events(len(events_of(w, conv)))
                assert {fr["data"]["external_ticket_id"] for fr in frames} == {ticket}  # nothing of the other box
                assert other not in str([fr["data"]["payload"] for fr in frames])
            before_b = events_of(w, b["conversation_id"])
            f.reply(a_start, a, message=text_part("Come in the morning."))  # a reply in box A ...
            after_a = streams[a["conversation_id"]].events(2, timeout=30)  # ... shows up in A's stream
            assert {fr["data"]["external_ticket_id"] for fr in after_a} == {"TICKET-A"}
            assert events_of(w, b["conversation_id"]) == before_b  # ... and not a thing in B's log
            assert w.flow.snapshot(b["conversation_id"]).json()["messages"][-1]["text"] == "Hotel: which night do you want?"
        finally:
            for s in streams.values():
                s.close()


def test_13_9_07_a_wrong_ticket_conversation_workflow_match_is_409_and_nothing_is_dispatched_or_guessed(tmp_path):
    with world(tmp_path, scripts.interactive) as w:
        f = w.flow
        a_start, a = f.begin()
        b_start, b = f.begin()  # a second chat box of the same resident
        wrong = {
            "TICKET-A + CHAT-B": dict(external_conversation_id=b_start["external_conversation_id"]),
            "TICKET-A + wf_B": dict(workflow_id=b["workflow_id"]),
            "TICKET-B + CHAT-A": dict(external_ticket_id=b_start["external_ticket_id"]),
            "an unknown workflow": dict(workflow_id="wf_00000000000000000000000000000000"),
        }
        before = counts(w)
        for name, over in wrong.items():
            err = assert_envelope(f.post(f.reply_body(a, a_start, **over)), 409, "WORKFLOW_BINDING_MISMATCH")
            assert err["details"] == {}, name  # it does not say which one it would have been
        # a new ticket in a used chat box is not a new workflow, and a new start does not adopt an old ticket
        assert_envelope(f.post(f.start_body(external_conversation_id=a_start["external_conversation_id"])), 409,
                        "CONVERSATION_ALREADY_BOUND")
        assert_envelope(f.post(f.start_body(external_ticket_id=a_start["external_ticket_id"])), 409, "TICKET_ALREADY_BOUND")
        assert counts(w) == before  # no job, no message, no workflow, no model call


def test_13_9_08_a_provider_duplicate_is_deduped_and_an_out_of_order_event_never_moves_the_state_back(noise):
    n = noise
    assert n.dup.status_code == 202 and n.dup.json()["duplicate"] is True and n.dup.json()["receipt_id"] == n.receipt
    assert_envelope(n.conflict, 409, "EVENT_ID_CONFLICT")  # the same id with other content is refused, not applied
    assert n.inbox == [(1,)]
    assert n.stale["ingestion_status"] == "rejected" and n.stale["error"]["code"] == "STALE_EVENT"  # kept for audit
    status, partner_status, rank, version, _job = n.settled[0]
    assert (status, partner_status, rank, version) == ("pending", "on_the_way", 20, "2")
    assert n.after == n.settled  # operation, public events, wake jobs, model calls: nothing changed by any of the three


def test_13_9_09_a_restart_while_waiting_recovers_from_the_database_and_creates_no_job_or_operation(restart):
    r = restart
    assert r.after == r.before  # the same jobs, turns, operation ids and workflow state and revision
    assert r.partner_calls == 1 and r.effects == ["repair"]  # the provider was not called for a second plumber
    assert r.later == [("pending", "on_the_way", "2")] and r.state == "waiting_external_event"  # and the news lands
    assert r.jobs_after_event == r.before[0]  # a quiet event wakes nobody, here as before the restart


def test_13_9_10_a_route_remapped_from_a_to_b_leaves_the_old_ticket_on_a_and_moves_no_history_to_b(tmp_path):
    with world(tmp_path, scripts.interactive) as w:
        f = w.flow
        start, first = f.begin()
        old = f.route["route_id"]
        new = w.env.post(f"{W}/routes/{old}/replace", {"external_management_ref": "BQL-OP1-B"}).json()["route"]
        assert w.env.confirm(f.key["api_key"], new).status_code == 200
        only_b = key_headers(w.env.key(f.client["client_id"], routes=[new["route_id"]])["api_key"])
        err = assert_envelope(f.post(f.reply_body(first, start), headers=only_b), 403, "ROUTE_NOT_AUTHORIZED")  # the key is revalidated
        assert w.sql("select route_id, state from wf_workflows") == [(old, "awaiting_user")]  # a key's lack of rights blocks nothing
        err = assert_envelope(f.post(f.reply_body(first, start)), 403, "ROUTE_NOT_AUTHORIZED")  # the key of A: the route moved
        assert err["details"] == {"reason": "route_replaced"}
        assert w.sql("select route_id, state from wf_workflows") == [(old, "blocked_route_changed")]  # still A's, visibly blocked
        fresh = f.post(f.start_body(external_management_ref="BQL-OP1-B"))
        assert fresh.status_code == 200
        new_wf = fresh.json()
        assert w.sql("select route_id from wf_workflows where id=?", (new_wf["workflow_id"],)) == [(new["route_id"],)]
        assert new_wf["conversation_id"] != first["conversation_id"]  # B has its own conversation: no history was moved
        history_b = [m["workflow_id"] for m in f.snapshot(new_wf["conversation_id"]).json()["messages"]]
        assert set(history_b) == {new_wf["workflow_id"]}
        assert {m["workflow_id"] for m in f.snapshot(first["conversation_id"]).json()["messages"]} == {first["workflow_id"]}


@pytest.mark.slow
def test_13_9_11_a_close_racing_a_reply_or_an_event_is_decided_by_the_revision_and_nothing_follows_the_close(tmp_path, partner):
    (tmp_path / "chat").mkdir()
    (tmp_path / "event").mkdir()
    with world(tmp_path / "chat", scripts.interactive) as w:
        f = w.flow
        # in one order: the reply wins and the close, which was made on the old revision, is refused
        start, first = f.begin()
        assert f.reply(start, first)[0].status_code == 200
        err = assert_envelope(f.close(first, start)[0], 409, "REVISION_CONFLICT")
        assert w.state(first["workflow_id"])[0] != "closed" and err["details"]["current_revision"] > first["workflow_revision"]
        # in the other: the close wins and the reply is refused before anything is queued or asked of the model
        start2, second = f.begin()
        calls = len(CALLS)
        assert f.close(second, start2)[0].status_code == 200
        assert_envelope(f.post(f.reply_body(second, start2)), 409, "WORKFLOW_CLOSED")
        assert len(CALLS) == calls and not w.sql("select 1 from wf_jobs where status in ('queued','dispatched')")
        assert kinds_of(w, second["conversation_id"])[-1] == "workflow.closed"
        # and at the same moment, over and over: whoever wins, no chat after the close and no reopening
        for i in range(5):
            start3, third = f.begin()
            rev = third["workflow_revision"]
            with ThreadPoolExecutor(2) as ex:
                a = ex.submit(lambda: f.reply(start3, third)[0])
                b = ex.submit(lambda: f.close(third, start3, revision=rev)[0])
                a.result(60), b.result(60)
            w.quiet(30)
            conv_log = kinds_of(w, third["conversation_id"])
            if w.state(third["workflow_id"])[0] == "closed":
                assert conv_log[-1] == "workflow.closed" and conv_log.count("workflow.closed") == 1, (i, conv_log)
            assert not w.sql("select 1 from wf_requests where workflow_id=? and status in ('accepted','queued','running')",
                             (third["workflow_id"],))
    with pending_world(tmp_path / "event", partner, leader_only_notes, begin=False) as (w, prov, _):
        start, first = w.flow.begin()
        p = t2kit_pending(w, partner, prov, start, first)
        w.quiet()

        def do_close():
            for _ in range(20):
                r = close_pending(w, p)
                if r.status_code == 200:
                    return r
                assert r.status_code == 409, r.text  # the event moved the revision: ask again
            raise AssertionError("never closed")

        with ThreadPoolExecutor(2) as ex:
            c, e = ex.submit(do_close), ex.submit(lambda: p.send("x.progress", version=1, data={"note": "halfway"}))
            c.result(60), e.result(60)
        w.quiet(30)
        wait_status(w, prov, e.result()[0])
        log = events_of(w, p.conv)
        assert p.state() == "closed" and log[-1]["event_type"] == "workflow.closed"
        assert [x["event_type"] for x in log].count("workflow.closed") == 1


def purge_aged(db_url: str) -> dict:
    """The retention job of contract 12 (90 days), run on the app's database file (the live server has its own loop)."""
    import asyncio

    from awp.db import Database
    from awp.workforce.retention import purge_events

    async def go():
        db = Database(db_url)
        try:
            return await purge_events(db, 90)
        finally:
            await db.dispose()
    return asyncio.run(go())


def t2kit_pending(w, partner, prov, start, first):
    from t2kit import Pending
    return Pending(w, partner, prov, start, first)


def test_13_9_12_an_event_after_the_close_is_kept_for_audit_deduped_and_never_reopens_anything(tmp_path, partner):
    with pending_world(tmp_path, partner) as (w, prov, p):
        w.quiet()
        assert close_pending(w, p).status_code == 200 and p.state() == "closed"
        log, calls, jobs = events_of(w, p.conv), len(CALLS), w.sql("select count(*) from wf_jobs")
        for kind, data in (("x.assigned", DATA), ("x.completed", {"summary": "Done"})):
            r, body = p.send(kind, data=data)
            got = wait_status(w, prov, r)
            assert got["ingestion_status"] == "applied" and got["note"] == "after_close"  # stored, flagged
            assert prov.post(body).json()["duplicate"] is True  # and a retry of it is a duplicate
        assert events_of(w, p.conv) == log and log[-1]["event_type"] == "workflow.closed"  # the resident's app sees nothing
        assert p.state() == "closed" and w.sql("select status from awp_cases") == [("closed",)]
        assert len(CALLS) == calls and w.sql("select count(*) from wf_jobs") == jobs  # nobody was woken
        assert w.sql("select count(*) from wf_provider_inbox where note='after_close'") == [(2,)]


# ======================================================================================================================
# 14.3 Kiểm thử chung trước production (13 checklist bullets; the coordinator's brief said 14)
# ======================================================================================================================
def test_14_3_01_read_only_is_200_closed_none_with_no_sse_provider_event_or_close(tmp_path):
    with world(tmp_path, scripts.lookup) as w:
        r, _ = w.flow.start()
        j = r.json()
        assert r.status_code == 200 and (j["request_status"], j["workflow_state"], j["next_action"]) == ("completed", "closed", "none")
        assert said(j) and j["ticket_id"] is None
        assert w.sql("select count(*) from wf_operations") == [(0,)] and w.sql("select count(*) from wf_provider_inbox") == [(0,)]
        assert w.sql("select status from awp_cases") == [("closed",)]  # closed by the platform: the partner sent no close
        assert kinds_of(w, j["conversation_id"])[-1] == "workflow.closed"


def test_14_3_02_plan_reply_approval_confirmed_booking_confirm_close(tmp_path):
    with world(tmp_path, ck.trip, **CK) as w:
        ck.declare(w)
        f = w.flow
        start, first = f.begin(message=text_part(ck.START))
        assert (first["request_status"], first["workflow_state"], first["next_action"]) == ("completed", "awaiting_user", "submit_reply")
        r = f.reply(start, first, message=text_part(ck.CHOOSE))[0]
        second = r.json()
        assert r.status_code == 200 and second["workflow_id"] == first["workflow_id"]  # the same workflow
        assert (second["workflow_state"], second["next_action"]) == ("awaiting_approval", "submit_approval") and ck.BOOKED == []
        [appr] = f.approvals(second["conversation_id"])
        d = f.decide(appr["approval_id"], f.decide_body(start, second, appr))
        assert d.status_code == 202
        w.wait_state(first["workflow_id"], "awaiting_confirmation")
        assert len(ck.BOOKED) == 1  # the booking ran once, after the consent, and confirmed at once
        snap = f.snapshot(second["conversation_id"]).json()["workflows"][0]
        assert (snap["state"], snap["next_action"]) == ("awaiting_confirmation", "confirm_close")
        c = f.close({"workflow_id": first["workflow_id"], "workflow_revision": snap["revision"]}, start)[0]
        assert c.status_code == 200 and (c.json()["state"], c.json()["next_action"]) == ("closed", "none")


def test_14_3_03_a_booking_confirmed_at_once_has_no_tracking_and_only_a_pending_one_waits_for_events(tmp_path, partner):
    for name in ("now", "later"):
        (tmp_path / name).mkdir()
    confirmed = act("partner_hotel", {"hotel": "Sunrise", "nights": 2}, "Your hotel is in place. Please check the details.")
    with world(tmp_path / "now", confirmed, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        _, first = w.flow.begin()
        assert (first["workflow_state"], first["next_action"]) == ("awaiting_confirmation", "confirm_close")
        states = [e["payload"]["state"] for e in events_of(w, first["conversation_id"]) if e["event_type"] == "workflow.status_changed"]
        assert "waiting_external_event" not in states and w.sql("select count(*) from wf_jobs where kind='provider_wake'") == [(0,)]
    pending = act("partner_repair", {"slot": "mon"}, "I asked for a plumber; it is pending.")
    with world(tmp_path / "later", pending, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        _, first = w.flow.begin()
        assert (first["workflow_state"], first["next_action"]) == ("waiting_external_event", "watch_events")
        assert w.sql("select status from wf_operations") == [("pending",)]


def test_14_3_04_post_call_the_plumber_sse_updates_reply_in_the_same_ticket_and_the_resident_close(tracking):
    t = tracking
    assert t.first["workflow_state"] == "waiting_external_event" and t.first["ticket_id"] and t.partner_calls == 1
    assert t.replayed_ids == [m["message_id"] for m in said(t.first)]  # the POST's message arrives again by SSE, same id
    assert t.status_frame["data"]["payload"]["status"] == "assigned" and "Worker An" in t.template_frame["data"]["payload"]["text"]
    assert t.reply.status_code == 200 and t.reply_json["workflow_id"] == t.first["workflow_id"]
    assert t.reply_json["ticket_id"] == t.first["ticket_id"]  # the reply goes to the same ticket, no new one
    assert t.reply_frame["data"]["payload"]["text"] == "I noted that you want the plumber to use gate B."
    assert t.confirm_frame["data"]["payload"]["text"] == compkit.CONFIRM_TEXT and t.before_close == ("awaiting_confirmation", "confirm_close")
    assert t.close.status_code == 200 and t.close.json()["state"] == "closed"
    assert t.closed_frame["data"]["workflow_id"] == t.wid and t.kinds[-1] == "workflow.closed" and t.case_status == [("closed",)]


def test_14_3_05_the_202_fallback_a_lost_post_response_and_events_before_the_first_sse(slow, replay, early):
    assert slow.status == 202 and slow.by_sse["message_id"] == said(slow.by_get)[0]["message_id"]  # 202, then SSE/GET agree
    assert replay.again.status_code == 200 and replay.again.json() == replay.first  # the lost response is sent again
    assert [f["id"] for f in early.frames] == [e["event_id"] for e in early.persisted]  # nothing before the first SSE is lost


def test_14_3_06_a_duplicate_customer_request_and_a_duplicate_provider_event_change_nothing(replay, noise):
    assert replay.again.json() == replay.first and replay.partner_calls == 1 and replay.requests == [(1,)]
    assert noise.dup.json()["duplicate"] is True and noise.dup.json()["receipt_id"] == noise.receipt
    assert noise.after == noise.settled and noise.inbox == [(1,)]


def test_14_3_07_events_out_of_order_and_a_callback_before_the_tool_answered(noise, tmp_path, partner):
    assert noise.stale["error"]["code"] == "STALE_EVENT" and noise.after[0][1] == "on_the_way"  # no step back
    partner.delay = 3  # the partner has the request and the event is out before its answer is back
    with pending_world(tmp_path, partner, begin=False) as (w, prov, _):
        out: list = []
        th = threading.Thread(target=lambda: out.append(w.flow.start()))
        th.start()
        row = w.wait(lambda: t1kit.ops(w), 10, "the operation row")[0]
        assert row["job"] is None  # the tool has not yet stored the partner's job id
        rid, _ = sent_ok(prov, "x.assigned", ref=row["reference"], version=1, data=DATA)
        wait_status(w, prov, rid)  # applied although the operation had no job id yet
        th.join(60)
        w.wait_state(w.sql("select id from wf_workflows")[0][0], "waiting_external_event")
        [op] = t1kit.ops(w)
        assert (op["status"], op["partner_status"], op["job"]) == ("pending", "assigned", "JOB-1")  # the late answer undid nothing
        assert len(partner.of("book_repair")) == 1


def test_14_3_08_platform_and_worker_restarts_lose_nothing_and_repeat_nothing(restart, tmp_path):
    assert restart.after == restart.before and restart.partner_calls == 1  # a new process on the same data
    with world(tmp_path, scripts.interactive, wf_wait_seconds=0.3, wf_job_attempts=2, sweep_every=3600) as w:  # a worker that died with its job
        w.engine.notify = lambda *a: None
        r, _ = w.flow.start()
        first = r.json()
        w.sql("update wf_jobs set status='dispatched', attempts=1, lease_until=1")  # its owner died holding it
        w.run(w.engine.sweep)  # the job is given back ...
        assert w.sql("select status from wf_jobs") == [("queued",)]
        w.run(w.engine.sweep)  # ... and run once
        done = w.wait(lambda: (g := w.flow.request(first["request_id"]).json())["request_status"] == "completed" and g)
        assert [m["text"] for m in said(done)] == ["What time suits you?"] and w.sql("select count(*) from wf_turns") == [(1,)]


@pytest.mark.skip(reason="partner side: a restart of the partner's own backend is theirs to test (14.1/14.2); the platform's "
                         "side of an unreachable partner is covered by test_wf_t1_ledger and test_wf_t1_review_ledger")
def test_14_3_08b_the_partners_backend_restarts():
    pass


@pytest.mark.skip(reason="needs real infrastructure: kill -9 of a real process (and, for several processes, Redis and Postgres). "
                         "The default run simulates a restart (a new app on the same files, 14_3_08 above). The P0 crash probe "
                         "that killed a real process used the API that P4 deleted and no longer runs; it is to be rewritten "
                         "for the Workforce API in slice S7 (tests/probes/conftest.py)")
def test_14_3_08c_a_real_process_kill_during_a_wait():
    pass


def test_14_3_09_sse_reconnect_with_last_event_id_loses_nothing_and_an_expired_cursor_is_410(tmp_path):
    with world(tmp_path, scripts.interactive, live=True) as w:
        f = w.flow
        start, first = f.begin()
        conv = first["conversation_id"]
        f.reply(start, first)
        log = events_of(w, conv)
        s = open_stream(f, conv)
        try:
            got = s.events(3)
        finally:
            s.close()  # the network drops after the third event
        again = open_stream(f, conv, last=got[-1]["id"])  # reconnect with Last-Event-ID
        try:
            rest = again.events(len(log) - 3)
        finally:
            again.close()
        assert [x["id"] for x in got + rest] == [e["event_id"] for e in log]  # no event lost, none twice
        # retention: the workflow ends, its events age past the window and are purged; the old cursor is gone
        snap = f.snapshot(conv).json()["workflows"][0]
        assert f.close({"workflow_id": first["workflow_id"], "workflow_revision": snap["revision"]}, start)[0].status_code == 200
        w.sql("update wf_workflows set closed_at=?", (time.time() - 100 * 86400,))
        w.sql("update wf_events set recorded_at=?, occurred_at=?", (time.time() - 100 * 86400,) * 2)
        assert purge_aged(w.env.db.url)["events"] > 0
        err = assert_envelope(f.history(conv, after_cursor=log[0]["event_id"]), 410, "EVENT_CURSOR_EXPIRED")
        assert err["details"]["snapshot_url"].endswith(f"/conversations/{conv}")
        refused = open_stream(f, conv, after=log[0]["event_id"])  # the stream answers 410 too, before any header
        assert refused.status == 410 and b"EVENT_CURSOR_EXPIRED" in refused.body
        assert f.snapshot(conv).status_code == 200  # the snapshot is the way back in


def test_14_3_10_a_bad_signature_a_revoked_key_and_a_wrong_route_or_audience_are_refused(tmp_path, partner):
    with pending_world(tmp_path, partner) as (w, prov, p):
        w.quiet()
        body = prov.event("x.on_the_way", ref=p.ref, data={"eta_minutes": 1})
        bad = prov.post(body, secret="not-the-secret")
        assert assert_envelope(bad, 401, "UNAUTHENTICATED")["details"] == {"reason": "signature_invalid"}
        assert w.sql("select count(*) from wf_provider_inbox") == [(0,)]  # nothing was stored
        key_id = prov.api_key.split(".")[0][3:]
        assert w.env.post(f"{W}/keys/{key_id}/revoke").status_code == 200
        assert assert_envelope(prov.post(body), 401, "UNAUTHENTICATED")["details"] == {"reason": "revoked"}
        other = w.env.route(w.flow.client["client_id"], "ELSEWHERE")  # a key that covers another route only
        narrow = key_headers(w.env.key(w.flow.client["client_id"], routes=[other["route_id"]])["api_key"])
        assert_envelope(w.flow.post(w.flow.reply_body(p.first, p.start), headers=narrow), 403, "ROUTE_NOT_AUTHORIZED")
        for call in (lambda u: w.flow.request(p.first["request_id"], user=u), lambda u: w.flow.snapshot(p.conv, user=u),
                     lambda u: w.flow.history(p.conv, user=u)):
            assert_envelope(call("resident-999"), 404, "NOT_FOUND")  # another audience: it does not even exist
            assert call("resident-123").status_code == 200
        assert p.state() == "waiting_external_event" and p.op_row()[1] == "pending"  # none of it touched the workflow


def test_14_3_11_two_managers_in_one_area_and_two_residents_never_share_data(tmp_path):
    with world(tmp_path, scripts.topics, live=True) as w:
        f = w.flow
        w.env.active_route(f.client["client_id"], f.key["api_key"], ref="MANAGER-2")  # a second manager of the same area
        a_start, a = f.begin(external_user_id="resident-A", external_ticket_id="T-A", external_conversation_id="C-A",
                             message=text_part("My pipe leaks."))
        b_start, b = f.begin(external_user_id="resident-B", external_ticket_id="T-B", external_conversation_id="C-B",
                             message=text_part("Please book a hotel."))
        c_start, c = f.begin(external_user_id="resident-C", external_ticket_id="T-C", external_conversation_id="C-C",
                             external_management_ref="MANAGER-2", message=text_part("My pipe leaks."))
        assert len({x["workflow_id"] for x in (a, b, c)}) == 3
        assert w.sql("select count(distinct route_id) from wf_workflows") == [(2,)]
        for conv, owner, stranger in ((a["conversation_id"], "resident-A", "resident-B"), (b["conversation_id"], "resident-B", "resident-A")):
            for read in (f.snapshot, f.history):
                assert read(conv, user=owner).status_code == 200
                assert_envelope(read(conv, user=stranger), 404, "NOT_FOUND")
            s = open_stream(f, conv, user=stranger)
            assert s.status == 404  # the stranger's stream is refused before it starts
        assert not {m["text"] for m in f.snapshot(a["conversation_id"], user="resident-A").json()["messages"]} & \
            {m["text"] for m in f.snapshot(b["conversation_id"], user="resident-B").json()["messages"] if m["sender"] == "assistant"}
        # the key of the first manager only does not reach the second manager's workflow
        first_only = key_headers(w.env.key(f.client["client_id"], routes=[f.route["route_id"]])["api_key"])
        assert_envelope(f.post(f.reply_body(c, c_start), headers=first_only), 403, "ROUTE_NOT_AUTHORIZED")


def test_14_3_12_two_integrations_with_different_status_words_never_share_state_or_operations(tmp_path, partner):
    hotel = {"version": "1", "version_mode": "snapshot", "events": {
        "h.held": {"status": "room_held", "rank": 5, "public_status": "held", "public_fields": ["room"]},
        "h.booked": {"status": "booked", "rank": 50, "terminal": True, "outcome": "confirmed", "public_status": "booked",
                     "public_fields": ["room"], "message": "Your room {room} is booked."}}}
    with pending_world(tmp_path, partner, begin=False) as (w, repair, _):
        stay = Provider(w.env, w.flow.client["client_id"], hotel)
        configure(w, partner, [t1kit.lookup(), t1kit.action("partner_repair", "book_repair", integration_id=repair.id),
                               t1kit.action("partner_repair_b", "book_repair", integration_id=stay.id)])

        def both(c):
            turn = c.after_user()
            if turn.called("partner_repair") == 0:
                return [("partner_repair", {"slot": "a"}), ("partner_repair_b", {"slot": "b"})]
            return say("Both are pending.", "none") if turn.called("CaseSay") == 0 else "Said."

        from fake_llm import MODE
        MODE["script"] = both
        _, first = w.flow.begin()
        a, b = t1kit.ops(w)
        w.quiet()
        wait_status(w, repair, sent_ok(repair, "x.on_the_way", ref=a["reference"], data={"eta_minutes": 5})[0])
        wait_status(w, stay, sent_ok(stay, "h.held", ref=b["reference"], data={"room": "12B"})[0])
        a, b = t1kit.ops(w)
        assert (a["partner_status"], b["partner_status"]) == ("on_the_way", "room_held")  # each integration in its own words
        # neither can touch the other's operation, nor send the other's event types
        rid, _ = sent_ok(repair, "x.on_the_way", ref=b["reference"], data={"eta_minutes": 1})
        assert repair.status_of(rid) == "quarantined"
        assert stay.send("x.on_the_way", ref=b["reference"], data={"eta_minutes": 1})[0].json()["error"]["code"] == "UNKNOWN_EVENT_TYPE"
        wait_status(w, stay, sent_ok(stay, "h.booked", ref=b["reference"], data={"room": "12B"})[0])
        a, b = t1kit.ops(w)
        assert (a["status"], b["status"], b["partner_status"]) == ("pending", "completed", "booked")
        # the core carries the same five generic states whatever the words of an integration are
        assert {a["status"], b["status"]} <= {"intent", "sent", "pending", "completed", "failed", "unknown"}
        assert w.state(first["workflow_id"])[0] == "waiting_external_event"  # one operation is still open, in its own words


def test_14_3_13_a_sandbox_client_is_kept_apart_from_a_production_one_and_the_evidence_is_labelled_mock(tmp_path):
    with world(tmp_path, scripts.interactive) as w:
        sandbox = w.flow
        assert w.env.http.get(f"{W}/clients/{sandbox.client['client_id']}", headers=ADM).json()["environment"] == "sandbox"
        prod = w.env.client(name="Production partner", env="production")
        assert w.env.http.get(f"{W}/clients/{prod['client_id']}", headers=ADM).json()["environment"] == "production"
        k = w.env.key(prod["client_id"])
        route = w.env.active_route(prod["client_id"], k["api_key"])
        real = Flow(w.env, prod, k, route, w.engine)
        start, mine = sandbox.begin()
        # a production key cannot see, answer or close what the sandbox did, even with every id right
        assert_envelope(real.snapshot(mine["conversation_id"]), 404, "NOT_FOUND")
        assert_envelope(real.post(real.reply_body(mine, start)), 409, "WORKFLOW_BINDING_MISMATCH")  # it does not even exist for them
        assert_envelope(real.close(mine, start)[0], 404, "NOT_FOUND")
        assert w.sql("select count(*) from wf_workflows") == [(1,)]
        assert {c["environment"] for c in w.env.http.get(f"{W}/clients", headers=ADM).json()["clients"]} == {"sandbox", "production"}
    # What this suite is: scripted model, fake partner and fake provider. It proves the platform side of the contract
    # and says nothing about a real model or a real partner (docs/WORKFORCE_V1_KIEM_THU_TUAN_THU.md): never a production pass.
    assert "mock" in (__doc__ or "").lower() or "scripted" in (__doc__ or "").lower()
