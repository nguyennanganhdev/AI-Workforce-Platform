"""Harness and reusable prototypes for the turn/wake probe.

Contents
  TurnRecorder  agent middleware (`on_reply`) that records every run of a session ("turn"), whoever started it.
  TurnLog       where the recorder writes; in the engine this is the `wf_turns` table.
  Env           a real AgentScope app (create_app, in process, no awp code) on a scripted model.
  SerialDispatcher  one in-flight job per session; next job only when the previous turn(s) ended AND the
                    session is idle. Three sending strategies, so the probe can compare them.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
from agentscope.app import create_app
from agentscope.app._bus_ops import deliver_to_inbox, enqueue_run_trigger
from agentscope.app.message_bus import InMemoryMessageBus, MessageBusKeys
from agentscope.app.storage import AsyncSQLAlchemyStorage
from agentscope.app.workspace_manager import LocalWorkspaceManager
from agentscope.event import (HintBlockEvent, ReplyEndEvent, ReplyStartEvent, RequireExternalExecutionEvent,
                              RequireUserConfirmEvent)
from agentscope.message import HintBlock, Msg
from agentscope.middleware import MiddlewareBase

from p0_turn_wake_llm import LLM, FakeServer

USER = "probe-user"


# --------------------------------------------------------------------------- recorder
@dataclass
class Turn:
    n: int
    session_id: str
    agent_name: str
    trigger: str  # "message" (inputs is a Msg) | "continue" (inputs None: inbox wake or loop-back) | event class name
    msg_id: str | None
    started: float
    ended: float | None = None
    reply_id: str | None = None
    saw_start: bool = False
    saw_end: bool = False
    finished_reason: str | None = None
    error: dict | None = None
    parked: bool = False
    # How the on_reply stream left: "end_event" | "parked" | "exception:<Cls>" | "cancelled" | "closed" | "no_end_event"
    left: str = "?"
    hints: list[str] = field(default_factory=list)  # HintBlockEvent texts seen during the turn
    done: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def status(self) -> str:
        """The value we would store in wf_turns.status."""
        if self.parked:
            return "parked"
        if self.left.startswith("exception") or self.finished_reason == "error":
            return "error"
        if self.left == "cancelled" or self.finished_reason == "interrupted":
            return "interrupted"
        if self.finished_reason in ("completed", "exceed_max_iters"):
            return "completed"
        return "unknown"


class TurnLog:
    def __init__(self) -> None:
        self.turns: list[Turn] = []
        self._changed = asyncio.Event()
        self.on_end: Callable[[Turn], None] | None = None  # test hook, called inside the run task

    def begin(self, **kw) -> Turn:
        t = Turn(n=len(self.turns) + 1, started=time.perf_counter(), **kw)
        self.turns.append(t)
        return t

    def end(self, t: Turn) -> None:
        t.ended = time.perf_counter()
        t.done.set()
        self._changed.set()
        if self.on_end is not None:
            self.on_end(t)

    def of(self, session_id: str) -> list[Turn]:
        return [t for t in self.turns if t.session_id == session_id]

    async def wait_count(self, session_id: str, n: int, timeout: float = 30.0) -> list[Turn]:
        """Wait until `session_id` has >= n *finished* turns."""
        end = time.perf_counter() + timeout
        while True:
            done = [t for t in self.of(session_id) if t.done.is_set()]
            if len(done) >= n:
                return done
            left = end - time.perf_counter()
            if left <= 0:
                raise AssertionError(f"only {len(done)} finished turns for {session_id}, wanted {n}: "
                                     f"{[(t.trigger, t.left) for t in self.of(session_id)]}")
            self._changed.clear()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._changed.wait(), min(left, 0.25))


class TurnRecorder(MiddlewareBase):
    """Records one `Turn` per `on_reply` call. Writes only through `log`, never changes the stream."""

    def __init__(self, log: TurnLog) -> None:
        self.log = log

    async def on_reply(self, agent, input_kwargs, next_handler):
        inputs = input_kwargs.get("inputs")
        if isinstance(inputs, Msg):
            trigger, msg_id = "message", inputs.id
        elif isinstance(inputs, list) and inputs:
            trigger, msg_id = "message", inputs[0].id
        elif inputs is None:
            trigger, msg_id = "continue", None
        else:
            trigger, msg_id = type(inputs).__name__, None
        t = self.log.begin(session_id=agent.state.session_id, agent_name=agent.name, trigger=trigger, msg_id=msg_id)
        t.left = "no_end_event"  # replaced below if something more precise happens
        try:
            async for item in next_handler(**input_kwargs):
                if isinstance(item, ReplyStartEvent):
                    t.saw_start, t.reply_id = True, item.reply_id
                elif isinstance(item, HintBlockEvent):
                    t.hints.append(item.hint)
                elif isinstance(item, (RequireUserConfirmEvent, RequireExternalExecutionEvent)):
                    t.parked, t.left = True, "parked"
                elif isinstance(item, ReplyEndEvent):
                    t.saw_end = True
                    t.finished_reason = str(getattr(item.finished_reason, "value", item.finished_reason))
                    t.error = item.error.model_dump(mode="json") if item.error else None
                    t.reply_id = item.reply_id
                    if not t.parked:
                        t.left = "end_event"
                yield item
        except asyncio.CancelledError:
            t.left = "cancelled"
            raise
        except GeneratorExit:
            t.left = "closed"
            raise
        except BaseException as e:  # noqa: BLE001 - we only label it and re-raise
            t.left = f"exception:{type(e).__name__}"
            t.error = {"message": str(e)[:300]}
            raise
        finally:
            # In the engine this is where wf_turns is updated (a short DB write; not shielded here).
            self.log.end(t)


# --------------------------------------------------------------------------- environment
class ProbeBus(InMemoryMessageBus):
    """In-memory bus that timestamps every acquire/release of a lock, so 'when exactly was the session
    lock released' is measured, not polled."""

    def __init__(self) -> None:
        super().__init__()
        self.lock_events: list[tuple[str, str, float]] = []

    @contextlib.asynccontextmanager
    async def acquire_lock(self, key, *, ttl_secs=600):
        async with super().acquire_lock(key, ttl_secs=ttl_secs):
            self.lock_events.append((key, "acq", time.perf_counter()))
            try:
                yield
            finally:
                self.lock_events.append((key, "rel", time.perf_counter()))


class Env:
    def __init__(self, tmp: Path, llm: LLM, *, recorder: bool = True) -> None:
        self.tmp, self.llm, self.recorder = Path(tmp), llm, recorder
        self.log = TurnLog()

    async def __aenter__(self) -> "Env":
        self.fake = FakeServer(self.llm).__enter__()
        self.storage = AsyncSQLAlchemyStorage(
            f"sqlite+aiosqlite:///{(self.tmp / 'as.db').as_posix()}",
            engine_kwargs={"connect_args": {"timeout": 30}})
        self.bus = ProbeBus()

        async def mw_factory(user_id, agent_id, session_id, *rest):
            return [TurnRecorder(self.log)] if self.recorder else []

        self.app = create_app(
            self.storage, self.bus, LocalWorkspaceManager(basedir=str(self.tmp / "ws")),
            enable_scheduler=False, enable_channel_worker=False, enable_index_worker=False,
            extra_agent_middlewares=mw_factory, custom_subagent_templates=[], title="probe")
        self._lifespan = self.app.router.lifespan_context(self.app)
        await self._lifespan.__aenter__()
        self.http = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://as.local",
                                      headers={"X-User-ID": USER}, timeout=60.0)
        r = await self.http.post("/credential/", json={"data": {
            "type": "openai_credential", "api_key": "x", "base_url": self.fake.base_url, "name": "fake"}})
        assert r.status_code < 300, r.text
        self.credential_id = r.json()["credential_id"]
        return self

    async def __aexit__(self, *exc) -> None:
        await self.http.aclose()
        with contextlib.suppress(Exception):
            await self._lifespan.__aexit__(None, None, None)
        self.fake.__exit__()

    # ---- setup
    async def agent(self, name: str, prompt: str = "You are a probe agent. Answer briefly.", max_iters: int = 10) -> str:
        r = await self.http.post("/agent/", json={"name": name, "system_prompt": prompt,
                                                  "react_config": {"max_iters": max_iters}})
        assert r.status_code < 300, r.text
        return r.json()["agent_id"]

    async def session(self, agent_id: str, name: str | None = "wf", mode: str = "bypass") -> str:
        body: dict[str, Any] = {"agent_id": agent_id, "chat_model_config": {
            "type": "openai_chat", "credential_id": self.credential_id, "model": "fake-1", "parameters": {}}}
        if name is not None:
            body["name"] = name
        r = await self.http.post("/sessions/", json=body)
        assert r.status_code < 300, r.text
        sid = r.json()["session_id"]
        r = await self.http.patch(f"/sessions/{sid}", params={"agent_id": agent_id}, json={"permission_mode": mode})
        assert r.status_code < 300, r.text
        return sid

    async def leader(self, name: str = "boss", **kw) -> tuple[str, str]:
        aid = await self.agent(name)
        return aid, await self.session(aid, **kw)

    # ---- the three ways to put work into an idle/busy session
    async def say(self, sid: str, aid: str, text: str, msg_id: str | None = None) -> httpx.Response:
        """POST /chat with a user Msg, exactly like AgentScopeClient.say()."""
        msg: dict[str, Any] = {"name": "intake", "role": "user", "content": [{"type": "text", "text": text}]}
        if msg_id:
            msg["id"] = msg_id
        return await self.http.post("/chat/", json={"agent_id": aid, "session_id": sid, "input": msg})

    async def wake(self, sid: str, aid: str, text: str) -> None:
        """Runtime.deliver() minus the case lookup: a HintBlock into the inbox (wakes an idle session)."""
        hint = HintBlock(hint=f'<provider-event>\n{text}\n</provider-event>',
                         source=json.dumps({"label": "case", "sublabel": "provider"}))
        await deliver_to_inbox(self.bus, user_id=USER, session_id=sid, agent_id=aid,
                               payload=hint.model_dump(mode="json"))

    async def queue_message(self, sid: str, aid: str, text: str, msg_id: str | None = None) -> None:
        """enqueue_run_trigger(kind="message"): the dispatcher re-queues it while the session is busy."""
        msg = Msg(name="intake", role="user", content=[{"type": "text", "text": text}],
                  **({"id": msg_id} if msg_id else {}))
        await enqueue_run_trigger(self.bus, user_id=USER, session_id=sid, agent_id=aid,
                                  kind=MessageBusKeys.WAKEUP_KIND_MESSAGE, inputs=msg)

    # ---- observation
    def runs(self, sid: str) -> int:
        """How many ChatService.run invocations took the session lock (one run may hold several turns)."""
        key = MessageBusKeys.session_lock(sid)
        return sum(1 for k, what, _ in self.bus.lock_events if k == key and what == "acq")

    def lock_release_after(self, sid: str, t: float) -> float | None:
        """First time >= t at which the session lock was released."""
        key = MessageBusKeys.session_lock(sid)
        for k, what, ts in self.bus.lock_events:
            if k == key and what == "rel" and ts >= t:
                return ts
        return None

    def locked(self, sid: str) -> Awaitable[bool]:
        return self.bus.is_locked(MessageBusKeys.session_lock(sid))

    def registry_busy(self, sid: str) -> bool:
        t = self.app.state.chat_run_registry.get(sid)
        return t is not None and not t.done()

    async def status(self, sid: str, aid: str) -> str:
        r = await self.http.get(f"/sessions/{sid}/status", params={"agent_id": aid})
        assert r.status_code == 200, r.text
        return r.json()["status"]

    async def messages(self, sid: str, aid: str) -> list[dict]:
        r = await self.http.get(f"/sessions/{sid}/messages", params={"agent_id": aid, "limit": 200})
        assert r.status_code == 200, r.text
        return r.json()["messages"]

    async def wait_idle(self, sid: str, timeout: float = 30.0, step: float = 0.005) -> float:
        """Seconds waited until the session lock is free and no run task is registered."""
        t0 = time.perf_counter()
        while await self.locked(sid) or self.registry_busy(sid):
            if time.perf_counter() - t0 > timeout:
                raise AssertionError(f"session {sid} still busy after {timeout}s")
            await asyncio.sleep(step)
        return time.perf_counter() - t0

    async def settle(self, sid: str, quiet: float = 0.4, timeout: float = 30.0) -> None:
        """Idle and nothing new started for `quiet` seconds (covers the 0.1 s dispatcher backoff)."""
        end = time.perf_counter() + timeout
        while time.perf_counter() < end:
            await self.wait_idle(sid, timeout)
            await asyncio.sleep(quiet)
            if not await self.locked(sid) and not self.registry_busy(sid):
                return
        raise AssertionError("session never settled")


# --------------------------------------------------------------------------- serialised dispatch
@dataclass
class Job:
    id: str
    text: str
    kind: str = "resident_message"  # resident_message -> say / message ; provider_wake -> wake


@dataclass
class JobResult:
    job: Job
    sent_at: float
    attempts: int  # how many POSTs were needed (409 retries count)
    n409: int
    turns: list[Turn]
    turn_ended_at: float


class SerialDispatcher:
    """One dispatched job at a time for a session. A job is DONE when (a) the turn(s) it started have ended
    (recorder) AND (b) the session is idle (lock free). Only then does the next job go out.

    strategy
      "say_idle"   wait for idle, then POST /chat. A 409 here would be a bug of the helper (reported, retried).
      "say_retry"  POST /chat right away when the previous turn ended and retry on 409 (no idle wait).
      "bus_message" enqueue_run_trigger(kind="message"): the dispatcher itself waits for the lock.
    """

    def __init__(self, env: Env, aid: str, sid: str, strategy: str = "say_idle") -> None:
        self.env, self.aid, self.sid, self.strategy = env, aid, sid, strategy
        self.queue: asyncio.Queue[Job] = asyncio.Queue()
        self.results: list[JobResult] = []
        self._task: asyncio.Task | None = None

    def submit(self, job: Job) -> None:
        self.queue.put_nowait(job)

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def drain(self, n: int, timeout: float = 120.0) -> list[JobResult]:
        end = time.perf_counter() + timeout
        while len(self.results) < n:
            if self._task and self._task.done() and self._task.exception():
                raise self._task.exception()
            if time.perf_counter() > end:
                raise AssertionError(f"{len(self.results)}/{n} jobs done")
            await asyncio.sleep(0.01)
        return self.results

    async def _loop(self) -> None:
        env, log = self.env, self.env.log
        while True:
            job = await self.queue.get()
            before = len(log.of(self.sid))
            sent, attempts, n409 = time.perf_counter(), 0, 0
            if job.kind == "provider_wake":
                await env.wake(self.sid, self.aid, job.text)
                attempts = 1
            elif self.strategy == "bus_message":
                await env.queue_message(self.sid, self.aid, job.text, job.id)
                attempts = 1
            else:
                if self.strategy == "say_idle":
                    await env.wait_idle(self.sid)
                while True:
                    attempts += 1
                    r = await env.say(self.sid, self.aid, job.text, job.id)
                    if r.status_code == 409:
                        n409 += 1
                        await asyncio.sleep(0.02)  # Windows timer tick is ~15.6 ms: shorter sleeps are no sleep
                        continue
                    assert r.status_code == 200, r.text
                    break
            # the job's turns: every turn that started after sending, until the session is quiet
            first = await self._first_turn(before)
            turns = [first]
            while True:
                await first.done.wait()
                if self.strategy != "say_retry":
                    await env.wait_idle(self.sid)
                more = [t for t in log.of(self.sid)[before:] if t not in turns]
                for t in more:
                    turns.append(t)
                if all(t.done.is_set() for t in turns):
                    break
            ended = max(t.ended for t in turns)  # type: ignore[type-var]
            self.results.append(JobResult(job, sent, attempts, n409, turns, ended))

    async def _first_turn(self, before: int, timeout: float = 30.0) -> Turn:
        end = time.perf_counter() + timeout
        while time.perf_counter() < end:
            ts = self.env.log.of(self.sid)
            if len(ts) > before:
                return ts[before]
            await asyncio.sleep(0.002)
        raise AssertionError("job produced no turn within the timeout")
