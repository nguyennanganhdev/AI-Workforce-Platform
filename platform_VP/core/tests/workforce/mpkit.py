"""The platform as REAL operating-system processes, for the tests that kill one (slice P5b; spec 13.25).

A `Fleet` is what a deployment is: `python -m awp` started several times (each its own process, its own port) on one
PostgreSQL and one Redis, with the scripted model and the sample partner MCP server of `platform_VP/deploy/demo` as two
more processes. A test talks to it over HTTP only, like a partner and an operator would, and may

  kill(i)      end process i at once (TerminateProcess on Windows, SIGKILL elsewhere): no handler runs, nothing is
               flushed, its Redis session lock and its job lease are left behind;
  freeze(i)    stop process i without ending it (NtSuspendProcess / SIGSTOP): what it has committed is in the database,
               what it has not sent yet never leaves;
  hold the model or the partner so that a kill lands in the middle of a model call or of a tool call.

Needs `AWP_TEST_PG_URL` (a PostgreSQL user that may create databases; the databases are made and dropped by
tests/dbtest.py) and `AWP_TEST_REDIS_URL` (a Redis the tests may FLUSH: never one that holds anything). Without both
every test that uses this module is skipped. How to run them: docs/WORKFORCE_V1_VAN_HANH.md, section 11.
"""
from __future__ import annotations

import ctypes
import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

import dbtest
from conftest import ADM, SECRET_KEY, Env
from flowkit import Flow, Stream
from t2kit import Provider

REDIS_URL = os.environ.get("AWP_TEST_REDIS_URL", "").strip()
READY = bool(dbtest.IS_PG and REDIS_URL)
needs_fleet = pytest.mark.skipif(not READY, reason="real processes need AWP_TEST_PG_URL and AWP_TEST_REDIS_URL")
CORE = Path(__file__).resolve().parents[2]
DEMO = CORE.parent / "deploy" / "demo"
LEASE = 4.0  # seconds a process may be silent before the others take its work over (60 in production)
SCHEMA = {
    "version": "1", "version_mode": "snapshot",
    "events": {
        "job.assigned": {"status": "assigned", "rank": 10, "public_status": "assigned", "public_fields": ["worker_name"],
                         "message": "Worker {worker_name} is on the way.", "wake": False},
        "job.completed": {"status": "completed", "rank": 90, "terminal": True, "outcome": "completed",
                          "public_status": "completed", "wake": True, "evidence": True},
    },
}
TERMINAL = ("completed", "failed", "blocked")


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def until(check, timeout: float = 60.0, what: str = "condition", every: float = 0.1):
    """Poll `check()` until it returns something truthy; an HTTP hiccup of a process that is starting counts as no."""
    end, last = time.monotonic() + timeout, None
    while time.monotonic() < end:
        try:
            got = check()
            if got:
                return got
        except (httpx.HTTPError, OSError) as e:
            last = e
        time.sleep(every)
    raise AssertionError(f"timed out after {timeout:.0f} s waiting for {what}" + (f" (last error: {last!r})" if last else ""))


class Proc:
    def __init__(self, name: str, port: int, popen: subprocess.Popen, log: Path) -> None:
        self.name, self.port, self.popen, self.log = name, port, popen, log
        self.url = f"http://127.0.0.1:{port}"
        self.http = httpx.Client(base_url=self.url, timeout=30)

    @property
    def alive(self) -> bool:
        return self.popen.poll() is None

    @property
    def pid(self) -> int:
        """The process that serves, by its own word in its log ("Started server process [n]"). On Windows the venv's
        python.exe is a launcher that starts the interpreter as a child: the Popen handle is the launcher's."""
        found = re.search(r"Started server process \[(\d+)\]", self.log.read_text(encoding="utf-8", errors="replace"))
        return int(found.group(1)) if found else self.popen.pid

    def stop(self) -> None:
        self.http.close()
        if self.alive:
            self.popen.kill()
        try:
            self.popen.wait(15)
        except subprocess.TimeoutExpired:
            pass


class Fleet:
    def __init__(self, tmp_path: Path, **settings: str) -> None:
        import redis

        self.dir = tmp_path
        self.awp, self.scope = dbtest.urls(tmp_path)
        self.redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        self.redis.flushdb()
        self.settings = {k: str(v) for k, v in settings.items()}
        self.procs: list[Proc] = []
        self.api: list[Proc] = []
        self.model = self._spawn("model", [str(DEMO / "fake_model.py")], {"DEMO_MODEL_PORT": None}, "/health")
        self.mcp = self._spawn("mcp", [str(DEMO / "fake_mcp.py")], {"DEMO_MCP_PORT": None}, "/health")
        models = tmp_path / "models.yaml"
        models.write_text("models:\n" + "".join(
            f"  - id: demo-{tier}\n    provider: openai_compatible\n    model: demo-scripted-{tier}\n    tier: {tier}\n"
            f"    base_url: {self.model.url}/v1\n    api_key_env: DEMO_MODEL_KEY\n" for tier in ("strong", "standard", "cheap")),
            encoding="utf-8")
        self.models = models

    # ---- processes ---------------------------------------------------------------------------------------------
    def _spawn(self, name: str, argv: list[str], env: dict, health: str, wait: bool = True) -> Proc:
        port = free_port()
        full = {**os.environ, "PYTHONPATH": str(CORE / "src"), "PYTHONUNBUFFERED": "1", "DEMO_HOST": "127.0.0.1"}
        full.update({k: (str(port) if v is None else v) for k, v in env.items()})
        log = self.dir / f"{name}-{len(self.procs)}.log"
        with open(log, "wb") as out:
            popen = subprocess.Popen([sys.executable, *argv], env=full, cwd=str(self.dir), stdout=out, stderr=subprocess.STDOUT)
        proc = Proc(name, port, popen, log)
        self.procs.append(proc)
        if wait:
            self.ready(proc, health)
        return proc

    def ready(self, proc: Proc, health: str = "/platform/v1/health") -> Proc:
        def up():
            assert proc.alive, f"{proc.name} ended while starting:\n{self.tail(proc)}"
            return proc.http.get(health).status_code == 200
        until(up, 90, f"{proc.name} to answer")
        return proc

    def start_api(self, wait: bool = True) -> Proc:
        """One more platform process on the same database and the same Redis."""
        env = {
            "AWP_PORT": None, "AWP_HOST": "127.0.0.1", "AWP_DB_URL": self.awp.url, "AWP_AGENTSCOPE_DB_URL": self.scope.url,
            "AWP_REDIS_URL": REDIS_URL, "AWP_ADMIN_KEYS": "adm-a:ta;adm-b:tb", "AWP_SECRET_KEY": SECRET_KEY,
            "AWP_MODELS_FILE": str(self.models), "DEMO_MODEL_KEY": "demo", "AWP_WORKSPACE_DIR": str(self.dir / "ws"),
            "AWP_MCP_ALLOW_PRIVATE": "1", "AWP_AUTO_CREATE": "1", "AWP_SHUTDOWN_SECONDS": "2",
            "AWP_WF_LEASE_SECONDS": str(LEASE), "AWP_WF_OP_GRACE_SECONDS": "3", "AWP_WF_ACK_SECONDS": "3",
            "AWP_WF_WAIT_SECONDS": "1", "AWP_WF_RATE_PER_MINUTE": "0", "AWP_RETENTION_EVERY_SECONDS": "0",
            "AWP_DB_POOL_SIZE": "5", "AWP_DB_MAX_OVERFLOW": "10", **self.settings}
        proc = self._spawn("api", ["-m", "awp"], env, "/platform/v1/health", wait)
        self.api.append(proc)
        return proc

    def kill(self, proc: Proc) -> None:
        """The process ends now, with no chance to do anything about it: SIGKILL, or TerminateProcess on Windows (which
        is what os.kill does there for any signal but the two console ones). No handler runs, nothing is flushed."""
        pid = proc.pid
        os.kill(pid, signal.SIGTERM if os.name == "nt" else signal.SIGKILL)
        if pid != proc.popen.pid:
            proc.popen.kill()  # the launcher, which has nothing left to wait for
        proc.popen.wait(15)
        assert not proc.alive
        until(lambda: not self.listening(proc.port), 15, "the killed process's port to close")

    def listening(self, port: int) -> bool:
        s = socket.socket()
        s.settimeout(0.5)
        try:
            return s.connect_ex(("127.0.0.1", port)) == 0
        finally:
            s.close()

    def freeze(self, proc: Proc) -> None:
        """The process stops running without ending: nothing more leaves it, what it committed stays committed."""
        if os.name == "nt":
            handle = ctypes.windll.kernel32.OpenProcess(0x0800, False, proc.pid)  # PROCESS_SUSPEND_RESUME
            assert handle, "the process could not be opened"
            try:
                assert ctypes.windll.ntdll.NtSuspendProcess(handle) == 0
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        else:
            os.kill(proc.pid, signal.SIGSTOP)

    def tail(self, proc: Proc, lines: int = 60) -> str:
        try:
            kept = [x for x in proc.log.read_text(encoding="utf-8", errors="replace").splitlines()
                    if not (x.startswith("INFO:") and '" 20' in x)]  # the access log of the calls that went well
            return "\n".join(kept[-lines:])
        except OSError:
            return ""

    def close(self) -> None:
        for proc in reversed(self.procs):
            proc.stop()
        for proc in self.api:  # shown by pytest when the test failed
            print(f"---- {proc.name} on port {proc.port} (last lines) ----\n{self.tail(proc, 40)}")
        self.redis.close()

    # ---- the scripted model and the sample partner ---------------------------------------------------------------
    def hold_model(self, pattern: str) -> None:
        assert self.model.http.post("/control", json={"hold": pattern}).status_code == 200

    def model_held(self) -> int:
        return self.model.http.get("/health").json()["held"]

    def hold_partner(self, on: bool) -> None:
        assert self.mcp.http.post("/control", json={"hold": on}).status_code == 200

    def partner(self) -> dict:
        """What the partner saw: calls and side effects by client_reference, how many calls are held or answered."""
        return self.mcp.http.get("/stats").json()

    def running_the_turn(self) -> Proc:
        """The process that holds the one session lock there is right now: the one a turn runs in. A decision wakes its
        agent through AgentScope's wake-up queue, which any process of the fleet may take, so a test that wants to kill
        "the process that runs the tool" has to ask which one that is. Read behind the API (the lock's value names the
        node, the nodes' rows are in start order): this steers the kill, it asserts nothing."""
        [(value, _)] = self.session_locks().values()
        node = value.partition(":")[0]
        con = dbtest.connect(self.awp)
        try:
            rows = con.execute("select owner from wf_leases where name like 'node:%' order by last_run_at")
        finally:
            con.close()
        order = [r[0] for r in rows]
        live = [p for p in self.api if p.alive]
        assert node in order and len(order) == len(live), (node, order)
        return live[order.index(node)]

    # ---- what a dead process leaves in Redis ---------------------------------------------------------------------
    def session_locks(self) -> dict[str, tuple[str, int]]:
        """Every session lock in Redis: key -> (value, seconds left)."""
        return {k: (self.redis.get(k), self.redis.ttl(k)) for k in self.redis.scan_iter("agentscope:session:lock:*")}


class RowLock:
    """Hold the write lock of one conversation from outside the platform: no process can write that conversation
    (events, operations, messages) until `release`. This is how a test keeps an answer the platform has in hand from
    being written down, so that a kill lands exactly there."""

    def __init__(self, fleet: Fleet, conversation_id: str) -> None:
        import asyncpg

        async def take():
            conn = await asyncpg.connect(fleet.awp.url.replace("postgresql+asyncpg://", "postgresql://"))
            tx = conn.transaction()
            await tx.start()
            await conn.fetch("select id from wf_conversations where id = $1 for update", conversation_id)
            return conn, tx

        self.conn, self.tx = dbtest._bg().run(take())

    def release(self) -> None:
        async def drop():
            await self.tx.rollback()
            await self.conn.close()

        dbtest._bg().run(drop())


# ---- reading the platform the way a partner does ------------------------------------------------------------------
class Reads:
    """What a test reads, through the public API only. Shared by the fleet's World and by the one-process world of the
    owner's scenarios (ownerkit.Local), so a scenario is written once and run on both."""

    def settled(self, flow: Flow, response, timeout: float = 90.0) -> dict:
        """The request of a POST once it ended (200 at once, or 202 and then GET until it is terminal)."""
        assert response.status_code in (200, 202), response.text
        rid = response.json()["request_id"]

        def done():
            r = flow.request(rid)
            return r.json() if r.status_code == 200 and r.json()["request_status"] in TERMINAL else None
        return until(done, timeout, f"request {rid} to end")

    def state(self, flow: Flow, conv: str, workflow_id: str | None = None) -> dict:
        """The workflow as the snapshot shows it."""
        r = flow.snapshot(conv)
        assert r.status_code == 200, r.text
        wf = next(w for w in r.json()["workflows"] if workflow_id is None or w["workflow_id"] == workflow_id)
        return {**wf, "workflow_state": wf["state"], "workflow_revision": wf["revision"]}  # (named as a request names them)

    def until_state(self, flow: Flow, conv: str, state: str | tuple, timeout: float = 90.0) -> dict:
        want = (state,) if isinstance(state, str) else state

        def there():
            wf = self.state(flow, conv)
            return wf if wf["workflow_state"] in want else None
        return until(there, timeout, f"the workflow of {conv} to be {want}")

    def events(self, flow: Flow, conv: str) -> list[dict]:
        r = flow.history(conv, limit=500)
        assert r.status_code == 200, r.text
        return r.json()["items"]

    def approval(self, flow: Flow, conv: str) -> dict:
        return until(lambda: (flow.approvals(conv) or [None])[0], 60, "a pending approval")

    def stream(self, flow: Flow, conv: str, last: str | None = None) -> Stream:
        headers = {**flow.h, **({"Last-Event-ID": last} if last else {})}
        return Stream(flow.http, f"/workforce/v1/partner/conversations/{conv}/events", headers,
                      {"external_user_id": "resident-123"})


def booking_tool(integration_id: str, consent: bool = True, resend: bool = True) -> dict:
    """The route's one action: the partner's `book_repair`, followed by the provider's events."""
    tool = {"name": "book_repair", "server": "p", "mcp_tool": "book_repair", "kind": "action", "tracking": "events",
            "client_reference_arg": "client_reference", "integration_id": integration_id}
    if resend:  # the partner is idempotent by this argument: a request left half sent is sent again with the same value
        tool["idempotency_arg"] = "client_reference"
    tool.update({"requires_consent": True, "consent_summary": "Book a repair visit for {slot}"} if consent else
                {"requires_consent": False, "consent_waiver": "kill test: this one is not about consent"})
    return tool


# ---- a partner on the fleet ---------------------------------------------------------------------------------------
class World(Reads):
    """One partner client with a key, a route whose leader may call `book_repair`, a provider integration, and the
    same partner seen through each process: `on(i)` is its Flow at process i."""

    def __init__(self, fleet: Fleet, consent: bool = True, resend: bool = True, wait_seconds: float = 1.0) -> None:
        from enginekit import publish_profiles

        self.fleet = fleet
        env = Env(fleet.api[0].http, None, None)
        publish_profiles(env, leader_tools=["book_repair", "lookup_ticket"])
        self.client = env.client()
        self.key = env.key(self.client["client_id"])
        self.route = env.active_route(self.client["client_id"], self.key["api_key"], wait_seconds=wait_seconds)
        self.provider = Provider(env, self.client["client_id"], SCHEMA)
        rid = self.route["route_id"]
        r = env.http.put(f"/platform/v1/wf/routes/{rid}/mcp", headers=ADM, json={"servers": [
            {"name": "p", "url": fleet.mcp.url + "/mcp", "headers": {}}]})
        assert r.status_code == 200, r.text
        r = env.http.put(f"/platform/v1/wf/routes/{rid}/tools", headers=ADM,
                         json={"tools": [booking_tool(self.provider.id, consent, resend)]})
        assert r.status_code == 200, r.text
        self.env = env
        self._flows: dict[int, Flow] = {}
        self.main = self.on(0)

    def on(self, i: int) -> Flow:
        """The partner's client pointed at process i (same key, same route, one numbering of its request ids)."""
        if i not in self._flows:
            flow = Flow(Env(self.fleet.api[i].http, None, None), self.client, self.key, self.route, None)
            if self._flows:
                flow._n = next(iter(self._flows.values()))._n
            self._flows[i] = flow
        return self._flows[i]

    def provider_on(self, i: int) -> Provider:
        import copy

        other = copy.copy(self.provider)
        other.env = Env(self.fleet.api[i].http, None, None)
        return other

    flow, provider_at = on, provider_on  # the names a scenario uses (ownerkit)

    def partner(self) -> dict:
        return self.fleet.partner()


def audit(world: Reads, flow: Flow, conv: str) -> SimpleNamespace:
    """What must hold for a conversation whatever was killed: the sequences have no gap, no event and no message is
    there twice, and nothing was said to the resident twice."""
    events = world.events(flow, conv)
    seqs = [e["sequence"] for e in events]
    assert seqs == list(range(1, len(seqs) + 1)), f"the sequences of {conv} have a gap or a repeat: {seqs}"
    assert len({e["event_id"] for e in events}) == len(events)
    said = [e["payload"] for e in events if e["event_type"] == "assistant.message"]
    ids = [m["message_id"] for m in said]
    texts = [m["text"] if "text" in m else str(m) for m in said]
    assert len(set(ids)) == len(ids), f"a message is in the log twice: {ids}"
    assert len(set(texts)) == len(texts), f"the resident was told the same thing twice: {texts}"
    kinds = [e["event_type"] for e in events]
    assert kinds.count("workflow.closed") <= 1
    resolved = [e["payload"]["approval_id"] for e in events if e["event_type"] == "approval.resolved"]
    assert len(set(resolved)) == len(resolved), "an approval was resolved twice"
    return SimpleNamespace(events=events, kinds=kinds, texts=texts)


def one_effect(who, calls: int | tuple = 1) -> str:
    """The partner carried the action out exactly once, under one reference; `calls` is how often it was called with
    that reference (2 when the platform sent a half-sent request again, which an idempotent partner makes a no-op).
    `who`: anything with `partner()` (a Fleet, a World, ownerkit.Local)."""
    seen = who.partner()
    assert seen["side_effects"] == 1 and len(seen["jobs"]) == 1, seen
    [(ref, n)] = seen["book_repair_calls_by_reference"].items()
    assert n in ((calls,) if isinstance(calls, int) else calls), seen
    assert seen["side_effects_by_reference"] == {ref: 1}
    return ref


@pytest.fixture
def fleet(tmp_path):
    """Two platform processes on one PostgreSQL and one Redis, with the scripted model and the sample partner."""
    f = Fleet(tmp_path)
    try:
        first = f.start_api(wait=False)
        f.ready(first)  # the first makes sure the tables are there; then the second
        f.start_api()
        yield f
    finally:
        f.close()
