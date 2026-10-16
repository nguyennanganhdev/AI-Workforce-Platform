"""Scenarios of the compliance suite (tests/workforce/test_compliance.py): each drives the real API on the real engine
with the scripted model and the fake partner and returns what it OBSERVED. The assertions are the tests': a row of
contract 13.9 and a bullet of 14.3 that depend on the same scenario both read its observations."""
from __future__ import annotations

import re
import time
from types import SimpleNamespace

import scripts
from enginekit import hold_leader, world
from fake_llm import CALLS
from flowkit import Stream
from scripts import say
from t1kit import SETTINGS, ops
from t2kit import pending_world, wait_status
from test_wf_sse import open_stream
from test_wf_t2_apply import DATA

PENDING_TEXT = "I asked for a plumber; it is pending."
CONFIRM_TEXT = "The plumber reports the visit finished. Is everything right?"


def events_of(w, conv: str) -> list[dict]:
    return w.flow.history(conv, limit=500).json()["items"]


def kinds_of(w, conv: str) -> list[str]:
    return [e["event_type"] for e in events_of(w, conv)]


def until_frame(stream: Stream, wanted, timeout: float = 30.0) -> dict:
    """Read frames until `wanted(frame)`; return that frame. The ceiling only keeps a broken test from hanging."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        frame = stream.next(timeout=max(end - time.monotonic(), 0.1))
        if frame is not None and "comment" not in frame and wanted(frame):
            return frame
    raise AssertionError("the stream never carried the frame that was waited for")


def counts(w) -> dict:
    """What a refused command must not change: rows that mean work, and the model calls made."""
    tables = ("wf_jobs", "wf_messages", "wf_requests", "wf_workflows", "wf_conversations", "wf_events", "awp_cases")
    return {**{t: w.sql(f"select count(*) from {t}")[0][0] for t in tables}, "model_calls": len(CALLS)}


# ---- 13.9 row 1: the POST whose answer was lost is sent again -----------------------------------------------------------------
def replayed_post(tmp_path, partner) -> SimpleNamespace:
    with pending_world(tmp_path, partner) as (w, prov, p):
        w.quiet()
        again = w.flow.post(p.start)
        third = w.flow.post(p.start)
        return SimpleNamespace(
            first=p.first, again=again, third=third, partner_calls=len(partner.of("book_repair")),
            effects=list(partner.effects), requests=w.sql("select count(*) from wf_requests"), ops=len(ops(w)),
            workflows=w.sql("select count(*) from wf_workflows"))


# ---- 13.9 row 2: the first turn is slower than the wait --------------------------------------------------------------------
def slow_first_turn(tmp_path) -> SimpleNamespace:
    with world(tmp_path, scripts.interactive, live=True, wf_wait_seconds=0.3) as w:
        gate = hold_leader()
        r, body = w.flow.start()
        pending = r.json()
        stream = open_stream(w.flow, pending["conversation_id"])  # opened at once, as the contract says
        try:
            gate.set()
            frame = until_frame(stream, lambda f: f["event"] == "assistant.message")
        finally:
            stream.close()
        done = w.wait(lambda: (g := w.flow.request(pending["request_id"]).json())["request_status"] == "completed" and g,
                      what="the request")
        spoken = [e["payload"] for e in events_of(w, pending["conversation_id"]) if e["event_type"] == "assistant.message"]
        snap = w.flow.snapshot(pending["conversation_id"]).json()
        return SimpleNamespace(status=r.status_code, pending=pending, body=body, by_sse=frame["data"]["payload"], by_get=done,
                               by_history=spoken, by_snapshot=[m for m in snap["messages"] if m["sender"] == "assistant"])


# ---- 13.9 row 3: events that came before the first SSE ----------------------------------------------------------------------
def events_before_sse(tmp_path, partner) -> SimpleNamespace:
    with pending_world(tmp_path, partner, live=True, wf_sse_poll_seconds=0.2) as (w, prov, p):
        w.quiet()
        p.applied("x.assigned", version=1, data=DATA)
        p.applied("x.on_the_way", version=2, data={"eta_minutes": 5})
        persisted = events_of(w, p.conv)
        s = open_stream(w.flow, p.conv)  # no cursor: from the start of the log
        try:
            frames = s.events(len(persisted))
        finally:
            s.close()
        return SimpleNamespace(persisted=persisted, frames=frames, first=p.first)


# ---- 13.9 row 8: the provider sends twice, and out of order -----------------------------------------------------------------
def provider_noise(tmp_path, partner) -> SimpleNamespace:
    with pending_world(tmp_path, partner) as (w, prov, p):
        w.quiet()
        rid, body = p.send("x.on_the_way", version=2, data={"eta_minutes": 5})
        wait_status(w, prov, rid)
        settled = (p.op_row(), len(events_of(w, p.conv)), p.jobs(), len(CALLS))
        dup = prov.post(body)  # the same event again, byte for byte
        conflict = prov.post({**body, "data": {"eta_minutes": 99}})  # the same id with other content
        old, old_body = p.send("x.assigned", version=1, data=DATA)  # older news, lower rank, arrives late
        stale = wait_status(w, prov, old, "rejected")
        return SimpleNamespace(
            receipt=rid, settled=settled, dup=dup, conflict=conflict, stale=stale,
            after=(p.op_row(), len(events_of(w, p.conv)), p.jobs(), len(CALLS)),
            inbox=w.sql("select count(*) from wf_provider_inbox where external_event_id=?", (body["external_event_id"],)))


# ---- 13.9 row 9: the platform restarts while it waits ------------------------------------------------------------------------
def restart_while_waiting(tmp_path, partner) -> SimpleNamespace:
    with pending_world(tmp_path, partner) as (w, prov, p):
        w.quiet()
        p.applied("x.assigned", version=1, data=DATA)
        wid, conv, ref = p.wid, p.conv, p.ref

        def picture(x):
            return (x.sql("select count(*) from wf_jobs"), x.sql("select count(*) from wf_turns"),
                    x.sql("select id, client_reference, status from wf_operations"), x.state(wid))
        before = picture(w)
    # the process is gone; a new one opens the same databases (the profiles are in them already)
    with world(tmp_path, None, publish=False, **SETTINGS) as w2:
        w2.run(w2.engine.sweep)
        w2.run(w2.engine.sweep)
        after = picture(w2)
        prov.env = w2.env  # the provider's backend sends on: same keys, new process
        rid = prov.send("x.on_the_way", ref=ref, version=2, data={"eta_minutes": 3})[0].json()["receipt_id"]
        wait_status(w2, prov, rid)
        return SimpleNamespace(before=before, after=after, partner_calls=len(partner.of("book_repair")),
                               effects=list(partner.effects), later=w2.sql("select status, normalized_status, provider_version from wf_operations"),
                               jobs_after_event=w2.sql("select count(*) from wf_jobs"), state=w2.state(wid)[0])


# ---- the leader of a tracked repair (13.4): action, notes, and the question after the end ---------------------------
def tracked(c):
    turn = c.after_user()
    if "<provider-event" in c.last_user:
        kind = re.search(r'type="([^"]+)"', c.last_user).group(1)
        ev = (re.search(r'evidence="(E\d+)"', c.last_user) or [None, None])[1]
        if turn.called("CaseSay"):
            return "Said."
        if kind == "x.completed":
            return say(CONFIRM_TEXT, "confirmation", [ev])
        return say("Noted.", "none")
    if "cổng B" in c.last_user:
        return say("I noted that you want the plumber to use gate B.", "none") if not turn.called("CaseSay") else "Said."
    if turn.called("partner_repair") == 0:
        return [("partner_repair", {"slot": "mon"})]
    return say(PENDING_TEXT, "none") if turn.called("CaseSay") == 0 else "Said."


def tracking_flow(tmp_path, partner) -> SimpleNamespace:
    """13.4 as the contract draws it, end to end: POST, SSE, provider events, a reply, the end, the close."""
    out = SimpleNamespace()
    with pending_world(tmp_path, partner, tracked, live=True, wf_sse_poll_seconds=0.2) as (w, prov, p):
        out.first, out.start, out.partner_calls = p.first, p.start, len(partner.of("book_repair"))
        s = open_stream(w.flow, p.conv)
        try:
            replay = s.events(len(events_of(w, p.conv)))
            out.replayed_ids = [f["data"]["payload"].get("message_id") for f in replay if f["event"] == "assistant.message"]
            p.applied("x.assigned", version=1, data=DATA)
            out.status_frame = until_frame(s, lambda f: f["event"] == "ticket.status_changed")
            out.template_frame = until_frame(s, lambda f: f["event"] == "assistant.message")
            r, _ = w.flow.reply(p.start, p.first, message={"type": "text", "text": "Nhờ báo thợ đi vào cổng B giúp tôi."})
            out.reply, out.reply_json = r, r.json()
            out.reply_frame = until_frame(s, lambda f: f["event"] == "assistant.message"
                                          and f["data"]["payload"]["message_id"] in [m["message_id"] for m in r.json()["result"]["messages"]])
            rid, _ = p.send("x.completed", version=2, job=p.job, data={"summary": "Pipe replaced"})
            wait_status(w, prov, rid)
            w.wait_state(p.wid, "awaiting_confirmation")
            out.confirm_frame = until_frame(s, lambda f: f["event"] == "assistant.message"
                                            and f["data"]["payload"]["text"] == CONFIRM_TEXT)
            snap = w.flow.snapshot(p.conv).json()["workflows"][0]
            out.before_close = (snap["state"], snap["next_action"])
            c = w.flow.close({"workflow_id": p.wid, "workflow_revision": snap["revision"]}, p.start,
                             reason="resident_confirmed", stop_tracking_only=False)[0]
            out.close = c
            out.closed_frame = until_frame(s, lambda f: f["event"] == "workflow.closed")
        finally:
            s.close()
        out.kinds = kinds_of(w, p.conv)
        out.case_status = w.sql("select status from awp_cases")
        out.conv, out.wid = p.conv, p.wid
    return out
