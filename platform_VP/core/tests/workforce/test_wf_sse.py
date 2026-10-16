"""GET /partner/conversations/{id}/events: the SSE stream (contract 9.6, 13.5, 13.9). Runs on a real server."""
import random
import re
import threading
import time

import httpx
import pytest

from conftest import key_headers
from fake_engine import Plan
from flowkit import P, Stream
from test_wf_errors import assert_envelope


def open_stream(f, conv, *, last=None, after=None, user="resident-123", headers=None):
    h = {**(f.h if headers is None else headers), "Accept": "text/event-stream"}
    if last:
        h["Last-Event-ID"] = last
    params = {"external_user_id": user, **({"after_cursor": after} if after else {})}
    return Stream(f.http, f"{P}/conversations/{conv}/events", h, params)


@pytest.fixture
def live(make_flow):
    with make_flow(live=True, wf_wait_seconds=3, wf_sse_poll_seconds=0.2) as f:
        yield f


# ---- wire format ------------------------------------------------------------------------------------------------------
def test_the_frames_have_exactly_the_shape_of_contract_9_6(live):
    f = live
    start, started = f.begin()
    s = open_stream(f, started["conversation_id"])
    try:
        assert s.status == 200
        assert s.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert "no-cache" in s.headers["cache-control"]
        got = s.events(4)
    finally:
        s.close()
    history = f.history(started["conversation_id"]).json()["items"]
    for frame, item in zip(got, history):
        assert [line.split(": ", 1)[0] for line in frame["raw"]] == ["id", "event", "data"]
        assert frame["id"] == item["event_id"] == frame["data"]["event_id"]
        assert frame["event"] == item["event_type"] == frame["data"]["event_type"]
        assert frame["data"] == item  # the data line is the history item, field for field


def test_the_raw_bytes_are_id_event_data_and_a_blank_line(live):
    f = live
    start, started = f.begin()
    h = {**f.h, "Accept": "text/event-stream"}
    buf = b""
    with httpx.Client(base_url=f.http.base_url, timeout=10) as c:
        with c.stream("GET", f"{P}/conversations/{started['conversation_id']}/events", headers=h,
                      params={"external_user_id": "resident-123"}) as r:
            for chunk in r.iter_raw():
                buf += chunk
                if buf.count(b"\n\n") >= 4:
                    break
    frames = buf.split(b"\n\n")[:4]
    for raw in frames:
        assert re.fullmatch(rb"id: evt_[0-9a-f]{32}\nevent: [a-z]+\.[a-z_]+\ndata: \{.*\}", raw, re.S), raw
        assert raw.count(b"\n") == 2  # one line each: JSON carries no raw newline


# ---- replay and live --------------------------------------------------------------------------------------------------
def test_events_from_before_the_first_stream_are_replayed_from_the_start(live):
    f = live
    start, started = f.begin()
    f.reply(start, started)
    f.reply(start, started)
    log = f.history(started["conversation_id"], limit=500).json()["items"]
    s = open_stream(f, started["conversation_id"])  # no cursor: from the beginning of the log
    try:
        got = s.events(len(log))
    finally:
        s.close()
    assert [g["id"] for g in got] == [i["event_id"] for i in log]
    assert [g["data"]["sequence"] for g in got] == list(range(1, len(log) + 1))


def test_the_same_message_has_the_same_id_by_post_and_by_stream(live):
    f = live
    start, started = f.begin()
    s = open_stream(f, started["conversation_id"], after=f.history(started["conversation_id"]).json()["next_cursor"])
    try:
        f.engine.plan = Plan(say=("Technician is on the way.",), state="awaiting_user")
        r, _ = f.reply(start, started)
        posted = r.json()["result"]["messages"][0]
        events = s.events(4)  # request.accepted, status_changed, assistant.message, awaiting_user
    finally:
        s.close()
    [bubble] = [e for e in events if e["event"] == "assistant.message"]
    assert bubble["data"]["payload"] == {"message_id": posted["message_id"], "text": "Technician is on the way."}
    assert bubble["data"]["workflow_id"] == started["workflow_id"]


def test_a_turn_that_outlives_the_post_reaches_the_open_stream(make_flow):
    with make_flow(live=True, route={"wait_seconds": 0}, wf_sse_poll_seconds=0.2) as f:
        f.engine.plan = Plan(say=("Booked.",), delay=1.0)
        r, body = f.start()
        assert r.status_code == 202 and r.json()["result"] is None
        started = r.json()
        s = open_stream(f, started["conversation_id"])  # opened right after the 202, before the turn ends
        try:
            events = s.events(4, timeout=10)
        finally:
            s.close()
        assert [e["event"] for e in events] == [
            "request.accepted", "workflow.status_changed", "assistant.message", "workflow.awaiting_user"]
        done = f.request(started["request_id"]).json()
        assert done["request_status"] == "completed"
        assert done["result"]["messages"][0]["message_id"] == events[2]["data"]["payload"]["message_id"]


# ---- resuming -----------------------------------------------------------------------------------------------------------
def test_last_event_id_and_after_cursor_resume_after_that_event(live):
    f = live
    start, started = f.begin()
    f.reply(start, started)
    log = f.history(started["conversation_id"], limit=500).json()["items"]
    assert len(log) >= 8
    cut = log[2]["event_id"]
    for kwargs in ({"last": cut}, {"after": cut}, {"last": cut, "after": cut}):
        s = open_stream(f, started["conversation_id"], **kwargs)
        try:
            got = s.events(len(log) - 3)
        finally:
            s.close()
        assert [g["id"] for g in got] == [i["event_id"] for i in log[3:]], kwargs


def test_two_different_cursors_are_a_400_before_any_stream_starts(live):
    f = live
    start, started = f.begin()
    log = f.history(started["conversation_id"]).json()["items"]
    s = open_stream(f, started["conversation_id"], last=log[0]["event_id"], after=log[1]["event_id"])
    assert s.status == 400 and "application/json" in s.headers["content-type"]
    import json
    err = json.loads(s.body)["error"]
    assert err["code"] == "INVALID_REQUEST" and err["request_id"].startswith("req_")


def test_cursor_and_audience_are_refused_with_json_before_the_headers(live):
    f = live
    a_start, a = f.begin()
    b_start, b = f.begin()
    foreign = f.history(b["conversation_id"]).json()["items"][0]["event_id"]
    f.env.sql("insert into wf_event_tombstones (event_id, conversation_id, sequence) values ('evt_gone', ?, 1)",
              (a["conversation_id"],))
    cases = [
        (dict(after="evt_nothing"), 422, "VALIDATION_FAILED"),
        (dict(last="evt_nothing"), 422, "VALIDATION_FAILED"),
        (dict(after=foreign), 422, "VALIDATION_FAILED"),  # a cursor of another conversation
        (dict(last=foreign), 422, "VALIDATION_FAILED"),
        (dict(after="evt_gone"), 410, "EVENT_CURSOR_EXPIRED"),
        (dict(last="evt_gone"), 410, "EVENT_CURSOR_EXPIRED"),
        (dict(user="resident-999"), 404, "NOT_FOUND"),
    ]
    import json
    for kwargs, status, code in cases:
        s = open_stream(f, a["conversation_id"], **kwargs)
        assert s.status == status and "application/json" in s.headers["content-type"], (kwargs, s.status)
        err = json.loads(s.body)["error"]
        assert err["code"] == code
        if status == 410:
            assert err["details"] == {"snapshot_url": f"{P}/conversations/{a['conversation_id']}"}
    f.env.sql("update wf_conversations set purged_through=1 where id=?", (b["conversation_id"],))
    s = open_stream(f, b["conversation_id"])  # "from the start" after the head was purged
    assert s.status == 410
    other = open_stream(f, "conv_nope")
    assert other.status == 404


def test_the_stream_needs_the_credential_and_both_operations(live):
    f = live
    start, started = f.begin()
    url = f"{P}/conversations/{started['conversation_id']}/events"
    r = httpx.get(f"{f.http.base_url}{url}", params={"external_user_id": "resident-123"})
    assert_envelope(r, 401, "UNAUTHENTICATED")
    only_read = key_headers(f.env.key(f.client["client_id"], operations=["read_result"])["api_key"])
    only_events = key_headers(f.env.key(f.client["client_id"], operations=["receive_events"])["api_key"])
    for h in (only_read, only_events):
        r = httpx.get(f"{f.http.base_url}{url}", params={"external_user_id": "resident-123"}, headers=h)
        assert_envelope(r, 403, "PERMISSION_DENIED")
    r = httpx.get(f"{f.http.base_url}{url}", headers=f.h)
    assert_envelope(r, 422, "VALIDATION_FAILED")  # the audience is required


@pytest.mark.slow
def test_a_reconnecting_reader_loses_and_duplicates_nothing_while_a_writer_runs(live):
    f = live
    f.engine.plan = Plan(say=("a", "b"), state="awaiting_user")
    start, started = f.begin()
    done = threading.Event()

    def writer():
        for _ in range(14):
            f.reply(start, started)
        done.set()

    th = threading.Thread(target=writer)
    th.start()
    seen, cursor, quiet = [], None, 0
    rng = random.Random(7)
    deadline = time.monotonic() + 60
    while quiet < 2 and time.monotonic() < deadline:
        s = open_stream(f, started["conversation_id"], last=cursor)
        before = len(seen)
        try:
            for _ in range(rng.randint(1, 6)):  # take a few, then drop the connection mid-stream
                fr = s.next(timeout=0.8 if done.is_set() else 3)
                if fr is None:
                    break
                if "comment" in fr:
                    continue
                seen.append(fr)
                cursor = fr["id"]
        finally:
            s.close()
        quiet = quiet + 1 if (done.is_set() and len(seen) == before) else 0
    th.join(30)
    log = f.history(started["conversation_id"], limit=500).json()["items"]
    assert [g["id"] for g in seen] == [i["event_id"] for i in log]  # all of them, once, in order
    assert [g["data"]["sequence"] for g in seen] == list(range(1, len(log) + 1))
    assert len(log) > 60


def test_two_chats_of_one_resident_have_two_streams_that_never_mix(live):
    f = live
    a_start, a = f.begin()
    b_start, b = f.begin()
    sa = open_stream(f, a["conversation_id"], after=f.history(a["conversation_id"]).json()["next_cursor"])
    sb = open_stream(f, b["conversation_id"], after=f.history(b["conversation_id"]).json()["next_cursor"])
    try:
        for _ in range(3):
            f.reply(a_start, a)
        f.reply(b_start, b)
        ea, eb = sa.events(12), sb.events(4)
    finally:
        sa.close()
        sb.close()
    assert {e["data"]["conversation_id"] for e in ea} == {a["conversation_id"]}
    assert {e["data"]["external_ticket_id"] for e in ea} == {a_start["external_ticket_id"]}
    assert {e["data"]["workflow_id"] for e in ea} == {a["workflow_id"]}
    assert {e["data"]["conversation_id"] for e in eb} == {b["conversation_id"]}
    assert {e["data"]["external_ticket_id"] for e in eb} == {b_start["external_ticket_id"]}
    assert not {e["id"] for e in ea} & {e["id"] for e in eb}


def test_a_stream_of_one_chat_never_carries_the_close_of_the_other(live):
    f = live
    f.engine.plan = Plan(state="awaiting_confirmation")
    a_start, a = f.begin()
    b_start, b = f.begin()
    sb = open_stream(f, b["conversation_id"], after=f.history(b["conversation_id"]).json()["next_cursor"])
    try:
        assert f.close(a, a_start)[0].status_code == 200
        assert sb.next(timeout=1.0) is None  # nothing for chat B
        assert f.close(b, b_start)[0].status_code == 200
        [closed] = sb.events(1)
    finally:
        sb.close()
    assert closed["event"] == "workflow.closed" and closed["data"]["workflow_id"] == b["workflow_id"]


# ---- heartbeat, revalidation, wake-ups -------------------------------------------------------------------------------------
def test_heartbeats_are_comments_that_create_no_events_and_use_no_sequence(make_flow):
    with make_flow(live=True, wf_heartbeat_seconds=0.2, wf_sse_poll_seconds=0.1) as f:
        start, started = f.begin()
        cid = started["conversation_id"]
        count = f.env.sql("select count(*), max(sequence) from wf_events where conversation_id=?", (cid,))[0]
        last_seq = f.env.sql("select last_sequence from wf_conversations where id=?", (cid,))[0][0]
        s = open_stream(f, cid)
        try:
            s.events(count[0])
            beats = []
            deadline = time.monotonic() + 5
            while len(beats) < 4 and time.monotonic() < deadline:
                fr = s.next(timeout=2)
                assert fr is not None and fr == {"comment": ": heartbeat"}
                beats.append(fr)
            assert len(beats) == 4
            assert f.env.sql("select count(*), max(sequence) from wf_events where conversation_id=?", (cid,))[0] == count
            assert f.env.sql("select last_sequence from wf_conversations where id=?", (cid,))[0][0] == last_seq
            f.reply(start, started)  # the next real event is the next number: beats took none
            nxt = s.events(1)[0]
            assert nxt["data"]["sequence"] == last_seq + 1
        finally:
            s.close()


def test_a_busy_stream_sends_no_heartbeat_between_events(make_flow):
    with make_flow(live=True, wf_heartbeat_seconds=60) as f:
        start, started = f.begin()
        s = open_stream(f, started["conversation_id"])
        try:
            got = [s.next(timeout=5) for _ in range(4)]
        finally:
            s.close()
        assert all(g and "comment" not in g for g in got)


def test_the_stream_ends_soon_after_its_key_is_revoked(make_flow):
    with make_flow(live=True, wf_revalidate_seconds=0.3, wf_sse_poll_seconds=0.1) as f:
        start, started = f.begin()
        s = open_stream(f, started["conversation_id"])
        try:
            s.events(4)
            time.sleep(1.0)  # several re-checks pass while the key is good
            f.reply(start, started)
            s.events(4)
            assert f.env.post(f"/platform/v1/wf/keys/{f.key['key_id']}/revoke").status_code == 200
            assert s.ended(timeout=5), "the stream outlived its key"
        finally:
            s.close()
        r = httpx.get(f"{f.http.base_url}{P}/conversations/{started['conversation_id']}/events",
                      params={"external_user_id": "resident-123"}, headers=f.h)
        assert_envelope(r, 401, "UNAUTHENTICATED")  # a reconnect has to authenticate again


@pytest.mark.parametrize("sql", [
    "update wf_keys set operations='[\"submit_request\",\"reply\",\"read_result\"]' where key_id=:k",
    "update wf_keys set routes='[\"route_other\"]' where key_id=:k",
    "update wf_keys set expires_at=1.0 where key_id=:k",
    "update wf_clients set status='disabled' where id=(select client_id from wf_keys where key_id=:k)"],
    ids=["operation_removed", "route_not_covered", "key_expired", "client_disabled"])
def test_the_stream_ends_when_the_grant_goes_away(make_flow, sql):
    with make_flow(live=True, wf_revalidate_seconds=0.3, wf_sse_poll_seconds=0.1) as f:
        start, started = f.begin()
        s = open_stream(f, started["conversation_id"])
        try:
            s.events(4)
            f.env.sql(sql.replace(":k", "'" + f.key["key_id"] + "'"))
            assert s.ended(timeout=5)
        finally:
            s.close()


def test_a_live_event_arrives_fast_on_the_wake_up_signal_even_if_polling_is_slow(make_flow):
    with make_flow(live=True, wf_sse_poll_seconds=30) as f:
        start, started = f.begin()
        s = open_stream(f, started["conversation_id"], after=f.history(started["conversation_id"]).json()["next_cursor"])
        try:
            time.sleep(0.3)
            f.reply(start, started)
            s.events(4, timeout=10)  # polling would answer in 30 s: the wake-up signal is what delivers it
        finally:
            s.close()


def test_the_wake_up_signal_comes_after_the_commit_not_before_it(make_flow):
    """A reader woken before the writer's commit has landed reads nothing new and then sleeps until the next poll: the
    event is late by a whole poll (this is what made the test above fail once in a full run). The driver's commit is
    held for a moment here while the loop turns, as it does while a real commit is on its way to the database, so a
    signal sent before the commit always comes too early."""
    import asyncio

    from sqlalchemy.util import await_only

    with make_flow(live=True, wf_sse_poll_seconds=30) as f:
        dialect = f.env.app.state.wf.db.engine.dialect
        assert not getattr(dialect, "_awp_pokes", False)  # nothing was signalled yet: the hold goes under the platform's own wrapper
        commit = dialect.do_commit

        def held(dbapi_connection):
            await_only(asyncio.sleep(0.2))
            commit(dbapi_connection)
        dialect.do_commit = held
        start, started = f.begin()
        s = open_stream(f, started["conversation_id"], after=f.history(started["conversation_id"]).json()["next_cursor"])
        try:
            time.sleep(0.3)
            f.reply(start, started)
            assert [e["event"] for e in s.events(4, timeout=10)] == [
                "request.accepted", "workflow.status_changed", "assistant.message", "workflow.awaiting_user"]
        finally:
            s.close()


def test_without_any_wake_up_signal_polling_alone_delivers_every_event(make_flow, monkeypatch):
    from awp.workforce.waker import Waker
    monkeypatch.setattr(Waker, "poke", lambda self, key: None)  # no Redis, no signal at all
    with make_flow(live=True, wf_sse_poll_seconds=0.15, wf_wait_seconds=0.3) as f:
        start, started = f.begin()
        s = open_stream(f, started["conversation_id"], after=f.history(started["conversation_id"]).json()["next_cursor"])
        try:
            f.reply(start, started)
            assert [e["event"] for e in s.events(4, timeout=5)] == [
                "request.accepted", "workflow.status_changed", "assistant.message", "workflow.awaiting_user"]
        finally:
            s.close()


def test_a_client_that_drops_the_post_does_not_cancel_the_turn(make_flow):
    with make_flow(live=True, wf_wait_seconds=10) as f:
        f.engine.plan = Plan(say=("Done anyway.",), delay=1.0)
        body = f.start_body()
        with pytest.raises(httpx.TimeoutException):
            httpx.post(f"{f.http.base_url}{P}/requests", json=body, headers=f.h, timeout=0.3)
        again = f.post(body)  # the retry finds the same request, finished by now or soon
        assert again.status_code == 200 and again.json()["result"]["messages"][0]["text"] == "Done anyway."
        assert len(f.engine.seen) == 1
        assert f.env.sql("select count(*) from wf_workflows")[0][0] == 1
