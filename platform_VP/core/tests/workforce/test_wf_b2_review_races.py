"""What the review of B2 found about things done at the same moment and about a process that dies, each as a test:
two applies of one proposal, two tenants and one key, two starts of one evaluation, one tenant's runs and another's,
and what a dead process leaves behind (a run that says `running`, a sandbox workflow with a queued job).
Requests "at the same moment" are tasks of the app's own loop (evalkit.parallel). Run on PostgreSQL too
(AWP_TEST_PG_URL): the two evaluation-start races cannot show on SQLite, which has one writer."""
from __future__ import annotations

import time

import evalkit as ek
import pytest
from conftest import ADM, ADM_B, build, publish as override
from enginekit import world
from fake_llm import CALLS, MODE

from awp.evals import runner, sandbox

P, B = ek.P, ek.B
PARKING = {"key": "parking", "name": "Parking desk", "mission": "books visitor parking slots for residents.",
           "handles": ["visitor parking", "parking slots"], "refuses": ["fines"], "tools_allow": []}
PLAIN = {"key": "tech", "name": "Technician", "mission": "a technician.", "handles": ["tickets"]}
BARE = {**ek.TECH, "refuses": [], "tools_allow": []}  # two platform cases


def versions(env, key, tenant="ta"):
    return env.sql("select version, status from awp_profiles where tenant=? and key=? order by version", (tenant, key))


def proposes(action, profile):
    return lambda c: {"reply": "x", "proposals": [{"action": action, "profile": profile, "reason": "asked"}]}


def runs(env, key, headers=ADM, version=1):
    return env.http.get(f"{P}/{key}/versions/{version}/evals", headers=headers).json()["runs"]


# ---- the builder's apply ----------------------------------------------------------------------------------------------
def test_applies_of_one_proposal_at_once_make_one_draft_and_all_answer_with_it(tmp_path):
    with world(tmp_path, publish=False) as w:
        env = w.env
        MODE["builder"] = proposes("create", PARKING)
        sid = ek.session(env)
        assert ek.say(env, sid, "parking please").status_code == 200
        rs = ek.parallel(env, [("POST", f"{B}/{sid}/apply", {}, ADM)] * 4)
        assert [r.status_code for r in rs] == [200] * 4, [(r.status_code, r.text[:200]) for r in rs]
        assert {(x["created"], x["key"], x["version"]) for r in rs for x in r.json()["results"]} == {(True, "parking", 1)}
        assert versions(env, "parking") == [(1, "draft")]
        assert [e["kind"] for e in env.http.get(f"{P}/parking/history", headers=ADM).json()["events"]] == ["create"]
        # the same for a new version of an existing agent
        MODE["builder"] = proposes("revise", {**PARKING, "mission": "books parking, revised."})
        assert ek.say(env, sid, "change parking").status_code == 200
        rs = ek.parallel(env, [("POST", f"{B}/{sid}/apply", {}, ADM)] * 4)
        assert [r.status_code for r in rs] == [200] * 4 and versions(env, "parking") == [(1, "draft"), (2, "draft")]


def test_an_apply_and_a_message_at_once_leave_no_draft_that_the_session_does_not_know(tmp_path):
    with world(tmp_path, publish=False) as w:
        env = w.env
        MODE["builder"] = proposes("create", PARKING)
        sid = ek.session(env)
        assert ek.say(env, sid, "parking please").status_code == 200
        for i in range(4):
            MODE["builder"] = proposes("create", {**PARKING, "key": f"parking{i}"})
            said, applied = ek.parallel(env, [("POST", f"{B}/{sid}/messages", {"text": "and more"}, ADM),
                                              ("POST", f"{B}/{sid}/apply", {}, ADM)])
            assert said.status_code in (200, 409) and applied.status_code == 200, (said.text[:200], applied.text[:200])
            made = {(x["key"], x["version"]) for x in applied.json()["results"] if x["created"]}
            session = env.http.get(f"{B}/{sid}", headers=ADM).json()
            known = {(p["applied"]["key"], p["applied"]["version"]) for p in session["proposals"] if p["applied"]}
            if said.status_code == 409:  # the apply won: its drafts are on the session
                assert made <= known
        have = {(k, v) for k, v in env.sql("select key, version from awp_profiles where key like 'parking%'")}
        assert all(v == 1 for _, v in have) and len(have) == len({k for k, _ in have})  # never two versions from one proposal


# ---- one key, one tenant ------------------------------------------------------------------------------------------------
def test_two_tenants_that_take_a_new_key_at_once_do_not_both_get_it(tmp_path):
    with build(tmp_path) as env:
        for i in range(8):
            body = {**PLAIN, "key": f"shared{i}"}
            rs = ek.parallel(env, [("POST", P, body, ADM), ("POST", P, body, ADM_B)])
            assert sorted(r.status_code for r in rs) == [201, 409], [(r.status_code, r.text[:120]) for r in rs]
            [(owner,)] = env.sql("select distinct tenant from awp_profiles where key=?", (f"shared{i}",))
            assert env.sql("select tenant from awp_profile_keys where key=?", (f"shared{i}",)) == [(owner,)]


def test_a_rollback_cannot_make_a_key_live_for_two_tenants(tmp_path):
    with build(tmp_path) as env:
        rt = env.app.state.awp.rt
        live = lambda: env.sql("select tenant from awp_profiles where key='tech' and status='published' order by tenant")  # noqa: E731
        ek.draft(env, {**PLAIN, "mission": "tenant A's technician."})
        override(env, "tech", 1)
        assert env.post(f"{P}/tech/retire").status_code == 200
        ek.draft(env, {**PLAIN, "mission": "tenant B's technician."}, ADM_B)  # allowed: nothing of A's is a draft or live
        override(env, "tech", 1, ADM_B)
        r = env.post(f"{P}/tech/rollback", {"to_version": 1})
        assert r.status_code == 409 and "another tenant" in r.text and live() == [("tb",)]
        assert rt.template_tenant["tech"] == "tb" and "tenant B's" in rt.templates["tech"].system_prompt_template
        assert env.post(P, {**PLAIN, "mission": "A again."}).status_code == 409  # nor a new draft while B holds it
        # B lets go of it: now A's retired version may come back, and the key is A's again
        assert env.post(f"{P}/tech/retire", {}, ADM_B).status_code == 200
        assert env.post(f"{P}/tech/rollback", {"to_version": 1}).status_code == 200 and live() == [("ta",)]
        assert rt.template_tenant["tech"] == "ta" and env.sql("select tenant from awp_profile_keys where key='tech'") == [("ta",)]
        assert env.post(f"{P}/tech/rollback", {"to_version": 1}, ADM_B).status_code == 409 and live() == [("ta",)]


# ---- one run of a version, a slot per tenant --------------------------------------------------------------------------
def test_starts_of_one_evaluation_at_once_give_one_run(tmp_path):
    with world(tmp_path, publish=False) as w:
        env = w.env
        ek.agents(tech=ek.careful)
        MODE["delay"] = lambda system: 0.1
        ek.draft(env, BARE)
        rs = ek.parallel(env, [("POST", f"{P}/tech/versions/1/evals", {}, ADM)] * 4)
        assert sorted(r.status_code for r in rs) == [202, 409, 409, 409], [(r.status_code, r.text[:120]) for r in rs]
        assert len(env.sql("select id from awp_eval_runs where key='tech'")) == 1
        run = w.wait(lambda: (lambda x: x if x["status"] != "running" else None)(runs(env, "tech")[0]), 90, "the run to end")
        assert run["status"] == "passed", run  # nobody took the draft's template away under it
        w.quiet(30)
        # the database refuses a second running run of the version whoever asks (another process has no `_live` of ours)
        store = w.rt.evals.store

        async def twice():
            first = await store.open_run("ta", "tech", 1, "sha256:x", "t", time.time() + 60)
            try:
                await store.open_run("ta", "tech", 1, "sha256:x", "t", time.time() + 60)
            except Exception as e:  # noqa: BLE001
                return first["id"], getattr(e, "status", repr(e))
            return first["id"], None
        run_id, refused = w.run(twice)
        assert refused == 409
        other = w.run(lambda: store.open_run("ta", "tech", 2, "sha256:x", "t", time.time() + 60))  # another version is free
        env.sql("update awp_eval_runs set status='error' where id in (?, ?)", (run_id, other["id"]))


def test_one_tenants_evaluation_does_not_wait_for_anothers(tmp_path):
    with world(tmp_path, publish=False, eval_parallel=1) as w:
        env = w.env
        ek.agents(tech=ek.careful, helper=ek.careful)
        MODE["delay"] = lambda system: 1.5 if 'key="tech"' in system else 0  # tenant A's agent is slow
        ek.draft(env, BARE)
        ek.draft(env, {**BARE, "key": "helper", "name": "Helper"}, ADM_B)
        assert env.post(f"{P}/tech/versions/1/evals", {}).status_code == 202
        assert env.post(f"{P}/helper/versions/1/evals", {}, ADM_B).status_code == 202
        mine = w.wait(lambda: (lambda x: x if x["status"] != "running" else None)(runs(env, "helper", ADM_B)[0]), 60,
                      "tenant B's run to end")
        assert mine["status"] == "passed", mine
        assert runs(env, "tech")[0]["status"] == "running"  # A's is still going: B did not queue behind it
        # a tenant's own runs do take turns (eval_parallel = 1): a second profile of A waits for the first
        ek.draft(env, {**BARE, "key": "second", "name": "Second"})
        ek.agents(tech=ek.careful, helper=ek.careful, second=ek.careful)
        r = env.post(f"{P}/second/versions/1/evals", {})
        assert r.status_code == 202
        time.sleep(1.0)
        begun = env.sql("select count(*) from wf_requests where external_request_id like ?", (r.json()["run_id"] + ":%",))
        if runs(env, "tech")[0]["status"] == "running":  # (always, unless the machine stood still for many seconds)
            assert begun == [(0,)]
        for key in ("tech", "second"):
            w.wait(lambda: runs(env, key)[0]["status"] != "running", 120, f"the run of {key} to end")
        assert runs(env, "second")[0]["status"] == "passed"
        w.quiet(30)


# ---- a process that died ----------------------------------------------------------------------------------------------
def test_a_live_run_keeps_its_lease_and_a_dead_one_gives_the_version_back_after_it(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "LEASE", 2.0)
    with world(tmp_path, publish=False) as w:
        env = w.env
        ek.agents(tech=ek.careful)
        MODE["delay"] = lambda system: 0.35  # the run takes several leases
        ek.draft(env, BARE)
        began = time.time()
        assert env.post(f"{P}/tech/versions/1/evals", {}).status_code == 202
        seen = []
        while runs(env, "tech")[0]["status"] == "running" and time.time() - began < 90:
            [(deadline,)] = env.sql("select deadline from awp_eval_runs")
            seen.append(deadline)
            assert deadline <= time.time() + 2.5  # never further away than the lease
            time.sleep(0.2)
        run = runs(env, "tech")[0]
        assert run["status"] == "passed" and run["duration_s"] > 4.0, run  # it outlived its first lease more than once
        assert len(set(seen)) >= 3 and seen == sorted(seen)  # because the deadline kept moving
        w.quiet(30)
        # what a process that died leaves: a row that says running, with the lease it last took
        row = ("run_dead", "ta", "tech", 1, "sha256:x", "running", "[]", 0.0, "admin", time.time() + 600, time.time())
        env.sql("insert into awp_eval_runs (id, tenant, key, version, profile_hash, status, results, cost_usd, started_by, "
                "deadline, created_at) values (?,?,?,?,?,?,?,?,?,?,?)", row)
    with world(tmp_path, publish=False) as w:  # the platform restarted
        env = w.env
        ek.agents(tech=ek.careful)
        # its lease ends 3 s from now, whatever the restart took (on PostgreSQL a restart alone outlasts a 2 s lease)
        env.sql("update awp_eval_runs set deadline=? where id='run_dead'", (time.time() + 3.0,))
        assert env.post(f"{P}/tech/versions/1/evals", {}).status_code == 409  # within the lease it may still be alive elsewhere
        r = w.wait(lambda: (lambda x: x if x.status_code != 409 else None)(env.post(f"{P}/tech/versions/1/evals", {})), 10,
                   "the dead run to stop blocking the version")
        assert r.status_code == 202
        dead = next(x for x in runs(env, "tech") if x["run_id"] == "run_dead")
        assert dead["status"] == "error" and "interrupted" in dead["error"]
        w.wait(lambda: runs(env, "tech")[0]["status"] != "running", 90, "the new run to end")
        w.quiet(30)


def test_a_run_that_was_ended_from_outside_stops_working(tmp_path, monkeypatch):
    """A run whose row was reaped (its process stalled past the lease) cannot write a result any more: it stops instead of
    going on to spend the tenant's budget."""
    monkeypatch.setattr(runner, "LEASE", 1.0)
    with world(tmp_path, publish=False) as w:
        env = w.env
        ek.agents(tech=ek.careful)
        MODE["delay"] = lambda system: 0.5
        ek.draft(env, BARE)
        assert env.post(f"{P}/tech/versions/1/evals", {}).status_code == 202
        w.wait(lambda: w.sql("select 1 from wf_turns where status='running'"), 30, "a sandbox turn to run")
        env.sql("update awp_eval_runs set status='error', error='interrupted: test'")
        w.wait(lambda: not w.rt.evals._tasks, 15, "the run's task to stop")
        w.quiet(30)
        assert not w.sql("select 1 from wf_workflows where state <> 'closed'")
        assert runs(env, "tech")[0]["error"] == "interrupted: test"
        assert w.sql("select count(*) from wf_workflows") == [(1,)]  # the second case was never started


def test_a_sandbox_workflow_left_by_a_dead_process_gets_no_turn_and_is_closed(tmp_path):
    """The rows a crash leaves between `sandbox.start` and `sandbox.stop`: a running run, an open sandbox workflow and its
    queued job. Nothing of it is in memory, so the next process has only these rows."""
    with world(tmp_path, publish=False, sweep_every=3600) as w:
        ek.draft(w.env, BARE)
        ctx = w.env.app.state.wf

        async def crash_state():
            run = await w.rt.evals.store.open_run("ta", "tech", 1, "sha256:x", "admin:x", time.time() + 4.0)
            pin = {"run": run["id"], "index": 0, "key": "tech", "version": 1, "role": "specialist", "fixtures": {},
                   "type": sandbox.template_type("tech", 1)}
            accepted, case_id = await sandbox.start(ctx, "ta", f"{run['id']}:0", "What does the repair cost?", pin, 0.5, 400000)
            return run["id"], accepted.workflow_id, case_id
        run_id, wid, case_id = w.run(crash_state)  # the engine is never told and the sweep is off: nothing ran
        assert w.sql("select state from wf_workflows where id=?", (wid,))[0][0] != "closed"
    with world(tmp_path, publish=False) as w:  # the next process: its engine finds the queued job at once
        ek.agents(tech=ek.careful)
        # while the run's lease lives it may be running in another process of the fleet: its job is that process's (P5b)
        w.sql("update awp_eval_runs set deadline=? where id=?", (time.time() + 4.0, run_id))
        w.run(w.engine.sweep)
        assert w.sql("select status from wf_jobs where workflow_id=?", (wid,)) == [("queued",)]
        assert w.sql("select status from awp_eval_runs where id=?", (run_id,)) == [("running",)]
        # once the lease is over nobody runs it: the job is refused, never given a turn
        w.wait(lambda: w.sql("select 1 from wf_jobs where workflow_id=? and status='failed'", (wid,)), 30, "the job to be refused")
        w.wait(lambda: w.sql("select state from wf_workflows where id=?", (wid,)) == [("closed",)], 30,
               "the orphaned sandbox workflow to be closed")
        assert w.sql("select status from awp_eval_runs where id=?", (run_id,)) == [("error",)]
        w.quiet(30)
        assert not CALLS and w.sql("select count(*) from awp_ledger where case_id=?", (case_id,)) == [(0,)]
        assert not w.sql("select 1 from awp_case_sessions where case_id=?", (case_id,))  # no agent was made for it
        assert ek.evaluated(w.env, "tech")["status"] == "passed"  # and the version can be evaluated as usual


@pytest.mark.slow
def test_a_run_cut_by_a_clean_shutdown_is_an_error_and_leaves_nothing_running(tmp_path):
    with world(tmp_path, publish=False) as w:
        ek.agents(tech=ek.careful)
        MODE["delay"] = lambda system: 0.4
        ek.draft(w.env, BARE)
        assert w.env.post(f"{P}/tech/versions/1/evals", {}).status_code == 202
        w.wait(lambda: w.sql("select 1 from wf_turns where status='running'"), 30, "a sandbox turn to run")
    with world(tmp_path, publish=False) as w:
        ek.agents(tech=ek.careful)
        [run] = runs(w.env, "tech")
        assert run["status"] == "error" and "stopped" in run["error"], run
        time.sleep(4.5)  # two sweeps
        w.quiet(30)
        assert not w.sql("select 1 from wf_workflows where state <> 'closed'") and not CALLS
        assert ek.evaluated(w.env, "tech")["status"] == "passed"
