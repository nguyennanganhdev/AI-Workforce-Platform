"""Runs the evaluation of one exact profile version: every case in the sandbox, one after another, then the checks.

A run is a background task of this process and a row in `awp_eval_runs`. It is bounded on every side: each case
has a time limit and a budget (the case's own, as for any workflow), a few runs of a tenant go at once, and whatever
a case leaves running is closed and interrupted when it ends. Nothing here blocks the engine: a sandbox workflow is
one more workflow to it, with its own dispatcher.

A run belongs to the process that started it. While that process lives it moves the run's deadline on (`LEASE`); a
run whose deadline passed is dead and ends as an error, wherever it is read. A sandbox workflow is driven only while
its run is live here (`live`, asked by the engine before it gives the workflow a turn), and one left open by a
process that died is closed by `sweep`.

What ran is recorded as the profile's content hash and the hash of the cases. A draft edited during or after the run,
or a case written after it, leaves the version without a passing run.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from sqlalchemy import select

from .. import db
from ..profiles import ProfileRecord, to_template
from ..workforce import tables as t
from ..workforce.settle import TERMINAL
from . import sandbox
from .checks import Checks, Observation, evaluate
from .defaults import default_cases
from .store import EvalError, EvalStore, cases_digest, digest

log = logging.getLogger("awp")
POLL = 0.1
LEASE = 90.0  # a run is dead this long after its process last said it lives: longer than any stall of one database write


def clip(text: Any, n: int = 300) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


class EvalRunner:
    def __init__(self, ctx) -> None:
        self.ctx, self.rt, self.settings = ctx, ctx.rt, ctx.settings
        self.store = EvalStore(ctx.db)
        self._tasks: dict[str, asyncio.Task] = {}  # run id -> its task: the runs that are live in this process
        self._live: set[tuple[str, str, int]] = set()  # versions with a run in this process
        self._slots: dict[str, asyncio.Semaphore] = {}  # per tenant: one tenant's runs never queue behind another's

    def live(self, run_id: str) -> bool:
        """Is this run running in this process? Only then may one of its sandbox workflows be given a turn."""
        return run_id in self._tasks

    # ---- the cases of a profile ----------------------------------------------------
    async def cases(self, tenant: str, rec: ProfileRecord) -> list[dict]:
        """The platform's cases for this profile, then the tenant's own."""
        team = {}
        for key in rec.profile.team:
            member = await self.rt.profiles.get_published(tenant, key) or await self.rt.profiles.latest(tenant, key)
            if member is not None:
                team[key] = member.profile
        return [*default_cases(rec.profile, team), *await self.store.cases(tenant, rec.key)]

    # ---- starting and waiting ---------------------------------------------------------
    async def start(self, tenant: str, rec: ProfileRecord, by: str) -> dict:
        """One run of a version at a time. In this process the mark decides, taken before the first await; across
        processes the unique index on a running run does (`open_run`)."""
        mark = (tenant, rec.key, rec.version)
        if mark in self._live:
            raise EvalError(409, "an evaluation of this version is running; wait for it")
        self._live.add(mark)
        try:
            await self.store.reap()
            cases = await self.cases(tenant, rec)
            run = await self.store.open_run(tenant, rec.key, rec.version, digest(rec.profile), by, time.time() + LEASE,
                                            cases_digest(cases))
        except BaseException:
            self._live.discard(mark)
            raise
        task = asyncio.get_running_loop().create_task(self._run(run, rec, cases))
        self._tasks[run["id"]] = task
        task.add_done_callback(lambda _t: (self._tasks.pop(run["id"], None), self._live.discard(mark)))
        return run

    async def wait(self, tenant: str, run_id: str, seconds: float) -> dict | None:
        """The run as it is once it ended, or as it is when `seconds` are over."""
        end = time.monotonic() + seconds
        while True:
            run = await self.store.run(tenant, run_id)
            if run is None or run["status"] != "running" or time.monotonic() >= end:
                return run
            await asyncio.sleep(POLL)

    async def stop(self) -> None:
        """The app is going down: the runs of this process end as errors now, not at their deadline."""
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def sweep(self) -> None:
        """With every sweep of the app: dead runs end, and a sandbox workflow whose run is over is closed. A process that
        died between starting a case and closing it leaves such a workflow open, with a job the engine would pick up."""
        await self.store.reap()
        async with self.ctx.db.engine.connect() as conn:
            left = (await conn.execute(
                select(t.workflows.c.id, db.cases.c.meta)
                .join(t.clients, t.clients.c.id == t.workflows.c.client_id)
                .join(db.cases, db.cases.c.id == t.workflows.c.case_id)
                .where(t.clients.c.environment == sandbox.EVAL_ENV, t.workflows.c.state != "closed"))).all()
        for wid, meta in left:
            run_id = ((meta or {}).get("eval") or {}).get("run")
            if run_id and (self.live(run_id) or await self.store.status(run_id) == "running"):
                continue  # ours, or another process's that still says it lives
            try:
                await sandbox.stop(self.ctx, wid)
            except Exception:
                log.exception("could not close the sandbox workflow %s of an evaluation that is over", wid)

    # ---- one run ------------------------------------------------------------------------
    async def _beat(self, run_id: str, task: asyncio.Task) -> None:
        """Say that the run lives, for as long as its task does. A run that was ended from outside (reaped after this
        process stalled) is stopped: its result could not be written any more."""
        while True:
            await asyncio.sleep(LEASE / 4)
            try:
                if not await self.store.beat(run_id, time.time() + LEASE):
                    task.cancel()
                    return
            except Exception:
                log.exception("evaluation %s: could not renew its lease", run_id)

    async def _run(self, run: dict, rec: ProfileRecord, cases: list[dict]) -> None:
        tenant, started, results = run["tenant"], time.monotonic(), []
        kind = sandbox.template_type(rec.key, rec.version)
        specialist = rec.profile.role == "specialist"
        beat = asyncio.get_running_loop().create_task(self._beat(run["id"], asyncio.current_task()))
        slots = self._slots.setdefault(tenant, asyncio.Semaphore(max(1, self.settings.eval_parallel)))
        try:
            async with slots:
                self.rt._profile_cache.pop((tenant, rec.key, rec.version), None)  # the draft as it is now, not as it was
                if specialist:  # the exact version, as a sub-agent type only this run's sandbox cases may create (room.creatable)
                    self.rt.templates[kind] = to_template(rec.profile, rec.version, self.settings).model_copy(update={"type": kind})
                    self.rt.template_tenant[kind] = tenant
                try:
                    for i, case in enumerate(cases):
                        results.append(await self._case(run, rec, i, case))
                        await self.store.write_run(run["id"], results=results)
                finally:
                    if specialist:
                        self.rt.templates.pop(kind, None)
                        self.rt.template_tenant.pop(kind, None)
            passed = sum(1 for r in results if r["passed"])
            now_is = await self.rt.profiles.get(tenant, rec.key, rec.version)
            if now_is is None or digest(now_is.profile) != run["profile_hash"]:
                status, error = "error", "the draft was edited while it was evaluated; run it again"
            else:
                status, error = ("passed" if passed == len(results) else "failed"), None
            await self._end(run, rec, status, results, started, error)
        except asyncio.CancelledError:
            await asyncio.shield(self._end(run, rec, "error", results, started, "interrupted: the platform stopped"))
            raise
        except Exception as e:
            log.exception("evaluation %s failed", run["id"])
            await self._end(run, rec, "error", results, started, f"the evaluation could not run ({type(e).__name__})")
        finally:
            beat.cancel()

    async def _end(self, run: dict, rec: ProfileRecord, status: str, results: list, started: float, error: str | None) -> None:
        passed = sum(1 for r in results if r["passed"])
        await self.store.write_run(
            run["id"], status=status, results=results, score=(passed / len(results)) if results else None,
            cost_usd=sum(r.get("cost_usd") or 0.0 for r in results), duration_s=time.monotonic() - started,
            error=error, finished_at=time.time())
        await self.rt.profiles.note(run["tenant"], rec.key, rec.version, "eval", run["started_by"], {
            "run_id": run["id"], "status": status, "passed": passed, "cases": len(results), **({"error": error} if error else {})})

    # ---- one case -----------------------------------------------------------------------
    async def _case(self, run: dict, rec: ProfileRecord, index: int, case: dict) -> dict:
        """Start the sandbox workflow, wait until it rests (or the time is up), read what it left, close it."""
        s, started, wid = self.settings, time.monotonic(), None
        out = {"name": case["name"], "platform": bool(case.get("platform")), "passed": False, "checks": []}
        role = rec.profile.role
        pin = {"run": run["id"], "index": index, "key": rec.key, "version": rec.version, "role": role,
               "fixtures": case["fixtures"], "type": sandbox.template_type(rec.key, rec.version)}
        try:
            accepted, case_id = await sandbox.start(self.ctx, run["tenant"], f"{run['id']}:{index}", case["input"], pin,
                                                    s.eval_case_budget_usd, s.eval_case_budget_tokens)
            wid = accepted.workflow_id
            out.update(case_id=case_id, workflow_id=wid)
            self.ctx.engine.notify(wid, accepted.job_id)
            rested = await self._rested(accepted.request_id, s.eval_case_timeout_seconds)
            obs, shown = await self._observe(wid, case_id, role, case["input"])
            obs.timed_out = not rested
            checks = Checks.model_validate(case["checks"])
            if role == "specialist":
                checks.expected_state = []  # the workflow of a specialist's evaluation is the harness's, not its own
            verdicts = evaluate(checks, obs)
            out.update(checks=verdicts, passed=all(v["ok"] for v in verdicts), state=obs.state, cost_usd=obs.cost_usd, **shown)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("evaluation %s: case %s failed to run", run["id"], case["name"])
            out.update(error=f"the case could not run ({type(e).__name__})")
        finally:
            if wid is not None:
                try:
                    await asyncio.shield(sandbox.stop(self.ctx, wid))
                except Exception:
                    log.exception("evaluation %s: could not close sandbox workflow %s", run["id"], wid)
        out["duration_s"] = round(time.monotonic() - started, 3)
        return out

    async def _rested(self, request_id: str, timeout: float) -> bool:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            async with self.ctx.db.engine.connect() as conn:
                status = (await conn.execute(select(t.requests.c.status).where(t.requests.c.id == request_id))).scalar()
            if status in TERMINAL:
                return True
            await asyncio.sleep(POLL)
        return False

    async def _observe(self, workflow_id: str, case_id: str, role: str, text: str) -> tuple[Observation, dict]:
        """The record of the agent under test: a leader's own calls and words, or those of the specialist(s) the
        harness brought in. Also returns what a person wants to see of it in the result."""
        rt = self.rt
        items = await rt.cases.items(case_id)
        async with self.ctx.db.engine.connect() as conn:
            state = (await conn.execute(select(t.workflows.c.state).where(t.workflows.c.id == workflow_id))).scalar()
            said = (await conn.execute(select(t.messages.c.text).where(
                t.messages.c.workflow_id == workflow_id, t.messages.c.sender == "assistant",
                t.messages.c.expects.is_not(None)).order_by(t.messages.c.sequence))).scalars().all()
        subject = "leader" if role == "leader" else "worker"
        names = {m["agent_name"] for m in await rt.cases.sessions_of_case(case_id) if m["role"] == subject}
        own = [i for i in items if i.author in names]
        calls = [{"tool": i.data.get("tool"), "input": i.data.get("input"), "ok": bool(i.data.get("ok"))}
                 for i in items if i.kind == "trace" and i.data.get("role") == subject]
        reports = [i.data.get("summary", "") for i in own if i.kind == "report" and not i.data.get("ended")]
        if role == "leader":
            outputs = list(said)
            gaps = sum(1 for i in own if i.kind == "gap" or (i.kind == "final" and (
                i.data.get("unknowns") or i.data.get("outcome") != "resolved")))
        else:
            outputs = [i.data.get("text", "") for i in own if i.kind in ("fact", "answer")] + reports
            gaps = sum(1 for i in own if i.kind == "gap")
        obs = Observation(
            calls=calls, outputs=outputs, gaps=gaps, state=state,
            sources=[text, *(i.data.get("text", "") for i in items if i.kind == "evidence")],
            cost_usd=(await rt.cost.case_totals(case_id))["cost_usd"],
            responded=bool(said) if role == "leader" else bool(reports))
        return obs, {"calls": [c["tool"] for c in calls][:60], "said": [clip(x) for x in outputs][:10]}
