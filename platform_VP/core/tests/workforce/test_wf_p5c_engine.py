"""What the load test of P5c found in the engine, each pinned by a test:

- an event that wakes a parked agent was sent a second time when its acknowledgement took longer than AWP_WF_ACK_SECONDS
  (it does under load); the second copy found the agent no longer waiting, its run failed, and the job was failed for
  it although its work was done (three times, then the workflow needed attention);
- a turn that ended well was outvoted by a failed second run under the same id;
- every wait of the engine looked every 30 ms for as long as it lasted.
"""
import asyncio
import time
from types import SimpleNamespace

import pytest
from sqlalchemy import insert

from awp.config import Settings
from awp.workforce import resume, runner, tables as t
from awp.workforce.leader import Leader
from awp.workforce.runner import JobFailed, Pace, WorkflowEngine
from dbkit import Lab
from enginekit import world
from partnerkit import Partner
from t1kit import SETTINGS, TOOLS, act, configure, ops

LEADER = Leader("ta", "agent_1", "session_1")


def engine(**settings):
    """Just enough of an engine for `_deliver`: its settings and a session that is never busy."""
    async def idle(leader, timeout):
        return True
    return SimpleNamespace(settings=Settings(**settings), _idle=idle, client=None)


def deliver(eng, **kw):
    return WorkflowEngine._deliver(eng, "wf_1", LEADER, "", "resume_appr_1", "", **kw)


def test_an_event_is_not_sent_again_while_its_agent_is_no_longer_parked():
    """The first copy was taken (the session runs it): the acknowledgement is late, and no second copy goes out."""
    async def go():
        sent, t0 = [], time.monotonic()

        async def send():
            sent.append(time.monotonic() - t0)

        async def acked():
            return time.monotonic() - t0 > 0.6  # three times the ack window

        async def parked():
            return not sent  # parked until the event was sent; then its session runs
        await deliver(engine(wf_ack_seconds=0.2), send=send, acked=acked, ready=parked)
        assert len(sent) == 1
    asyncio.run(go())


def test_an_event_waits_for_its_agent_to_be_parked_before_it_is_sent_at_all():
    """The decision came while the turn that asked was still ending: the event goes once that turn has parked."""
    async def go():
        sent, t0, state = [], time.monotonic(), {}

        async def send():
            sent.append(time.monotonic() - t0)
            state["taken"] = True

        async def acked():
            return bool(state.get("taken"))

        async def parked():
            return time.monotonic() - t0 > 0.3
        await deliver(engine(wf_ack_seconds=0.2), send=send, acked=acked, ready=parked)
        assert len(sent) == 1 and sent[0] > 0.3
    asyncio.run(go())


def test_an_event_that_was_lost_is_sent_again_while_the_agent_is_still_parked():
    async def go():
        sent = []

        async def send():
            sent.append(1)

        async def acked():
            return len(sent) >= 3  # the first two never arrived

        async def parked():
            return True
        await deliver(engine(wf_ack_seconds=0.05), send=send, acked=acked, ready=parked)
        assert len(sent) == 3
    asyncio.run(go())


def test_an_agent_that_never_takes_the_event_fails_the_attempt(monkeypatch):
    async def go():
        sent = []

        async def send():
            sent.append(1)

        async def never():
            return False

        async def always():
            return True
        monkeypatch.setattr(runner, "UNREADY", 0.3)
        t0 = time.monotonic()
        with pytest.raises(JobFailed, match="not waiting"):  # never parked: nothing is sent, and the wait is bounded
            await deliver(engine(wf_ack_seconds=0.05), send=send, acked=never, ready=never)
        assert sent == [] and 0.3 <= time.monotonic() - t0 < 3
        with pytest.raises(JobFailed, match="never taken"):  # parked and deaf: the old limit of sends still holds
            await deliver(engine(wf_ack_seconds=0.02), send=send, acked=never, ready=always)
        assert len(sent) == runner.MAX_SENDS
    asyncio.run(go())


def test_a_message_is_still_sent_again_without_asking_anybody():
    """`say()` has no `ready`: a second copy of a message gets a 409 while its run lives, so it is safe (P0)."""
    async def go():
        sent = []

        async def send():
            sent.append(1)

        async def acked():
            return len(sent) >= 2
        await deliver(engine(wf_ack_seconds=0.03), send=send, acked=acked)
        assert len(sent) == 2
    asyncio.run(go())


# ---- the turn of an attempt -------------------------------------------------------------------------------------------------
@pytest.fixture
def lab(tmp_path):
    lab = Lab(tmp_path / "turns.db")
    yield lab
    lab.close()


def turn(lab, wid, msg_id, status, at):
    async def go():
        async with lab.db.engine.begin() as conn:
            await conn.execute(insert(t.turns).values(id=f"turn_{at}", workflow_id=wid, job_id=None, trigger="x", msg_id=msg_id,
                                                      status=status, started_at=at, ended_at=at + 1))
    lab.run(go())


def check(lab, wid, msg_id):
    return lab.run(WorkflowEngine._check_turn(SimpleNamespace(ctx=SimpleNamespace(db=lab.db)), wid, msg_id))


def test_a_turn_that_ended_well_stands_whatever_a_second_run_under_its_id_did(lab):
    wid = lab.seed()["wf"]["id"]
    turn(lab, wid, "resume_appr_1", "completed", 100.0)
    turn(lab, wid, "resume_appr_1", "error", 105.0)  # the second copy of the event: "the agent is not waiting"
    check(lab, wid, "resume_appr_1")  # no JobFailed
    turn(lab, wid, "resume_appr_2", "parked", 200.0)  # the resumed turn asked for another consent: that is an outcome too
    turn(lab, wid, "resume_appr_2", "error", 205.0)
    check(lab, wid, "resume_appr_2")


def test_a_turn_that_only_failed_still_fails_its_attempt(lab):
    wid = lab.seed()["wf"]["id"]
    turn(lab, wid, "job_1", "error", 100.0)
    with pytest.raises(JobFailed, match="ended with an error"):
        check(lab, wid, "job_1")
    turn(lab, wid, "job_2", "interrupted", 300.0)
    turn(lab, wid, "job_2", "error", 301.0)
    with pytest.raises(JobFailed):
        check(lab, wid, "job_2")
    check(lab, wid, "job_3")  # no turn at all is not this check's business


# ---- how often a wait looks --------------------------------------------------------------------------------------------------
def test_a_wait_looks_often_for_a_second_and_then_slows_down(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(runner.time, "monotonic", lambda: clock[0])
    pace = Pace()
    assert [pace.next() for _ in range(5)] == [runner.POLL] * 5
    clock[0] += runner.QUICK + 0.01
    steps = [pace.next() for _ in range(12)]
    assert steps[0] == runner.POLL and steps == sorted(steps) and steps[-1] == runner.SLOW_POLL
    assert sum(1 for s in steps if s == runner.SLOW_POLL) >= 3  # it stays there
    pace.reset()
    assert pace.next() == runner.POLL


# ---- the same, on the real engine -------------------------------------------------------------------------------------------
CONSENT = act("partner_repair_consent", {"slot": "mon"}, "I asked for a plumber for Monday; it is pending.")


def slow_acknowledgement(monkeypatch, seconds: float):
    """The agent takes the event at once; the engine learns it only `seconds` later (as under load)."""
    real, first = resume.acked, {}

    async def acked(eng, approval_id):
        first.setdefault(approval_id, time.monotonic())
        return await real(eng, approval_id) and time.monotonic() - first[approval_id] > seconds
    monkeypatch.setattr(resume, "acked", acked)


def confirms(w) -> list:
    sent, real = [], w.env.app.state.awp.client.confirm

    async def confirm(*a, **k):
        sent.append(a[2])
        return await real(*a, **k)
    w.env.app.state.awp.client.confirm = confirm
    return sent


def approve(w):
    start, first = w.flow.begin()
    assert first["workflow_state"] == "awaiting_approval", first
    [approval] = w.flow.approvals(first["conversation_id"])
    assert w.flow.decide(approval["approval_id"], w.flow.decide_body(start, first, approval)).status_code == 202
    return first


def test_a_decision_whose_acknowledgement_is_late_is_handed_to_the_agent_once(tmp_path, monkeypatch):
    with Partner() as partner, world(tmp_path, CONSENT, wf_ack_seconds=0.15, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        sent = confirms(w)
        slow_acknowledgement(monkeypatch, 1.0)
        first = approve(w)
        w.wait_state(first["workflow_id"], "waiting_external_event")
        w.quiet()
        assert len(sent) == 1
        assert w.sql("select status from wf_turns where msg_id like 'resume_%'") == [("completed",)]
        assert w.sql("select kind, status, attempts from wf_jobs where kind='approval_resume'") == [("approval_resume", "done", 1)]
        assert [o["status"] for o in ops(w, first["workflow_id"])] == ["pending"] and len(partner.of("book_repair")) == 1


def test_even_a_second_copy_of_a_decision_does_not_fail_the_job_whose_work_is_done(tmp_path, monkeypatch):
    """The net under the first rule: were a copy sent twice after all, the agent's refusal of the second is not the job's failure."""
    async def wake_as_before(eng, wid, target, row):  # nobody asks whether the agent still waits
        await eng._deliver(wid, target, "", resume.RESUME + row["id"], "", send=lambda: resume._send(eng, target, row),
                           acked=lambda: resume.acked(eng, row["id"]))
    with Partner() as partner, world(tmp_path, CONSENT, wf_ack_seconds=0.15, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        sent = confirms(w)
        monkeypatch.setattr(resume, "wake", wake_as_before)
        slow_acknowledgement(monkeypatch, 0.25)
        first = approve(w)
        w.wait_state(first["workflow_id"], "waiting_external_event")
        # the second copy went out, was taken after the first, and its run failed: the agent was not waiting any more
        w.wait(lambda: sorted(r[0] for r in w.sql("select status from wf_turns where msg_id like 'resume_%'")) == ["completed", "error"],
               what="the failed run of the second copy")
        w.quiet()
        assert len(sent) == 2
        assert w.sql("select kind, status, attempts from wf_jobs where kind='approval_resume'") == [("approval_resume", "done", 1)]
        assert w.state(first["workflow_id"])[0] == "waiting_external_event"
        assert [o["status"] for o in ops(w, first["workflow_id"])] == ["pending"] and len(partner.of("book_repair")) == 1
        said = [m[1] for m in w.messages(first["workflow_id"]) if m[0] == "assistant"]
        assert said == ["I asked for a plumber for Monday; it is pending."]
