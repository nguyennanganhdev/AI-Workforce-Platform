"""Many workflows at once (spec section 10, P5: "20 workflows at the same time do not mix").

A `Lane` is one resident with one ticket in one chat. `walk` takes it through a whole multi-turn workflow over the real
HTTP API, the way a partner's backend would, driven by the lane's own event stream (no polling):

    start_workflow (a question)      -> the leader answers and waits for the resident
    workflow_reply (asks for a visit)-> the leader's action needs consent: the workflow parks
    decision: approve                -> the partner is called once; the workflow waits for the partner
    two signed provider events       -> a template message, then the leader asks the resident to confirm
    close                            -> closed

`drive` runs every lane on its own thread at once; `verify` then checks what must hold whatever the load was: nothing of
one lane in another, sequences without a gap, the stream equal to the history, one partner action per workflow, every
request settled. The scripted leader (deploy/demo/fake_model.py) answers a ticket's message with every ticket name its
session was ever shown, so a session that saw another lane's words says so itself.

Times are of the POSTs as the caller sees them. A POST of a request waits for the leader's turn (contract 9.1), so its
time is the time of a turn under this load, with a scripted model that answers at once.
"""
from __future__ import annotations

import statistics
import threading
import time
from dataclasses import dataclass, field

import httpx

from conftest import key_headers
from flowkit import P, Stream

FIRST = "Noted ({}), message "  # then a letter: how many of the resident's messages the session holds (its own only)
PENDING = "I asked for the visit on Monday; it is pending."
FINISHED = "The partner reports the work finished. Is everything right?"
STEP = 150.0  # seconds one step of a lane may take before the lane gives up (the bound of the whole test is the caller's)


def letters(i: int) -> str:
    """A name without a digit (the scripted leader may only say what is in the resident's words): AA, AB, ..."""
    return chr(65 + i // 26) + chr(65 + i % 26)


@dataclass
class Lane:
    name: str
    ref: str  # the route's external_management_ref
    post: httpx.Client  # the process its commands go to
    read: httpx.Client  # the process its event stream is read from
    key: str
    provider: object  # t2kit.Provider at some process
    times: dict = field(default_factory=dict)  # kind of POST -> seconds
    codes: dict = field(default_factory=dict)  # kind of POST -> HTTP status
    frames: list = field(default_factory=list)  # every event the stream delivered, in order
    ids: dict = field(default_factory=dict)
    error: BaseException | None = None
    stream: Stream | None = None

    def __post_init__(self) -> None:
        self.user, self.ticket, self.chat = f"resident-{self.name}", f"TICKET-{self.name}", f"CHAT-{self.name}"
        self.tag, self.h = f"TKT-{self.name}", key_headers(self.key)

    def body(self, command: str, text: str, **more) -> dict:
        return {"schema_version": "1", "command_type": command, "external_request_id": f"rq-{self.name}-{command}",
                "external_management_ref": self.ref, "external_user_id": self.user, "external_ticket_id": self.ticket,
                "external_conversation_id": self.chat, "message": {"type": "text", "text": text}, **more}

    def timed(self, kind: str, send) -> httpx.Response:
        t0 = time.perf_counter()
        r = send()
        self.times[kind], self.codes[kind] = time.perf_counter() - t0, r.status_code
        return r

    def until(self, match, what: str) -> dict:
        """The next event of the stream that `match` accepts (every event read on the way is kept)."""
        end = time.monotonic() + STEP
        while time.monotonic() < end:
            f = self.stream.next(timeout=max(0.1, end - time.monotonic()))
            if f is None:
                break
            if "comment" in f:
                continue
            self.frames.append(f["data"])
            if match(f["data"]):
                return f["data"]
        raise AssertionError(f"lane {self.name}: no {what} within {STEP:.0f} s; got {[e['event_type'] for e in self.frames]}")

    def state(self, want: str) -> dict:
        return self.until(lambda e: e["payload"].get("state") == want, f"state {want}")


def walk(lane: Lane) -> None:
    ids = {"external_user_id": lane.user, "external_ticket_id": lane.ticket, "external_conversation_id": lane.chat}
    r = lane.timed("start", lambda: lane.post.post(f"{P}/requests", headers=lane.h, json=lane.body(
        "start_workflow", f"{lane.tag}: the tap in my kitchen drips.")))
    assert r.status_code in (200, 202), r.text
    started = r.json()
    lane.ids.update(conversation=started["conversation_id"], workflow=started["workflow_id"], requests=[started["request_id"]])
    lane.stream = Stream(lane.read, f"{P}/conversations/{started['conversation_id']}/events", lane.h, {"external_user_id": lane.user})
    assert lane.stream.status == 200, (lane.name, lane.stream.status, lane.stream.body)
    lane.state("awaiting_user")

    r = lane.timed("reply", lambda: lane.post.post(f"{P}/requests", headers=lane.h, json=lane.body(
        "workflow_reply", f"Please book a repair visit for it ({lane.tag}).", workflow_id=started["workflow_id"])))
    assert r.status_code in (200, 202), r.text
    lane.ids["requests"].append(r.json()["request_id"])
    asked = lane.until(lambda e: e["event_type"] == "approval.required", "approval.required")["payload"]

    r = lane.timed("decision", lambda: lane.post.post(f"{P}/approvals/{asked['approval_id']}/decision", headers=lane.h, json={
        "schema_version": "1", "external_request_id": f"rq-{lane.name}-decision", **ids, "workflow_id": started["workflow_id"],
        "decision": "approve", "expected_revision": asked["expected_revision"], "arguments_hash": asked["arguments_hash"]}))
    assert r.status_code == 202, r.text
    sent = lane.until(lambda e: e["event_type"] == "operation.status_changed" and e["payload"]["status"] == "pending",
                      "the pending operation")["payload"]
    lane.ids["reference"] = sent["client_reference"]
    lane.state("waiting_external_event")

    for n, (kind, data) in enumerate((("job.assigned", {"worker_name": lane.name}), ("job.completed", {})), 1):
        r = lane.timed(f"event{n}", lambda: lane.provider.send(kind, ref=sent["client_reference"], version=n, data=data,
                                                               event_id=f"ev-{lane.name}-{n}")[0])
        assert r.status_code == 202, r.text
    resting = lane.state("awaiting_confirmation")

    r = lane.timed("close", lambda: lane.post.post(f"{P}/workflows/{started['workflow_id']}/close", headers=lane.h, json={
        "schema_version": "1", "external_request_id": f"rq-{lane.name}-close", **ids,
        "expected_revision": resting["payload"]["revision"], "reason": "resident_confirmed_resolved", "stop_tracking_only": False}))
    assert r.status_code == 200 and r.json()["state"] == "closed", r.text
    lane.until(lambda e: e["event_type"] == "workflow.closed", "workflow.closed")


def drive(lanes: list[Lane]) -> float:
    """Every lane at once, each on its own thread. Returns the seconds the whole took."""
    gate = threading.Barrier(len(lanes))

    def run(lane: Lane) -> None:
        try:
            gate.wait(30)
            walk(lane)
        except BaseException as e:  # noqa: BLE001 (kept for the report: one lane's failure must not hide the others')
            lane.error = e
        finally:
            if lane.stream is not None:
                lane.stream.close()

    threads = [threading.Thread(target=run, args=(lane,), daemon=True) for lane in lanes]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return time.perf_counter() - t0


def verify(lanes: list[Lane], partner: dict) -> None:
    failed = [(lane.name, repr(lane.error)) for lane in lanes if lane.error is not None]
    assert not failed, f"{len(failed)} of {len(lanes)} lanes did not finish: {failed}"
    names = {lane.name for lane in lanes}
    for lane in lanes:
        get = lambda path, **q: lane.post.get(f"{P}{path}", headers=lane.h, params={"external_user_id": lane.user, **q})  # noqa: E731
        history = get(f"/conversations/{lane.ids['conversation']}/event-history", limit=500).json()["items"]
        # the stream gave exactly the log, in order, without a gap
        assert [e["sequence"] for e in history] == list(range(1, len(history) + 1)), (lane.name, [e["sequence"] for e in history])
        assert [e["event_id"] for e in lane.frames] == [e["event_id"] for e in history], lane.name
        assert lane.frames == history, lane.name
        # every event is this lane's own
        for e in history:
            assert (e["conversation_id"], e["external_conversation_id"], e["external_ticket_id"], e["external_user_id"]) == (
                lane.ids["conversation"], lane.chat, lane.ticket, lane.user), (lane.name, e)
            assert e["workflow_id"] == lane.ids["workflow"], (lane.name, e)
        kinds = [e["event_type"] for e in history]
        for kind in ("approval.required", "approval.resolved", "ticket.created", "workflow.closed"):
            assert kinds.count(kind) == 1, (lane.name, kind, kinds)
        assert kinds[-1] == "workflow.closed"
        # what was said: this lane's words only, each once (the leader names every ticket its session ever saw)
        said = [e["payload"]["text"] for e in history if e["event_type"] == "assistant.message"]
        assert len(said) == 4 and said[0].startswith(FIRST.format(lane.tag)), (lane.name, said)  # "(TKT-AA+TKT-AB)" would be a leak
        assert said[1:] == [PENDING, f"Worker {lane.name} is on the way.", FINISHED], (lane.name, said)
        everything = repr(history)
        assert not [n for n in names - {lane.name} if f"TKT-{n}" in everything or f"-{n}'" in everything], lane.name
        snap = get(f"/conversations/{lane.ids['conversation']}").json()
        assert [(w["workflow_id"], w["state"], w["next_action"]) for w in snap["workflows"]] == [(lane.ids["workflow"], "closed", "none")]
        assert snap["approvals"] == [] and all(m["workflow_id"] == lane.ids["workflow"] for m in snap["messages"])
        assert [m["text"] for m in snap["messages"] if m["sender"] == "user"] == [
            f"{lane.tag}: the tap in my kitchen drips.", f"Please book a repair visit for it ({lane.tag})."]
        for rid in lane.ids["requests"]:  # every request settled
            req = get(f"/requests/{rid}").json()
            assert req["request_status"] == "completed" and req["workflow_id"] == lane.ids["workflow"], (lane.name, req)
    # the partner: one action per workflow, each under its own reference, each made and called once
    refs = [lane.ids["reference"] for lane in lanes]
    assert len(set(refs)) == len(lanes)
    assert partner["side_effects"] == len(lanes) and set(partner["jobs"]) == set(refs), partner
    assert partner["book_repair_calls_by_reference"] == {ref: 1 for ref in refs}, partner
    assert len(set(partner["jobs"].values())) == len(lanes)


def pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))]


def numbers(lanes: list[Lane], total: float) -> dict:
    """p50, p95 and the slowest of each kind of POST, in seconds; how many request POSTs answered 202; the total."""
    out: dict = {"workflows": len(lanes), "total_seconds": round(total, 2)}
    groups = {"start_workflow": ("start",), "workflow_reply": ("reply",), "decision": ("decision",),
              "provider_event": ("event1", "event2"), "close": ("close",)}
    for name, kinds in groups.items():
        took = [lane.times[k] for lane in lanes for k in kinds if k in lane.times]
        if took:
            out[name] = {"p50": round(statistics.median(took), 3), "p95": round(pct(took, 0.95), 3), "max": round(max(took), 3)}
    posts = [lane.times[k] for lane in lanes for k in lane.times]
    if posts:
        out["all_posts"] = {"n": len(posts), "p50": round(statistics.median(posts), 3), "p95": round(pct(posts, 0.95), 3),
                            "max": round(max(posts), 3)}
    out["answered_202"] = sum(1 for lane in lanes for k in ("start", "reply") if lane.codes.get(k) == 202)
    return out
