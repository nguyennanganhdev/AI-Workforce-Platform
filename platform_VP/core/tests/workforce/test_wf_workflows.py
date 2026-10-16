"""Workflow states, next_action and the one transition function (spec 5, contract 9.3, A1)."""
import asyncio

import pytest
from sqlalchemy import select

from awp.workforce import tables as t
from awp.workforce.common import iso
from awp.workforce.workflows import (BUSY, IllegalTransition, NEXT_ACTION, STATES, StateConflict,
                                     next_action, transition)
from dbkit import Lab


@pytest.fixture
def lab(tmp_path):
    lab = Lab(tmp_path / "lab.db")
    yield lab
    lab.close()


def move(lab, wf, new, **kw):
    """Read the workflow as the caller would, transition it, return (updated, committed row)."""
    async def go():
        async with lab.db.engine.begin() as conn:
            row = (await conn.execute(select(t.workflows).where(t.workflows.c.id == wf["id"]))).mappings().one()
            return await transition(conn, row, new, **kw)
    return lab.run(go())


def events(lab, cid):
    return sorted(lab.rows(t.events, conversation_id=cid), key=lambda r: r["sequence"])


def test_every_state_has_the_next_action_of_contract_9_3():
    assert set(STATES) == set(NEXT_ACTION)
    assert {s: next_action(s) for s in STATES} == {
        "closed": "none", "awaiting_user": "submit_reply", "awaiting_approval": "submit_approval",
        "awaiting_confirmation": "confirm_close", "waiting_external_event": "watch_events",
        "needs_attention": "resolve_attention", "blocked_authorization": "resolve_attention",
        "blocked_route_changed": "resolve_attention", "accepted": "watch_request", "active": "watch_request"}
    assert set(BUSY) == {"accepted", "active"}


def test_a_transition_changes_state_and_revision_and_emits_one_event(lab):
    s = lab.seed(state="accepted")
    out = move(lab, s["wf"], "active")
    row = lab.one(t.workflows, id=s["wf"]["id"])
    assert (row["state"], row["revision"]) == ("active", 2) and out["revision"] == 2
    [ev] = events(lab, s["conv"]["id"])
    assert (ev["event_type"], ev["payload"]) == ("workflow.status_changed", {"state": "active", "revision": 2})
    assert ev["workflow_id"] == s["wf"]["id"]


@pytest.mark.parametrize("state,etype,extra,expects", [
    ("awaiting_user", "workflow.awaiting_user", {"reason": "reply_expected"}, "reply"),
    ("awaiting_confirmation", "workflow.status_changed", {}, "confirmation"),
    ("waiting_external_event", "workflow.status_changed", {}, None),
    ("awaiting_approval", "workflow.status_changed", {}, None),
    ("blocked_authorization", "workflow.status_changed", {}, None),
])
def test_each_state_announces_itself_with_the_event_of_contract_9_7(lab, state, etype, extra, expects):
    s = lab.seed(state="active")
    move(lab, s["wf"], state)
    [ev] = events(lab, s["conv"]["id"])
    assert ev["event_type"] == etype and ev["payload"] == {"state": state, "revision": 2, **extra}
    assert lab.one(t.workflows, id=s["wf"]["id"])["expects"] == expects


def test_needs_attention_needs_a_public_reason_and_clears_it_on_leaving(lab):
    s = lab.seed(state="active")
    with pytest.raises(ValueError):
        move(lab, s["wf"], "needs_attention")
    move(lab, s["wf"], "needs_attention", reason="leader_silent")
    row = lab.one(t.workflows, id=s["wf"]["id"])
    assert row["attention_reason"] == "leader_silent"
    [ev] = events(lab, s["conv"]["id"])
    assert ev["event_type"] == "workflow.needs_attention" and ev["payload"]["reason"] == "leader_silent"
    move(lab, row, "active", reason="resident_reply")
    assert lab.one(t.workflows, id=s["wf"]["id"])["attention_reason"] is None


def test_closing_records_reason_and_time_in_row_and_event(lab):
    s = lab.seed(state="awaiting_confirmation", revision=4)
    out = move(lab, s["wf"], "closed", reason="resident_confirmed_resolved")
    row = lab.one(t.workflows, id=s["wf"]["id"])
    assert row["state"] == "closed" and row["revision"] == 5 and row["close_reason"] == "resident_confirmed_resolved"
    assert row["closed_at"] == out["closed_at"] and row["closed_at"] is not None
    ev = events(lab, s["conv"]["id"])[-1]
    assert ev["event_type"] == "workflow.closed"
    assert ev["payload"]["state"] == "closed" and ev["payload"]["revision"] == 5
    assert ev["payload"]["reason"] == "resident_confirmed_resolved" and ev["payload"]["closed_at"] == iso(row["closed_at"])


@pytest.mark.parametrize("target", [s for s in STATES])
def test_nothing_leaves_closed(lab, target):
    s = lab.seed(state="closed", closed_at=1.0, revision=7)
    with pytest.raises(IllegalTransition):
        move(lab, s["wf"], target, reason="x")
    row = lab.one(t.workflows, id=s["wf"]["id"])
    assert (row["state"], row["revision"]) == ("closed", 7) and events(lab, s["conv"]["id"]) == []


def test_accepted_is_only_the_first_state_and_unknown_states_are_refused(lab):
    s = lab.seed(state="active")
    for bad in ("accepted", "done", ""):
        with pytest.raises(IllegalTransition):
            move(lab, s["wf"], bad)
    assert lab.one(t.workflows, id=s["wf"]["id"])["revision"] == 1


def test_staying_in_the_same_state_records_activity_only(lab):
    s = lab.seed(state="active")
    out = move(lab, s["wf"], "active", request_id="req_9")
    row = lab.one(t.workflows, id=s["wf"]["id"])
    assert row["revision"] == 1 and row["current_request_id"] == "req_9" and out["revision"] == 1
    assert row["last_activity_at"] >= s["wf"]["last_activity_at"] and events(lab, s["conv"]["id"]) == []


def test_extra_events_ride_in_the_same_commit_after_the_state_event(lab):
    s = lab.seed(state="active")
    move(lab, s["wf"], "awaiting_user",
         emit_after=[("ticket.status_changed", {"status": "assigned"})])
    kinds = [e["event_type"] for e in events(lab, s["conv"]["id"])]
    assert kinds == ["workflow.awaiting_user", "ticket.status_changed"]


def test_a_stale_reader_loses_and_nothing_of_its_attempt_remains(lab):
    s = lab.seed(state="active")
    stale = s["wf"]  # read before the other writer got in

    async def go():
        async with lab.db.engine.begin() as conn:
            await transition(conn, stale, "awaiting_user")
        async with lab.db.engine.begin() as conn:
            await transition(conn, stale, "waiting_external_event")

    with pytest.raises(StateConflict):
        lab.run(go())
    assert lab.one(t.workflows, id=s["wf"]["id"])["state"] == "awaiting_user"
    assert len(events(lab, s["conv"]["id"])) == 1


def test_two_writers_from_the_same_read_exactly_one_wins(lab):
    s = lab.seed(state="active")

    async def one(target):
        try:
            async with lab.db.engine.begin() as conn:
                row = (await conn.execute(select(t.workflows).where(t.workflows.c.id == s["wf"]["id"]))).mappings().one()
                await asyncio.sleep(0.05)  # both have read before either writes
                await transition(conn, row, target)
            return target
        except StateConflict:
            return None

    async def go():
        return await asyncio.gather(*(one(x) for x in ("awaiting_user", "waiting_external_event", "closed")))

    out = lab.run(go())
    assert len([x for x in out if x]) == 1
    row = lab.one(t.workflows, id=s["wf"]["id"])
    assert row["revision"] == 2 and row["state"] == next(x for x in out if x)
    assert len(events(lab, s["conv"]["id"])) == 1


def test_a_rolled_back_transaction_leaves_state_and_log_alone(lab):
    s = lab.seed(state="active")

    async def go():
        async with lab.db.engine.begin() as conn:
            row = (await conn.execute(select(t.workflows).where(t.workflows.c.id == s["wf"]["id"]))).mappings().one()
            await transition(conn, row, "closed", reason="x")
            raise RuntimeError("later step failed")

    with pytest.raises(RuntimeError):
        lab.run(go())
    assert lab.one(t.workflows, id=s["wf"]["id"])["state"] == "active"
    assert events(lab, s["conv"]["id"]) == []
    assert lab.one(t.conversations, id=s["conv"]["id"])["last_sequence"] == 0
