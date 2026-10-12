"""The owner's named scenarios (docs/MVP_DAC_TA_BO_SUNG.md M5 and M7; the owner's own names for the ticket ones are
M8, M8I and M9, described as "two tickets of one customer never mix; events are not lost after an interruption").

  M5  controlled booking     the partner's action needs the resident's confirmation, is never called twice, and the
                             booking survives the platform stopping in the middle
  M7  multi-turn tickets     two tickets of one customer, several turns each, interleaved, with approvals and
                             provider events: nothing of one ever shows in the other, and no event is lost when the
                             client's stream is cut and resumed with Last-Event-ID

Each scenario is written once (below) and run twice: on one process, in the default suite, where "the platform stops"
is a clean stop and a new app on the same databases; and on a fleet of real processes on PostgreSQL and Redis
(marker `multiproc`, skipped without AWP_TEST_PG_URL and AWP_TEST_REDIS_URL), where it is a kill.

Scripted model and a sample partner in both: this is the platform's bookkeeping, not a model's judgment.
"""
from __future__ import annotations

import time

import pytest

from mpkit import audit, fleet, needs_fleet, one_effect, until  # noqa: F401 (fleet: fixture)
from mpkit import World
from ownerkit import Local

BOOK = "Please book a repair visit for the leaking tap."
PENDING = "I asked for the visit on Monday; it is pending."
HANDLED = "Your request for a visit is being handled; I will tell you when it changes."
FINISHED = "The partner reports the work finished. Is everything right?"
DECLINED = "Understood, nothing was requested. Anything else?"


def text(words: str) -> dict:
    return {"type": "text", "text": words}


# ---- M5: controlled booking ----------------------------------------------------------------------------------------------
def ask_for_a_visit(x, f) -> tuple[dict, dict, dict]:
    """The resident asks; the leader wants to book; the platform asks the resident first and sends nothing."""
    r, body = f.start(message=text(BOOK))
    started = x.settled(f, r)
    assert (started["workflow_state"], started["next_action"]) == ("awaiting_approval", "submit_approval"), started
    appr = x.approval(f, started["conversation_id"])
    assert appr["status"] == "pending" and x.partner()["side_effects"] == 0
    again = f.post(body)  # the partner's retry of the same request: the same answer, and still nothing sent
    assert again.status_code == 200, again.text
    same = ("request_id", "workflow_id", "workflow_state")
    assert {k: again.json()[k] for k in same} == {k: started[k] for k in same}
    assert x.partner()["side_effects"] == 0 and len(f.approvals(started["conversation_id"])) == 1
    return body, started, appr


def report_and_close(x, f, provider, body: dict, started: dict, ref: str) -> None:
    conv = started["conversation_id"]
    for kind, data in (("job.assigned", {"worker_name": "An"}), ("job.completed", {})):
        r, _ = provider.send(kind, ref=ref, data=data)
        assert r.status_code == 202, r.text
    wf = x.until_state(f, conv, "awaiting_confirmation")
    assert wf["next_action"] == "confirm_close"
    closed, _ = f.close({"workflow_id": started["workflow_id"], "workflow_revision": wf["workflow_revision"]}, body)
    assert closed.status_code == 200 and (closed.json()["state"], closed.json()["next_action"]) == ("closed", "none")


def booked_once(x, f, conv: str, calls: int) -> None:
    seen = audit(x, f, conv)
    assert seen.kinds.count("approval.required") == 1 and seen.kinds.count("approval.resolved") == 1
    assert seen.kinds.count("ticket.created") == 1 and seen.kinds.count("workflow.closed") == 1
    assert seen.texts.count(FINISHED) == 1 and seen.texts.count("Worker An is on the way.") == 1
    assert seen.texts.count(PENDING) + seen.texts.count(HANDLED) == 1
    one_effect(x, calls=calls)


def test_m5_controlled_booking_needs_confirmation_is_sent_once_and_survives_restarts(tmp_path):
    x = Local(tmp_path)
    try:
        body, started, appr = ask_for_a_visit(x, x.flow())
        conv = started["conversation_id"]

        x.restart()  # the platform stops and starts while the resident thinks about it
        f = x.flow()
        assert x.approval(f, conv)["approval_id"] == appr["approval_id"] and x.partner()["side_effects"] == 0
        assert x.state(f, conv)["workflow_state"] == "awaiting_approval"

        decision = f.decide_body(body, started, appr)
        d = f.decide(appr["approval_id"], decision)
        assert d.status_code == 202 and d.json()["status"] == "approved", d.text
        x.until_state(f, conv, "waiting_external_event")
        ref = one_effect(x, calls=1)
        again = f.decide(appr["approval_id"], decision)  # the same decision again: the same answer, no second visit
        assert again.status_code == 202 and again.json() == d.json()

        x.restart()  # and once more while the partner works
        f = x.flow()
        time.sleep(3.0)  # a sweep of the new process: nothing is picked up to be done again
        assert x.state(f, conv)["workflow_state"] == "waiting_external_event" and one_effect(x, calls=1) == ref
        report_and_close(x, f, x.provider_at(), body, started, ref)
        booked_once(x, f, conv, calls=1)
        refused = f.decide(appr["approval_id"], {**decision, "external_request_id": "rq-late"})
        assert refused.status_code == 409  # a decision after all that changes nothing
        one_effect(x, calls=1)
    finally:
        x.close()


@pytest.mark.slow
@pytest.mark.multiproc
@needs_fleet
def test_m5_controlled_booking_with_every_process_killed_on_the_way(fleet):
    """Process 0 is killed while the resident thinks; process 1 is killed inside the approved call to the partner; a
    third process is started on what they left. One visit, one of every message."""
    x = World(fleet)
    body, started, appr = ask_for_a_visit(x, x.flow(0))
    conv = started["conversation_id"]

    fleet.kill(fleet.api[0])
    f = x.flow(1)
    assert x.approval(f, conv)["approval_id"] == appr["approval_id"]
    fleet.hold_partner(True)
    d = f.decide(appr["approval_id"], f.decide_body(body, started, appr))
    assert d.status_code == 202, d.text
    until(lambda: fleet.partner()["held"] == 1, 30, "the approved call to hang at the partner")
    fleet.kill(fleet.api[1])  # nobody is left
    fleet.hold_partner(False)

    fleet.start_api()  # the restart
    f = x.flow(2)
    x.until_state(f, conv, "waiting_external_event")
    until(lambda: max(fleet.partner()["book_repair_calls_by_reference"].values()) == 2, 60, "the request to be sent again")
    ref = one_effect(x, calls=2)  # asked again with the same reference: the partner has one visit
    report_and_close(x, f, x.provider_at(2), body, started, ref)
    booked_once(x, f, conv, calls=2)


# ---- M7: multi-turn tickets ------------------------------------------------------------------------------------------
def two_tickets(x, p: int, q: int, cut, after_cut=lambda: None) -> None:
    """Two tickets of one resident, their turns interleaved and alternating between the processes p and q.

    `cut(stream)` is the interruption: from then on nothing more reaches the stream the client of ticket ALPHA holds
    open on process p, while the workflow goes on (through q). The client then reconnects to q with the id of the last
    event it received."""
    fp, fq = x.flow(p), x.flow(q)
    ra, a_body = fp.start(message=text("TKT-ALPHA the kitchen tap leaks"))
    rb, b_body = fq.start(message=text("TKT-BRAVO the hall lamp flickers"))
    a, b = x.settled(fp, ra), x.settled(fq, rb)
    conv_a, conv_b = a["conversation_id"], b["conversation_id"]
    assert conv_a != conv_b and a["workflow_id"] != b["workflow_id"]
    assert a_body["external_user_id"] == b_body["external_user_id"]  # one customer
    assert a["result"]["messages"][0]["text"].startswith("Noted (TKT-ALPHA)")
    assert b["result"]["messages"][0]["text"].startswith("Noted (TKT-BRAVO)")

    for part, (fa, fb) in (("one", (fq, fp)), ("two", (fp, fq))):  # each ticket's next turn through the other process
        r1, _ = fa.reply(a_body, a, message=text(f"TKT-ALPHA more about the tap, part {part}"))
        r2, _ = fb.reply(b_body, b, message=text(f"TKT-BRAVO more about the lamp, part {part}"))
        for f, r, own in ((fa, r1, "ALPHA"), (fb, r2, "BRAVO")):
            done = x.settled(f, r)
            assert done["workflow_state"] == "awaiting_user"
            assert done["result"]["messages"][0]["text"].startswith(f"Noted (TKT-{own})"), done

    stream = x.stream(fp, conv_a)  # the client of ALPHA follows its ticket on process p
    got = stream.events(len(x.events(fq, conv_a)), timeout=20)

    r1, _ = fq.reply(a_body, a, message=text("TKT-ALPHA " + BOOK))  # both ask for a visit: each needs its own consent
    r2, _ = fp.reply(b_body, b, message=text("TKT-BRAVO " + BOOK))
    assert x.settled(fq, r1)["workflow_state"] == "awaiting_approval"
    assert x.settled(fp, r2)["workflow_state"] == "awaiting_approval"
    appr_a, appr_b = x.approval(fq, conv_a), x.approval(fq, conv_b)
    assert appr_a["approval_id"] != appr_b["approval_id"] and x.partner()["side_effects"] == 0
    got += stream.events(len(x.events(fq, conv_a)) - len(got), timeout=20)

    cut(stream)  # ---- nothing more reaches that stream ----
    da = fq.decide(appr_a["approval_id"], fq.decide_body(a_body, a, appr_a))
    db = fq.decide(appr_b["approval_id"], fq.decide_body(b_body, b, appr_b, decision="reject"))
    assert da.status_code == 202 and db.status_code == 202, (da.text, db.text)
    x.until_state(fq, conv_a, "waiting_external_event")
    x.until_state(fq, conv_b, "awaiting_user")
    ref = one_effect(x, calls=1)  # ALPHA's visit; BRAVO's was declined and never sent
    provider = x.provider_at(q)
    for kind, data in (("job.assigned", {"worker_name": "An"}), ("job.completed", {})):
        r, _ = provider.send(kind, ref=ref, data=data)
        assert r.status_code == 202, r.text
    wf_a = x.until_state(fq, conv_a, "awaiting_confirmation")
    r, _ = fq.reply(b_body, b, message=text("TKT-BRAVO thank you, that is all"))  # BRAVO goes on meanwhile
    assert x.settled(fq, r)["result"]["messages"][0]["text"].startswith("Noted (TKT-BRAVO)")
    after_cut()

    log = x.events(fq, conv_a)
    missed = log[len(got):]
    assert len(missed) >= 8  # the decision, the visit, the provider's reports, the leader's question: all after the cut
    resumed = x.stream(fq, conv_a, last=got[-1]["id"])
    rest = resumed.events(len(missed), timeout=20)
    assert [f["id"] for f in got + rest] == [e["event_id"] for e in log]  # nothing lost, nothing twice, in order
    assert [f["data"] for f in rest] == missed

    closed, _ = fq.close({"workflow_id": a["workflow_id"], "workflow_revision": wf_a["workflow_revision"]}, a_body)
    assert closed.status_code == 200 and closed.json()["state"] == "closed", closed.text
    [last] = resumed.events(1, timeout=20)
    assert last["event"] == "workflow.closed" and last["data"]["sequence"] == len(log) + 1
    resumed.close()
    wf_b = x.state(fq, conv_b)
    closed, _ = fq.close({"workflow_id": b["workflow_id"], "workflow_revision": wf_b["workflow_revision"]}, b_body)
    assert closed.status_code == 200 and closed.json()["state"] == "closed", closed.text

    # ---- nothing of one ticket in the other ----
    for conv, body, own, other in ((conv_a, a_body, "ALPHA", "BRAVO"), (conv_b, b_body, "BRAVO", "ALPHA")):
        seen = audit(x, fq, conv)
        assert {e["external_ticket_id"] for e in seen.events} == {body["external_ticket_id"]}
        assert {e["external_conversation_id"] for e in seen.events} == {body["external_conversation_id"]}
        assert not any(f"TKT-{other}" in t for t in seen.texts), seen.texts
        noted = [t for t in seen.texts if t.startswith("Noted")]
        assert noted and all(t.startswith(f"Noted (TKT-{own})") for t in noted), noted  # the session only ever saw its own
        snap = fq.snapshot(conv).json()
        assert not any(f"TKT-{other}" in m["text"] for m in snap["messages"]) and len(snap["workflows"]) == 1
        assert seen.kinds.count("approval.required") == 1 and seen.kinds.count("workflow.closed") == 1
    a_seen, b_seen = audit(x, fq, conv_a), audit(x, fq, conv_b)
    assert a_seen.texts.count(PENDING) == 1 and a_seen.texts.count(FINISHED) == 1 and DECLINED not in a_seen.texts
    assert b_seen.texts.count(DECLINED) == 1 and PENDING not in b_seen.texts and FINISHED not in b_seen.texts
    assert "operation.status_changed" in a_seen.kinds and "operation.status_changed" not in b_seen.kinds
    assert [e["payload"]["status"] for e in a_seen.events if e["event_type"] == "approval.resolved"] == ["approved"]
    assert [e["payload"]["status"] for e in b_seen.events if e["event_type"] == "approval.resolved"] == ["rejected"]
    assert one_effect(x, calls=1) == ref


def test_m7_two_tickets_of_one_customer_never_mix_and_a_cut_stream_loses_no_event(tmp_path):
    x = Local(tmp_path)
    try:
        two_tickets(x, 0, 0, cut=lambda stream: stream.close())  # the client's connection drops in the middle
    finally:
        x.close()


@pytest.mark.slow
@pytest.mark.multiproc
@needs_fleet
def test_m7_two_tickets_across_two_processes_with_a_kill_between_commit_and_delivery(fleet):
    """The turns of both tickets alternate between two processes. The process that the client of ALPHA streams from is
    frozen (so the events committed from then on are never delivered by it) and then killed; the client resumes on the
    other process with Last-Event-ID."""
    x = World(fleet)
    held = {}

    def cut(stream) -> None:
        held["stream"] = stream
        fleet.freeze(fleet.api[0])

    def kill() -> None:
        while (frame := held["stream"].next(timeout=2.0)) is not None:
            assert "comment" in frame, f"a frozen process delivered {frame}"
        fleet.kill(fleet.api[0])
        assert held["stream"].ended(15)

    two_tickets(x, 0, 1, cut, kill)
