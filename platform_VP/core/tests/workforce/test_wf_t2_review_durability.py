"""Regression tests for the T2 review: events that arrive together or out of step, a fault in the middle of applying one, a
process that dies after the 202. The effects of an event happen exactly once. (From the concurrency reviewer's probes.)"""
from __future__ import annotations

import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

import pytest
from enginekit import world
from partnerkit import Partner
from t1kit import SETTINGS, ops
from t2kit import DELTA, pending_world, sent_ok, wait_status
from test_wf_t2_apply import DATA, leader_only_notes

from awp.casefile.store import CaseStore
from awp.workforce import provider_apply, provider_effects, provider_sweep


@pytest.fixture
def partner():
    with Partner() as p:
        yield p


def test_identical_posts_made_at_once_are_one_event_and_events_with_the_same_content_apply_once(tmp_path, partner):
    with pending_world(tmp_path, partner, leader_only_notes) as (w, prov, p):
        w.quiet()
        body = prov.event("x.cost_reported", ref=p.ref, version=1, data={"items": [], "total": 1})
        with ThreadPoolExecutor(12) as ex:
            rs = list(ex.map(lambda _: prov.post(body), range(12)))
        assert {r.status_code for r in rs} == {202}
        assert len({r.json()["receipt_id"] for r in rs}) == 1 and sum(1 for r in rs if not r.json()["duplicate"]) == 1
        bodies = [prov.event("x.cost_reported", ref=p.ref, version=2, data={"items": [], "total": 2}) for _ in range(8)]
        with ThreadPoolExecutor(8) as ex:  # the same news under eight ids
            rs = list(ex.map(prov.post, bodies))
        assert {r.status_code for r in rs} == {202}
        time.sleep(2)
        w.quiet(60)
        states = sorted(prov.status_of(r.json()["receipt_id"]) for r in rs)
        assert states.count("applied") == 1 and states.count("duplicate") == 7, states
        assert w.sql("select count(*) from awp_case_items where author='provider'") == [(2,)]  # one piece of evidence each
        assert 1 <= p.jobs() <= 2  # one wake for each version at most, and fewer when the leader was still busy


def test_delta_events_sent_at_once_in_any_order_are_all_applied_and_in_order(tmp_path, partner):
    with pending_world(tmp_path, partner, leader_only_notes, schema=DELTA) as (w, prov, p):
        w.quiet()
        p.applied("x.assigned", version=1, data=DATA)
        bodies = [prov.event("x.progress", ref=p.ref, version=v, data={"note": f"n{v}"}) for v in (6, 5, 4, 3, 2)]
        with ThreadPoolExecutor(5) as ex:
            rs = list(ex.map(prov.post, bodies))
        assert {r.status_code for r in rs} == {202}
        for r in rs:
            wait_status(w, prov, r.json()["receipt_id"], "applied", 30)
        assert p.op_row()[3] == "6"
        order = w.sql("select provider_version from wf_provider_inbox where ingestion_status='applied' order by applied_at")
        assert [int(v) for (v,) in order] == [1, 2, 3, 4, 5, 6]


def test_delta_events_shuffled_in_parallel_end_in_order_and_the_last_one_finishes_the_work(tmp_path, partner):
    with pending_world(tmp_path, partner, schema=DELTA) as (w, prov, p):
        w.quiet()
        p.applied("x.assigned", version=1, data={"worker_name": "An", "eta_minutes": 9})
        evs = [prov.event("x.progress" if v != 5 else "x.finished_quietly", ref=p.ref, version=v, data={"note": f"n{v}"})
               for v in range(2, 6)]
        random.Random(7).shuffle(evs)
        with ThreadPoolExecutor(4) as ex:
            rs = list(ex.map(prov.post, evs))
        for r in rs:
            wait_status(w, prov, r.json()["receipt_id"], "applied", 30)
        assert p.op_row()[3] == "5" and p.op_row()[0] == "completed"


@pytest.mark.parametrize("where", ["emit", "cases", "mark"])
def test_a_fault_between_the_steps_of_applying_an_event_leaves_nothing_and_it_is_applied_once_later(tmp_path, partner, where):
    state = {"down": True, "n": 0}
    real_emit, real_add, real_mark = provider_effects.emit, CaseStore.add, provider_apply._mark

    async def emit(*a, **k):
        state["n"] += 1
        if state["down"] and where == "emit" and state["n"] % 2 == 0:
            raise RuntimeError("boom")
        return await real_emit(*a, **k)

    async def add(self, *a, **k):
        if state["down"] and where == "cases" and k.get("conn") is not None:
            raise RuntimeError("boom")
        return await real_add(self, *a, **k)

    async def mark(*a, **k):
        if state["down"] and where == "mark" and k.get("applied"):
            raise RuntimeError("boom")
        return await real_mark(*a, **k)

    with pending_world(tmp_path, partner, leader_only_notes) as (w, prov, p):
        w.quiet()
        snap = lambda: (w.state(p.wid), w.sql("select count(*) from wf_jobs"), w.sql("select count(*) from awp_case_items"),
                        w.sql("select count(*) from wf_events"), p.op_row())
        before = snap()
        with mock.patch.object(provider_effects, "emit", emit), mock.patch.object(CaseStore, "add", add), \
                mock.patch.object(provider_apply, "_mark", mark):
            rid = p.send("x.completed", version=1, data={"summary": "ok"})[0]
            time.sleep(1.5)
            w.run(w.engine.sweep)
            assert prov.status_of(rid) == "accepted" and snap() == before
            state["down"] = False
            w.run(w.engine.sweep)
            wait_status(w, prov, rid)
        w.quiet()
        assert p.jobs() == 1 and w.sql("select count(*) from awp_case_items where author='provider'") == [(1,)]
        assert len([e for e in p.events("operation.status_changed") if "operation_state" in e["payload"]]) == 1


def test_a_wake_up_the_engine_was_never_told_about_is_found_by_the_sweep(tmp_path, partner):
    with pending_world(tmp_path, partner, leader_only_notes, sweep_every=1.0) as (w, prov, p):  # the background sweep is the point
        w.quiet()
        eng = w.engine
        with mock.patch.object(type(eng), "notify", lambda self, *a: (_ for _ in ()).throw(RuntimeError("process died"))):
            wait_status(w, prov, p.send("x.progress", version=1, data={"note": "halfway"})[0])
        w.wait(lambda: w.sql("select 1 from wf_jobs where kind='provider_wake' and status='done'"), 30, "the wake to be done")
        assert p.jobs() == 1


def test_a_process_that_dies_after_the_202_applies_the_stored_event_once_when_the_next_one_starts(tmp_path, partner):
    with pending_world(tmp_path, partner, leader_only_notes) as (w, prov, p):
        w.quiet()
        with mock.patch.object(provider_sweep, "schedule", lambda *a: None):
            rid = p.send("x.completed", version=1, data={"summary": "ok"})[0]
        assert prov.status_of(rid) == "accepted"
    with world(tmp_path, leader_only_notes, publish=False, **SETTINGS) as w2:
        prov.env = w2.env
        w2.run(w2.engine.sweep)
        w2.run(w2.engine.sweep)
        wait_status(w2, prov, rid)
        w2.wait(lambda: w2.sql("select 1 from wf_jobs where kind='provider_wake' and status='done'"), 40, "the wake")
        assert w2.sql("select count(*) from wf_jobs where kind='provider_wake'") == [(1,)]
        assert w2.sql("select count(*) from wf_events where event_type='operation.status_changed'")[0][0] == 2


def test_a_quiet_event_that_comes_before_the_tools_own_answer_leaves_the_work_ready_to_confirm(tmp_path, partner):
    partner.delay = 3
    with pending_world(tmp_path, partner, begin=False) as (w, prov, _):
        out: list = []
        th = threading.Thread(target=lambda: out.append(w.flow.start()))
        th.start()
        row = w.wait(lambda: ops(w), 10, "the operation row")[0]
        wait_status(w, prov, sent_ok(prov, "x.finished_quietly", ref=row["reference"], version=1)[0])
        th.join(30)
        wid = w.sql("select id from wf_workflows")[0][0]
        w.wait_state(wid, "awaiting_confirmation")
        w.quiet()
        assert w.state(wid)[0] == "awaiting_confirmation"
