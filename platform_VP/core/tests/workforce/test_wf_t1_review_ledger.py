"""Review of slice T1, durability of the ledger: an answer the partner gave is never dropped, a resend that could not
connect says nothing about the original request, stop tracking stops the resends of a pass, and 'do not retry' holds for
a reworded request too. Scripted model only; a real MCP server."""
from __future__ import annotations

import asyncio
import json
import threading

import pytest
from partnerkit import Partner
from t1kit import crash_at, ops, tools_of
from test_wf_t1_ledger import call, dies, room, state, sweep, words

from awp.workforce import ledger


@pytest.fixture
def partner():
    with Partner() as p:
        yield p


async def until(check, ceiling: float = 20.0) -> None:
    """Wait (on the app's loop) until `check()` holds; the ceiling only makes a broken test fail instead of hang."""
    for _ in range(int(ceiling / 0.01)):
        if check():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("timed out")


def held_finish(monkeypatch, gate: threading.Event) -> list:
    """`ledger.finish` waits until the test opens the gate: a busy database, or a lock held by another writer of the
    conversation. A gate, not a delay: how long the write takes no longer depends on the speed of the machine. The
    returned list gains an item when a write has begun to wait."""
    real, entered = ledger.finish, []

    async def held(*a, **k):
        entered.append(1)
        await until(gate.is_set, 40)
        return await real(*a, **k)
    monkeypatch.setattr(ledger, "finish", held)
    return entered


def status_of(w) -> str:
    return ops(w)[0]["status"]


# ---- the answer in hand is never dropped -----------------------------------------------------------------------------
def test_a_slow_result_write_loses_nothing_and_does_not_hold_the_model_past_its_deadline(tmp_path, partner, monkeypatch):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_hotel"]
        t.total = 1.0
        gate = threading.Event()
        entered = held_finish(monkeypatch, gate)
        try:
            out = words(call(w, t, hotel="Sunrise", nights=2))
            # the tool answered while the write was still held: the deadline of the body, not the database, set the pace
            assert entered and status_of(w) == "sent"
            assert "confirmed" in out and "<platform-verified>" in out  # the model has the partner's real answer
        finally:
            gate.set()
        w.wait(lambda: status_of(w) == "completed", 10, "the write that was still going")
        assert partner.effects == ["hotel"]


def test_a_result_write_that_fails_is_tried_again_and_the_sweep_finishes_it_from_memory(tmp_path, partner, monkeypatch):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_hotel"]
        ledger.HELD.clear()
        real = ledger.finish

        async def boom(*a, **k):
            raise RuntimeError("database hiccup")
        monkeypatch.setattr(ledger, "finish", boom)
        out = words(call(w, t, hotel="Sunrise", nights=2))
        monkeypatch.setattr(ledger, "finish", real)
        assert "confirmed" in out  # the resident may be told: the partner did say so
        assert status_of(w) == "sent" and len(ledger.HELD) == 1  # nothing was written, the answer is held
        sweep(w)
        assert status_of(w) == "completed" and ledger.HELD == {}
        assert state(w)[0] != "needs_attention"  # not turned into an unknown: the answer was never lost
        assert len(partner.of("book_hotel")) == 1


def test_a_write_that_fails_once_is_retried_at_once(tmp_path, partner, monkeypatch):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_hotel"]
        real, seen = ledger.finish, []

        async def flaky(*a, **k):
            seen.append(1)
            if len(seen) == 1:
                raise RuntimeError("database hiccup")
            return await real(*a, **k)
        monkeypatch.setattr(ledger, "finish", flaky)
        call(w, t, hotel="Sunrise", nights=2)
        assert status_of(w) == "completed" and len(seen) == 2 and ledger.HELD == {}


def test_a_cancel_while_the_result_is_written_does_not_drop_the_answer(tmp_path, partner, monkeypatch):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_hotel"]
        gate = threading.Event()
        entered = held_finish(monkeypatch, gate)

        async def go():
            task = asyncio.ensure_future(t.call(hotel="Sunrise", nights=2))
            await until(lambda: entered)  # the partner has answered; the write is in progress
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        try:
            w.run(go)
        finally:
            gate.set()
        w.wait(lambda: status_of(w) == "completed", 10, "the answer to be written after the cancel")
        assert partner.effects == ["hotel"]


def test_a_cancel_before_any_answer_is_written_down_as_unknown(tmp_path, partner, monkeypatch):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_slow"]
        partner.delay = 20

        async def go():
            task = asyncio.ensure_future(t.call(seconds=20))
            await until(lambda: partner.of("slow_action"))  # sent, no answer yet
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        w.run(go)
        w.wait(lambda: status_of(w) == "unknown", 10, "the interrupted call to be recorded")


def test_a_timeout_whose_unknown_is_written_late_is_still_unknown_in_the_ledger(tmp_path, partner, monkeypatch):
    """The client gives up at total+0.5 s and the body's deadline is total+0.7 s: the row used to stay `sent`,
    counted as moving, while the model had been told UNKNOWN."""
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_slow"]  # call_timeout 1.5
        partner.delay = 20
        gate = threading.Event()
        held_finish(monkeypatch, gate)
        try:
            out = words(call(w, t, seconds=20))
            assert out.startswith("UNKNOWN:") and status_of(w) == "sent"  # told UNKNOWN while the write is still held
        finally:
            gate.set()
        monkeypatch.undo()
        w.wait(lambda: status_of(w) == "unknown", 10, "the unknown to be written")
        assert words(call(w, t, seconds=20)).startswith("UNKNOWN:")  # a repeat is told so, not 'IN PROGRESS'


# ---- a resend that cannot connect says nothing about the original request --------------------------------------------
def test_a_resend_that_cannot_connect_leaves_the_request_unresolved_and_wakes_nobody(tmp_path, monkeypatch):
    p = Partner().start()
    try:
        with room(tmp_path, p) as w:
            t = tools_of(w)["partner_repair_keyed"]  # idempotency_arg: recovery resends with the same reference
            crash_at(monkeypatch, ledger, "finish")
            assert dies(w, t, slot="mon")  # the partner DID get it and made the booking; the answer was lost
            monkeypatch.undo()
            assert p.effects == ["repair"]
            p.stop()  # the partner is unreachable when the restarted process looks
            sweep(w)
            assert status_of(w) == "sent"  # not `failed`, not 'nothing was carried out'
            assert w.sql("select count(*) from wf_jobs where kind='provider_wake'") == [(0,)]
            assert state(w)[0] != "needs_attention"
    finally:
        p.stop()


def test_a_resend_that_gets_through_after_a_failed_one_settles_the_request(tmp_path, monkeypatch):
    p = Partner().start()
    port = p.port
    try:
        with room(tmp_path, p) as w:
            t = tools_of(w)["partner_repair_keyed"]
            crash_at(monkeypatch, ledger, "finish")
            assert dies(w, t, slot="mon")
            monkeypatch.undo()
            ref = ops(w)[0]["reference"]
            p.stop()
            sweep(w)
            assert status_of(w) == "sent"
            back = Partner(port=port).start()
            try:
                back.jobs[ref] = "JOB-1"  # the partner kept the booking
                sweep(w)
                assert status_of(w) == "pending" and len(back.effects) == 0  # it answered; no second booking
            finally:
                back.stop()
    finally:
        p.stop()


# ---- stop tracking stops the resends of a pass -----------------------------------------------------------------------
def test_a_close_during_a_pass_stops_the_resends_of_the_rows_after_it(tmp_path, partner, monkeypatch):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_repair_keyed"]
        for slot in ("mon", "tue"):  # two leftovers of one workflow that were never sent
            crash_at(monkeypatch, ledger, "mark_sent")
            assert dies(w, t, slot=slot)
            monkeypatch.undo()
        assert len(ops(w)) == 2 and partner.calls == []
        partner.delay = 2.0  # the first resend takes a while

        async def go():
            from sqlalchemy import update

            from awp.workforce import tables as tb
            from awp.workforce.reconcile import reconcile

            async def closer():
                await until(lambda: partner.of("book_repair"))  # the workflow is closed while the first resend is out
                async with w.rt.db.engine.begin() as conn:
                    await conn.execute(update(tb.workflows).values(state="closed", closed_at=1.0))
            await asyncio.gather(reconcile(w.engine, grace=0.0), closer())
        w.run(go)
        assert len(partner.of("book_repair")) == 1  # the one that was out; none after the close


# ---- 'do not retry' holds for a reworded request ---------------------------------------------------------------------
def test_after_an_unknown_outcome_a_reworded_request_of_the_same_tool_is_not_sent(tmp_path, partner):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_nostatus"]
        assert words(call(w, t, thing="plumber monday")).startswith("UNKNOWN:")
        again = words(call(w, t, thing="Plumber on Monday"))
        assert again.startswith("Not sent") and "nobody knows" in again
        assert len(partner.of("no_status_action")) == 1 and len(ops(w)) == 1
        other = tools_of(w)["partner_hotel"]  # another tool is not held up by it
        assert "confirmed" in words(call(w, other, hotel="Sunrise", nights=1))


def test_a_deliberate_repeat_with_a_nonce_or_after_a_person_looked_is_sent(tmp_path, partner):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_nostatus"]
        call(w, t, thing="plumber monday")
        assert words(call(w, t, thing="Plumber on Monday", idempotency_nonce="on purpose")).startswith("UNKNOWN:")
        assert len(partner.of("no_status_action")) == 2
        for op_id, result in w.sql("select id, result from wf_operations"):  # an operator has reviewed them
            w.sql("update wf_operations set result=? where id=?", (json.dumps({**json.loads(result), "reviewed": True}), op_id))
        call(w, t, thing="a third wording")
        assert len(partner.of("no_status_action")) == 3
