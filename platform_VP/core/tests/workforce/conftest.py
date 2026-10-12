"""Fixtures for the workforce tests: a plain app on temporary SQLite files, no model."""
from __future__ import annotations

import contextlib
import sys
from pathlib import Path
import threading
import time
from dataclasses import dataclass, field

import httpx
import pytest
import uvicorn
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # tests/: fake_llm and support, for the engine tests

import dbtest
from awp.app import build_app
from awp.config import Settings
from awp.providers import ModelCatalog

ADM = {"Authorization": "Bearer adm-a"}  # tenant ta
ADM_B = {"Authorization": "Bearer adm-b"}  # tenant tb
OLD_SVC = {"Authorization": "Bearer svc-key"}  # a connector key of the removed API: the platform does not know it
SECRET_KEY = Fernet.generate_key().decode()
WAIT = 20.0  # the wait ceiling of the fake-engine fixtures (see `flow`)
ALL_CUSTOMER = ["submit_request", "reply", "read_result", "receive_events", "submit_consent",
                "close_workflow", "confirm_route", "sync_residence"]
EVENT_SCHEMA = {
    "version": "1", "version_mode": "snapshot",
    "events": {
        "repair.assigned": {"status": "assigned", "rank": 10, "public_status": "assigned",
                            "public_fields": ["worker_name"], "message": "Worker {worker_name} is on the way.",
                            "wake": False},
        "repair.completed": {"status": "completed", "rank": 90, "terminal": True, "outcome": "success",
                             "wake": True, "evidence": True},
    },
}


def key_headers(api_key: str) -> dict:
    return {"Authorization": f"ApiKey {api_key}"}


TEST_OVERRIDE = "test fixture: this test is not about the evaluation gate"


def publish(env, key: str, version: int = 1, headers=ADM, expect: int | None = 200):
    """Publish a profile version for a test that is not about the evaluation gate. The gate stays on (as in production):
    this is the explicit, recorded override an admin has. Tests of the gate itself run evaluations (evalkit.py)."""
    r = env.post(f"/platform/v1/profiles/{key}/versions/{version}/publish", {"override_reason": TEST_OVERRIDE}, headers)
    if expect is not None:
        assert r.status_code == expect, r.text
    return r


def just_before(monkeypatch, env, statement: str, query: str, args=()) -> list:
    """Write a row behind the platform's back at the moment the app is about to run its first statement that starts
    with `statement` ("UPDATE wf_routes"): the parallel request that wins between a handler's read and its write.
    Returns a list that is non-empty once that happened.

    The write is made from a worker thread while the handler waits for it. A test must never write synchronously from
    inside the app's event loop (a patched function that calls `env.sql`): that holds the loop still, so a background
    transaction that is open at that moment (the clean-up at start-up, a sweep) can never commit, and on SQLite the
    write waits for it until it times out: "database is locked", one run in some dozens."""
    import asyncio

    from sqlalchemy.ext.asyncio import AsyncConnection

    real, fired = AsyncConnection.execute, []

    async def execute(self, stmt, *a, **kw):
        if not fired and str(stmt).lstrip().upper().startswith(statement.upper()):
            fired.append(statement)
            await asyncio.to_thread(env.sql, query, args)
        return await real(self, stmt, *a, **kw)

    monkeypatch.setattr(AsyncConnection, "execute", execute)
    return fired


@dataclass
class Env:
    http: TestClient
    app: object
    db: dbtest.Db  # the awp database (a file on SQLite, a clone of the template on PostgreSQL)
    _pg: object = None  # one bare connection kept for `sql` on PostgreSQL (SQLite opens one per call)
    _managers: dict = field(default_factory=dict)  # client id -> its default manager (made on first use)
    _leaders: set = field(default_factory=set)  # leader profiles known to exist, as (admin key, profile key)
    _loop_thread: int | None = None  # the thread the app's event loop runs in

    @property
    def db_path(self) -> str:
        return self.db.path

    # ---- admin helpers (tenant ta unless a header is given) ----
    def post(self, path, body=None, headers=ADM):
        return self.http.post(path, json=body if body is not None else {}, headers=headers)

    def client(self, domain="homes", name="Partner", env="sandbox", headers=ADM) -> dict:
        r = self.post("/platform/v1/wf/clients", {"name": name, "domain": domain, "environment": env}, headers)
        assert r.status_code == 201, r.text
        return r.json()

    def key(self, client_id, operations=None, routes=None, headers=ADM, **extra) -> dict:
        body = {"operations": operations or ALL_CUSTOMER, **extra}
        if routes is not None:
            body["routes"] = routes
        r = self.post(f"/platform/v1/wf/clients/{client_id}/keys", body, headers)
        assert r.status_code == 201, r.text
        return r.json()

    def manager(self, client_id, name="Management", headers=ADM) -> dict:
        r = self.post(f"/platform/v1/wf/clients/{client_id}/managers", {"name": name}, headers)
        assert r.status_code == 201, r.text
        return r.json()

    def manager_key(self, manager_id, headers=ADM) -> dict:
        """{"Authorization": "Bearer mk_..."}: what an operator of that manager sends."""
        r = self.post(f"/platform/v1/wf/managers/{manager_id}/keys", {}, headers)
        assert r.status_code == 201, r.text
        return {"Authorization": f"Bearer {r.json()['api_key']}"}

    def default_manager(self, client_id, headers=ADM) -> str:
        """Every route belongs to a manager (M6); a test that does not care which gets the client's default one."""
        if client_id not in self._managers:
            self._managers[client_id] = self.manager(client_id, headers=headers)["manager_id"]
        return self._managers[client_id]

    def leader(self, key="supervisor", headers=ADM) -> str:
        """A route needs a leader profile that exists (M4): a draft of one is enough, and is made when missing."""
        seen = (headers["Authorization"], key)
        if seen not in self._leaders:
            have = self.http.get("/platform/v1/profiles", headers=headers).json()["profiles"]
            if not any(p["key"] == key for p in have):
                r = self.post("/platform/v1/profiles", {"key": key, "name": "Leader", "role": "leader",
                                                        "mission": "the leader of a test route."}, headers)
                assert r.status_code == 201, r.text
            self._leaders.add(seen)
        return key

    def route(self, client_id, ref="BQL-OP1-A", headers=ADM, manager_id=None, leader="supervisor", **config) -> dict:
        body = {"external_management_ref": ref, "leader_profile": self.leader(leader, headers), "config": config,
                "manager_id": manager_id or self.default_manager(client_id, headers)}
        r = self.post(f"/platform/v1/wf/clients/{client_id}/routes", body, headers)
        assert r.status_code == 201, r.text
        return r.json()

    def confirm(self, api_key, route, revision=None, ref=None):
        return self.http.post(
            f"/workforce/v1/partner/routes/{route['route_id']}/confirm", headers=key_headers(api_key),
            json={"schema_version": "1", "expected_revision": route["revision"] if revision is None else revision,
                  "external_management_ref": ref or route["external_management_ref"]})

    def active_route(self, client_id, api_key, ref="BQL-OP1-A", manager_id=None, **config) -> dict:
        route = self.route(client_id, ref, manager_id=manager_id, **config)
        assert self.confirm(api_key, route).status_code == 200
        return self.http.get(f"/platform/v1/wf/routes/{route['route_id']}", headers=ADM).json()

    def _off_loop(self) -> None:
        """A bare connection is synchronous: used from inside the app's event loop it holds the loop still, so a
        transaction the app has open at that moment can never commit, and a write waits for it until it times out
        ("database is locked" on SQLite, one run in some dozens). Refused, so that it fails every time instead: from a
        coroutine of the app use `await asyncio.to_thread(...)`, and for a write between a handler's read and its write
        `just_before`."""
        if threading.get_ident() == self._loop_thread:
            raise AssertionError("a bare database connection was used from inside the app's event loop (see Env._off_loop)")

    def raw(self):
        """A bare connection to the awp database; the caller closes it."""
        self._off_loop()
        return dbtest.connect(self.db)

    def sql(self, query, args=()):
        """Rows behind the platform's back (portable SQL: `?` placeholders; every statement commits at once)."""
        self._off_loop()
        if not dbtest.IS_PG:
            con = self.raw()
            try:
                return con.execute(query, args)
            finally:
                con.close()
        if self._pg is None:
            self._pg = self.raw()
        return self._pg.execute(query, args)

    def dump(self) -> str:
        return dbtest.dump(self.db)

    def close(self) -> None:
        if self._pg is not None:
            self._pg.close()
            self._pg = None


def _app(tmp_path, wire, over):
    catalog = over.pop("catalog", None)
    judge = over.pop("judge", None)  # a second-opinion judge (awp.guard.SupportJudge) for tests that need one
    # How often the lifespan sweep runs (the default is the production 2 s). A test that steps the sweep by hand, or that
    # edits rows the sweep reads, turns the background one off (a large value) so that nobody else acts in between.
    sweep = over.pop("sweep_every", None)
    awp, scope = dbtest.urls(tmp_path)
    base = dict(
        db_url=awp.url,
        agentscope_db_url=scope.url,
        workspace_dir=str(tmp_path / "ws"),
        admin_keys={"adm-a": "ta", "adm-b": "tb"},
        secret_key=SECRET_KEY)
    base.update(over)
    app = build_app(Settings(**base), catalog=catalog or ModelCatalog([]), judge=judge, **({"sweep_every": sweep} if sweep else {}))
    if wire:
        wire(app)
    return app


@contextlib.contextmanager
def build(tmp_path, wire=None, **over):
    app = _app(tmp_path, wire, over)
    env = None
    with TestClient(app) as http:
        env = Env(http, app, dbtest.urls(tmp_path)[0], _loop_thread=http.portal.call(threading.get_ident))
        try:
            yield env
        finally:
            env.close()


@contextlib.contextmanager
def build_live(tmp_path, wire=None, **over):
    """The same app behind a real uvicorn server (TestClient cannot stream an endless SSE
    response): `env.http` is an httpx client for it."""
    app = _app(tmp_path, wire, over)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning",
                                           timeout_graceful_shutdown=2))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 30
    while not server.started:
        assert thread.is_alive() and time.monotonic() < deadline, "server did not start"
        time.sleep(0.02)
    port = server.servers[0].sockets[0].getsockname()[1]
    http = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=30)
    env = None
    try:
        env = Env(http, app, dbtest.urls(tmp_path)[0], _loop_thread=thread.ident)
        yield env
    finally:
        if env is not None:
            env.close()
        http.close()
        server.should_exit = True
        thread.join(30)


@pytest.fixture
def env(tmp_path):
    with build(tmp_path) as e:
        yield e


@pytest.fixture
def make_env(tmp_path):
    """For tests that need other settings: `with make_env(wf_rate_per_minute=2) as env:`."""
    return lambda **over: build(tmp_path, **over)


@pytest.fixture
def world(env):
    """(env, client, key, route): a client with a full-rights key and an active route."""
    c = env.client()
    k = env.key(c["client_id"])
    route = env.active_route(c["client_id"], k["api_key"])
    return env, c, k, route


# ---- the request flow: a partner, a key, an active route and a scripted engine -------------------
def _wire_engine(app):
    from fake_engine import TestEngine
    app.state.wf.engine = TestEngine(app.state.wf)


def _flow(env, **config):
    from flowkit import Flow
    c = env.client()
    k = env.key(c["client_id"])
    route = env.active_route(c["client_id"], k["api_key"], **config)
    return Flow(env, c, k, route, env.app.state.wf.engine)


@pytest.fixture
def flow(tmp_path):
    """A flow with a generous wait ceiling: a POST returns the moment its turn settles, so the ceiling costs nothing
    when things are fast and a loaded machine cannot turn a 200 into a 202. A test that wants the 202 says so with
    `flow.waiting(seconds)` and holds the turn with a gate (`Plan(hold=...)`)."""
    with build(tmp_path, wire=_wire_engine, wf_wait_seconds=WAIT, wf_rate_per_minute=0) as env:
        yield _flow(env)


@pytest.fixture
def make_flow(tmp_path):
    """`with make_flow(route={...}, wf_wait_seconds=3) as flow:` for other settings or route config."""
    @contextlib.contextmanager
    def maker(live=False, route=None, **over):
        over.setdefault("wf_wait_seconds", WAIT)
        over.setdefault("wf_rate_per_minute", 0)  # these tests send far more than 600 calls a minute
        with (build_live if live else build)(tmp_path, wire=_wire_engine, **over) as env:
            yield _flow(env, **(route or {}))
    return maker


@pytest.fixture(scope="module")
def shared_flow(tmp_path_factory):
    """One app per test module for tests that only add data under fresh ids (every test file that
    uses it must not suspend routes, change settings or leave the engine paused)."""
    path = tmp_path_factory.mktemp("wf")
    try:
        with build(path, wire=_wire_engine, wf_wait_seconds=WAIT, wf_rate_per_minute=0) as env:
            yield _flow(env)
    finally:
        dbtest.drop(str(path))


@pytest.fixture
def sf(shared_flow):
    """The shared flow with the engine back to its defaults."""
    from fake_engine import Plan
    e = shared_flow.engine
    e.plan, e.paused = Plan(), False
    e.seen.clear()
    e.errors.clear()
    yield shared_flow
    e.plan, e.paused = Plan(), False
