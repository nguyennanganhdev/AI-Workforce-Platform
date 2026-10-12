"""P0 probe: turns, wake-ups and serialisation of inputs for one leader session.

Everything runs against a real AgentScope app (create_app, in process) on a scripted model; no awp code
is involved, so the result is about AgentScope. Numbers are printed (run with -s) and also written to
`p0_turn_wake_numbers.json` next to this file when P0_WRITE_NUMBERS=1.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import statistics
import time
import warnings
from pathlib import Path

import pytest

from p0_turn_wake_env import Env, Job, SerialDispatcher
from p0_turn_wake_llm import LLM, called

NUMBERS: dict = {}


def run(coro):
    return asyncio.run(coro)


def note(key: str, value) -> None:
    NUMBERS[key] = value
    print(f"[p0-turn-wake] {key} = {json.dumps(value, ensure_ascii=False, default=str)}")
    if os.environ.get("P0_WRITE_NUMBERS"):
        (Path(__file__).parent / "p0_turn_wake_numbers.json").write_text(
            json.dumps(NUMBERS, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def test_smoke_say_is_one_recorded_turn(tmp_path):
    async def main():
        llm = LLM()
        async with Env(tmp_path, llm) as env:
            aid, sid = await env.leader()
            r = await env.say(sid, aid, "hello", msg_id="m-1")
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "started"
            [t] = await env.log.wait_count(sid, 1)
            assert (t.trigger, t.msg_id, t.saw_start, t.saw_end, t.finished_reason, t.left, t.status) == \
                   ("message", "m-1", True, True, "completed", "end_event", "completed"), t
            await env.settle(sid)
            assert len(env.log.of(sid)) == 1
            assert len(llm.of(sid)) == 1

    run(main())


# ---------------------------------------------------------------------------------------------- helpers
def team_policy(leader_sid_box: list, worker_delay: float = 0.0, final_leader_text: str = "got the report"):
    """Leader: TeamCreate -> AgentCreate(w1) -> text. Worker: TeamSay(REPORT-1, to=boss) -> text.
    The leader's next model call after the report says `final_leader_text`."""
    def policy(c):
        if c.sid == leader_sid_box[0]:
            if called(c.msgs, "TeamCreate") == 0:
                return [("TeamCreate", {"name": "t1", "description": "probe team"})]
            if called(c.msgs, "AgentCreate") == 0:
                return [("AgentCreate", {"name": "w1", "description": "reporter", "prompt": "report to boss"})]
            if "REPORT-1" in c.blob:
                return final_leader_text
            return "dispatched w1"
        if called(c.msgs, "TeamSay") == 0:
            return [("TeamSay", {"content": "REPORT-1 done", "to": "boss"})]
        return "reported"
    return policy


def leader_turns(env, sid):
    return [t for t in env.log.of(sid)]


# ---------------------------------------------------------------------------------------------- (1) recorder
@pytest.mark.parametrize("worker_delay", [1.0, 0.0], ids=["leader_idle_when_report_arrives", "report_races_leader_run"])
def test_worker_report_wakes_leader_and_recorder_sees_the_turn(tmp_path, worker_delay):
    """A worker's TeamSay -> deliver_to_inbox must show up as a recorded leader turn with no POST /chat.
    Case A: the leader's first run is over when the report arrives (wake by dispatcher).
    Case B: the report arrives while the leader is still running (no wake; the run goes around again)."""
    async def main():
        llm = LLM()
        box: list = [None]
        async with Env(tmp_path, llm) as env:
            aid, sid = await env.leader("boss")
            box[0] = sid
            llm.policy = team_policy(box)
            if worker_delay:  # worker is slow -> leader's first run ends before the report
                llm.delay = lambda c: worker_delay if c.sid != sid else 0.0
            else:  # leader is slow on its last call -> the report lands while the leader is running
                llm.delay = lambda c: 0.0 if c.sid != sid or called(c.msgs, "AgentCreate") == 0 else 1.5
            r = await env.say(sid, aid, "start", msg_id="m-start")
            assert r.status_code == 200
            ts = await env.log.wait_count(sid, 2, timeout=30)
            await env.settle(sid, quiet=0.6)
            ts = env.log.of(sid)
            rows = [(t.trigger, t.msg_id, t.saw_end, t.finished_reason, t.left, any("REPORT-1" in h for h in t.hints))
                    for t in ts]
            kind = "idle" if worker_delay else "racing"
            note(f"worker_report_{kind}_leader_turns", rows)
            note(f"worker_report_{kind}_leader_runs", env.runs(sid))
            # idle: the report starts a second run (dispatcher wake). racing: same run, second turn.
            assert env.runs(sid) == (2 if worker_delay else 1)
            assert ts[0].trigger == "message" and ts[0].msg_id == "m-start"
            woke = [t for t in ts[1:] if any("REPORT-1" in h for h in t.hints)]
            assert len(woke) == 1, rows
            assert woke[0].trigger == "continue" and woke[0].saw_end and woke[0].finished_reason == "completed"
            # the model really saw the report, and answered it
            assert any(c.out == "got the report" for c in llm.of(sid))
            # the worker's own turns are recorded too (filter by session in the engine)
            for other in {t.session_id for t in env.log.turns if t.session_id != sid}:
                await env.settle(other, quiet=0.6)
            wk = [t for t in env.log.turns if t.session_id != sid]
            note('worker_turns', [(t.agent_name, t.trigger, t.saw_start, t.saw_end, t.finished_reason, t.left) for t in wk])
            assert wk and all(t.saw_end for t in wk)
            assert wk[0].trigger == "continue"  # its first run was started by AgentCreate's inbox hint
    run(main())


# ---------------------------------------------------------------------------------------------- (1) error / interrupt
def test_model_error_what_the_recorder_sees(tmp_path):
    async def main():
        llm = LLM()
        async with Env(tmp_path, llm) as env:
            aid, sid = await env.leader()
            llm.fail = lambda c: True
            t0 = time.perf_counter()
            assert (await env.say(sid, aid, "will fail", msg_id="m-err")).status_code == 200
            [t] = await env.log.wait_count(sid, 1, timeout=60)
            took = time.perf_counter() - t0
            await env.settle(sid)
            row = dict(trigger=t.trigger, msg_id=t.msg_id, saw_start=t.saw_start, saw_end=t.saw_end,
                       finished_reason=t.finished_reason, left=t.left, status=t.status, error=t.error,
                       model_http_calls=len(llm.of(sid)), seconds=round(took, 2),
                       turns_after=len(env.log.of(sid)))
            note("model_error_turn", row)
            # What is stored for the failed reply (this is what the public stream/history would show)
            msgs = await env.messages(sid, aid)
            note("model_error_persisted_messages", [(m["role"], m.get("finished_reason"),
                                                     (m.get("error") or {}).get("type")) for m in msgs])
            assert t.status == "error", row
            # recovery: the same session takes the next input normally
            llm.fail = lambda c: False
            assert (await env.say(sid, aid, "after the error", msg_id="m-ok")).status_code == 200
            ts = await env.log.wait_count(sid, 2)
            assert ts[1].status == "completed" and ts[1].msg_id == "m-ok"
    run(main())


def test_interrupt_what_the_recorder_sees(tmp_path):
    async def main():
        llm = LLM()
        async with Env(tmp_path, llm) as env:
            aid, sid = await env.leader()
            llm.delay = lambda c: 3.0
            assert (await env.say(sid, aid, "long one", msg_id="m-int")).status_code == 200
            while not llm.calls:  # model call is in flight
                await asyncio.sleep(0.01)
            t0 = time.perf_counter()
            r = await env.http.post(f"/sessions/{sid}/interrupt", params={"agent_id": aid})
            assert r.status_code == 202, r.text
            [t] = await env.log.wait_count(sid, 1, timeout=20)
            took = time.perf_counter() - t0
            await env.settle(sid)
            row = dict(trigger=t.trigger, saw_end=t.saw_end, finished_reason=t.finished_reason, left=t.left,
                       status=t.status, seconds_to_end=round(took, 2), turns_after=len(env.log.of(sid)))
            note("interrupt_turn", row)
            assert t.status == "interrupted", row
            # the session is usable afterwards
            llm.delay = lambda c: 0.0
            assert (await env.say(sid, aid, "again", msg_id="m-2")).status_code == 200
            ts = await env.log.wait_count(sid, 2)
            assert ts[1].status == "completed"
    run(main())


# ---------------------------------------------------------------------------------------------- (2) wake vs say
def test_sequential_wake_and_say_each_make_exactly_one_turn(tmp_path):
    """Idle session, one input at a time, N=20 each: turns per input and what the model saw."""
    async def main():
        llm = LLM()
        N = 20
        async with Env(tmp_path, llm) as env:
            aid, sid = await env.leader()
            wake_turns, wake_seen = [], []
            lat_wake, lat_say = [], []
            for i in range(N):
                before, ncalls = len(env.log.of(sid)), len(llm.of(sid))
                t0 = time.perf_counter()
                await env.wake(sid, aid, f"WAKE-{i}")
                await env.log.wait_count(sid, before + 1)
                lat_wake.append(time.perf_counter() - t0)
                await env.settle(sid, quiet=0.15)
                new = env.log.of(sid)[before:]
                wake_turns.append(len(new))
                new_calls = llm.of(sid)[ncalls:]
                wake_seen.append((len(new), new[0].trigger, sum(f"WAKE-{i}" in h for h in new[0].hints),
                                  any(f"WAKE-{i}" in c.blob for c in new_calls), len(new_calls)))
            say_turns, say_seen = [], []
            for i in range(N):
                before, ncalls = len(env.log.of(sid)), len(llm.of(sid))
                t0 = time.perf_counter()
                assert (await env.say(sid, aid, f"SAY-{i}", msg_id=f"s-{i}")).status_code == 200
                await env.log.wait_count(sid, before + 1)
                lat_say.append(time.perf_counter() - t0)
                await env.settle(sid, quiet=0.15)
                new = env.log.of(sid)[before:]
                say_turns.append(len(new))
                new_calls = llm.of(sid)[ncalls:]
                say_seen.append((len(new), new[0].trigger, new[0].msg_id == f"s-{i}",
                                 any(f"SAY-{i}" in c.blob for c in new_calls), len(new_calls)))
            note("seq_wake_turns_per_input", sorted(set(wake_turns)))
            note("seq_say_turns_per_input", sorted(set(say_turns)))
            note("seq_wake_detail_set", sorted(set(map(tuple, wake_seen))))
            note("seq_say_detail_set", sorted(set(map(tuple, say_seen))))
            note("seq_latency_ms_end_of_turn", {
                "wake_median": round(statistics.median(lat_wake) * 1000), "wake_max": round(max(lat_wake) * 1000),
                "say_median": round(statistics.median(lat_say) * 1000), "say_max": round(max(lat_say) * 1000)})
            # every wake: exactly 1 turn, trigger "continue", the hint is in that turn's events and in the prompt
            assert set(wake_seen) == {(1, "continue", 1, True, 1)}, set(wake_seen)
            assert set(say_seen) == {(1, "message", True, True, 1)}, set(say_seen)
    run(main())


def _real_hints(t):
    """Hint events that carry provider text (the runtime-state reminder AgentScope adds is not one)."""
    return [h for h in t.hints if "<provider-event>" in h]


def test_bursts_wake_coalesces_say_drops(tmp_path):
    """3 inputs fired back-to-back at an idle session whose model takes 0.4 s per call. Wakes: 8 trials."""
    async def main():
        llm = LLM()
        async with Env(tmp_path, llm) as env:
            trials = []
            for k in range(8):
                aid, sid = await env.leader(f"boss{k}")
                llm.delay = lambda c: 0.4
                for i in range(3):
                    await env.wake(sid, aid, f"BURST{k}-W{i}")
                await env.settle(sid, quiet=0.7)
                ts = env.log.of(sid)
                seen = [sum(f"BURST{k}-W{i}" in h for t in ts for h in t.hints) for i in range(3)]
                trials.append(dict(turns=len(ts), runs=env.runs(sid), model_calls=len(llm.of(sid)),
                                   empty_turns=sum(1 for t in ts if not _real_hints(t)), markers_seen=seen))
            note("burst_3_wakes_8_trials", trials)
            assert all(t["markers_seen"] == [1, 1, 1] for t in trials)  # nothing lost, nothing doubled
            assert all(t["model_calls"] == t["turns"] for t in trials)
            note("burst_3_wakes_summary", dict(
                turns_distribution=sorted(t["turns"] for t in trials),
                trials_with_an_empty_turn=sum(1 for t in trials if t["empty_turns"]),
                max_model_calls=max(t["model_calls"] for t in trials)))
            # --- 3 says (fire as fast as the HTTP calls return)
            aid, sid = await env.leader("sayer")
            base_turns, base_calls = len(env.log.of(sid)), len(llm.of(sid))
            codes = []
            for i in range(3):
                r = await env.say(sid, aid, f"BURST-S{i}", msg_id=f"b-{i}")
                codes.append(r.status_code)
            await env.settle(sid, quiet=0.6)
            msgs = await env.messages(sid, aid)
            persisted = [m for m in msgs if m["role"] == "user" and any("BURST-S" in (b.get("text") or "")
                                                                         for b in m["content"])]
            say = dict(status_codes=codes, new_turns=len(env.log.of(sid)) - base_turns,
                       model_calls=len(llm.of(sid)) - base_calls,
                       persisted_burst_user_messages=len(persisted),
                       model_saw=[any(f"BURST-S{i}" in c.blob for c in llm.of(sid)[base_calls:]) for i in range(3)])
            note("burst_3_says", say)
            assert codes[0] == 200 and codes.count(409) == 2
            assert say["persisted_burst_user_messages"] == 1 and say["model_saw"] == [True, False, False]
    run(main())


def test_wake_during_a_run_is_never_lost(tmp_path):
    """Inbox hint delivered while the leader is mid-run. Where it lands depends on timing (absorbed by the
    running turn, a second turn of the same run, or - if the run had not registered as inbox consumer yet -
    ALSO an extra empty run). It must be delivered exactly once; the extra empty run is the thing to know about."""
    async def main():
        llm = LLM()
        rows = []
        async with Env(tmp_path, llm) as env:
            llm.delay = lambda c: 0.8
            for when in (0.02, 0.1, 0.4, 0.7):
                aid, sid = await env.leader(f"boss{when}")
                assert (await env.say(sid, aid, f"go-{when}")).status_code == 200
                await asyncio.sleep(when)
                await env.wake(sid, aid, f"MID-{when}")
                await env.settle(sid, quiet=0.7)
                new = env.log.of(sid)
                rows.append(dict(delivered_after_s=when, turns=len(new), runs=env.runs(sid),
                                 model_calls=len(llm.of(sid)),
                                 hint_per_turn=[sum(f"MID-{when}" in h for h in t.hints) for t in new],
                                 empty_turns=sum(1 for t in new[1:] if not _real_hints(t))))
            note("wake_during_run", rows)
            for r in rows:
                assert sum(r["hint_per_turn"]) == 1, r  # delivered exactly once
                assert r["model_calls"] == r["turns"]
    run(main())


# ---------------------------------------------------------------------------------------------- (3) POST /chat while busy
def test_post_chat_while_running_is_409_and_the_message_is_lost(tmp_path):
    async def main():
        import gc
        llm = LLM()
        async with Env(tmp_path, llm) as env:
            aid, sid = await env.leader()
            llm.delay = lambda c: 1.0
            assert (await env.say(sid, aid, "FIRST", msg_id="m-1")).status_code == 200
            while not llm.calls:
                await asyncio.sleep(0.01)
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                r = await env.say(sid, aid, "SECOND-LOST", msg_id="m-2")
                gc.collect()
            body = {"status": r.status_code, "json": r.json()}
            note("post_chat_while_running", body)
            note("post_chat_409_unawaited_coroutine_warning", any("never awaited" in str(x.message) for x in w))
            assert r.status_code == 409
            await env.settle(sid, quiet=0.3)
            msgs = await env.messages(sid, aid)
            texts = [b.get("text") for m in msgs for b in m["content"] if m["role"] == "user"]
            note("post_chat_409_persisted_user_texts", [t for t in texts if t and "FIRST" in t or t and "SECOND" in t])
            assert not any("SECOND-LOST" in (t or "") for t in texts)
            assert not any("SECOND-LOST" in c.blob for c in llm.calls)
            assert len(env.log.of(sid)) == 1 and [t.msg_id for t in env.log.of(sid)] == ["m-1"]
            # sending it again once idle works: nothing remembers the rejected attempt
            llm.delay = lambda c: 0.0
            assert (await env.say(sid, aid, "SECOND-LOST", msg_id="m-2")).status_code == 200
            await env.log.wait_count(sid, 2)
    run(main())


def test_post_chat_when_the_lock_is_held_elsewhere_waits_instead_of_409(tmp_path):
    """Simulates 'the run is in another process': the session lock is held, but this process' registry is
    empty. /chat answers 200 'started' at once; the run blocks on the lock; the message is not persisted
    until the lock is acquired."""
    async def main():
        from agentscope.app.message_bus import MessageBusKeys
        llm = LLM()
        async with Env(tmp_path, llm) as env:
            aid, sid = await env.leader()
            async with env.bus.acquire_lock(MessageBusKeys.session_lock(sid)):
                t0 = time.perf_counter()
                r = await env.say(sid, aid, "WAITS", msg_id="m-w")
                http_s = time.perf_counter() - t0
                await asyncio.sleep(1.0)
                held = dict(status=r.status_code, http_seconds=round(http_s, 3),
                            turns_while_held=len(env.log.of(sid)), model_calls_while_held=len(llm.calls),
                            persisted_while_held=any("WAITS" in (b.get("text") or "")
                                                     for m in await env.messages(sid, aid) for b in m["content"]),
                            registry_busy=env.registry_busy(sid))
            note("lock_held_elsewhere", held)
            assert held["status"] == 200 and held["turns_while_held"] == 0 and not held["persisted_while_held"]
            [t] = await env.log.wait_count(sid, 1)
            assert t.msg_id == "m-w" and t.status == "completed"
    run(main())


# ---------------------------------------------------------------------------------------------- (4) the race, 20 back-to-back
def _gaps_ms(env, sid):
    """For every finished turn: ms from 'on_reply ended' to 'session lock released' (None if no release after)."""
    out = []
    for t in env.log.of(sid):
        rel = env.lock_release_after(sid, t.ended)
        out.append(None if rel is None else (rel - t.ended) * 1000)
    return out


def _stats(xs):
    xs = sorted(x for x in xs if x is not None)
    return dict(n=len(xs), min=round(xs[0], 1), median=round(statistics.median(xs), 1),
                p90=round(xs[int(len(xs) * 0.9) - 1], 1), max=round(xs[-1], 1))


N = 20


def test_race_naive_send_inside_the_turn_end_hook(tmp_path):
    """Worst case on purpose: the next say() is fired from inside the recorder's `finally`, i.e. the moment
    on_reply ends. Shows whether 'on_reply ended' can be taken as 'session can take the next input'."""
    async def main():
        llm = LLM()
        async with Env(tmp_path, llm) as env:
            aid, sid = await env.leader()
            first409, sent, lost_forever = [], [0], []
            done = asyncio.Event()
            pending: set = set()

            async def send(i):
                tries = 0
                while True:
                    r = await env.say(sid, aid, f"N-{i}", msg_id=f"n-{i}")
                    tries += 1
                    if r.status_code == 200:
                        break
                    assert r.status_code == 409
                    if tries == 1:
                        first409.append(i)
                    await asyncio.sleep(0.02)

            def on_end(t):
                if sent[0] < N - 1:
                    sent[0] += 1
                    task = asyncio.create_task(send(sent[0]))
                    pending.add(task)
                    task.add_done_callback(pending.discard)

            env.log.on_end = on_end
            sent[0] = 0
            await send(0)
            await env.log.wait_count(sid, N, timeout=60)
            await env.settle(sid)
            ts = env.log.of(sid)
            note("race_naive_hook", dict(jobs=N, turns=len(ts), first_attempt_409=len(first409),
                                         fraction=round(len(first409) / (N - 1), 2),
                                         gap_ms=_stats(_gaps_ms(env, sid))))
            assert len(ts) == N and sorted(t.msg_id for t in ts) == sorted(f"n-{i}" for i in range(N))
            # the point of the probe: "turn ended" is NOT "session free"
            assert len(first409) > 0
    run(main())


@pytest.mark.parametrize("strategy", ["say_retry", "say_idle", "bus_message"])
@pytest.mark.parametrize("model_delay", [0.0, 0.05], ids=["instant_model", "50ms_model"])
def test_serial_dispatch_20_jobs(tmp_path, strategy, model_delay):
    async def main():
        llm = LLM()
        llm.delay = lambda c: model_delay
        async with Env(tmp_path, llm) as env:
            aid, sid = await env.leader()
            d = SerialDispatcher(env, aid, sid, strategy)
            d.start()
            t0 = time.perf_counter()
            for i in range(N):
                d.submit(Job(id=f"j-{i}", text=f"JOB-{i}"))
            res = await d.drain(N, timeout=120)
            total = time.perf_counter() - t0
            await d.stop()
            await env.settle(sid)
            ts = env.log.of(sid)
            order = [t.msg_id for t in ts]
            per_job_ms = [(r.turn_ended_at - r.sent_at) * 1000 for r in res]
            row = dict(strategy=strategy, model_delay_s=model_delay, jobs=N, turns=len(ts), runs=env.runs(sid),
                       model_calls=len(llm.of(sid)), n409=sum(r.n409 for r in res),
                       posts=sum(r.attempts for r in res), total_s=round(total, 2),
                       per_job_ms=_stats(per_job_ms), gap_ms=_stats(_gaps_ms(env, sid)),
                       in_order=order == [f"j-{i}" for i in range(N)],
                       prompts_with_two_new_jobs=sum(1 for c in llm.of(sid) if len(
                           set(re.findall(r"JOB-\d+", json.dumps(c.msgs[-1])))) > 1))
            note(f"serial_{strategy}_{'instant' if not model_delay else '50ms'}", row)
            assert row["turns"] == N and row["model_calls"] == N and row["in_order"]  # exactly one turn per job
            assert all(len(r.turns) == 1 for r in res)
            assert row["prompts_with_two_new_jobs"] == 0  # a model call never mixes two jobs' inputs
            # no two jobs overlapped: each turn started after the previous one ended
            for a, b in zip(ts, ts[1:]):
                assert b.started >= a.ended
            if strategy in ("say_idle", "bus_message"):
                assert row["n409"] == 0
    run(main())


# ---------------------------------------------------------------------------------------------- failure paths that bypass on_reply
def test_failure_before_the_reply_starts_never_reaches_on_reply(tmp_path):
    """The model credential is gone: the agent cannot even be assembled. /chat still answers 200, no turn is
    recorded (on_reply never runs), the user message is not persisted - only the bus/history show an error."""
    async def main():
        llm = LLM()
        async with Env(tmp_path, llm) as env:
            aid, sid = await env.leader()
            r = await env.http.delete(f"/credential/{env.credential_id}")
            assert r.status_code < 300, r.text
            resp = await env.say(sid, aid, "LOST-ASSEMBLY", msg_id="m-asm")
            await env.settle(sid, quiet=0.5)
            msgs = await env.messages(sid, aid)
            row = dict(http=resp.status_code, turns_recorded=len(env.log.of(sid)), model_calls=len(llm.calls),
                       persisted=[(m["role"], m.get("finished_reason"), (m.get("error") or {}).get("type"),
                                   [b.get("text") for b in m["content"] if b.get("text")]) for m in msgs])
            note("assembly_failure", row)
            assert resp.status_code == 200 and row["turns_recorded"] == 0 and row["model_calls"] == 0
            assert not any(any("LOST-ASSEMBLY" in (t or "") for t in p[3]) for p in row["persisted"])
            assert any(p[1] == "error" for p in row["persisted"])
    run(main())


def test_unnamed_session_makes_a_hidden_extra_model_call(tmp_path):
    """create_session without `name` -> AgentScope asks the model for a title after the first reply, still
    under the session lock. awp always passes a name; this documents why it must."""
    async def main():
        llm = LLM()
        async with Env(tmp_path, llm) as env:
            aid = await env.agent("boss")
            sid_named = await env.session(aid, name="x")
            sid_unnamed = await env.session(aid, name=None)
            for sid in (sid_named, sid_unnamed):
                assert (await env.say(sid, aid, "first message")).status_code == 200
                await env.log.wait_count(sid, 1)
                await env.settle(sid, quiet=0.3)
            # the title request carries no session attachment, so the fake files it under sid "?"
            row = dict(named_model_calls=len(llm.of(sid_named)), unnamed_model_calls=len(llm.of(sid_unnamed)),
                       title_requests=len(llm.of("?")),
                       unnamed_gap_ms=_stats(_gaps_ms(env, sid_unnamed)), named_gap_ms=_stats(_gaps_ms(env, sid_named)))
            note("auto_naming_extra_call", row)
            assert row["named_model_calls"] == 1 and row["unnamed_model_calls"] == 1 and row["title_requests"] >= 1  # 3 here: the fake answers prose, AgentScope retries the structured output
    run(main())


def test_bus_message_burst_all_arrive_but_order_is_not_guaranteed(tmp_path):
    """enqueue_run_trigger(kind="message") x5 at once on a busy-ish session: none dropped, order observed."""
    async def main():
        llm = LLM()
        async with Env(tmp_path, llm) as env:
            aid, sid = await env.leader()
            llm.delay = lambda c: 0.15
            for i in range(5):
                await env.queue_message(sid, aid, f"Q-{i}", msg_id=f"q-{i}")
            await env.log.wait_count(sid, 5, timeout=30)
            await env.settle(sid, quiet=0.6)
            order = [t.msg_id for t in env.log.of(sid)]
            note("bus_message_burst_order", dict(order=order, turns=len(order), runs=env.runs(sid)))
            assert sorted(order) == [f"q-{i}" for i in range(5)]  # none lost, none doubled
    run(main())


def test_status_endpoint_is_the_lock_and_flips_after_persist(tmp_path):
    """GET /sessions/{id}/status says `running` exactly while the session lock is held, and `idle` only after
    the reply and state are stored - so it can serve as the 'safe to send the next input' check."""
    async def main():
        llm = LLM()
        async with Env(tmp_path, llm) as env:
            aid, sid = await env.leader()
            llm.delay = lambda c: 0.5
            assert await env.status(sid, aid) == "idle"
            assert (await env.say(sid, aid, "x", msg_id="m-st")).status_code == 200
            while not llm.calls:
                await asyncio.sleep(0.005)
            during = await env.status(sid, aid)
            [t] = await env.log.wait_count(sid, 1)
            await env.wait_idle(sid)
            after = await env.status(sid, aid)
            msgs = await env.messages(sid, aid)
            note("status_endpoint", dict(during=during, after=after, stored_roles=[m["role"] for m in msgs]))
            assert (during, after) == ("running", "idle")
            assert [m["role"] for m in msgs] == ["user", "assistant"]  # reply stored by the time it reads idle
    run(main())
