"""TurnRecorder: one wf_turns row per run of the leader, and never a risk to the reply (slice S3)."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from dbkit import Lab

from agentscope.event import ReplyEndEvent, ReplyStartEvent, RequireUserConfirmEvent
from agentscope.message import Msg

from awp.workforce import tables as t
from awp.workforce.turns import TurnRecorder, job_of, status_of


@pytest.fixture
def lab(tmp_path):
    lab = Lab(tmp_path / "turns.db")
    yield lab
    lab.close()


def msg(msg_id: str) -> Msg:
    return Msg(name="resident", role="user", content=[{"type": "text", "text": "hi"}], id=msg_id)


def end(reason: str = "completed") -> ReplyEndEvent:
    return ReplyEndEvent(session_id="s", reply_id="r", finished_reason=reason)


def handler(*items, then=None):
    async def run(**kw):
        for item in items:
            yield item
        if then is not None:
            raise then
    return run


def play(lab, rec, inputs, next_handler) -> tuple[list, BaseException | None]:
    """Drive `rec.on_reply` to its end; (items it passed on, the exception it raised, if any)."""
    async def go():
        out, err = [], None
        try:
            async for item in rec.on_reply(None, {"inputs": inputs}, next_handler):
                out.append(item)
        except BaseException as e:  # noqa: BLE001
            err = e
        return out, err
    return lab.run(go())


def recorder(lab, hook=None):
    wf = lab.seed("active")["wf"]
    rt = SimpleNamespace(db=lab.db, turn_hook=hook)
    return TurnRecorder(rt, wf["id"]), wf["id"]


def rows(lab, wid):
    return lab.rows(t.turns, workflow_id=wid)


def test_job_ids_come_from_the_message_id():
    assert job_of("job_abc") == "job_abc" and job_of("job_abc.2") == "job_abc"
    assert job_of(None) is None and job_of("msg_abc") is None


def test_status_of_the_ways_a_turn_ends():
    assert status_of("completed", False, "end") == "completed"
    assert status_of("exceed_max_iters", False, "end") == "completed"
    assert status_of(None, True, "end") == "parked"  # parked wins: a permission was asked, no ReplyEnd followed
    assert status_of(None, False, "error") == "error" and status_of("error", False, "end") == "error"
    assert status_of("interrupted", False, "end") == "interrupted" and status_of(None, False, "interrupted") == "interrupted"


def test_a_normal_turn_is_recorded_from_start_to_end(lab):
    told = []
    rec, wid = recorder(lab, told.append)
    items = [ReplyStartEvent(session_id="s", reply_id="r", name="x", role="assistant"), end()]
    out, err = play(lab, rec, msg("job_1"), handler(*items))
    assert err is None and out == items  # the stream is passed on untouched
    [row] = rows(lab, wid)
    assert (row["status"], row["trigger"], row["msg_id"], row["job_id"]) == ("completed", "message", "job_1", "job_1")
    assert row["ended_at"] is not None and told == [wid]  # the engine is told after the row is closed


def test_a_run_nobody_sent_has_no_job(lab):
    rec, wid = recorder(lab)
    play(lab, rec, None, handler(end()))  # a worker's report woke the leader: inputs None
    [row] = rows(lab, wid)
    assert (row["trigger"], row["msg_id"], row["job_id"]) == ("continue", None, None)


def test_the_second_attempt_of_a_job_still_belongs_to_it(lab):
    rec, wid = recorder(lab)
    play(lab, rec, msg("job_9.2"), handler(end()))
    assert rows(lab, wid)[0]["job_id"] == "job_9" and rows(lab, wid)[0]["msg_id"] == "job_9.2"


def test_a_turn_parked_on_a_permission_has_no_end_event_and_is_parked(lab):
    rec, wid = recorder(lab)
    out, err = play(lab, rec, msg("job_1"), handler(RequireUserConfirmEvent(reply_id="r", tool_calls=[])))
    assert err is None and len(out) == 1
    assert rows(lab, wid)[0]["status"] == "parked"


def test_an_interrupted_turn_is_interrupted(lab):
    rec, wid = recorder(lab)
    play(lab, rec, msg("job_1"), handler(end("interrupted")))
    assert rows(lab, wid)[0]["status"] == "interrupted"


def test_a_model_failure_is_an_exception_in_on_reply_and_is_recorded_and_raised_on(lab):
    rec, wid = recorder(lab)
    boom = RuntimeError("the model is down")
    out, err = play(lab, rec, msg("job_1"), handler(then=boom))
    assert err is boom  # the same exception, for AgentScope to turn into its error reply
    assert rows(lab, wid)[0]["status"] == "error"


def test_a_cancelled_turn_is_interrupted_and_the_cancel_goes_on(lab):
    rec, wid = recorder(lab)
    out, err = play(lab, rec, msg("job_1"), handler(then=asyncio.CancelledError()))
    assert isinstance(err, asyncio.CancelledError)
    assert rows(lab, wid)[0]["status"] == "interrupted"


class BrokenDb:
    """A database that fails on every use, as when the recorder's own writes go wrong."""

    @property
    def engine(self):
        raise RuntimeError("the recorder's database is gone")


def test_the_recorders_own_failure_never_breaks_the_reply(lab):
    def bad_hook(_):
        raise RuntimeError("hook bug")

    rec = TurnRecorder(SimpleNamespace(db=BrokenDb(), turn_hook=bad_hook), "wf_x")
    items = [ReplyStartEvent(session_id="s", reply_id="r", name="x", role="assistant"), end()]
    out, err = play(lab, rec, msg("job_1"), handler(*items))
    assert err is None and out == items  # begin, end and the hook all failed; the stream did not notice

    boom = ValueError("the model failed")  # and it does not hide the real error behind its own
    out, err = play(lab, rec, msg("job_2"), handler(then=boom))
    assert err is boom


def test_a_hook_that_raises_does_not_break_a_working_recorder(lab):
    def bad_hook(_):
        raise RuntimeError("hook bug")

    rec, wid = recorder(lab, bad_hook)
    out, err = play(lab, rec, msg("job_1"), handler(end()))
    assert err is None and len(out) == 1 and rows(lab, wid)[0]["status"] == "completed"
