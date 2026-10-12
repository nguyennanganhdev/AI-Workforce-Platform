"""The evaluation cases a tenant wrote and the runs of its profile versions. Every read and write names the tenant."""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from .. import db
from ..profiles import AgentProfile
from .checks import TOOL_NAME, Checks
from .defaults import PREFIX

MAX_CASES = 30  # a tenant's own cases of one profile key
MAX_FIXTURE = 20000  # characters of one tool's recorded answer


class EvalError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


class CaseIn(BaseModel):
    """A case as a tenant writes it: what the resident (or the leader, for a specialist) asks, what each tool
    answers in the sandbox, and what must hold afterwards."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    input: str = Field(min_length=1, max_length=20000)
    fixtures: dict[str, Any] = Field(default_factory=dict, max_length=50)
    checks: Checks

    @field_validator("name")
    @classmethod
    def _own_name(cls, v: str) -> str:
        v = "".join(c for c in v if c.isprintable()).strip()  # it goes into a varchar: PostgreSQL stores no NUL
        if not v or v.startswith(PREFIX):
            raise ValueError(f"a name is needed, and names that start with {PREFIX!r} are the platform's")
        return v

    @field_validator("input")
    @classmethod
    def _no_nul(cls, v: str) -> str:
        return v.replace("\x00", "")  # PostgreSQL stores no NUL in text

    @field_validator("fixtures")
    @classmethod
    def _fixtures(cls, v: dict) -> dict:
        for name, answer in v.items():
            if not re.match(TOOL_NAME, name):
                raise ValueError(f"not a tool name: {name!r}")
            if len(answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)) > MAX_FIXTURE:
                raise ValueError(f"the answer of {name} is longer than {MAX_FIXTURE} characters")
        return v

    @field_validator("checks")
    @classmethod
    def _some(cls, v: Checks) -> Checks:
        if v.empty():
            raise ValueError("a case needs at least one check")
        return v


def digest(profile: AgentProfile) -> str:
    """The content of a profile version: what a run ran, and what a publish must still find."""
    raw = json.dumps(profile.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def cases_digest(cases: list[dict]) -> str:
    """The cases of a run, the platform's and the tenant's: a case added or changed afterwards has not run."""
    raw = json.dumps([[c["name"], c["input"], c["fixtures"], c["checks"]] for c in cases], sort_keys=True,
                     separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def case_out(r: Any) -> dict:
    return {"id": r["id"], "name": r["name"], "input": r["input"], "fixtures": r["fixtures"], "checks": r["checks"],
            "platform": False}


def run_out(r: Any) -> dict:
    return {"run_id": r["id"], "key": r["key"], "version": r["version"], "status": r["status"], "score": r["score"],
            "results": r["results"], "cost_usd": r["cost_usd"], "duration_s": r["duration_s"],
            "started_by": r["started_by"], "error": r["error"], "profile_hash": r["profile_hash"],
            "cases_hash": r["cases_hash"],
            "created_at": r["created_at"], "finished_at": r["finished_at"]}


class EvalStore:
    def __init__(self, database: db.Database) -> None:
        self._db = database

    # ---- cases ---------------------------------------------------------------
    async def cases(self, tenant: str, key: str) -> list[dict]:
        c = db.eval_cases.c
        async with self._db.engine.connect() as conn:
            rows = (await conn.execute(select(db.eval_cases).where(c.tenant == tenant, c.key == key)
                                       .order_by(c.created_at, c.id))).mappings().all()
        return [case_out(r) for r in rows]

    async def add_case(self, tenant: str, key: str, body: CaseIn) -> dict:
        c = db.eval_cases.c
        row = dict(id="evc_" + uuid.uuid4().hex[:16], tenant=tenant, key=key, name=body.name, input=body.input,
                   fixtures=body.fixtures, checks=body.checks.model_dump(mode="json"), created_at=time.time(),
                   updated_at=time.time())
        try:
            async with self._db.engine.begin() as conn:
                have = (await conn.execute(select(func.count()).select_from(db.eval_cases).where(
                    c.tenant == tenant, c.key == key))).scalar_one()
                if have >= MAX_CASES:
                    raise EvalError(409, f"a profile has at most {MAX_CASES} cases of its own")
                await conn.execute(insert(db.eval_cases).values(**row))
        except IntegrityError:
            raise EvalError(409, "a case of this profile already has that name")
        return case_out(row)

    async def set_case(self, tenant: str, key: str, case_id: str, body: CaseIn) -> dict:
        c = db.eval_cases.c
        values = dict(name=body.name, input=body.input, fixtures=body.fixtures,
                      checks=body.checks.model_dump(mode="json"), updated_at=time.time())
        try:
            async with self._db.engine.begin() as conn:
                done = await conn.execute(update(db.eval_cases).where(
                    c.id == case_id, c.tenant == tenant, c.key == key).values(**values))
        except IntegrityError:
            raise EvalError(409, "a case of this profile already has that name")
        if done.rowcount != 1:
            raise EvalError(404, "no such evaluation case")
        return {"id": case_id, **{k: values[k] for k in ("name", "input", "fixtures", "checks")}, "platform": False}

    async def drop_case(self, tenant: str, key: str, case_id: str) -> None:
        c = db.eval_cases.c
        async with self._db.engine.begin() as conn:
            done = await conn.execute(delete(db.eval_cases).where(c.id == case_id, c.tenant == tenant, c.key == key))
        if done.rowcount != 1:
            raise EvalError(404, "no such evaluation case")

    # ---- runs ----------------------------------------------------------------
    async def reap(self) -> None:
        """A run still `running` past its deadline died with its process (a live one moves its deadline on, `beat`): it
        ends as an error, so it neither blocks the next run nor looks as if it might still pass."""
        r = db.eval_runs.c
        dead = (r.status == "running", r.deadline < time.time())
        async with self._db.engine.connect() as conn:  # asked with every sweep and every gate: no write when there is none
            if (await conn.execute(select(r.id).where(*dead).limit(1))).first() is None:
                return
        async with self._db.engine.begin() as conn:
            await conn.execute(update(db.eval_runs).where(*dead).values(
                status="error", error="interrupted: the process that ran it stopped", finished_at=time.time()))

    async def open_run(self, tenant: str, key: str, version: int, profile_hash: str, by: str, deadline: float,
                       cases_hash: str | None = None) -> dict:
        """The unique index lets one run of a version be `running`: a second one, from this process or another, is
        refused by the database."""
        row = dict(id="run_" + uuid.uuid4().hex[:16], tenant=tenant, key=key, version=version, profile_hash=profile_hash,
                   cases_hash=cases_hash, status="running", score=None, results=[], cost_usd=0.0, duration_s=None,
                   started_by=by[:80], error=None, deadline=deadline, created_at=time.time(), finished_at=None)
        try:
            async with self._db.engine.begin() as conn:
                await conn.execute(insert(db.eval_runs).values(**row))
        except IntegrityError:
            raise EvalError(409, "an evaluation of this version is running; wait for it")
        return row

    async def beat(self, run_id: str, deadline: float) -> bool:
        """Its process is alive: move the deadline on. False when the run is not running any more (it was reaped)."""
        async with self._db.engine.begin() as conn:
            done = await conn.execute(update(db.eval_runs).where(
                db.eval_runs.c.id == run_id, db.eval_runs.c.status == "running").values(deadline=deadline))
        return done.rowcount == 1

    async def ahead(self, run: dict) -> int:
        """How many running runs of the same tenant were started before this one: its place in the tenant's queue, the
        same from every process."""
        r = db.eval_runs.c
        async with self._db.engine.connect() as conn:
            rows = (await conn.execute(select(r.created_at, r.id).where(
                r.tenant == run["tenant"], r.status == "running", r.id != run["id"]))).all()
        return sum(1 for at, rid in rows if (at, rid) < (run["created_at"], run["id"]))

    async def status(self, run_id: str) -> str | None:
        async with self._db.engine.connect() as conn:
            return (await conn.execute(select(db.eval_runs.c.status).where(db.eval_runs.c.id == run_id))).scalar()

    async def write_run(self, run_id: str, **values: Any) -> None:
        """Only a run that is still running is written: one that was reaped or cancelled stays as it ended."""
        if "error" in values and values["error"]:
            values["error"] = str(values["error"])[:300]
        async with self._db.engine.begin() as conn:
            await conn.execute(update(db.eval_runs).where(
                db.eval_runs.c.id == run_id, db.eval_runs.c.status == "running").values(**values))

    async def run(self, tenant: str, run_id: str) -> dict | None:
        r = db.eval_runs.c
        async with self._db.engine.connect() as conn:
            row = (await conn.execute(select(db.eval_runs).where(r.id == run_id, r.tenant == tenant))).mappings().first()
        return dict(row) if row else None

    async def runs(self, tenant: str, key: str, version: int, limit: int = 20) -> list[dict]:
        """Newest first."""
        r = db.eval_runs.c
        async with self._db.engine.connect() as conn:
            rows = (await conn.execute(select(db.eval_runs).where(r.tenant == tenant, r.key == key, r.version == version)
                                       .order_by(r.created_at.desc(), r.id.desc()).limit(limit))).mappings().all()
        return [dict(x) for x in rows]

    async def latest(self, tenant: str, key: str, version: int) -> dict | None:
        await self.reap()
        rows = await self.runs(tenant, key, version, 1)
        return rows[0] if rows else None
