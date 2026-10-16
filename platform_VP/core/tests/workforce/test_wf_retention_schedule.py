"""Retention on a schedule (contract 12, spec 9): what is purged and what never is, with the clock in the test's hand,
and the lease that lets one process in a fleet do it."""
import asyncio
import time
from types import SimpleNamespace

import pytest
from sqlalchemy import insert, select

import dbtest
from awp.config import Settings
from awp.db import Database
from awp.workforce import lease, retention, tables as t
from awp.workforce.events import emit
from awp.workforce.retention import DAY
from dbkit import Lab

NOW = 1_800_000_000.0  # the test's "today"


@pytest.fixture
def lab(tmp_path):
    lab = Lab(tmp_path / "ret.db")
    yield lab
    lab.close()


def ctx(lab, **settings):
    return SimpleNamespace(db=lab.db, settings=Settings(**settings))


def put(lab, table, **values):
    async def go():
        async with lab.db.engine.begin() as conn:
            await conn.execute(insert(table).values(**values))
    lab.run(go())


def closed(lab, days_ago, at=NOW):
    return lab.seed(state="closed", closed_at=at - days_ago * DAY)


def receipt(lab, rid, days_ago, status="applied", workflow_id=None, operation_id=None):
    put(lab, t.provider_inbox, receipt_id=rid, integration_id="int_1", external_event_id=f"ev-{rid}", payload_hash="h",
        event_type="x.assigned", payload={}, ingestion_status=status, workflow_id=workflow_id, operation_id=operation_id,
        received_at=NOW - days_ago * DAY)


def operation(lab, wid, oid, status):
    put(lab, t.operations, id=oid, workflow_id=wid, route_id="route_1", tool_name="book", args_hash=oid,
        client_reference=f"cr_{oid}", status=status, created_at=1.0, updated_at=1.0)


def ids(lab, table, key):
    return {r[key] for r in lab.rows(table)}


# ---- the inbox (contract 12: dedupe kept at least 180 days) --------------------------------------------------------------
def test_inbox_rows_are_purged_only_past_the_window_and_the_boundary_is_exact(lab):
    receipt(lab, "r_old", 181)
    receipt(lab, "r_edge_in", 180 - 1 / DAY)  # one second younger than 180 days: kept
    receipt(lab, "r_edge_out", 180 + 1 / DAY)  # one second older: gone
    receipt(lab, "r_new", 1)
    assert lab.run(retention.purge_inbox(lab.db, 180, at=NOW)) == 2
    assert ids(lab, t.provider_inbox, "receipt_id") == {"r_edge_in", "r_new"}


def test_inbox_rows_still_being_processed_are_never_purged_however_old(lab):
    for i, status in enumerate(("accepted", "processing", "quarantined")):
        receipt(lab, f"r_{status}", 400, status=status)
    for status in ("applied", "duplicate", "rejected", "needs_attention"):
        receipt(lab, f"r_{status}", 400, status=status)
    assert lab.run(retention.purge_inbox(lab.db, 180, at=NOW)) == 4
    assert ids(lab, t.provider_inbox, "receipt_id") == {"r_accepted", "r_processing", "r_quarantined"}


def test_inbox_rows_of_open_workflows_and_of_unfinished_operations_are_kept(lab):
    open_wf = lab.seed(state="waiting_external_event")["wf"]["id"]
    done = closed(lab, 400)["wf"]["id"]
    held = closed(lab, 400)["wf"]["id"]
    for oid, wid, status in (("op_done", done, "completed"), ("op_unknown", held, "unknown"), ("op_open", open_wf, "pending")):
        operation(lab, wid, oid, status)
    receipt(lab, "r_open_wf", 400, workflow_id=open_wf, operation_id="op_open")
    receipt(lab, "r_unknown", 400, workflow_id=held, operation_id="op_unknown")
    receipt(lab, "r_done", 400, workflow_id=done, operation_id="op_done")
    receipt(lab, "r_nowhere", 400)  # matched nothing: no workflow to protect
    assert lab.run(retention.purge_inbox(lab.db, 180, at=NOW)) == 2
    assert ids(lab, t.provider_inbox, "receipt_id") == {"r_open_wf", "r_unknown"}


def test_the_inbox_purge_is_idempotent(lab):
    receipt(lab, "r_old", 300)
    assert lab.run(retention.purge_inbox(lab.db, 180, at=NOW)) == 1
    assert lab.run(retention.purge_inbox(lab.db, 180, at=NOW)) == 0
    assert lab.run(retention.purge_inbox(lab.db, 180, at=NOW + 1000 * DAY)) == 0


# ---- what a closed workflow leaves behind --------------------------------------------------------------------------------
def leave(lab, wid, jobs=(), turns=()):
    for i, status in enumerate(jobs):
        put(lab, t.jobs, id=f"job_{wid[-6:]}_{i}_{status}", workflow_id=wid, kind="resident_message", payload={}, status=status,
            attempts=1, created_at=1.0)
    for i, status in enumerate(turns):
        put(lab, t.turns, id=f"turn_{wid[-6:]}_{i}_{status}", workflow_id=wid, status=status, started_at=1.0)


def test_leftovers_of_a_workflow_closed_past_the_window_go_and_the_rest_stays(lab):
    old, recent, openwf = closed(lab, 100)["wf"]["id"], closed(lab, 10)["wf"]["id"], lab.seed(state="active")["wf"]["id"]
    for wid in (old, recent, openwf):
        leave(lab, wid, jobs=("done", "failed", "queued", "dispatched"), turns=("completed", "error", "running"))
    out = lab.run(retention.purge_leftovers(lab.db, 90, at=NOW))
    assert out == {"jobs": 2, "turns": 2}  # the done/failed jobs and the ended turns of the old workflow only
    left_jobs = {(r["workflow_id"], r["status"]) for r in lab.rows(t.jobs)}
    assert (old, "done") not in left_jobs and (old, "failed") not in left_jobs
    assert {(old, "queued"), (old, "dispatched"), (recent, "done"), (openwf, "done")} <= left_jobs
    assert {(r["workflow_id"], r["status"]) for r in lab.rows(t.turns)} >= {(old, "running"), (recent, "completed")}
    assert lab.run(retention.purge_leftovers(lab.db, 90, at=NOW)) == {"jobs": 0, "turns": 0}


def test_leftovers_of_a_closed_workflow_with_an_unfinished_operation_stay(lab):
    wid = closed(lab, 400)["wf"]["id"]
    operation(lab, wid, "op_pending", "pending")
    leave(lab, wid, jobs=("done",), turns=("completed",))
    assert lab.run(retention.purge_leftovers(lab.db, 90, at=NOW)) == {"jobs": 0, "turns": 0}


# ---- the whole job, as the schedule runs it -------------------------------------------------------------------------------
def test_run_applies_the_periods_of_the_settings_and_zero_switches_a_purge_off(lab):
    wid = closed(lab, 100)
    cid = wid["conv"]["id"]

    async def events():
        for i in range(4):
            async with lab.db.engine.begin() as conn:
                await emit(conn, cid, "workflow.status_changed", {"i": i}, occurred_at=NOW - 100 * DAY)
        async with lab.db.engine.begin() as conn:  # recorded_at is the platform's clock: age the rows
            await conn.execute(t.events.update().values(recorded_at=NOW - 100 * DAY))
    lab.run(events())
    receipt(lab, "r_old", 200)
    leave(lab, wid["wf"]["id"], jobs=("done",))
    off = lab.run(retention.run(ctx(lab, event_retention_days=0, inbox_retention_days=0, closed_retention_days=0), at=NOW))
    assert off == {"events": 0, "inbox": 0, "jobs": 0, "turns": 0}  # a period of 0 keeps everything
    on = lab.run(retention.run(ctx(lab, event_retention_days=90, inbox_retention_days=180, closed_retention_days=90), at=NOW))
    assert on == {"events": 3, "inbox": 1, "jobs": 1, "turns": 0}  # the newest event always stays
    assert lab.run(retention.run(ctx(lab, event_retention_days=90, inbox_retention_days=180, closed_retention_days=90),
                                 at=NOW)) == {"events": 0, "inbox": 0, "jobs": 0, "turns": 0}  # and again: nothing


def test_nothing_of_an_open_workflow_is_purged_whatever_the_age(lab):
    seeded = lab.seed(state="waiting_external_event")
    cid, wid = seeded["conv"]["id"], seeded["wf"]["id"]

    async def events():
        async with lab.db.engine.begin() as conn:
            for i in range(3):
                await emit(conn, cid, "workflow.status_changed", {"i": i})
    lab.run(events())
    leave(lab, wid, jobs=("done",), turns=("completed",))
    receipt(lab, "r_open", 5000, workflow_id=wid)
    operation(lab, wid, "op_p", "pending")
    out = lab.run(retention.run(ctx(lab), at=NOW + 5000 * DAY))
    assert out == {"events": 0, "inbox": 0, "jobs": 0, "turns": 0}
    assert len(lab.rows(t.events, conversation_id=cid)) == 3 and len(lab.rows(t.jobs)) == 1


# ---- the lease: one runner in a fleet, once per period -------------------------------------------------------------------
def other_process(lab) -> Database:
    """A second engine on the same database: another process of the fleet, as far as the database can tell."""
    return Database(lab.where.url)


def test_two_runners_at_once_do_the_work_once(lab):
    peer = other_process(lab)
    runs = []

    async def work():
        runs.append(1)
        await asyncio.sleep(0.2)  # long enough for the other runner to arrive while this one still holds the lease
        return "done"

    async def go():
        try:
            return await asyncio.gather(
                lease.run_once(lab.db, "retention", "node-a", work, period=3600, ttl=60),
                lease.run_once(peer, "retention", "node-b", work, period=3600, ttl=60))
        finally:
            await peer.dispose()

    got = lab.run(go())
    assert sorted(g[0] for g in got) == [False, True] and len(runs) == 1
    assert [g[1] for g in got if g[0]] == ["done"]


def test_many_runners_at_once_still_do_the_work_once(lab):
    peers = [other_process(lab) for _ in range(5)]
    runs = []

    async def work():
        runs.append(1)
        await asyncio.sleep(0.1)

    async def go():
        try:
            return await asyncio.gather(*[lease.run_once(d, "retention", f"n{i}", work, period=3600, ttl=60)
                                          for i, d in enumerate([lab.db, *peers])])
        finally:
            await asyncio.gather(*[p.dispose() for p in peers])

    got = lab.run(go())
    assert sum(g[0] for g in got) == 1 and len(runs) == 1


def test_the_work_comes_round_again_only_after_the_period_and_a_crash_does_not_count_as_a_run(lab):
    runs = []

    async def work():
        runs.append(1)

    async def fails():
        raise RuntimeError("the purge broke")

    async def go():
        db = lab.db
        assert (await lease.run_once(db, "j", "a", work, period=100, ttl=10, at=1000.0))[0]
        assert not (await lease.run_once(db, "j", "b", work, period=100, ttl=10, at=1099.0))[0]  # not a period yet
        assert (await lease.run_once(db, "j", "b", fails, period=100, ttl=10, at=1100.0))[0]  # it runs, and breaks
        assert (await lease.run_once(db, "j", "a", work, period=100, ttl=10, at=1101.0))[0]  # so it is tried again at once
        assert not (await lease.run_once(db, "j", "b", work, period=100, ttl=10, at=1150.0))[0]
        assert (await lease.run_once(db, "j", "b", work, period=100, ttl=10, at=1201.0))[0]
    lab.run(go())
    assert len(runs) == 3


def test_a_lease_whose_holder_died_is_taken_over_after_its_ttl(lab):
    async def go():
        assert await lease.claim(lab.db, "j", "dead", period=100, ttl=30, at=1000.0)  # claimed, never finished
        assert not await lease.claim(lab.db, "j", "other", period=100, ttl=30, at=1029.0)  # still its lease
        assert await lease.claim(lab.db, "j", "other", period=100, ttl=30, at=1031.0)  # run out: taken over
        await lease.finish(lab.db, "j", "dead", ok=True, at=1032.0)  # a late word from the dead one changes nothing
        row = (await _row(lab, "j"))
        assert row["owner"] == "other" and row["last_run_at"] is None
    lab.run(go())


async def _row(lab, name):
    async with lab.db.engine.connect() as conn:
        return (await conn.execute(select(t.leases).where(t.leases.c.name == name))).mappings().one()


def test_the_tick_runs_the_purge_under_the_lease_once_per_period(lab):
    seeded = closed(lab, 100)
    receipt(lab, "r_old", 300)
    c = ctx(lab, retention_every_seconds=3600)

    async def go():
        first = await retention.tick(c, "a", at=NOW)
        again = await retention.tick(c, "b", at=NOW + 10)  # a second process, a moment later
        later = await retention.tick(c, "b", at=NOW + 3601)
        return first, again, later

    first, again, later = lab.run(go())
    assert first["inbox"] == 1 and again is None and later == {"events": 0, "inbox": 0, "jobs": 0, "turns": 0}
    assert seeded and not lab.rows(t.provider_inbox)


# ---- the schedule inside the app ------------------------------------------------------------------------------------------
def test_the_app_purges_on_its_own_and_an_old_cursor_is_then_410(tmp_path):
    from conftest import _flow, _wire_engine, build
    from flowkit import P

    with build(tmp_path, wire=_wire_engine, wf_wait_seconds=20.0, wf_rate_per_minute=0, retention_every_seconds=0) as env:
        flow = _flow(env)
        start, started = flow.begin()
        cid, wid = started["conversation_id"], started["workflow_id"]
        flow.close(started, start)
        events = flow.history(cid, limit=500).json()["items"]
        assert len(events) > 2 and flow.history(cid, after_cursor=events[0]["event_id"]).status_code == 200
        long_ago = time.time() - 120 * DAY
        env.sql("update wf_workflows set closed_at=? where id=?", (long_ago, wid))
        env.sql("update wf_events set recorded_at=?, occurred_at=?", (long_ago, long_ago))
        headers, first = flow.h, events[0]["event_id"]
        assert env.sql("select count(*) from wf_leases") == [(0,)]  # the schedule was off: nothing ran

    with build(tmp_path, wire=_wire_engine, retention_every_seconds=3600, sweep_every=0.2) as env2:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and env2.sql("select count(*) from wf_events where conversation_id=?", (cid,)) != [(1,)]:
            time.sleep(0.1)
        assert env2.sql("select count(*) from wf_events where conversation_id=?", (cid,)) == [(1,)]  # the newest stays
        [(owner, last_run)] = env2.sql("select owner, last_run_at from wf_leases where name='retention'")
        assert owner is None and last_run is not None  # it ran, and gave the lease back
        gone = env2.http.get(f"{P}/conversations/{cid}/event-history", params={"external_user_id": "resident-123",
                                                                               "after_cursor": first}, headers=headers)
        assert gone.status_code == 410 and gone.json()["error"]["code"] == "EVENT_CURSOR_EXPIRED"
        assert env2.http.get(f"{P}/conversations/{cid}", params={"external_user_id": "resident-123"},
                             headers=headers).status_code == 200  # the snapshot is what a client reloads
