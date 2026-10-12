"""The engine's housekeeping: expiry rules (spec A9), lost notifications, a dead dispatcher, the old
sweeps leaving workflow cases alone, shutdown, settle run twice (slice S3)."""
from __future__ import annotations

import time

import scripts
from enginekit import world
from fake_llm import MODE

from awp.workforce.expiry import expire
from awp.workforce.settling import settle


def texts(body: dict) -> list[str]:
    return [m["text"] for m in body["result"]["messages"]]


def set_age(w, wid: str, seconds: float, state: str | None = None) -> None:
    """Make the workflow look as if it last did anything `seconds` ago (and put it in `state`)."""
    then = time.time() - seconds
    w.sql("update wf_workflows set last_activity_at=?, created_at=? where id=?", (then, then, wid))
    w.sql("update wf_turns set started_at=?, ended_at=? where workflow_id=?", (then, then, wid))
    w.sql("update awp_case_items set created_at=? where case_id=(select case_id from wf_workflows where id=?)",
          (then, wid))
    if state:
        w.sql("update wf_workflows set state=?, attention_reason=null where id=?", (state, wid))


def sweep_expiry(w) -> int:
    return w.run(lambda: expire(w.engine))


def stateof(w, wid: str) -> tuple:
    return w.sql("select state, attention_reason from wf_workflows where id=?", (wid,))[0]


def test_expiry_rules_of_a9(tmp_path):
    with world(tmp_path, scripts.interactive, case_stall_seconds=60, request_timeout_hours=1.0, sweep_every=3600) as w:
        _, r = w.flow.begin()
        wid = r["workflow_id"]

        # waiting for a person never changes by time
        for state in ("awaiting_user", "awaiting_approval", "awaiting_confirmation"):
            set_age(w, wid, 10 * 86400, state)
            assert sweep_expiry(w) == 0 and stateof(w, wid)[0] == state

        # working, but something is queued, or a turn runs: not stalled
        set_age(w, wid, 600, "active")
        w.sql("insert into wf_jobs (id, workflow_id, kind, payload, status, attempts, created_at) "
              "values ('job_x', ?, 'nudge', '{}', 'queued', 0, ?)", (wid, time.time()))
        assert sweep_expiry(w) == 0 and stateof(w, wid)[0] == "active"
        w.sql("delete from wf_jobs where id='job_x'")
        w.sql("insert into wf_turns (id, workflow_id, trigger, status, started_at) values ('turn_x', ?, 'continue', 'running', ?)",
              (wid, time.time()))
        assert sweep_expiry(w) == 0 and stateof(w, wid)[0] == "active"
        w.sql("delete from wf_turns where id='turn_x'")

        # recent activity: not stalled
        w.sql("update wf_workflows set last_activity_at=? where id=?", (time.time(), wid))
        assert sweep_expiry(w) == 0

        # nothing ran, nothing queued, for longer than case_stall_seconds: needs attention, the waiting request fails
        set_age(w, wid, 600, "active")
        w.sql("update wf_requests set status='running', response=null, completed_at=null where workflow_id=?", (wid,))
        assert sweep_expiry(w) == 1
        assert stateof(w, wid) == ("needs_attention", "stalled")
        req = w.sql("select status, error from wf_requests where workflow_id=?", (wid,))[0]
        assert req[0] == "failed" and "stalled" in str(req[1])

        # waiting for the outside: twenty minutes (longer than the stall limit) is nothing ...
        set_age(w, wid, 1200, "waiting_external_event")
        assert sweep_expiry(w) == 0 and stateof(w, wid)[0] == "waiting_external_event"
        # ... only request_timeout_hours (one here) is
        set_age(w, wid, 2 * 3600, "waiting_external_event")
        assert sweep_expiry(w) == 1 and stateof(w, wid) == ("needs_attention", "external_timeout")


def test_the_lifespan_sweep_expires_a_stalled_workflow(tmp_path):
    with world(tmp_path, scripts.interactive, case_stall_seconds=60) as w:
        _, r = w.flow.begin()
        set_age(w, r["workflow_id"], 600, "active")
        w.wait(lambda: stateof(w, r["workflow_id"])[0] == "needs_attention", timeout=8, what="the sweep to expire it")
        assert stateof(w, r["workflow_id"])[1] == "stalled"


def test_a_job_whose_notification_was_lost_is_picked_up_by_the_sweep(tmp_path):
    with world(tmp_path, scripts.interactive, wf_wait_seconds=0.3, sweep_every=3600) as w:
        w.engine.notify = lambda *a: None  # the notification never arrives
        r, _ = w.flow.start()
        queued = r.json()
        assert r.status_code == 202 and queued["request_status"] == "queued"
        assert w.sql("select count(*) from wf_turns") == [(0,)]
        w.run(w.engine.sweep)
        done = w.wait(lambda: (g := w.flow.request(queued["request_id"]).json())["request_status"] == "completed" and g)
        assert texts(done) == ["What time suits you?"]


def test_a_job_left_dispatched_by_a_dead_dispatcher_is_given_back_then_failed(tmp_path):
    with world(tmp_path, scripts.interactive, wf_wait_seconds=0.3, wf_job_attempts=2, sweep_every=3600) as w:
        w.engine.notify = lambda *a: None
        r, _ = w.flow.start()
        first = r.json()
        w.sql("update wf_jobs set status='dispatched', attempts=1, lease_until=1")  # its owner died
        w.run(w.engine.sweep)  # gives the job back (attempt 1 of 2) ...
        assert w.sql("select status from wf_jobs") == [("queued",)]
        w.run(w.engine.sweep)  # ... and picks it up
        done = w.wait(lambda: (g := w.flow.request(first["request_id"]).json())["request_status"] == "completed" and g)
        assert texts(done) == ["What time suits you?"]

        r2, start2 = w.flow.start()
        second = r2.json()
        w.sql("update wf_jobs set status='dispatched', attempts=2, lease_until=1 where request_id=?", (second["request_id"],))
        w.run(w.engine.sweep)  # no attempts left: the workflow needs attention, the request fails
        g = w.flow.request(second["request_id"]).json()
        assert (g["request_status"], g["workflow_state"], g["error"]["code"]) == ("failed", "needs_attention", "engine_error")


def test_the_sweep_leaves_the_case_of_a_resting_workflow_open(tmp_path):
    with world(tmp_path, scripts.interactive, case_stall_seconds=1, sweep_every=3600) as w:
        _, r = w.flow.begin()
        wid = r["workflow_id"]
        case_id = w.sql("select case_id from wf_workflows where id=?", (wid,))[0][0]
        set_age(w, wid, 3600, "awaiting_user")  # waiting for the resident for an hour, far past case_stall_seconds
        w.run(w.engine.sweep)
        assert w.sql("select status from awp_cases where id=?", (case_id,)) == [("open",)]
        assert stateof(w, wid)[0] == "awaiting_user"


def test_stopping_the_engine_with_a_turn_running_is_clean(tmp_path):
    scope = world(tmp_path, scripts.interactive, wf_wait_seconds=0.2)
    w = scope.__enter__()
    MODE["leader_delay"] = 8.0
    r, _ = w.flow.start()
    assert r.status_code == 202
    w.wait(lambda: w.sql("select 1 from wf_turns where status='running'"), what="the turn to start")
    started = time.monotonic()
    scope.__exit__(None, None, None)  # the lifespan ends while the leader waits for its model
    assert time.monotonic() - started < 25


def test_settle_run_twice_changes_nothing_the_second_time(tmp_path):
    with world(tmp_path, scripts.interactive) as w:
        _, r = w.flow.begin()
        wid = r["workflow_id"]
        w.sql("update wf_workflows set state='active', expects=null where id=?", (wid,))  # the chain is unsettled
        assert w.run(lambda: settle(w.engine, wid)) is None
        after = w.sql("select state, revision from wf_workflows where id=?", (wid,))[0]
        events = w.sql("select count(*) from wf_events")[0]
        assert after[0] == "awaiting_user"
        assert w.run(lambda: settle(w.engine, wid)) is None
        assert w.sql("select state, revision from wf_workflows where id=?", (wid,))[0] == after
        assert w.sql("select count(*) from wf_events")[0] == events
